"""Decode and normalize uploads before storing private student portraits."""
from io import BytesIO
from uuid import uuid4
import warnings

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

MAX_PHOTO_BYTES = 5 * 1024 * 1024


def normalize_photo(upload):
    if upload.size > MAX_PHOTO_BYTES:
        raise ValidationError("Choose a photo no larger than 5 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValidationError("Choose a JPEG, PNG, or WebP photo.")
                if image.width * image.height > 20_000_000:
                    raise ValidationError("Choose a photo with at most 20 megapixels.")
                image.load()
                portrait = ImageOps.exif_transpose(image).convert("RGB")
                portrait.thumbnail((1200, 1200))
                output = BytesIO()
                portrait.save(output, format="JPEG", quality=85)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError("This file is not a supported, valid image.")
    return ContentFile(output.getvalue(), name=f"{uuid4().hex}.jpg")
