"""Validação e normalização de fotos publicadas no guia visual."""

from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_PHOTO_PIXELS = 16_000_000
MAX_PHOTO_SIDE = 3200


class InvalidPhoto(ValueError):
    pass


def normalize_photo(content: bytes) -> bytes:
    if not content:
        raise InvalidPhoto("Selecione uma imagem JPEG, PNG ou WebP.")
    if len(content) > MAX_PHOTO_BYTES:
        raise InvalidPhoto("A foto deve ter até 5 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InvalidPhoto("Envie uma imagem JPEG, PNG ou WebP.")
                if source.width * source.height > MAX_PHOTO_PIXELS:
                    raise InvalidPhoto("Reduza a imagem para até 16 megapixels.")
                source.verify()
            with Image.open(BytesIO(content)) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
                output = BytesIO()
                image.save(output, format="JPEG", quality=85)
                result = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        if isinstance(exc, InvalidPhoto):
            raise
        raise InvalidPhoto("O arquivo não contém uma imagem válida.") from exc
    if len(result) > MAX_PHOTO_BYTES:
        raise InvalidPhoto("Reduza a resolução da foto antes de enviar.")
    return result
