import argparse
import logging
import math
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_size(value: str):
    split_value = value.split("x")
    if len(split_value) != 2:
        split_value = value.split(",")
    if len(split_value) != 2:
        raise argparse.ArgumentTypeError(f"Size must be specified as WxH: {value}")
    try:
        width = int(split_value[0])
        height = int(split_value[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"Size must be integer: {value}")
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"Size must be positive: {value}")
    return (width, height)


def ffloor(value: float) -> float:
    """Floor function that returns float and works for infinity."""
    if math.isinf(value):
        return value
    return math.floor(value)


def get_real_image_size(image) -> Tuple[int, int]:
    from PIL import ExifTags

    width, height = image.size
    try:
        orientation = image.getexif().get(ExifTags.Base.Orientation, 1)
        if orientation in (5, 6, 7, 8):
            logger.debug(
                "Image orientation is %s, swapping %sx%s -> %sx%s",
                orientation,
                width,
                height,
                height,
                width,
            )
            width, height = height, width
    except Exception:
        pass
    return width, height
