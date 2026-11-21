"""Upload validation required by the task: allowed formats only, MIME sniffed from the bytes
(content must match the extension), file name rules, configurable max size.

Format detection uses magic bytes and zip container inspection, so it needs no native libmagic."""

import io
import zipfile
from enum import StrEnum


class Kind(StrEnum):
    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    ODS = "ods"
    XLSX = "xlsx"
    JPEG = "jpeg"
    PNG = "png"


MIME = {
    Kind.PDF: "application/pdf",
    Kind.DOC: "application/msword",
    Kind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    Kind.ODS: "application/vnd.oasis.opendocument.spreadsheet",
    Kind.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    Kind.JPEG: "image/jpeg",
    Kind.PNG: "image/png",
}

EXTENSIONS = {
    "pdf": Kind.PDF,
    "doc": Kind.DOC,
    "docx": Kind.DOCX,
    "ods": Kind.ODS,
    "xlsx": Kind.XLSX,
    "jpg": Kind.JPEG,
    "jpeg": Kind.JPEG,
    "jpe": Kind.JPEG,
    "png": Kind.PNG,
}

# The task lists Word as one format "DOC (.doc .docx)", and offices often save a .docx under a .doc name
# (materials 5 and 7). Within that group the real content decides how the file is read.
SAME_FORMAT = {Kind.DOC: {Kind.DOC, Kind.DOCX}, Kind.DOCX: {Kind.DOC, Kind.DOCX}}

FORBIDDEN_CHARS = set(";:><\\/|'*%$")
MAX_NAME_LENGTH = 250


class UploadError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def validate_filename(name: str | None) -> Kind:
    """Checks the file name rules and returns the format declared by the extension."""
    if not name or not name.strip():
        raise UploadError("FILENAME_MISSING", "Plik nie ma nazwy.")
    if len(name) > MAX_NAME_LENGTH:
        raise UploadError("FILENAME_TOO_LONG", f"Nazwa pliku może mieć najwyżej {MAX_NAME_LENGTH} znaków.")
    bad = sorted(FORBIDDEN_CHARS.intersection(name))
    if bad:
        raise UploadError(
            "FILENAME_FORBIDDEN_CHARS", f"Nazwa pliku zawiera niedozwolone znaki: {' '.join(bad)}"
        )
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    kind = EXTENSIONS.get(ext)
    if kind is None:
        allowed = ", ".join(sorted(EXTENSIONS))
        raise UploadError(
            "UNSUPPORTED_FORMAT", f"Nieobsługiwany format pliku. Dozwolone: {allowed}.", status=415
        )
    return kind


def sniff(data: bytes) -> Kind | None:
    """Detects the real format from file content."""
    if data.startswith(b"%PDF-"):
        return Kind.PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return Kind.PNG
    if data.startswith(b"\xff\xd8\xff"):
        return Kind.JPEG
    if data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):  # OLE2 compound file (legacy .doc)
        return Kind.DOC
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "mimetype" in names:
                    mt = z.read("mimetype").decode("ascii", "ignore").strip()
                    if mt == MIME[Kind.ODS]:
                        return Kind.ODS
                    return None
                if "[Content_Types].xml" in names:
                    if any(n.startswith("word/") for n in names):
                        return Kind.DOCX
                    if any(n.startswith("xl/") for n in names):
                        return Kind.XLSX
        except zipfile.BadZipFile:
            return None
    return None


def validate_upload(name: str | None, data: bytes, max_bytes: int) -> Kind:
    declared = validate_filename(name)
    if not data:
        raise UploadError("FILE_EMPTY", "Plik jest pusty.")
    if len(data) > max_bytes:
        raise UploadError(
            "FILE_TOO_LARGE",
            f"Plik jest za duży. Maksymalny rozmiar: {max_bytes / 1_048_576:g} MB.",
            status=413,
        )
    actual = sniff(data)
    if actual is None:
        raise UploadError("UNSUPPORTED_CONTENT", "Nie rozpoznano zawartości pliku.", status=415)
    if actual not in SAME_FORMAT.get(declared, {declared}):
        raise UploadError(
            "MIME_MISMATCH",
            f"Zawartość pliku ({MIME[actual]}) nie pasuje do rozszerzenia ({MIME[declared]}).",
            status=415,
        )
    return actual
