"""OCR for scans: page image -> text lines in reading order, so scans get the same Document blocks as
text files (the model classifies blocks, the code keeps the text, legal text is copied word for word).

Tesseract (Apache-2.0, Polish model `pol` from tessdata, Apache-2.0) runs as a separate process with the
image on stdin: nothing is written to disk. One thread (OMP_THREAD_LIMIT=1) keeps the result repeatable.
Without Tesseract the scan still goes to the vision model as an image (see `extract.scan`)."""

import csv
import io
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

WINDOWS_TESSERACT = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
PAGE_TIMEOUT_S = 60
# --psm 4: one column of text of variable sizes; keeps form rows ("Label ....") as single lines. It drops
# the words after a long dotted leader ("w miejscowości ……… przy ulicy ………": "przy ulicy" was lost on the
# scan of material 1), so a second pass with --psm 11 (sparse text) finds them (`merge_sparse`).
PSM = "4"
SPARSE_PSM = "11"
# A sparse-pass word is trusted from this Tesseract confidence (0-100); lower ones are mostly box borders.
SPARSE_MIN_CONF = 60
FILL = "……"  # marks the place to fill in between two parts of a row, as in text documents


@dataclass(frozen=True)
class Ocr:
    binary: str
    lang: str = "pol"
    tessdata_dir: str | None = None


class OcrError(Exception):
    pass


def find_tesseract(configured: str) -> str | None:
    found = shutil.which(configured)
    if found:
        return found
    return str(WINDOWS_TESSERACT) if WINDOWS_TESSERACT.exists() else None


def ocr_from(binary: str, lang: str, tessdata_dir: str | None) -> Ocr | None:
    """OCR settings, or None when Tesseract is not installed."""
    found = find_tesseract(binary)
    return Ocr(found, lang, tessdata_dir) if found else None


def _tsv(png: bytes, ocr: Ocr, psm: str) -> str:
    cmd = [ocr.binary, "stdin", "stdout", "-l", ocr.lang, "--psm", psm, "-c", "tessedit_create_tsv=1"]
    if ocr.tessdata_dir:
        cmd += ["--tessdata-dir", ocr.tessdata_dir]
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    try:
        r = subprocess.run(cmd, input=png, capture_output=True, timeout=PAGE_TIMEOUT_S, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise OcrError(str(e)) from e
    if r.returncode != 0:
        raise OcrError(r.stderr.decode("utf-8", "replace")[:300])
    return r.stdout.decode("utf-8", "replace")


def page_lines(img: Image.Image, ocr: Ocr) -> list[str]:
    """Text lines of one page in reading order: Tesseract's column pass, completed with the words its sparse
    pass found and the column pass dropped (`merge_sparse`). Lines without letters or digits (scan noise,
    box borders) are dropped."""
    buf = io.BytesIO()
    img.convert("L").save(buf, format="PNG")
    png = buf.getvalue()
    main = tsv_rows(_tsv(png, ocr, PSM))
    sparse = tsv_rows(_tsv(png, ocr, SPARSE_PSM), min_conf=SPARSE_MIN_CONF)
    return [
        line for line in (row_text(r) for r in merge_sparse(main, sparse)) if any(c.isalnum() for c in line)
    ]


@dataclass
class Row:
    """One line of words with its box (pixels): left, top, right, bottom."""

    words: list[tuple[int, str]]  # (left, text)
    top: int
    bottom: int
    right: int


def tsv_rows(tsv: str, min_conf: float = -1) -> list[Row]:
    """Words (level 5) grouped into lines by (block, paragraph, line), in output order, with their boxes."""
    rows: dict[tuple[str, str, str], Row] = {}
    for r in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        word = (r.get("text") or "").strip()
        if r.get("level") != "5" or not word:
            continue
        try:
            left, top, width, height = (int(r[k]) for k in ("left", "top", "width", "height"))
            conf = float(r.get("conf") or -1)
        except KeyError, ValueError:
            continue
        if conf < min_conf:
            continue
        key = (r["block_num"], r["par_num"], r["line_num"])
        row = rows.get(key)
        if row is None:
            rows[key] = Row([(left, word)], top, top + height, left + width)
        else:
            row.words.append((left, word))
            row.top, row.bottom = min(row.top, top), max(row.bottom, top + height)
            row.right = max(row.right, left + width)
    return list(rows.values())


def _key(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())


def row_text(row: Row) -> str:
    return " ".join(w for _, w in row.words)


def merge_sparse(main: list[Row], sparse: list[Row]) -> list[Row]:
    """Adds to the column pass the sparse-pass lines it does not have: into the row they share (half of the
    height overlaps), in left-to-right order with FILL between them (the dotted leader that hid them), or
    as a new row in vertical order. A sparse line counts only with a word of 3+ letters, so box borders
    read as text stay out."""
    have = " ".join(_key(row_text(r)) for r in main)
    out = [Row(list(r.words), r.top, r.bottom, r.right) for r in main]
    for s in sparse:
        text = row_text(s)
        if not any(sum(c.isalpha() for c in w) >= 3 for _, w in s.words) or _key(text) in have:
            continue
        height = max(1, s.bottom - s.top)
        same = [r for r in out if min(r.bottom, s.bottom) - max(r.top, s.top) >= height / 2]
        if same:
            row = same[0]
            # The same row read a little differently by both passes ("1a i" / "lai"): most of its words
            # are already there, so nothing was hidden. Adding it would double the row (form 8).
            present = {_key(w) for _, w in row.words}
            found = sum(_key(w) in present for _, w in s.words if _key(w))
            if found >= 0.5 * len(s.words):
                continue
            row.words = sorted(row.words + [(s.words[0][0] - 1, FILL), *s.words], key=lambda w: w[0])
            row.right = max(row.right, s.right)
        else:
            at = next((i for i, r in enumerate(out) if r.top > s.top), len(out))
            out.insert(at, Row(list(s.words), s.top, s.bottom, s.right))
        have += " " + _key(text)
    return out


def tsv_lines(tsv: str) -> list[str]:  # one pass, no boxes: kept for tests and simple callers
    """Words (level 5) grouped into lines by (block, paragraph, line), in output order."""
    lines: dict[tuple[str, str, str], list[str]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        word = (row.get("text") or "").strip()
        if row.get("level") == "5" and word:
            lines.setdefault((row["block_num"], row["par_num"], row["line_num"]), []).append(word)
    out = [" ".join(words) for words in lines.values()]
    return [line for line in out if any(ch.isalnum() for ch in line)]
