import base64
import dataclasses
import io
import select
from abc import ABC, abstractmethod
from dataclasses import dataclass, is_dataclass
from enum import Enum
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Iterator,
    Optional,
    Tuple,
    TypeVar,
    Union,
)


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
    SHARED_MEMORY = "s"

    @staticmethod
    def from_string(s: str) -> "TransmissionMedium":
        if s == "d" or s == "direct" or s == "stream":
            return TransmissionMedium.DIRECT
        elif s == "f" or s == "file":
            return TransmissionMedium.FILE
        elif s == "t" or s == "temp" or s == "tempfile":
            return TransmissionMedium.TEMP_FILE
        elif s == "s" or s == "shm":
            return TransmissionMedium.SHARED_MEMORY
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


class GraphicsCommand(ABC):
    """Base class for all graphics commands.

    Note that all graphics commands are assumed to be mutable dataclasses.
    """

    DEFAULT_TEMPLATE = b"\033_G%b\033\\"

    @abstractmethod
    def header_to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        """Returns the header of the command as a dictionary of key-value pairs. The
        values can be bytes or integers.
        Example: `((b"a", b"t"), (b"i", 42), (b"q", 2))`.
        """
        pass

    def header_to_bytes(self) -> bytes:
        """Returns the header of the command (no payload, no escape characters) as a
        byte string.
        Example: `b"a=t,i=42,q=2"`.
        """
        return b",".join(
            k + b"=" + (v if isinstance(v, bytes) else str(v).encode("ascii"))
            for k, v in self.header_to_tuple()
        )

    def get_raw_payload(self) -> Optional[bytes]:
        """Returns the payload of the command as a byte string."""
        return None

    def get_encoded_payload(self) -> Optional[bytes]:
        """Returns the base64-encoded payload of the command as a byte string."""
        data = self.get_raw_payload()
        if data is None:
            return None
        return base64.b64encode(data)

    def content_to_bytes(self) -> bytes:
        """Returns the content of the command (header + base64-encoded payload, but no
        escape characters) as a byte string.
        Example: `b"a=t,i=42,q=2;123ABC"`."""
        payload = self.get_encoded_payload()
        if payload is None:
            return self.header_to_bytes()
        return self.header_to_bytes() + b";" + payload

    T = TypeVar("T", bound="GraphicsCommand")

    def clone_with(self: T, **kwargs) -> T:
        """Returns a new instance of the command with the specified fields updated."""
        assert is_dataclass(self)
        return dataclasses.replace(self, **kwargs)

    def to_bytes(self, template: bytes) -> bytes:
        """Returns the command as a byte string formatted using the specified template.

        Args:
            template: The template to use to format the command. It should contain a
                single `%b` format specifier where the command content should be
                inserted. See `GraphicsCommand.DEFAULT_TEMPLATE`.
        """
        return template % self.content_to_bytes()

    def send(
        self,
        tty: BinaryIO,
        template: bytes,
        max_size: Optional[int] = None,
        callback: Optional[Callable[["GraphicsCommand"], None]] = None,
    ) -> None:
        """Sends the command to the TTY.

        Args:
            tty: The file-like object to write the command to.
            template: The template to use to format the command. It should contain a
                single `%b` format specifier where the command content should be
                inserted. See `GraphicsCommand.DEFAULT_TEMPLATE`.
            max_size: The maximum total size of the command. If it's a transmission
                command, it will be split to fit this size. The default is
                `select.PIPE_BUF`.
            callback: A callback that will be called for each command after it's sent.
                This can be used to track the progress of a split transmission command.
        """
        if max_size is None:
            max_size = select.PIPE_BUF
        tty.flush()
        if not isinstance(self, TransmitCommand):
            tty.write(template % self.content_to_bytes())
            tty.flush()
            if callback is not None:
                callback(self)
            return
        # If it's a TransmitCommand, we may need to split it into multiple commands.
        max_base64_payload_size = (
            max_size - len(template) - len(self.header_to_bytes()) - 4
        )
        # Each 3 bytes of payload will be encoded to 4 bytes of base64.
        max_payload_size = (max_base64_payload_size // 4) * 3
        if max_payload_size < 1:
            raise ValueError(
                "The maximum payload size is too small. "
                f"Increase the max_size parameter (now {max_size})"
            )
        for cmd in self.split(max_payload_size=max_payload_size):
            tty.write(template % cmd.content_to_bytes())
            tty.flush()
            if callback is not None:
                callback(cmd)


def normalize_header_value(value: Any) -> bytes | int:
    """Normalizes a header value to a byte string or an integer."""
    if isinstance(value, str):
        return value.encode("ascii")
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, bytes)):
        return value
    if isinstance(
        value, (Quietness, Format, TransmissionMedium, Compression, WhatToDelete)
    ):
        return normalize_header_value(value.value)
    raise ValueError(f"Unsupported header value: {value}")


def normalize_header_tuple(
    tup: Tuple[Tuple[bytes, Any], ...],
) -> Tuple[Tuple[bytes, bytes | int], ...]:
    """Converts a tuple of key-value pairs to a tuple of key-value pairs where the
    values are bytes or integers. None values are dropped."""
    return tuple((k, normalize_header_value(v)) for k, v in tup if v is not None)


@dataclass
class PlacementData:
    """Data for placing an image on the terminal screen.

    This is a base class of `PutCommand` (which is a placement command essentially), and
    this data may also be attached to a `TransmitCommand` to perform transmission and
    placement in a single command."""

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

    def to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        """Returns the placement data as a tuple of key-value pairs that can be used for
        the header."""
        return normalize_header_tuple(
            (
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
        )


@dataclass
class TransmitCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    medium: Optional[TransmissionMedium] = None
    data: Union[bytes, BinaryIO] = b""
    size: Optional[int] = None
    offset: Optional[int] = None
    quiet: Optional[Quietness] = None
    more: Optional[bool] = None
    format: Optional[Format] = None
    compression: Optional[Compression] = None
    pix_width: Optional[int] = None
    pix_height: Optional[int] = None
    query: Optional[bool] = None
    placement: Optional[PlacementData] = None
    # Used for debugging to omit `a=...` from the command.
    omit_action: bool = False

    def get_pure_transmit_command(self) -> "TransmitCommand":
        """Returns a copy of the command without the placement data."""
        return self.clone_with(placement=None)

    def get_put_command(self) -> Optional["PutCommand"]:
        """Returns a PutCommand with the placement data taken from this command."""
        if self.placement is None:
            return None
        return PutCommand(
            image_id=self.image_id,
            image_number=self.image_number,
            quiet=self.quiet,
            **dataclasses.asdict(self.placement),
        )

    def split(self, *, max_payload_size: int) -> Iterator[GraphicsCommand]:
        """Splits the command into multiple commands if the data is too large. The first
        command will be a `TransmitCommand`, and the rest will be `MoreDataCommand`.
        Each payload will be at most `max_payload_size` bytes **before**
        base64-encoding.
        """
        if self.medium != TransmissionMedium.DIRECT:
            yield self
            return
        original_more = self.more
        data = self.data
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        data.seek(0)
        cur_chunk = data.read(max_payload_size)
        next_chunk = data.read(max_payload_size)
        yield self.clone_with(data=cur_chunk, more=original_more or bool(next_chunk))
        while next_chunk:
            cur_chunk = next_chunk
            next_chunk = data.read(max_payload_size)
            yield MoreDataCommand(
                image_id=self.image_id,
                image_number=self.image_number,
                data=cur_chunk,
                more=original_more or bool(next_chunk),
            )

    def header_to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        action = None
        if not self.omit_action:
            action = "q" if self.query else "t" if self.placement is None else "T"
        tup = normalize_header_tuple(
            (
                (b"i", self.image_id),
                (b"I", self.image_number),
                (b"t", self.medium),
                (b"S", self.size),
                (b"O", self.offset),
                (b"q", self.quiet),
                (b"m", self.more),
                (b"f", self.format),
                (b"o", self.compression),
                (b"s", self.pix_width),
                (b"v", self.pix_height),
                (b"a", action),
            )
        )
        if self.placement is not None:
            tup = tup + self.placement.to_tuple()
        return tup

    def get_raw_payload(self) -> Optional[bytes]:
        data = self.data
        if not isinstance(data, bytes):
            data.seek(0)
            data = data.read()
        return data

    def set_filename(self, filename: str) -> "TransmitCommand":
        """Sets the data to be a filename."""
        self.data = filename.encode()
        return self

    def set_data(self, data: Union[bytes, BinaryIO]) -> "TransmitCommand":
        """Sets the data to be a byte string or a file-like object."""
        self.data = data
        return self

    def set_data_from_file(self, filename: str) -> "TransmitCommand":
        """Sets the data to be the contents of a file."""
        self.data = open(filename, "rb")
        return self

    def set_placement(self, **kwargs) -> "TransmitCommand":
        """Sets the placement data built from kwargs."""
        self.placement = PlacementData(**kwargs)
        return self


@dataclass
class MoreDataCommand(GraphicsCommand):
    """This command is used to send additional data after a `TransmitCommand`.

    Essentially, it's a special case of a transmission command with most of the
    parameters omitted."""

    image_id: Optional[int] = None
    image_number: Optional[int] = None
    data: bytes = b""
    more: Optional[bool] = None

    def header_to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        return normalize_header_tuple(
            (
                (b"i", self.image_id),
                (b"I", self.image_number),
                (b"m", self.more),
            )
        )

    def get_raw_payload(self) -> Optional[bytes]:
        return self.data


@dataclass
class PutCommand(GraphicsCommand, PlacementData):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    quiet: Optional[Quietness] = None

    def header_to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        tup = normalize_header_tuple(
            (
                (b"a", b"p"),
                (b"i", self.image_id),
                (b"I", self.image_number),
                (b"q", self.quiet),
            )
        ) + PlacementData.to_tuple(self)
        return tup


@dataclass
class DeleteCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    placement_id: Optional[int] = None
    quiet: Optional[Quietness] = None
    what: Optional[WhatToDelete] = None
    delete_data: Optional[bool] = None

    def header_to_tuple(self) -> Tuple[Tuple[bytes, bytes | int], ...]:
        # Whether we are deleting data is indicated by the case of the what string.
        what_str = None
        if self.what is not None:
            what_str = self.what.value
            if self.delete_data:
                what_str = what_str.upper()
        return normalize_header_tuple(
            (
                (b"a", b"d"),
                (b"i", self.image_id),
                (b"I", self.image_number),
                (b"p", self.placement_id),
                (b"q", self.quiet),
                (b"d", what_str),
            )
        )


@dataclass
class GraphicsResponse:
    """This class represents a response from the graphics terminal."""

    image_id: Optional[int] = None
    image_number: Optional[int] = None
    placement_id: Optional[int] = None
    additional_data: Dict[str, Optional[str]] = dataclasses.field(default_factory=dict)
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
