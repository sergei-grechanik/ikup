import base64
import copy
import io
from dataclasses import dataclass
from enum import Enum
from typing import BinaryIO, List, Optional


class Quietness(Enum):
    VERBOSE = 0
    QUIET_UNLESS_ERROR = 1
    QUIET_ALWAYS = 2

    def __str__(self):
        return str(self.value)


class Format(Enum):
    RGB = 24
    RGBA = 32
    PNG = 100

    def __str__(self):
        return str(self.value)


class TransmissionMedium(Enum):
    DIRECT = "d"
    FILE = "f"
    TEMP_FILE = "t"

    def __str__(self):
        return str(self.value)


class Compression(Enum):
    ZLIB = "z"

    def __str__(self):
        return str(self.value)


class GraphicsCommand:
    def to_tuple(self):
        raise NotImplementedError()

    def content_to_stream(self, stream: BinaryIO):
        raise NotImplementedError()

    def content_to_bytes(self) -> bytes:
        with io.BytesIO() as bio:
            self.content_to_stream(bio)
            return bio.getvalue()

    def clone_with(self, **kwargs):
        clone = copy.copy(self)
        for k, v in kwargs.items():
            setattr(clone, k, v)
        return clone


def kv_tuple_to_stream(tup, stream: BinaryIO):
    first = True
    for k, v in tup:
        if v is None:
            continue
        if not isinstance(v, bytes):
            if isinstance(v, bool):
                v = int(v)
            v = str(v).encode("ascii")
        if first:
            first = False
        else:
            stream.write(b",")
        stream.write(k)
        stream.write(b"=")
        stream.write(v)


@dataclass
class PlacementData:
    placement_id: Optional[int] = None
    virtual: Optional[bool] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    do_not_move_cursor: Optional[bool] = None
    # TODO: x, y, w, h, z, X, Y

    def to_tuple(self):
        return (
            (b"p", self.placement_id),
            (b"U", self.virtual),
            (b"r", self.rows),
            (b"c", self.columns),
            (b"C", self.do_not_move_cursor),
        )


@dataclass
class TransmitCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    medium: Optional[TransmissionMedium] = None
    base64_data: bytes = b""
    data_size: Optional[int] = None
    quiet: Optional[Quietness] = None
    more: Optional[bool] = None
    format: Optional[Format] = None
    compression: Optional[Compression] = None
    pix_width: Optional[int] = None
    pix_height: Optional[int] = None
    query: Optional[bool] = None
    placement: Optional[PlacementData] = None

    def split(self, max_size: int) -> List[GraphicsCommand]:
        if len(self.base64_data) <= max_size:
            return [self]
        result = [copy.copy(self)]
        result[0].base64_data = self.base64_data[:max_size]
        result[0].more = True
        for i in range(max_size, len(self.base64_data), max_size):
            more = MoreDataCommand(
                image_id=self.image_id,
                image_number=self.image_number,
                base64_data=self.base64_data[i : i + max_size],
                more=True,
            )
            result.append(more)
        result[-1].more = False
        return result

    def to_tuple(self):
        action = "q" if self.query else "t" if self.placement is None else "T"
        tup = (
            (b"a", action),
            (b"i", self.image_id),
            (b"I", self.image_number),
            (b"t", self.medium),
            (b"S", self.data_size),
            (b"q", self.quiet),
            (b"m", self.more),
            (b"f", self.format),
            (b"c", self.compression),
            (b"s", self.pix_width),
            (b"v", self.pix_height),
        )
        if self.placement is not None:
            tup = tup + self.placement.to_tuple()
        return tup

    def content_to_stream(self, stream: BinaryIO):
        kv_tuple_to_stream(self.to_tuple(), stream)
        stream.write(b";")
        stream.write(self.base64_data)

    def set_filename(self, filename: str) -> "TransmitCommand":
        self.base64_data = base64.b64encode(filename.encode())
        return self

    def set_data(self, data: bytes) -> "TransmitCommand":
        self.base64_data = base64.b64encode(data)
        return self

    def set_placement(self, **kwargs) -> "TransmitCommand":
        self.placement = PlacementData(**kwargs)
        return self


@dataclass
class MoreDataCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    base64_data: bytes = b""
    more: Optional[bool] = None

    def to_tuple(self):
        return (
            (b"i", self.image_id),
            (b"I", self.image_number),
            (b"m", self.more),
        )

    def content_to_stream(self, stream: BinaryIO):
        kv_tuple_to_stream(self.to_tuple(), stream)
        stream.write(b";")
        stream.write(self.base64_data)


@dataclass
class PutCommand(GraphicsCommand, PlacementData):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    quiet: Optional[Quietness] = None

    def to_tuple(self):
        tup = (
            (b"a", b"p"),
            (b"i", self.image_id),
            (b"I", self.image_number),
            (b"q", self.quiet),
        ) + PlacementData.to_tuple(self)
        return tup

    def content_to_stream(self, stream: BinaryIO):
        kv_tuple_to_stream(self.to_tuple(), stream)


@dataclass
class GraphicsResponse:
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    message: str = ""
    is_ok: bool = False
    is_valid: bool = False
    non_response: bytes = b""
