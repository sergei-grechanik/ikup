import io
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union, Callable, Tuple, TextIO, List
import copy

class Quietness(Enum):
    NORMAL = 0
    QUIET_UNLESS_ERROR = 1
    QUIET_ALWAYS = 2

class Format(Enum):
    RGB = 24
    RGBA = 32
    PNG = 100

class TransmissionMedium(Enum):
    DIRECT = "d"
    FILE = "f"
    TEMP_FILE = "t"

class Compression(Enum):
    ZLIB = "z"

class GraphicsCommand:
    def content_to_stream(self, stream: TextIO):
        raise NotImplementedError()

    def content_to_string(self) -> str:
        with io.StringIO() as sio:
            self.to_stream(sio)
            return sio.getvalue()

def kv_tuple_to_stream(tup, stream: TextIO):
    first = True
    for k, v in tup:
        if v is None:
            continue
        if first:
            stream.write(f"{k}={v}")
            first = False
        else:
            stream.write(f",{k}={v}")

@dataclass
class PlacementData:
    placement_id: Optional[int] = None
    virtual: Optiona[bool] = None
    rows: Optional[int] = None
    columns: Optional[int] = None
    do_not_move_cursor: Optional[bool] = None
    # TODO: x, y, w, h, z, X, Y

    def content_to_stream(self, stream: TexIO):
        tup = (('p', self.placement_id), ('U', self.virtual), ('r', self.rows), ('c', self.columns), ('C', self.do_not_move_cursor))
        kv_tuple_to_stream(tup, stream)

@dataclass
class TransmitCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    medium: TransmissionMedium
    data: str = ""
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
        if len(self.data) <= max_size:
            return [self]
        result = [copy.copy(self)]
        result[0].data = self.data[:max_size]
        result[0].more = True
        for i in range(max_size, len(self.data), max_size):
            more = MoreDataCommand(image_id=self.image_id, image_number=self.image_number, data=self.data[i:i+max_size], more=True)
            result.append(more)
        result[-1].more = False
        return result

    def content_to_stream(self, stream: TextIO):
        action = "q" if self.query else "t" if placement is None else "T"
        tup = (('a', action), ('i', self.image_id), ('I', self.image_number), ('t', self.medium.value), ('S', self.data_size), ('q', self.quiet.value), ('m', self.more), ('f', self.format.value), ('c', self.compression.value), ('s', self.pix_width), ('v', self.pix_height))
        kv_tuple_to_stream(tup, stream)
        if self.placement is not None:
            stream.write(",")
            self.placement.content_to_stream(stream)
        stream.write(";")
        stream.write(self.data)

@dataclass
class MoreDataCommand(GraphicsCommand):
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    data: Optional[str] = None
    more: Optional[bool] = None

    def content_to_stream(self, stream: TextIO):
        tup = (('i', self.image_id), ('I', self.image_number), ('m', self.more))
        kv_tuple_to_stream(tup, stream)
        stream.write(";")
        stream.write(self.data)

@dataclass
class PutCommand(GraphicsCommand, PlacementData):
    image_id: Optional[int] = None
    image_number: Optional[int] = None

    def content_to_stream(self, stream: TextIO):
        tup = (('i', self.image_id), ('I', self.image_number))
        kv_tuple_to_stream(tup, stream)
        stream.write(",")
        PlacementData.content_to_stream(self, stream)

@dataclass
class GraphicsResponse:
    image_id: Optional[int] = None
    image_number: Optional[int] = None
    message: str = ""
    is_ok: bool = False
    is_valid: bool = False
    non_response: str = ""
