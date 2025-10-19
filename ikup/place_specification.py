import re
from typing import Optional, Tuple, Union
from dataclasses import dataclass


class PlaceSpecificationError(ValueError):
    """Raised when there is an error parsing a place specification."""


@dataclass
class PlaceSpec:
    """Place specification containing dimensions and position."""

    # Dimensions
    cols: Optional[str] = None
    rows: Optional[str] = None
    max_cols: Optional[str] = None
    max_rows: Optional[str] = None
    # Position
    pos: Optional[str] = None


def _normalize_x_to_comma(spec: str) -> str:
    """Replaces `x` with `,` if spec contains only integers, `x` and `_`."""
    if not spec:
        return spec
    if re.fullmatch(r"[0-9x_]+", spec):
        return spec.replace("x", ",")
    return spec


def parse_place_specification(spec: str) -> PlaceSpec:
    """Parse a place specification string into a PlaceSpec object.

    The specification format is:

        C,R~M,N@X,Y

    Where:
        - C: Columns
        - R: Rows
        - M: Max Columns
        - N: Max Rows
        - X: X position
        - Y: Y position

    Some parts may be omitted, all values may be formulas, `,` may be replaced with `x` if
    both elements of a pair are integers or `_`. Examples:

        5x10
        5x10@0,2
        _x_~20,30@cx,cy+1
        @100,200
    """
    res = PlaceSpec()
    if not spec:
        return res

    size_and_pos = spec.split("@")
    if len(size_and_pos) > 2:
        raise PlaceSpecificationError(f"Too many '@' in place specification: {spec!r}")
    size_part = size_and_pos[0].strip()
    pos_part = size_and_pos[1].strip() if len(size_and_pos) > 1 else ""
    dims_part = ""
    maxdims_part = ""
    if size_part:
        dims_and_maxdims = size_part.split("~")
        if len(dims_and_maxdims) > 2:
            raise PlaceSpecificationError(
                f"Too many '~' in place specification: {spec!r}"
            )
        dims_part = dims_and_maxdims[0].strip()
        maxdims_part = dims_and_maxdims[1].strip() if len(dims_and_maxdims) > 1 else ""

    dims_part = _normalize_x_to_comma(dims_part)
    maxdims_part = _normalize_x_to_comma(maxdims_part)
    pos_part = _normalize_x_to_comma(pos_part)

    if dims_part:
        res.cols = f"first({dims_part})"
        res.rows = f"second({dims_part})"
    if maxdims_part:
        res.max_cols = f"first({maxdims_part})"
        res.max_rows = f"second({maxdims_part})"
    if pos_part:
        res.pos = pos_part

    return res
