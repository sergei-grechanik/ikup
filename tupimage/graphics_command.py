import base64
import io
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import BinaryIO, Optional, Union, Iterator, Dict


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

    @staticmethod
    def from_bits(bits: int) -> "Format":
        if bits == 24:
            return Format.RGB
        elif bits == 32:
            return Format.RGBA
        else:
            raise ValueError(f"Invalid number of bits: {bits}")

    def __str__(self):
        return str(self.value)


class TransmissionMedium(Enum):
    DIRECT = "d"
    FILE = "f"
    TEMP_FILE = "t"

    @staticmethod
    def from_string(s: str) -> "TransmissionMedium":
        if s == "d" or s == "direct" or s == "stream":
            return TransmissionMedium.DIRECT
        elif s == "f" or s == "file":
            return TransmissionMedium.FILE
        elif s == "t" or s == "temp" or s == "tempfile":
            return TransmissionMedium.TEMP_FILE
        else:
            raise ValueError(f"Unsupported transmission medium: {s}")

    def __str__(self):
        return str(self.value)


class Compression(Enum):
    ZLIB = "z"

    @staticmethod
    def from_bool(compress: bool) -> Optional["Compression"]:
        return Compression.ZLIB if compress else None

    def __str__(self):
        return str(self.value)


class WhatToDelete(Enum):
    VISIBLE_PLACEMENTS = "a"
    IMAGE_OR_PLACEMENT_BY_ID = "i"
    IMAGE_OR_PLACEMENT_BY_NUMBER = "n"
    PLACEMENTS_UNDER_CURSOR = "c"
    ANIMATION_FRAMES = "f"
    PLACEMENTS_AT_POSITION = "p"
    PLACEMENTS_AT_POSITION_AND_ZINDEX = "q"
    PLACEMENTS_AT_COLUMN = "x"
    PLACEMENTS_AT_ROW = "y"
    PLACEMENTS_AT_ZINDEX = "z"

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
        return dataclasses.replace(self, **kwargs)


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
    cols: Optional[int] = None
    do_not_move_cursor: Optional[bool] = None
    src_x: Optional[int] = None
    src_y: Optional[int] = None
    src_w: Optional[int] = None
    src_h: Optional[int] = None
    # TODO: z, X, Y

    def to_tuple(self):
        return (
            (b"p", self.placement_id),
            (b"U", self.virtual),
            (b"r", self.rows),
            (b"c", self.cols),
            (b"x", self.src_x),
            (b"y", self.src_y),
            (b"w", self.src_w),
            (b"h", self.src_h),
            (b"C", self.do_not_move_cursor),
        )


@dataclass
class TransmitCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    medium: Optional[TransmissionMedium] = None
    data: Union[bytes, BinaryIO] = b""
    size: Optional[int] = None
    quiet: Optional[Quietness] = None
    more: Optional[bool] = None
    format: Optional[Format] = None
    compression: Optional[Compression] = None
    pix_width: Optional[int] = None
    pix_height: Optional[int] = None
    query: Optional[bool] = None
    placement: Optional[PlacementData] = None

    def get_put_command(self) -> Optional["PutCommand"]:
        if self.placement is None:
            return None
        return PutCommand(
            image_id=self.image_id,
            image_number=self.image_number,
            quiet=self.quiet,
            **dataclasses.asdict(self.placement),
        )

    def split(self, max_size: int) -> Iterator[GraphicsCommand]:
        if self.medium != TransmissionMedium.DIRECT:
            yield self
            return
        original_more = self.more
        data = self.data
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        data.seek(0)
        cur_chunk = data.read(max_size)
        next_chunk = data.read(max_size)
        yield self.clone_with(
            data=cur_chunk, more=original_more or bool(next_chunk)
        )
        while next_chunk:
            cur_chunk = next_chunk
            next_chunk = data.read(max_size)
            yield MoreDataCommand(
                image_id=self.image_id,
                image_number=self.image_number,
                data=cur_chunk,
                more=original_more or bool(next_chunk),
            )

    def to_tuple(self):
        action = "q" if self.query else "t" if self.placement is None else "T"
        tup = (
            (b"a", action),
            (b"i", self.image_id),
            (b"I", self.image_number),
            (b"t", self.medium),
            (b"S", self.size),
            (b"q", self.quiet),
            (b"m", self.more),
            (b"f", self.format),
            (b"o", self.compression),
            (b"s", self.pix_width),
            (b"v", self.pix_height),
        )
        if self.placement is not None:
            tup = tup + self.placement.to_tuple()
        return tup

    def content_to_stream(self, stream: BinaryIO):
        kv_tuple_to_stream(self.to_tuple(), stream)
        stream.write(b";")
        data = self.data
        if not isinstance(data, bytes):
            data.seek(0)
            data = data.read()
        stream.write(base64.b64encode(data))

    def set_filename(self, filename: str) -> "TransmitCommand":
        self.data = filename.encode()
        return self

    def set_data(self, data: Union[bytes, BinaryIO]) -> "TransmitCommand":
        self.data = data
        return self

    def set_placement(self, **kwargs) -> "TransmitCommand":
        self.placement = PlacementData(**kwargs)
        return self


@dataclass
class MoreDataCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    data: bytes = b""
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
        stream.write(base64.b64encode(self.data))


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
class DeleteCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    placement_id: Optional[int] = None
    quiet: Optional[Quietness] = None
    what: Optional[WhatToDelete] = None
    delete_data: Optional[bool] = None

    def to_tuple(self):
        what_str = None
        if self.what is not None:
            what_str = self.what.value
            if self.delete_data:
                what_str = what_str.upper()
        return (
            (b"a", b"d"),
            (b"i", self.image_id),
            (b"I", self.image_number),
            (b"p", self.placement_id),
            (b"q", self.quiet),
            (b"d", what_str),
        )

    def content_to_stream(self, stream: BinaryIO):
        kv_tuple_to_stream(self.to_tuple(), stream)


@dataclass
class GraphicsResponse:
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    placement_id: Optional[int] = None
    additional_data: Dict[str, Optional[str]] = dataclasses.field(
        default_factory=dict
    )
    message: str = ""
    is_ok: bool = False
    is_valid: bool = False
    non_response: bytes = b""

    def is_err(
        self,
        message: str = "",
        image_id: Optional[int] = None,
        image_number: Optional[int] = None,
        placement_id: Optional[int] = None,
    ) -> bool:
        return (
            not self.is_ok
            and self.is_valid
            and message in self.message
            and self.image_id == image_id
            and self.image_number == image_number
            and self.placement_id == placement_id
        )

    @staticmethod
    def ok_response(
        image_id: Optional[int] = None,
        image_number: Optional[int] = None,
        placement_id: Optional[int] = None,
    ) -> "GraphicsResponse":
        return GraphicsResponse(
            image_id=image_id,
            image_number=image_number,
            placement_id=placement_id,
            is_ok=True,
            is_valid=True,
            message="OK",
        )
