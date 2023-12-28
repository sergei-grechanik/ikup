import argparse


def validate_size(value: str):
    split_value = value.split("x")
    if len(split_value) != 2:
        raise argparse.ArgumentTypeError(
            f"Size must be specified as WxH: {value}"
        )
    try:
        width = int(split_value[0])
        height = int(split_value[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"Size must be integer: {value}")
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"Size must be positive: {value}")
    return (width, height)


def validate_place(value: str):
    split_value = [part.split("x") for part in value.split("@")]
    if (
        len(split_value) != 2
        or len(split_value[0]) != 2
        or len(split_value[1]) != 2
    ):
        raise argparse.ArgumentTypeError(
            f"Place must be specified as WxH@XxY: {value}"
        )
    try:
        width = int(split_value[0][0])
        height = int(split_value[0][1])
        x = int(split_value[1][0])
        y = int(split_value[1][1])
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"All components of WxH@XxY must be integer: {value}"
        )
    if width < 1 or height < 1 or x < 0 or y < 0:
        raise argparse.ArgumentTypeError(
            f"Size must be positive, coordinates must be non-negative: {value}"
        )
    return ((width, height), (x, y))
