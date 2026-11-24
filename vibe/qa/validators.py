"""Validation helpers for uploaded answer attachments."""

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "webp"]
DOCUMENT_EXTENSIONS = [
    "pdf",
    "doc",
    "docx",
    "txt",
    "rtf",
    "odt",
    "xls",
    "xlsx",
    "csv",
    "ppt",
    "pptx",
]
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS


def validate_file_size(value):
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024)
    if value.size > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise ValidationError(
            f"Размер файла не должен превышать {limit_mb} МБ."
        )


def is_image_file(name):
    return Path(name).suffix.lower().lstrip(".") in IMAGE_EXTENSIONS
