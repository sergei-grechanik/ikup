"""Pure image optimization algorithms without I/O dependencies."""

import io
import logging
import math
from typing import TYPE_CHECKING, Optional, List, Tuple

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


def transpose_image_maybe(image: "Image.Image") -> "Image.Image":
    """Transpose image according to EXIF orientation if available. Returns the original
    image if no transpose is needed."""
    from PIL import ExifTags, ImageOps

    try:
        orientation = image.getexif().get(ExifTags.Base.Orientation, 1)
        if orientation != 1:
            logger.debug("Transposing image with orientation %s", orientation)
            return ImageOps.exif_transpose(image)
    except Exception:
        pass
    return image


def convert_image(
    image: "Image.Image",
    *,
    format: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Tuple[io.BytesIO, "Image.Image", float]:
    """Convert PIL Image to specified format and dims, handling transparency correctly.

    Returns:
        - BytesIO containing the converted image data
        - PIL Image object of the resized image (may be the original image object)
        - float: the quality of the converted image from `[0.0; 1.0]` (1.0 if lossless)
    """
    format = format.upper()
    image = transpose_image_maybe(image)
    src_area = image.width * image.height

    # Resize if needed
    if width is not None and height is not None and (width, height) != image.size:
        logger.debug("Resize %sx%s -> %sx%s", image.width, image.height, width, height)
        image = image.resize((width, height))

    # Handle JPEG transparency conversion
    if format == "JPEG" and image.mode in ("RGBA", "LA", "P"):
        if image.mode == "P" and "transparency" in image.info:
            # Convert palette with transparency to RGBA first
            image = image.convert("RGBA")

        if image.mode in ("RGBA", "LA"):
            from PIL import Image

            # FIXME: The background should be configurable
            background = Image.new("RGB", image.size, (0, 0, 0))
            background.paste(
                image, mask=image.split()[-1] if image.mode == "RGBA" else None
            )
            image = background

    # Currently compute quality as the ration between the number of pixels.
    quality = image.width * image.height / src_area

    # Convert and return
    output = io.BytesIO()
    image.save(output, format=format)
    output.seek(0)
    return output, image, quality


def optimize_image_to_size(
    image: "Image.Image",
    format: str,
    max_size_bytes: int,
    tolerance: float,
    samples: List[Tuple[int, int, int]] = [],
) -> Tuple[io.BytesIO, "Image.Image", float]:
    """
    Optimize an image to fit within a size constraint.

    Args:
        image: PIL Image to optimize
        format: Target format ('JPEG', 'PNG', etc.)
        max_size_bytes: Maximum allowed file size in bytes
        tolerance: The maximum allowed relative difference between the resulting
            file size and `max_size_bytes` when downscaling.
        samples: Optional list of (width, height, size_bytes) tuples to guide
            the optimization.

    Returns:
        - BytesIO containing the optimized image data
        - PIL Image object of the optimized image
        - float: the quality of the converted image from `[0.0; 1.0]` (1.0 if lossless)
    """
    image = transpose_image_maybe(image)
    logger.debug(
        "optimize_image_to_size: max_size_bytes=%s, format=%s, tolerance=%s, samples=%s",
        max_size_bytes,
        format,
        tolerance,
        samples,
    )

    if image.width <= 1 or image.height <= 1:
        logger.debug(
            "Image is too small (%s x %s), returning 1x1 image",
            image.width,
            image.height,
        )
        return convert_image(image, format=format, width=1, height=1)

    original_area = image.width * image.height
    logger.debug(
        "Original image area: %s x %s = %s", image.width, image.height, original_area
    )
    # Convert the samples from `width, height -> size` to `area -> size`. We will use
    # the elements of this list to build a model.
    area_to_size: List[Tuple[int, int]] = [(s[0] * s[1], s[2]) for s in samples]
    # Sort it by distance to `max_size_bytes`.
    area_to_size.sort(key=lambda s: abs(s[1] - max_size_bytes))

    # The best image that is smaller than `max_size_bytes` so far.
    best_data: Optional[io.BytesIO] = None
    best_image: Optional["Image.Image"] = None
    best_quality: float = 0.0
    best_size: int = -1
    best_dims = (0, 0)

    # The best image parameters that exceed `max_size_bytes` so far. We don't use it to
    # estimate coefficients, so we start with fake value: slightly larger than the
    # original image and infinite size.
    best_exceed_dims = (image.width + 1, image.height + 1)
    best_exceed_size = float("inf")

    for iteration in range(6):
        logger.debug("Iteration %s", iteration)
        logger.debug("area_to_size = %s", area_to_size)
        # Get the coefficients for the linear model `area = a * size_bytes + b`.
        a, b = _get_coefficients(area_to_size)
        logger.debug("Formula: area = %s * size_bytes + %s", a, b)

        # Target the middle of the tolerance range.
        target_size = max_size_bytes * (1 - tolerance / 2)
        target_area = max(0, a * target_size + b)
        logger.debug("target_size = %s, target_area = %s", target_size, target_area)

        # Calculate the new dimension sizes.
        side_scale_factor = math.sqrt(target_area / original_area)
        new_width = min(image.width, max(1, int(image.width * side_scale_factor + 0.5)))
        new_height = min(
            image.height, max(1, int(image.height * side_scale_factor + 0.5))
        )
        # Make sure we are within the tightest bounds so far.
        too_small = (
            best_image
            and new_width <= best_image.width
            and new_height <= best_image.height
        )
        too_large = (
            new_width >= best_exceed_dims[0] and new_height >= best_exceed_dims[1]
        )
        if too_small or too_large:
            # Resort to binary search.
            logger.debug("%s x %s are bad, resort to bin search", new_width, new_height)
            new_width = int((best_dims[0] + best_exceed_dims[0]) / 2 + 0.5)
            new_height = int((best_dims[1] + best_exceed_dims[1]) / 2 + 0.5)
        logger.debug(
            "Evaluating %s x %s = %s", new_width, new_height, new_width * new_height
        )

        # Resize the image.
        cur_data, cur_image, cur_quality = convert_image(
            image, format=format, width=new_width, height=new_height
        )
        cur_size = cur_data.getbuffer().nbytes
        area_to_size.insert(0, (new_width * new_height, cur_size))
        logger.debug(
            "%s * %s = %s  ->  %s bytes",
            new_width,
            new_height,
            new_width * new_height,
            cur_size,
        )

        if cur_size > max_size_bytes and cur_image.size == (1, 1):
            # This is the smallest possible image, and it's still too large. Stop here.
            logger.debug("Returning 1x1 image as the smallest possible")
            return cur_data, cur_image, cur_quality

        if cur_size <= max_size_bytes:
            logger.debug("cur_size %s < max_size_bytes %s", cur_size, max_size_bytes)
            # We never upscale, so if the current image is the same size as the
            # original, and the size is smaller than the maximum size, we are done.
            if cur_image.size == image.size:
                logger.debug("Returning, it's the max size without upscaling")
                return cur_data, cur_image, cur_quality
            logger.debug("tolerance threshold: %s", max_size_bytes * (1 - tolerance))
            # If the current image is within the tolerance, we can stop.
            if cur_size >= max_size_bytes * (1 - tolerance):
                logger.debug("Returning, it's within tolerance")
                return cur_data, cur_image, cur_quality
            # It's still too small, check if it's the best so far.
            if cur_size > best_size:
                best_data = cur_data
                best_image = cur_image
                best_quality = cur_quality
                best_size = cur_size
                best_dims = cur_image.size
        else:
            if cur_size < best_exceed_size:
                best_exceed_size = cur_size
                best_exceed_dims = (new_width, new_height)
            logger.debug("cur_size %s > max_size_bytes %s", cur_size, max_size_bytes)

    if best_data is None or best_image is None:
        logger.debug("Creating and returning a 1x1 image")
        return convert_image(image, format=format, width=1, height=1)
    # Return the best image found. Here it will not satisfy the tolerance.
    logger.debug(
        "Could not find an image within the tolerance, "
        "returning %s x %s with size %s bytes and quality %s",
        best_image.width,
        best_image.height,
        best_size,
        best_quality,
    )
    return best_data, best_image, best_quality


def _get_coefficients(area_to_size: List[Tuple[int, int]]) -> Tuple[float, float]:
    """Get coefficients (a, b) for the simple linear model:
    `area = a * size_bytes + b`
    """
    if not area_to_size or area_to_size[0][1] == 0:
        # Prefer larger images as the first guess.
        return 2, 0.0

    # Find two points with different sizes.
    # Always use the most recent points.
    (f1, s1) = area_to_size[0]
    (f2, s2) = 0.0, 0.0
    rest = area_to_size[1:]
    for f2_cand, s2_cand in rest:
        if s2_cand != s1:
            (f2, s2) = (f2_cand, s2_cand)
            break

    a = (f1 - f2) / (s1 - s2)
    b = f1 - a * s1
    return a, b
