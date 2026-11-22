"""Metrics of one conversion, to compare runs before and after a change (speed, tokens, cost, size).

Collected per request in a ContextVar (like progress.py), so parallel requests never mix. Nothing here
stores the file or its text: the file is identified by a short SHA-256 (same file = same hash across runs),
never by its name. Reported as one JSON log line, as `metrics` in `?details=true`, and by the result
generator in `wyniki/metrics.jsonl` (not committed)."""

import hashlib
import io
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from PIL import Image

TOKEN_PX = 28  # Qwen-VL: one image token per ~28x28 px (estimate)


@dataclass
class ModelCall:
    provider: str
    model: str
    seconds: float = 0.0
    first_token_s: float | None = None  # time to the first piece of the answer (streaming)
    prompt_chars: int = 0  # system + user text sent
    images: int = 0
    image_bytes: int = 0
    image_tokens_est: int = 0
    prompt_tokens: int | None = None  # as reported by the provider
    completion_tokens: int | None = None
    cost_usd: float | None = None
    finish_reason: str | None = None
    answer_chars: int = 0
    # Keys the model wrote with a default value: each is output time (and Eden cost) for nothing.
    answer_nulls: int = 0
    answer_empty_lists: int = 0
    answer_false: int = 0
    answer_whitespace: int = 0  # newlines + indentation in the answer
    ollama: dict = field(default_factory=dict)  # load/prompt/eval durations from Ollama, seconds
    raw: str = ""  # the answer itself: kept for the result generator only, never logged or returned

    def as_dict(self) -> dict:
        d = {
            "provider": self.provider,
            "model": self.model,
            "seconds": round(self.seconds, 2),
            "firstTokenS": None if self.first_token_s is None else round(self.first_token_s, 2),
            "promptChars": self.prompt_chars,
            "images": self.images,
            "imageBytes": self.image_bytes,
            "imageTokensEst": self.image_tokens_est,
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "costUsd": self.cost_usd,
            "finishReason": self.finish_reason,
            "answerChars": self.answer_chars,
            "answerNulls": self.answer_nulls,
            "answerEmptyLists": self.answer_empty_lists,
            "answerFalse": self.answer_false,
            "answerWhitespace": self.answer_whitespace,
        }
        if self.ollama:
            d["ollama"] = self.ollama
        return d


@dataclass
class Metrics:
    source_format: str | None = None
    file_bytes: int = 0
    file_sha: str | None = None  # first 12 hex chars of SHA-256
    blocks: int = 0
    blocks_to_model: int | None = None  # after presort
    presort: dict[str, int] = field(default_factory=dict)  # blocks the code recognised, per role
    candidates: int = 0
    steps: dict[str, float] = field(default_factory=dict)  # seconds per pipeline step
    calls: list[ModelCall] = field(default_factory=list)
    pages: int = 0
    sections: int = 0
    fields: int = 0
    lint_errors: int = 0
    lint_warnings: int = 0
    error: str | None = None  # error code when the conversion failed
    _start: float = field(default_factory=time.perf_counter)

    def as_dict(self) -> dict:
        calls = [c.as_dict() for c in self.calls]
        return {
            "sourceFormat": self.source_format,
            "fileBytes": self.file_bytes,
            "fileSha": self.file_sha,
            "blocks": self.blocks,
            "blocksToModel": self.blocks_to_model,
            "presort": self.presort,
            "candidates": self.candidates,
            "steps": {k: round(v, 2) for k, v in self.steps.items()},
            "totalS": round(time.perf_counter() - self._start, 2),
            "modelCalls": len(calls),
            "promptTokens": _sum(c.prompt_tokens for c in self.calls),
            "completionTokens": _sum(c.completion_tokens for c in self.calls),
            "costUsd": _sum(c.cost_usd for c in self.calls),
            "calls": calls,
            "pages": self.pages,
            "sections": self.sections,
            "fields": self.fields,
            "lintErrors": self.lint_errors,
            "lintWarnings": self.lint_warnings,
            "error": self.error,
        }


def _sum(values) -> float | int | None:
    known = [v for v in values if v is not None]
    return round(sum(known), 6) if known else None


_current: ContextVar[Metrics | None] = ContextVar("autoformularz_metrics", default=None)


@contextmanager
def collecting() -> Iterator[Metrics]:
    """Metrics of the work run inside this block (same thread)."""
    m = Metrics()
    token = _current.set(m)
    try:
        yield m
    finally:
        _current.reset(token)


def current() -> Metrics | None:
    return _current.get()


@contextmanager
def step(name: str) -> Iterator[None]:
    """Time a pipeline step (a no-op outside `collecting`)."""
    start = time.perf_counter()
    try:
        yield
    finally:
        if (m := current()) is not None:
            m.steps[name] = m.steps.get(name, 0.0) + time.perf_counter() - start


def file_info(data: bytes, kind: str) -> None:
    if (m := current()) is not None:
        m.file_bytes, m.source_format = len(data), kind
        m.file_sha = hashlib.sha256(data).hexdigest()[:12]


def image_tokens(images: list[bytes]) -> int:
    total = 0
    for img in images:
        try:
            w, h = Image.open(io.BytesIO(img)).size  # header only, no decoding
        except OSError:
            continue
        total += max(1, w // TOKEN_PX) * max(1, h // TOKEN_PX)
    return total


def answer_shape(call: ModelCall, text: str) -> None:
    """Size of the answer and the keys written with a default value."""
    call.raw = text
    call.answer_chars = len(text)
    call.answer_nulls = len(re.findall(r'":\s*null\b', text))
    call.answer_empty_lists = len(re.findall(r'":\s*\[\s*\]', text))
    call.answer_false = len(re.findall(r'":\s*false\b', text))
    call.answer_whitespace = sum(len(m) for m in re.findall(r"\n[ \t]*", text))


def start_call(provider: str, model: str, messages: list[dict], images: list[bytes]) -> ModelCall:
    """A model call, recorded in the current metrics (a detached record outside `collecting`)."""
    chars = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            chars += sum(len(p.get("text", "")) for p in content if isinstance(p, dict))
    call = ModelCall(
        provider=provider,
        model=model,
        prompt_chars=chars,
        images=len(images),
        image_bytes=sum(len(i) for i in images),
        image_tokens_est=image_tokens(images),
    )
    if (m := current()) is not None:
        m.calls.append(call)
    return call
