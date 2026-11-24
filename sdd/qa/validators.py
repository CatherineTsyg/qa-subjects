import os
import zipfile

from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "pdf", "txt", "doc", "docx"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
DOCUMENT_EXTENSIONS = {"pdf", "txt", "doc", "docx"}

MIME_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
PDF_MAGIC = b"%PDF-"
DOC_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _extension(name):
    return os.path.splitext(os.path.basename(name or ""))[1].lower().lstrip(".")


def _read_bytes(uploaded_file, size=None):
    uploaded_file.seek(0)
    data = uploaded_file.read() if size is None else uploaded_file.read(size)
    uploaded_file.seek(0)
    return data


def _is_docx(uploaded_file):
    uploaded_file.seek(0)
    try:
        with zipfile.ZipFile(uploaded_file) as archive:
            return "[Content_Types].xml" in archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    finally:
        uploaded_file.seek(0)


def _is_text(uploaded_file):
    try:
        _read_bytes(uploaded_file).decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def validate_attachment(uploaded_file):
    """Проверяет файл и возвращает MIME-тип для сохранения."""
    if uploaded_file is None:
        raise ValidationError("Файл не выбран.")

    extension = _extension(uploaded_file.name)
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Недопустимый тип файла.")

    size = uploaded_file.size or 0
    if size <= 0:
        raise ValidationError("Пустой файл не допускается.")

    if extension in IMAGE_EXTENSIONS:
        limit = MAX_IMAGE_SIZE
    else:
        limit = MAX_DOCUMENT_SIZE
    if size > limit:
        raise ValidationError("Размер файла превышает допустимый лимит.")

    head = _read_bytes(uploaded_file, 32)

    if extension in {"jpg", "jpeg"}:
        valid = head.startswith(JPEG_MAGIC)
    elif extension == "png":
        valid = head.startswith(PNG_MAGIC)
    elif extension == "webp":
        valid = (
            len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        )
    elif extension == "pdf":
        valid = head.startswith(PDF_MAGIC)
    elif extension == "doc":
        valid = head.startswith(DOC_MAGIC)
    elif extension == "docx":
        valid = _is_docx(uploaded_file)
    else:  # txt
        valid = b"\x00" not in _read_bytes(uploaded_file) and _is_text(uploaded_file)

    if not valid:
        raise ValidationError("Содержимое файла не соответствует расширению.")

    return MIME_TYPES[extension]
