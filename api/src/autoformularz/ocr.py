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
# --psm 4: one column of text of variable sizes; keeps form rows ("Label ....") as single lines.
PSM = "4"


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


def page_lines(img: Image.Image, ocr: Ocr) -> list[str]:
    """Text lines of one page in Tesseract's reading order. Lines without letters or digits (scan noise,
    box borders) are dropped."""
    buf = io.BytesIO()
    img.convert("L").save(buf, format="PNG")
    cmd = [ocr.binary, "stdin", "stdout", "-l", ocr.lang, "--psm", PSM, "-c", "tessedit_create_tsv=1"]
    if ocr.tessdata_dir:
        cmd += ["--tessdata-dir", ocr.tessdata_dir]
    env = {**os.environ, "OMP_THREAD_LIMIT": "1"}
    try:
        r = subprocess.run(cmd, input=buf.getvalue(), capture_output=True, timeout=PAGE_TIMEOUT_S, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise OcrError(str(e)) from e
    if r.returncode != 0:
        raise OcrError(r.stderr.decode("utf-8", "replace")[:300])
    return tsv_lines(r.stdout.decode("utf-8", "replace"))


def tsv_lines(tsv: str) -> list[str]:
    """Words (level 5) grouped into lines by (block, paragraph, line), in output order."""
    lines: dict[tuple[str, str, str], list[str]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        word = (row.get("text") or "").strip()
        if row.get("level") == "5" and word:
            lines.setdefault((row["block_num"], row["par_num"], row["line_num"]), []).append(word)
    out = [" ".join(words) for words in lines.values()]
    return [line for line in out if any(ch.isalnum() for ch in line)]
