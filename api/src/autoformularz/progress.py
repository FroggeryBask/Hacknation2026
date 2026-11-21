"""Progress of one conversion for the job API (jobs.py): stages from the pipeline and the names of pages,
sections and fields as the model writes them. A no-op outside a job (POST /api/v1/forms, /compile, tests).
Nothing here calls the model: progress costs no tokens."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

# (kind, text): "stage" (a pipeline step), "item" (what the model or the code found), "tick" (no text;
# lets the sink stop the work, e.g. a cancelled job, between two items).
Sink = Callable[[str, str], None]

_sink: ContextVar[Sink | None] = ContextVar("autoformularz_progress", default=None)


def _emit(kind: str, text: str = "") -> None:
    if (sink := _sink.get()) is not None:
        sink(kind, text)


def stage(text: str) -> None:
    _emit("stage", text)


def item(text: str) -> None:
    _emit("item", text)


def tick() -> None:
    _emit("tick")


@contextmanager
def reporting(sink: Sink) -> Iterator[None]:
    """Send the progress of the work run inside this block (same thread) to `sink`."""
    token = _sink.set(sink)
    try:
        yield
    finally:
        _sink.reset(token)
