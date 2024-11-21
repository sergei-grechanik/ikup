import dataclasses
import datetime
import hashlib
import io
import json
import math
import os
import re
import select
import subprocess
import tempfile
import typing
import zlib
from dataclasses import dataclass, field
from typing import BinaryIO, Callable, List, Literal, Optional, Tuple, Union

import platformdirs
import toml
from PIL import Image, ImageColor

import tupimage
from tupimage import (
    GraphicsCommand,
    GraphicsResponse,
    GraphicsTerminal,
    IDFeatures,
    IDManager,
    IDSubspace,
    ImagePlaceholder,
    ImagePlaceholderMode,
    PlacementData,
    PutCommand,
    TransmissionMedium,
    TransmitCommand,
)


@dataclass(frozen=True)
class ClipRectangle:
    start_col: int = 0
    start_row: int = 0
    end_col: Optional[int] = 0
    end_row: Optional[int] = 0

    @staticmethod
    def whole_window() -> "ClipRectangle":
        return ClipRectangle()

    def __init__(
        self,
        start_col: int = 0,
        start_row: int = 0,
        *,
        end_col: Optional[int] = None,
        end_row: Optional[int] = None,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
    ):
        self.start_col = start_col
        self.start_row = start_row
        if end_col is not None and cols is not None:
            raise ValueError("Cannot specify both end_col and cols")
        if end_row is not None and rows is not None:
            raise ValueError("Cannot specify both end_row and rows")
        if end_col is not None:
            self.end_col = end_col
        elif cols is not None:
            self.end_col = self.start_col + cols
        if end_row is not None:
            self.end_row = end_row
        elif rows is not None:
            self.end_row = self.start_row + rows
        if self.end_col < self.start_col:
            raise ValueError(
                f"end_col ({self.end_col}) must be >= start_col" f" ({self.start_col})"
            )
        if self.end_row < self.start_row:
            raise ValueError(
                f"end_row ({self.end_row}) must be >= start_row" f" ({self.start_row})"
            )
        if self.start_col < 0:
            raise ValueError(f"start_col ({self.start_col}) must be >= 0")
        if self.start_row < 0:
            raise ValueError(f"start_row ({self.start_row}) must be >= 0")


@dataclass(frozen=True)
class NoClipping:
    pass


BackgroundLike = Union[tupimage.AdditionalFormatting, str, int, None]
FinalCursorPos = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


@dataclass
class TupimageConfig:
    # Id allocation options.
    id_subspace: Union[IDSubspace, str, None] = IDSubspace()
    id_color_bits: Literal[0, 8, 24, None] = 24
    id_use_3rd_diacritic: Optional[bool] = True
    max_ids_per_subspace: Optional[int] = 1024
    id_database_dir: Optional[str] = ""

    # Image geometry options.
    cell_size: Union[Tuple[int, int], str, Literal["auto"], None] = "auto"
    default_cell_size: Union[Tuple[int, int], str, None] = (8, 16)
    scale: Optional[float] = 1.0
    max_rows: Union[int, Literal["auto"], None] = "auto"
    max_cols: Union[int, Literal["auto"], None] = "auto"

    # Uploading options
    max_command_size: Optional[int] = select.PIPE_BUF
    num_tmux_layers: Union[int, Literal["auto"], None] = "auto"
    reupload_max_uploads_ago: Optional[int] = 1024
    reupload_max_bytes_ago: Optional[int] = 20 * 1024 * 1024
    reupload_max_seconds_ago: Optional[int] = 3600
    force_reupload: Optional[bool] = False
    supported_formats: Union[List[str], Literal["auto"], None] = "auto"
    upload_method: Union[TransmissionMedium, str, None] = "auto"
    check_response: Optional[bool] = False
    check_response_timeout: Optional[float] = 3.0
    redetect_terminal: Optional[bool] = True
    stream_max_size: Optional[int] = 1 * 1024 * 1024
    file_max_size: Optional[int] = 2 * 1024 * 1024

    # Image display options.
    less_diacritics: Optional[bool] = False
    placeholder_char: Optional[str] = tupimage.PLACEHOLDER_CHAR
    final_cursor_pos: Optional[FinalCursorPos] = "bottom-right"
    background: BackgroundLike = "none"
    clip: Union[ClipRectangle, NoClipping, None] = NoClipping()

    # General options.
    ignore_unknown_attributes: Optional[bool] = False

    def to_toml_string(self) -> str:
        dic = dataclasses.asdict(self)
        if isinstance(self.id_subspace, IDSubspace):
            dic["id_subspace"] = self.id_subspace.to_string()
        if isinstance(self.cell_size, tuple):
            dic["cell_size"] = f"{self.cell_size[0]}x{self.cell_size[1]}"
        if isinstance(self.default_cell_size, tuple):
            dic["default_cell_size"] = (
                f"{self.default_cell_size[0]}x{self.default_cell_size[1]}"
            )
        if isinstance(self.upload_method, TransmissionMedium):
            dic["upload_method"] = self.upload_method.value
        return toml.dumps(dic)

    def override_from_toml_file(self, filename: str):
        with open(filename, "r") as f:
            self.override_from_toml_string(f.read())

    def override_from_toml_string(self, string: str):
        conf = toml.loads(string)
        field_names = set()
        for field in dataclasses.fields(self):
            field_names.add(field.name)
            if field.name in config:
                value = config[field.name]
                setattr(self, field.name, value)
        self.verify_and_normalize()
        if not self.ignore_unknown_attributes:
            for key, value in conf.items():
                if key not in field_names:
                    raise ValueError(f"Unknown config key: {key}")

    def override_from_dict(self, config: dict):
        field_names = {field.name for field in dataclasses.fields(self)}
        for key, value in config.items():
            if key not in field_names:
                raise ValueError(f"Unknown config key: {key}")
            if value is not None:
                setattr(self, key, value)
        self.verify_and_normalize()

    def override_from_kwargs(self, **kwargs):
        self.override_from_dict(kwargs)

    def verify_and_normalize(self):
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if not self._verify_type(value, field.type):
                raise ValueError(
                    f"Field {field.name} has type {field.type}, but got"
                    f" {value} of type {type(value)}"
                )
        if isinstance(self.id_subspace, str):
            self.id_subspace = IDSubspace.from_string(self.id_subspace)
        if isinstance(self.cell_size, str) and self.cell_size != "auto":
            self.cell_size = tupimage.utils.validate_size(self.cell_size)
        if isinstance(self.default_cell_size, str) and self.default_cell_size != "auto":
            self.default_cell_size = tupimage.utils.validate_size(
                self.default_cell_size
            )
        if self.id_database_dir == "":
            self.id_database_dir = platformdirs.user_state_dir("tupimage")
        if isinstance(self.max_cols, int) and self.max_cols <= 0:
            raise ValueError(f"max_cols must be positive: {self.max_cols}")
        if isinstance(self.max_rows, int) and not (0 < self.max_cols <= 256):
            raise ValueError(
                "max_rows must be positive and not greater than 256:"
                f" {self.max_cols}"
            )

    def _verify_type(self, value, type):
        origin = typing.get_origin(type)
        args = typing.get_args(type)
        if origin is Optional:
            if value is None:
                return True
            return self._verify_type(value, args[0])
        elif origin is Union:
            for arg in args:
                if self._verify_type(value, arg):
                    return True
            return False
        elif origin is tuple:
            if not isinstance(value, tuple):
                return False
            if len(value) != len(args):
                return False
            for i in range(len(value)):
                if not self._verify_type(value[i], args[i]):
                    return False
            return True
        elif origin is list:
            if not isinstance(value, list):
                return False
            for subval in value:
                if not self._verify_type(subval, args[0]):
                    return False
            return True
        elif origin is Literal:
            return value in args
        else:
            return isinstance(value, type)


@dataclass
class ImageInstance:
    path: str
    mtime: datetime.datetime
    cols: int
    rows: int
    id: Optional[int] = None
    image: Optional[Image.Image] = None

    def clone_with(self, **kwargs):
        return dataclasses.replace(self, **kwargs)

    @staticmethod
    def build_param_string(cols: int, rows: int) -> str:
        return json.dumps({"cols": cols, "rows": rows})

    def get_param_string(self):
        return self.build_param_string(cols=self.cols, rows=self.rows)

    def is_file_available(self) -> bool:
        return (
            os.path.exists(self.path)
            and datetime.datetime.fromtimestamp(os.path.getmtime(self.path))
            == self.mtime
        )

    def get_placeholder(self) -> ImagePlaceholder:
        return ImagePlaceholder(
            image_id=self.id,
            end_col=self.cols,
            end_row=self.rows,
        )


ImageOrFilename = Union[Image.Image, str]
ImageLike = Union[ImageOrFilename, ImageInstance]


def _config_property(name):
    def getter(obj):
        return getattr(obj._config, name)

    def setter(obj, new_value):
        setattr(obj._config, name, new_value)
        obj._config.verify_and_normalize()

    return property(getter, setter)


class TupimageTerminal:
    def __init__(
        self,
        *,
        tty_filename: Optional[str] = None,
        tty_out: Optional[BinaryIO] = None,
        tty_in: Optional[BinaryIO] = None,
        id_database: Optional[str] = None,
        session_id: Optional[str] = None,
        terminal_id: Optional[str] = None,
        terminal_name: Optional[str] = None,
        config: Optional[Union[TupimageConfig, str]] = None,
        **kwargs,
    ):
        if config is None:
            if os.environ.get("TUPIMAGE_CONFIG") is not None:
                config = os.environ["TUPIMAGE_CONFIG"]
            else:
                config_file = platformdirs.user_config_dir("tupimage") + "/config.toml"
                if os.path.exists(config_file):
                    config = config_file
                else:
                    config = TupimageConfig()
        if isinstance(config, str):
            if config == "DEFAULT":
                config = TupimageConfig()
            else:
                config = TupimageConfig().override_from_toml_file(config)
        config.override_from_dict(kwargs)

        if config.num_tmux_layers == "auto":
            term = os.environ.get("TERM", "")
            if os.environ.get("TMUX") and ("screen" in term or "tmux" in term):
                config.num_tmux_layers = 1
            else:
                config.num_tmux_layers = 0

        self.inside_ssh: bool = (
            os.environ.get("SSH_CLIENT") is not None
            or os.environ.get("SSH_TTY") is not None
            or os.environ.get("SSH_CONNECTION") is not None
        )

        self._config = config

        self.override_terminal_name = terminal_name
        self.override_terminal_id = terminal_id
        self.override_session_id = session_id

        self.detect_terminal()

        self.term = GraphicsTerminal(
            tty_filename=tty_filename,
            tty_out=tty_out,
            tty_in=tty_in,
            max_command_size=config.max_command_size,
            num_tmux_layers=config.num_tmux_layers,
        )

        if id_database is None:
            os.makedirs(os.path.dirname(config.id_database_dir), exist_ok=True)
            id_database = f"{config.id_database_dir}/{self._session_id}.sqlite"

        self.id_manager = IDManager(
            database_file=id_database,
            max_ids_per_subspace=config.max_ids_per_subspace,
        )

    max_cold = _config_property("max_cols")
    max_rows = _config_property("max_rows")
    scale = _config_property("scale")
    id_color_bits = _config_property("id_color_bits")
    id_use_3rd_diacritic = _config_property("id_use_3rd_diacritic")
    id_subspace = _config_property("id_subspace")
    check_response = _config_property("check_response")
    check_response_timeout = _config_property("check_response_timeout")
    upload_method = _config_property("upload_method")
    force_reupload = _config_property("force_reupload")
    less_diacritics = _config_property("less_diacritics")
    redetect_terminal = _config_property("less_diacritics")
    background = _config_property("background")
    final_cursor_pos = _config_property("final_cursor_pos")
    clip = _config_property("clip")
    supported_formats = _config_property("supported_formats")
    stream_max_size = _config_property("stream_max_size")
    file_max_size = _config_property("file_max_size")

    def _tmux_display_message(self, message: str):
        result = subprocess.run(
            ["tmux", "display-message", "-p", message],
            capture_output=True,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip()

    def _remove_bad_chars(self, string: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", string)

    def detect_terminal(self):
        self._terminal_name = self.override_terminal_name
        self._terminal_id = self.override_terminal_id
        self._session_id = self.override_session_id
        if self._config.num_tmux_layers == 0:
            if self._terminal_name is None:
                self._terminal_name = os.environ.get("TERM", "unknown-terminal")
            if self._terminal_id is None:
                self._terminal_id = (
                    self._terminal_name
                    + "-"
                    + os.environ.get("WINDOWID", "unknown-window")
                )
            if self._session_id is None:
                self._session_id = self._terminal_id
        else:
            data = self._tmux_display_message(
                "#{client_termname}||||#{client_pid}||||#{session_id}"
            ).split("||||")
            if self._terminal_name is None:
                self._terminal_name = data[0]
            if self._terminal_id is None:
                self._terminal_id = f"tmux-client-{data[0]}-{data[1]}"
            if self._session_id is None:
                self._session_id = f"tmux-{data[2]}"
        self._terminal_id = self._remove_bad_chars(self._terminal_id)
        self._session_id = self._remove_bad_chars(self._session_id)

    def get_cell_size(self) -> Tuple[int, int]:
        if self._config.cell_size == "auto":
            cell_size = self.term.get_cell_size()
            if cell_size is None:
                return self._config.default_cell_size
            return cell_size
        return self._config.cell_size

    def get_max_cols_and_rows(
        self, *, max_cols: Optional[int] = None, max_rows: Optional[int] = None
    ) -> Tuple[int, int]:
        if max_rows is None and self._config.max_rows != "auto":
            max_rows = self._config.max_rows
        if max_cols is None and self._config.max_cols != "auto":
            max_cols = self._config.max_cols
        if max_rows is None or max_cols is None:
            term_size = self.term.get_size()
            if term_size is None:
                max_cols = max_cols or 256
                max_rows = max_rows or 256
            else:
                max_cols = max_cols or term_size[0]
                max_rows = max_rows or min(term_size[1], 256)
        max_rows = max(1, max_rows)
        max_cols = max(1, max_cols)
        max_rows = min(256, max_rows)
        return max_cols, max_rows

    def get_optimal_cols_and_rows(
        self,
        width: int,
        height: int,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
    ) -> Tuple[int, int]:
        if cols is not None and rows is not None:
            return cols, rows
        if cols is not None and cols <= 0:
            raise ValueError(f"cols must be positive: {cols}")
        if rows is not None and rows <= 0:
            raise ValueError(f"rows must be positive: {rows}")
        max_cols, max_rows = self.get_max_cols_and_rows(
            max_cols=max_cols, max_rows=max_rows
        )
        cell_width, cell_height = self.get_cell_size()
        scale = scale or self._config.scale or 1.0
        width *= scale
        height *= scale

        cols_auto_computed = cols is None
        rows_auto_computed = rows is None

        if cols is None and rows is None:
            # If columns and rows are not specified, compute the optimal values
            # using the cell size.
            cols = math.ceil(width / cell_width)
            rows = math.ceil(height / cell_height)
        elif cols is None:
            # If only one dimension is specified, compute the other one to match
            # the aspect ratio as close as possible.
            cols = math.ceil(rows * cell_height * width / (height * cell_width))
        elif rows is None:
            rows = math.ceil(cols * cell_width * height / (width * cell_height))

        # Make sure that automatically computed rows and columns are within the
        # limits.
        if cols_auto_computed and cols > max_cols:
            cols = max_cols
            rows = math.ceil(cols * cell_width * height / (width * cell_height))
        if rows_auto_computed and rows > max_rows:
            rows = max_rows
            cols = math.ceil(rows * cell_height * width / (height * cell_width))
        # Limit them again, just in case.
        cols = max(1, min(cols, max_cols))
        rows = max(1, min(rows, max_rows))

        return cols, rows

    def build_image_instance(
        self,
        image: ImageOrFilename,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id: Optional[int] = None,
    ) -> ImageInstance:
        path, mtime = self._get_image_path_and_mtime(image)
        if cols is None or rows is None:
            if isinstance(image, str):
                open_image = Image.open(image)
                width, height = open_image.size
                open_image.close()
            else:
                width, height = image.size
            cols, rows = self.get_optimal_cols_and_rows(
                width,
                height,
                cols=cols,
                rows=rows,
                max_cols=max_cols,
                max_rows=max_rows,
                scale=scale,
            )
        return ImageInstance(
            id=id,
            path=path,
            mtime=mtime,
            cols=cols,
            rows=rows,
            image=image if isinstance(image, Image.Image) else None,
        )

    def _get_image_path_and_mtime(
        self, image: ImageOrFilename
    ) -> Tuple[str, datetime.datetime]:
        if isinstance(image, str):
            if image.startswith(":"):
                return image
            if image.startswith("~"):
                image = os.expanduser(image)
            if os.path.exists(image):
                return os.path.abspath(image), datetime.datetime.fromtimestamp(
                    os.path.getmtime(image)
                )
        else:
            md5sum = hashlib.md5(image.tobytes()).hexdigest()
            return f":tupimage:{md5sum}", datetime.datetime.fromtimestamp(0)

    def get_id_features(
        self,
        id_color_bits: Optional[int] = None,
        id_use_3rd_diacritic: Optional[bool] = None,
    ) -> IDFeatures:
        if id_color_bits is None:
            id_color_bits = self._config.id_color_bits
        if id_use_3rd_diacritic is None:
            id_use_3rd_diacritic = self._config.id_use_3rd_diacritic
        return IDFeatures(
            color_bits=id_color_bits,
            use_3rd_diacritic=id_use_3rd_diacritic,
        )

    def get_subspace(
        self, id_subspace: Union[IDSubspace, str, None] = None
    ) -> IDSubspace:
        if id_subspace is None:
            id_subspace = self._config.id_subspace
        if isinstance(id_subspace, str):
            return IDSubspace.from_string(id_subspace)
        return id_subspace

    def assign_id(
        self,
        image: ImageOrFilename,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_color_bits: Optional[int] = None,
        id_use_3rd_diacritic: Optional[bool] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
    ) -> ImageInstance:
        inst = self.build_image_instance(
            image,
            cols=cols,
            rows=rows,
            max_cols=max_cols,
            max_rows=max_rows,
            scale=scale,
        )
        params = inst.get_param_string()
        path = inst.path
        mtime = inst.mtime
        if force_id is not None:
            self.id_manager.set_id(force_id, path, mtime=mtime, params=params)
            inst.id = force_id
            return inst
        id_features = self.get_id_features(
            id_color_bits=id_color_bits,
            id_use_3rd_diacritic=id_use_3rd_diacritic,
        )
        id_subspace = self.get_subspace(id_subspace)
        inst.id = self.id_manager.get_id(
            path, id_features, mtime=mtime, params=params, subspace=id_subspace
        )
        return inst

    def upload(
        self,
        image: ImageLike,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_color_bits: Optional[int] = None,
        id_use_3rd_diacritic: Optional[bool] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
        force_reupload: Optional[bool] = None,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
    ) -> ImageInstance:
        if isinstance(image, ImageInstance):
            inst = image
            if cols is not None or rows is not None:
                raise ValueError(
                    "Cannot specify cols or rows when uploading an ImageInstance"
                )
            if force_id is not None:
                raise ValueError(
                    "Cannot specify force_id when uploading an ImageInstance"
                )
            if inst.id is None:
                raise ValueError("Cannot upload an ImageInstance without an ID")
        else:
            inst = self.assign_id(
                image,
                cols=cols,
                rows=rows,
                max_cols=max_cols,
                max_rows=max_rows,
                scale=scale,
                id_color_bits=id_color_bits,
                id_use_3rd_diacritic=id_use_3rd_diacritic,
                id_subspace=id_subspace,
                force_id=force_id,
            )
        max_uploads_ago = self._config.reupload_max_uploads_ago
        max_bytes_ago = self._config.reupload_max_bytes_ago
        max_time_ago = datetime.timedelta(seconds=self._config.reupload_max_seconds_ago)
        if force_reupload is None:
            force_reupload = self._config.force_reupload
        if self._config.redetect_terminal:
            self.detect_terminal()
        if force_reupload or self.id_manager.needs_uploading(
            inst.id,
            self._terminal_id,
            max_uploads_ago=max_uploads_ago,
            max_bytes_ago=max_bytes_ago,
            max_time_ago=max_time_ago,
        ):
            size = self._upload(
                inst, check_response=check_response, upload_method=upload_method
            )
            self.id_manager.mark_uploaded(inst.id, self._terminal_id, size=size)
        return inst

    def _is_format_supported(self, format: Optional[str]) -> bool:
        if format is None:
            return False
        if self._config.supported_formats == "auto":
            formats = ["png"]
            if self._terminal_name.startswith("st"):
                formats.append("jpeg")
            return format.lower() in formats
        else:
            return format.lower() in [f.lower() for f in self._config.supported_formats]

    def get_max_upload_size(self, upload_method: TransmissionMedium) -> int:
        if upload_method in [
            TransmissionMedium.FILE,
            TransmissionMedium.TEMP_FILE,
        ]:
            return self._config.file_max_size
        elif upload_method == TransmissionMedium.DIRECT:
            return self._config.stream_max_size
        else:
            raise ValueError(f"Unsupported upload method: {upload_method}")

    def _upload(
        self,
        inst: ImageInstance,
        *,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
    ) -> int:
        if check_response is None:
            check_response = self._config.check_response
        if upload_method is None:
            upload_method = self._config.upload_method
        if upload_method == "auto":
            if self.inside_ssh:
                upload_method = TransmissionMedium.DIRECT
            else:
                upload_method = TransmissionMedium.FILE
        if isinstance(upload_method, str):
            upload_method = TransmissionMedium.from_string(upload_method)
        if upload_method not in [
            TransmissionMedium.FILE,
            TransmissionMedium.DIRECT,
        ]:
            raise ValueError(f"Unsupported upload method: {upload_method}")

        if check_response:
            raise NotImplementedError("Checking the response is not yet implemented")

        max_upload_size = self.get_max_upload_size(upload_method)

        if inst.image is None:
            if not inst.is_file_available():
                raise FileNotFoundError(
                    f"Image file {inst.path} with mtime {inst.mtime} does not"
                    " exist or was overwritten"
                )
            image_object = Image.open(inst.path)
            if self._is_format_supported(image_object.format):
                size = os.path.getsize(inst.path)
                if size <= max_upload_size:
                    image_object.close()
                    self._transmit_file(inst.path, inst, upload_method)
                    return size
        else:
            image_object = inst.image

        bits = 24 if image_object.mode == "RGB" else 32
        width, height = image_object.size
        image_bytes = width * height * (bits / 8)
        if image_bytes > max_upload_size:
            ratio = math.sqrt(max_upload_size / image_bytes)
            width = max(1, math.floor(width * ratio))
            height = max(1, math.floor(height * ratio))
            image_object = image_object.resize((width, height))

        if upload_method == TransmissionMedium.FILE:
            with tempfile.NamedTemporaryFile(
                "wb", delete=False, prefix="tty-graphics-protocol-"
            ) as f:
                image_object.save(
                    f,
                    format=(
                        image_object.format
                        if self._is_format_supported(image_object.format)
                        else "PNG"
                    ),
                )
                f.flush()
                size = f.tell()
                f.close()
                self._transmit_file(f.name, inst, TransmissionMedium.TEMP_FILE)
                return size
        elif upload_method == TransmissionMedium.DIRECT:
            bytesio = io.BytesIO()
            image_object.save(bytesio, format="PNG")
            size = bytesio.tell()
            self.term.send_command(
                TransmitCommand(
                    image_id=inst.id,
                    medium=TransmissionMedium.DIRECT,
                    quiet=tupimage.Quietness.QUIET_ALWAYS,
                    format=tupimage.Format.PNG,
                    pix_width=image_object.width,
                    pix_height=image_object.height,
                )
                .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                .set_data(bytesio)
            )
            return size

    def _transmit_file(
        self,
        filename: str,
        inst: ImageInstance,
        upload_method: TransmissionMedium,
    ):
        if (
            upload_method == TransmissionMedium.FILE
            or upload_method == TransmissionMedium.TEMP_FILE
        ):
            self.term.send_command(
                TransmitCommand(
                    image_id=inst.id,
                    medium=upload_method,
                    quiet=tupimage.Quietness.QUIET_ALWAYS,
                    format=tupimage.Format.PNG,
                )
                .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                .set_filename(filename)
            )
        elif upload_method == TransmissionMedium.DIRECT:
            with open(inst.path, "rb") as f:
                self.term.send_command(
                    TransmitCommand(
                        image_id=inst.id,
                        medium=TransmissionMedium.DIRECT,
                        quiet=tupimage.Quietness.QUIET_ALWAYS,
                        format=tupimage.Format.PNG,
                    )
                    .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                    .set_data(f)
                )

    def upload_and_display(
        self,
        image: ImageLike,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_color_bits: Optional[int] = None,
        id_use_3rd_diacritic: Optional[bool] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
        force_reupload: Optional[bool] = None,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
        less_diacritics: Optional[bool] = None,
        background: Optional[Callable[[int, int], bytes]] = None,
        abs_pos: Optional[Tuple[int, int]] = None,
        clip: Union[ClipRectangle, NoClipping] = None,
        final_cursor_pos: Optional[FinalCursorPos] = None,
    ) -> ImagePlaceholder:
        inst = self.upload(
            image,
            cols=cols,
            rows=rows,
            max_cols=max_cols,
            max_rows=max_rows,
            scale=scale,
            id_color_bits=id_color_bits,
            id_use_3rd_diacritic=id_use_3rd_diacritic,
            id_subspace=id_subspace,
            force_id=force_id,
            force_reupload=force_reupload,
            check_response=check_response,
            upload_method=upload_method,
        )
        return self.display(
            inst,
            less_diacritics=less_diacritics,
            background=background,
            abs_pos=abs_pos,
            clip=clip,
            final_cursor_pos=final_cursor_pos,
        )

    def get_image_placeholder_mode(
        self,
        id: Union[int, ImageInstance, ImagePlaceholder],
        less_diacritics: Optional[bool] = None,
    ) -> ImagePlaceholderMode:
        if isinstance(id, ImagePlaceholder):
            id = id.image_id
        if isinstance(id, ImageInstance):
            id = id.id
        if less_diacritics is None:
            less_diacritics = self._config.less_diacritics
        return ImagePlaceholderMode(
            allow_256colors_for_image_id=True,
            allow_256colors_for_placement_id=False,
            skip_placement_id_if_zero=True,
            first_column_diacritic_level=tupimage.DiacriticLevel.ROW_COLUMN_ID4THBYTE_IF_NONZERO,
            other_columns_diacritic_level=(
                tupimage.DiacriticLevel.NONE
                if less_diacritics
                else tupimage.DiacriticLevel.ROW_COLUMN_ID4THBYTE_IF_NONZERO
            ),
            placeholder_char=self._config.placeholder_char,
        )

    def get_formatting(
        self, background: BackgroundLike
    ) -> tupimage.AdditionalFormatting:
        if background is None:
            background = self._config.background
        if isinstance(background, str):
            if background.lower() == "none":
                return None
            else:
                rgb = ImageColor.getrgb(background)
                return b"\033[48;2;%d;%d;%dm" % rgb
        if isinstance(background, int):
            return b"\033[48;5;%dm" % background
        return background

    def display(
        self,
        id: Union[int, ImageInstance, ImagePlaceholder],
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        less_diacritics: Optional[bool] = None,
        background: BackgroundLike = None,
        abs_pos: Optional[Tuple[int, int]] = None,
        clip: Union[ClipRectangle, NoClipping] = None,
        final_cursor_pos: Optional[FinalCursorPos] = None,
    ) -> ImagePlaceholder:
        if isinstance(id, ImagePlaceholder):
            if cols is not None or rows is not None:
                raise ValueError(
                    "Cannot specify cols or rows when displaying an"
                    " ImagePlaceholder, use clone_with to override rows and"
                    " cols"
                )
        elif isinstance(id, ImageInstance):
            cols = cols or id.cols
            rows = rows or id.rows
            id = id.id

        if isinstance(id, int):
            id = ImagePlaceholder(image_id=id, end_col=cols, end_row=rows)

        mode = self.get_image_placeholder_mode(id, less_diacritics=less_diacritics)

        formatting = self.get_formatting(background)

        if clip is None:
            clip = self._config.clip

        if clip == NoClipping():
            if abs_pos is None:
                self.term.print_placeholder(
                    placeholder=id, mode=mode, formatting=formatting
                )
            else:
                if abs_pos[0] < 0 or abs_pos[1] < 0:
                    raise ValueError(
                        "Absolute position must be non-negative (unless"
                        f" clipping is enabled): {abs_pos}"
                    )
                self.term.print_placeholder(
                    placeholder=id,
                    pos=abs_pos,
                    mode=mode,
                    formatting=formatting,
                )
            self._move_cursor_to_final_position(
                id.end_col - id.start_col,
                id.end_row - id.start_row,
                final_cursor_pos,
            )
            return id

        if abs_pos is None:
            abs_pos = self.term.get_cursor_position()
        if clip.end_col is None or clip.end_row is None:
            term_cols, term_rows = self.term.get_size()
            clip = clip.clone_with(
                end_col=clip.end_col or term_cols,
                end_row=clip.end_row or term_rows,
            )

        pos_col = abs_pos[0]
        pos_row = abs_pos[1]
        start_col = id.start_col
        start_row = id.start_row
        end_col = id.end_col
        end_row = id.end_row

        if pos_col < clip.start_col:
            start_col += clip.start_col - pos_col
            pos_col = clip.start_col
        if pos_row < clip.start_row:
            start_row += clip.start_row - pos_row
            pos_row = clip.start_row
        if pos_col + end_col - start_col > clip.end_col:
            end_col = clip.end_col - pos_col + start_col
        if pos_row + end_row - start_row > clip.end_row:
            end_row = clip.end_row - pos_row + start_row

        if end_col <= start_col or end_row <= start_row:
            return id

        self.term.print_placeholder(
            image_id=id.id,
            start_col=start_col,
            start_row=start_row,
            end_col=end_col,
            end_row=end_row,
            pos=(pos_col, pos_row),
            mode=mode,
            formatting=formatting,
        )
        self._move_cursor_to_final_position(
            end_col - start_col, end_row - start_row, final_cursor_pos
        )
        return id

    def _move_cursor_to_final_position(
        self, cols: int, rows: int, final_cursor_pos: Optional[FinalCursorPos]
    ):
        if final_cursor_pos is None:
            final_cursor_pos = self._config.final_cursor_pos

        if final_cursor_pos == "bottom-right":
            return
        elif final_cursor_pos == "top-right":
            self.term.move_cursor(up=rows - 1)
        elif final_cursor_pos == "top-left":
            self.term.move_cursor(up=rows - 1, left=cols)
        elif final_cursor_pos == "bottom-left":
            self.term.move_cursor(left=cols)
            # This sequence moves the cursor down, maybe creating a newline.
            self.term.write(b"\033D")
        else:
            raise ValueError(f"Invalid final_cursor_pos: {final_cursor_pos}")
