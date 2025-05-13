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
import random
from dataclasses import dataclass, field
from typing import (
    Any,
    BinaryIO,
    Callable,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    TYPE_CHECKING,
)

import platformdirs
import toml

import tupimage
from tupimage.id_manager import ImageInfo, UploadInfo
import tupimage.utils
from tupimage import (
    GraphicsCommand,
    GraphicsResponse,
    GraphicsTerminal,
    IDSpace,
    IDManager,
    IDSubspace,
    ImagePlaceholder,
    ImagePlaceholderMode,
    PlacementData,
    PutCommand,
    TransmissionMedium,
    TransmitCommand,
)

# PIL is expensive to import, we import is only when needed or when type checking.
if TYPE_CHECKING:
    from PIL import Image

BackgroundLike = Union[tupimage.AdditionalFormatting, str, int, None]
FinalCursorPos = Literal["top-left", "top-right", "bottom-left", "bottom-right"]


@dataclass
class TupimageConfig:
    # Id allocation options.
    id_space: IDSpace = IDSpace()
    id_subspace: IDSubspace = IDSubspace()
    max_ids_per_subspace: int = 1024
    id_database_dir: str = platformdirs.user_state_dir("tupimage")

    # Image geometry options.
    cell_size: Union[Tuple[int, int], Literal["auto"]] = "auto"
    default_cell_size: Tuple[int, int] = (8, 16)
    scale: float = 1.0
    global_scale: float = 1.0
    max_rows: Union[int, Literal["auto"]] = "auto"
    max_cols: Union[int, Literal["auto"]] = "auto"

    # Uploading options
    max_command_size: int = select.PIPE_BUF
    num_tmux_layers: Union[int, Literal["auto"]] = "auto"
    reupload_max_uploads_ago: int = 1024
    reupload_max_bytes_ago: int = 20 * 1024 * 1024
    reupload_max_seconds_ago: int = 3600
    force_upload: bool = False
    supported_formats: Union[List[str], Literal["auto"]] = "auto"
    upload_method: Union[TransmissionMedium, Literal["auto"]] = "auto"
    check_response: bool = False
    check_response_timeout: float = 3.0
    redetect_terminal: bool = True
    stream_max_size: int = 2 * 1024 * 1024
    file_max_size: int = 10 * 1024 * 1024

    # Image display options.
    fewer_diacritics: bool = False
    placeholder_char: str = tupimage.PLACEHOLDER_CHAR
    background: BackgroundLike = "none"

    # Terminal identification options.
    terminal_name: str = ""
    terminal_id: str = ""
    session_id: str = ""

    # General options.
    ignore_unknown_attributes: bool = False

    # Cleanup options.
    max_db_age_days: int = 7
    max_num_ids: int = 4 * 1024
    cleanup_probability: float = 0.01

    # Parallel upload options.
    upload_progress_update_interval: float = 0.5
    upload_stall_timeout: float = 2.0

    def __post_init__(self):
        self._provenance = {}
        self._current_provenance = None

    def get_provenance(self, name: str) -> str:
        provenance = self._provenance.get(name)
        if provenance is not None:
            return provenance
        field_obj = TupimageConfig.__dataclass_fields__[name]
        if getattr(self, name) == field_obj.default:
            return "default"
        return "set in code"

    def __setattr__(self, name: str, value: Any):
        super().__setattr__(name, value)
        if name[0] != "_":
            if hasattr(self, "_current_provenance"):
                self._provenance[name] = self._current_provenance

    def to_toml_string(
        self, with_provenance: bool = False, skip_default: bool = False
    ) -> str:
        dic = dataclasses.asdict(self)
        if isinstance(self.id_subspace, IDSubspace):
            dic["id_subspace"] = str(self.id_subspace)
        if isinstance(self.id_space, IDSpace):
            dic["id_space"] = str(self.id_space)
        if isinstance(self.cell_size, tuple):
            dic["cell_size"] = f"{self.cell_size[0]}x{self.cell_size[1]}"
        if isinstance(self.default_cell_size, tuple):
            dic["default_cell_size"] = (
                f"{self.default_cell_size[0]}x{self.default_cell_size[1]}"
            )
        if isinstance(self.upload_method, TransmissionMedium):
            dic["upload_method"] = self.upload_method.value

        # First collect all non-default lines if skipping
        kv_lines = []
        provenances = []
        for name, value in dic.items():
            provenance = self.get_provenance(name)
            if skip_default and provenance == "default":
                continue
            kv_lines.append(toml.dumps({name: value}).strip())
            provenances.append(provenance)

        if not with_provenance:
            return "\n".join(kv_lines) + "\n"

        # Calculate max line length for alignment (up to 32 chars)
        maxlen = min(32, max(len(l) for l in kv_lines)) if kv_lines else 0
        lines = []
        for l, prov in zip(kv_lines, provenances):
            lines.append(f"{l}{' ' * (maxlen - len(l))}  # {prov}")

        return "\n".join(lines) + "\n"

    def override_from_toml_file(self, filename: str, provenance: Optional[str] = None):
        if provenance is None:
            provenance = f"set from file {os.path.abspath(filename)}"
        with open(filename, "r") as f:
            self.override_from_toml_string(f.read(), provenance=provenance)

    def override_from_toml_string(self, string: str, provenance: Optional[str] = None):
        if provenance is None:
            provenance = "set from toml string"
        self._current_provenance = provenance
        config = toml.loads(string)
        unknown_keys = set()
        for key, value in config.items():
            if key not in TupimageConfig.__annotations__:
                unknown_keys.add(key)
                continue
            normalized = TupimageConfig.validate_and_normalize(key, value, provenance)
            setattr(self, key, normalized)
        self._current_provenance = None
        if unknown_keys and not self.ignore_unknown_attributes:
            raise KeyError(f"Unknown config keys: {', '.join(unknown_keys)}")

    def override_from_dict(self, config: dict, provenance: Optional[str] = None):
        if provenance is None:
            provenance = config.get("provenance", "set from dict")
        self._current_provenance = provenance
        for key, value in config.items():
            if key == "provenance":
                continue
            if value is not None:
                normalized = TupimageConfig.validate_and_normalize(
                    key, value, provenance
                )
                setattr(self, key, normalized)
        self._current_provenance = None

    def override_from_env(self):
        for name in TupimageConfig.__annotations__:
            env_var_name = f"TUPIMAGE_{name.upper()}"
            env_value = os.environ.get(env_var_name)
            if env_value is not None:
                self._current_provenance = f"set via {env_var_name}"
                normalized = TupimageConfig.validate_and_normalize(
                    name, env_value, self._current_provenance
                )
                setattr(self, name, normalized)
        self._current_provenance = None

    def override(self, provenance: Optional[str] = None, **kwargs):
        self.override_from_dict(kwargs, provenance=provenance)

    @staticmethod
    def validate_and_normalize(
        name: str, value: Any, provenance: Optional[str] = None
    ) -> Any:
        if name not in TupimageConfig.__annotations__:
            raise KeyError(f"Unknown config key: {name}")
        field_type = TupimageConfig.__annotations__[name]

        # Normalize values specified as strings.
        if isinstance(value, str) and value != "auto":
            if field_type is IDSubspace:
                value = IDSubspace.from_string(value)
            if field_type is IDSpace:
                value = IDSpace.from_string(value)
            if name == "cell_size" or name == "default_cell_size":
                value = tupimage.utils.validate_size(value)
            if name == "id_database_dir" and value == "":
                value = platformdirs.user_state_dir("tupimage")
            if name == "upload_method":
                value = TransmissionMedium.from_string(value)
            if name in [
                "max_rows",
                "max_cols",
                "num_tmux_layers",
                "max_db_age_days",
                "max_num_ids",
            ]:
                value = int(value)
            if name in [
                "scale",
                "global_scale",
                "cleanup_probability",
                "upload_progress_update_interval",
                "upload_stall_timeout",
            ]:
                value = float(value)
            if name == "supported_formats":
                value = re.split(r"[, ]+", value)

        provenance = f"({provenance})" if provenance else "(set in code)"

        # Verify the type.
        if not TupimageConfig._verify_type(value, field_type):
            raise ValueError(
                f"Option '{name}' has type {field_type}, but got"
                f" '{value}' of type {type(value)} {provenance}"
            )

        # Verify additional constraints.
        if isinstance(value, int):
            if name == "max_cols" and value <= 0:
                raise ValueError(f"max_cols must be positive: {value} {provenance}")
            if name == "max_rows" and not (0 < value <= 256):
                raise ValueError(
                    "max_rows must be positive and not greater than 256:"
                    f" {value} {provenance}"
                )

        return value

    @staticmethod
    def _verify_type(value, type):
        origin = typing.get_origin(type)
        args = typing.get_args(type)
        if origin is Optional:
            if value is None:
                return True
            return TupimageConfig._verify_type(value, args[0])
        elif origin is Union:
            for arg in args:
                if TupimageConfig._verify_type(value, arg):
                    return True
            return False
        elif origin is tuple:
            if not isinstance(value, tuple):
                return False
            if len(value) != len(args):
                return False
            for i in range(len(value)):
                if not TupimageConfig._verify_type(value[i], args[i]):
                    return False
            return True
        elif origin is list:
            if not isinstance(value, list):
                return False
            for subval in value:
                if not TupimageConfig._verify_type(subval, args[0]):
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
    id_atime: datetime.datetime
    cols: int
    rows: int
    id: int
    image: Optional["Image.Image"] = None

    def clone_with(self, **kwargs):
        return dataclasses.replace(self, **kwargs)

    @staticmethod
    def from_info(info: ImageInfo) -> Optional["ImageInstance"]:
        try:
            params = json.loads(info.description)
            return ImageInstance(
                path=params.get("path"),
                mtime=datetime.datetime.fromtimestamp(float(params.get("mtime"))),
                cols=int(params.get("cols")),
                rows=int(params.get("rows")),
                id=info.id,
                id_atime=info.atime,
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    @staticmethod
    def build_descr_string(
        path: str, mtime: datetime.datetime, cols: int, rows: int
    ) -> str:
        return json.dumps(
            {"path": path, "mtime": mtime.timestamp(), "cols": cols, "rows": rows}
        )

    def get_description(self):
        return self.build_descr_string(
            path=self.path, mtime=self.mtime, cols=self.cols, rows=self.rows
        )

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


ImageOrFilename = Union["PIL.Image.Image", str]


def _config_property(name: str):
    assert name in TupimageConfig.__annotations__

    def getter(obj: "TupimageTerminal"):
        return getattr(obj._config, name)

    def setter(obj: "TupimageTerminal", new_value):
        obj._config.override_from_dict({name: new_value})

    return property(getter, setter)


class TupimageTerminal:
    def __init__(
        self,
        *,
        out_command: Union[BinaryIO, str, None] = None,
        out_display: Union[BinaryIO, str, None] = None,
        out_status: Union[BinaryIO, str, None] = None,
        in_response: Union[BinaryIO, str, None] = None,
        id_database: Optional[str] = None,
        final_cursor_pos: FinalCursorPos = "bottom-left",
        config: Optional[Union[TupimageConfig, str]] = None,
        config_overrides: dict = {},
        **kwargs,
    ):
        self._config_file: str = "DEFAULT"
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
            self._config_file: str = config
            if config == "DEFAULT" or config == "":
                config = TupimageConfig()
            else:
                config = TupimageConfig()
                config.override_from_toml_file(self._config_file)
        assert config is not None
        config.override_from_env()
        config.override_from_dict(kwargs)
        config.override_from_dict(config_overrides)

        self.final_cursor_pos: FinalCursorPos = final_cursor_pos

        if config.num_tmux_layers == "auto":
            config._current_provenance = (
                f"expanded from 'auto' ({config.get_provenance('num_tmux_layers')})"
            )
            term = os.environ.get("TERM", "")
            if os.environ.get("TMUX") and ("screen" in term or "tmux" in term):
                config.num_tmux_layers = 1
            else:
                config.num_tmux_layers = 0
            config._current_provenance = None

        self.inside_ssh: bool = (
            os.environ.get("SSH_CLIENT") is not None
            or os.environ.get("SSH_TTY") is not None
            or os.environ.get("SSH_CONNECTION") is not None
        )

        self._config: TupimageConfig = config

        self.detect_terminal()

        self.term = GraphicsTerminal(
            out_command=out_command,
            out_display=out_display,
            in_response=in_response,
            in_userinput=None,
            max_command_size=config.max_command_size,
            num_tmux_layers=config.num_tmux_layers,
        )

        if id_database is None:
            os.makedirs(os.path.dirname(config.id_database_dir), exist_ok=True)
            id_database = f"{config.id_database_dir}/{self._session_id}.db"

        self.id_manager = IDManager(
            database_file=id_database,
            max_ids_per_subspace=config.max_ids_per_subspace,
        )

    max_cols = _config_property("max_cols")
    max_rows = _config_property("max_rows")
    scale = _config_property("scale")
    global_scale = _config_property("global_scale")
    id_space = _config_property("id_space")
    id_subspace = _config_property("id_subspace")
    check_response = _config_property("check_response")
    check_response_timeout = _config_property("check_response_timeout")
    upload_method = _config_property("upload_method")
    force_upload = _config_property("force_upload")
    fewer_diacritics = _config_property("fewer_diacritics")
    redetect_terminal = _config_property("redetect_terminal")
    background = _config_property("background")
    supported_formats = _config_property("supported_formats")
    stream_max_size = _config_property("stream_max_size")
    file_max_size = _config_property("file_max_size")
    num_tmux_layers = _config_property("num_tmux_layers")
    max_db_age_days = _config_property("max_db_age_days")
    max_num_ids = _config_property("max_num_ids")
    cleanup_probability = _config_property("cleanup_probability")
    upload_progress_update_interval = _config_property(
        "upload_progress_update_interval"
    )
    upload_stall_timeout = _config_property("upload_stall_timeout")

    def _tmux_display_message(self, message: str):
        result = subprocess.run(
            ["tmux", "display-message", "-p", message],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _remove_bad_chars(self, string: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", string)

    def detect_terminal(self):
        self._terminal_name = self._config.terminal_name
        self._terminal_id = self._config.terminal_id
        self._session_id = self._config.session_id
        if self._config.num_tmux_layers == 0:
            if not self._terminal_name:
                self._terminal_name = os.environ.get("TERM", "unknown-terminal")
            if not self._terminal_id:
                self._terminal_id = (
                    self._terminal_name
                    + "-"
                    + os.environ.get("WINDOWID", "unknown-window")
                )
            if not self._session_id:
                self._session_id = self._terminal_id
        else:
            data = self._tmux_display_message(
                "#{client_termname}||||#{client_pid}||||#{pid}_#{session_id}"
            ).split("||||")
            if not self._terminal_name:
                self._terminal_name = data[0]
            if not self._terminal_id:
                self._terminal_id = f"tmux-client-{data[0]}-{data[1]}"
            if not self._session_id:
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
        width: float,
        height: float,
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
        # Combine global and local scale factors
        local_scale = scale or self._config.scale
        effective_scale = self._config.global_scale * (
            local_scale if local_scale is not None else 1.0
        )
        width *= effective_scale
        height *= effective_scale

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
        id: int,
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_atime: Optional[datetime.datetime] = None,
    ) -> ImageInstance:
        path, mtime = self._get_image_path_and_mtime(image)
        if cols is None or rows is None:
            if isinstance(image, str):
                from PIL import Image

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
        if id_atime is None:
            id_atime = datetime.datetime.now()
        # Attach the image object if it is not a path.
        image_obj = None
        if not isinstance(image, str) and not isinstance(image, bytes):
            image_obj = image
        return ImageInstance(
            id=id,
            path=path,
            mtime=mtime,
            id_atime=id_atime,
            cols=cols,
            rows=rows,
            image=image_obj,
        )

    def _get_image_path_and_mtime(
        self, image: ImageOrFilename
    ) -> Tuple[str, datetime.datetime]:
        if isinstance(image, str):
            if image.startswith(":"):
                return image, datetime.datetime.fromtimestamp(0)
            if image.startswith("~"):
                image = os.expanduser(image)
            if os.path.exists(image):
                return os.path.abspath(image), datetime.datetime.fromtimestamp(
                    os.path.getmtime(image)
                )
            return image, datetime.datetime.fromtimestamp(0)
        else:
            md5sum = hashlib.md5(image.tobytes()).hexdigest()
            return f":tupimage:{md5sum}", datetime.datetime.fromtimestamp(0)

    def get_id_space(
        self,
        id_space: Union[IDSpace, str, int, None] = None,
    ) -> IDSpace:
        if id_space is None:
            id_space = self._config.id_space
        if isinstance(id_space, IDSpace):
            return id_space
        return IDSpace.from_string(str(id_space))

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
        id_space: Union[IDSpace, str, int, None] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
        update_atime: bool = True,
    ) -> ImageInstance:
        if random.random() < self._config.cleanup_probability:
            self.cleanup_old_databases()
            self.cleanup_current_database()
        inst = self.build_image_instance(
            image,
            id=0,
            cols=cols,
            rows=rows,
            max_cols=max_cols,
            max_rows=max_rows,
            scale=scale,
        )
        descr = inst.get_description()
        if force_id is not None:
            self.id_manager.del_id(force_id)
            self.id_manager.set_id(force_id, descr)
            inst.id = force_id
            return inst
        id_space = self.get_id_space(id_space)
        id_subspace = self.get_subspace(id_subspace)
        inst.id = self.id_manager.get_id(
            descr, id_space, subspace=id_subspace, update_atime=update_atime
        )
        return inst

    def get_image_instance(self, id: int) -> Optional[ImageInstance]:
        info = self.id_manager.get_info(id)
        if info is None:
            return None
        return ImageInstance.from_info(info)

    def needs_uploading(
        self,
        id: int,
        terminal_id: Optional[str] = None,
    ) -> bool:
        max_uploads_ago = self._config.reupload_max_uploads_ago
        max_bytes_ago = self._config.reupload_max_bytes_ago
        max_time_ago = datetime.timedelta(seconds=self._config.reupload_max_seconds_ago)
        if terminal_id is None:
            terminal_id = self._terminal_id
        if terminal_id is None:
            return True
        return self.id_manager.needs_uploading(
            id,
            terminal_id,
            max_uploads_ago=max_uploads_ago,
            max_bytes_ago=max_bytes_ago,
            max_time_ago=max_time_ago,
        )

    def upload(
        self,
        image: Union[ImageOrFilename, ImageInstance],
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_space: Union[IDSpace, str, int, None] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
        force_upload: Optional[bool] = None,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
        update_atime: bool = True,
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
                id_space=id_space,
                id_subspace=id_subspace,
                force_id=force_id,
                update_atime=update_atime,
            )
        if force_upload is None:
            force_upload = self._config.force_upload
        if self._config.redetect_terminal:
            self.detect_terminal()
        if force_upload or self.needs_uploading(inst.id):
            self._upload(
                inst,
                check_response=check_response,
                upload_method=upload_method,
                force_upload=force_upload,
            )
        return inst

    def get_supported_formats(self) -> List[str]:
        if self._config.supported_formats == "auto":
            formats = ["png"]
            if self._terminal_name.startswith("st"):
                formats.append("jpeg")
        else:
            formats = self._config.supported_formats
        return [f.lower() for f in formats]

    def _is_format_supported(self, format: Optional[str]) -> bool:
        return format is not None and format.lower() in self.get_supported_formats()

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

    def get_upload_method(self) -> TransmissionMedium:
        upload_method = self._config.upload_method
        if upload_method == "auto" or upload_method is None:
            if self.inside_ssh:
                upload_method = TransmissionMedium.DIRECT
            else:
                upload_method = TransmissionMedium.FILE
        if isinstance(upload_method, str):
            upload_method = TransmissionMedium.from_string(upload_method)
        return upload_method

    def _abort_transmission(self, id: int):
        """Send a final direct transmission command (`m=0`) to abort any existing
        transmission for this ID."""
        self.term.send_command(
            TransmitCommand(
                image_id=id,
                more=False,
                quiet=tupimage.Quietness.QUIET_ALWAYS,
            )
        )

    def _upload(
        self,
        inst: ImageInstance,
        *,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
        force_upload: bool = False,
    ):
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
            from PIL import Image

            image_object = Image.open(inst.path)
            if self._is_format_supported(image_object.format):
                size = os.path.getsize(inst.path)
                if size <= max_upload_size:
                    image_object.close()
                    self._transmit_file_or_bytes(
                        inst.path, inst, size, upload_method, force_upload=force_upload
                    )
                    return
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
                self._transmit_file_or_bytes(
                    f.name,
                    inst,
                    size,
                    TransmissionMedium.TEMP_FILE,
                    force_upload=force_upload,
                )
                return
        elif upload_method == TransmissionMedium.DIRECT:
            bytesio = io.BytesIO()
            image_object.save(bytesio, format="PNG")
            size = bytesio.tell()
            self._transmit_file_or_bytes(
                bytesio,
                inst,
                size,
                upload_method,
                pix_width=image_object.width,
                pix_height=image_object.height,
                force_upload=force_upload,
            )
            return

    def _transmit_file_or_bytes(
        self,
        filename_or_object: Union[str, io.BytesIO],
        inst: ImageInstance,
        size: int,
        upload_method: TransmissionMedium,
        pix_width: Optional[int] = None,
        pix_height: Optional[int] = None,
        force_upload: bool = False,
    ):
        def upload_fn(info: UploadInfo):
            if (
                upload_method == TransmissionMedium.FILE
                or upload_method == TransmissionMedium.TEMP_FILE
            ):
                assert isinstance(filename_or_object, str)
                self.term.send_command(
                    TransmitCommand(
                        image_id=inst.id,
                        medium=upload_method,
                        quiet=tupimage.Quietness.QUIET_ALWAYS,
                        format=tupimage.Format.PNG,
                    )
                    .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                    .set_filename(filename_or_object)
                )
            elif upload_method == TransmissionMedium.DIRECT:
                self._abort_transmission(inst.id)
                if isinstance(filename_or_object, str):
                    with open(filename_or_object, "rb") as f:
                        self.term.send_command(
                            TransmitCommand(
                                image_id=inst.id,
                                medium=TransmissionMedium.DIRECT,
                                quiet=tupimage.Quietness.QUIET_ALWAYS,
                                format=tupimage.Format.PNG,
                            )
                            .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                            .set_data(f),
                            callback=lambda cmd: self._report_progress(cmd, info),
                        )
                else:
                    assert pix_width is not None
                    assert pix_height is not None
                    self.term.send_command(
                        TransmitCommand(
                            image_id=inst.id,
                            medium=TransmissionMedium.DIRECT,
                            quiet=tupimage.Quietness.QUIET_ALWAYS,
                            format=tupimage.Format.PNG,
                            pix_width=pix_width,
                            pix_height=pix_height,
                        )
                        .set_placement(virtual=True, rows=inst.rows, cols=inst.cols)
                        .set_data(filename_or_object),
                        callback=lambda cmd: self._report_progress(cmd, info),
                    )

        # Now call the uploading function wrapped in a retry loop that will make sure we
        # don't interfere with uploads that are already in progress.
        self.id_manager.retry_uploading_until_success(
            inst.id,
            self._terminal_id,
            fn=upload_fn,
            size=size,
            description=inst.get_description(),
            stall_timeout=self._config.upload_stall_timeout,
            force_upload=force_upload,
        )

    def _report_progress(self, cmd: GraphicsCommand, info: UploadInfo):
        now = datetime.datetime.now()
        if now - info.upload_time > datetime.timedelta(
            seconds=self._config.upload_progress_update_interval
        ):
            info.upload_time = now
            self.id_manager.report_upload(info, upload_time=now)

    def upload_and_display(
        self,
        image: Union[ImageOrFilename, ImageInstance],
        *,
        cols: Optional[int] = None,
        rows: Optional[int] = None,
        max_cols: Optional[int] = None,
        max_rows: Optional[int] = None,
        scale: Optional[float] = None,
        id_space: Union[IDSpace, str, int, None] = None,
        id_subspace: Union[IDSubspace, str, None] = None,
        force_id: Optional[int] = None,
        force_upload: Optional[bool] = None,
        check_response: Optional[bool] = None,
        upload_method: Union[TransmissionMedium, str, None] = None,
        fewer_diacritics: Optional[bool] = None,
        background: Optional[Callable[[int, int], bytes]] = None,
        abs_pos: Optional[Tuple[int, int]] = None,
        final_cursor_pos: Optional[FinalCursorPos] = None,
        use_line_feeds: bool = False,
    ) -> ImagePlaceholder:
        inst = self.upload(
            image,
            cols=cols,
            rows=rows,
            max_cols=max_cols,
            max_rows=max_rows,
            scale=scale,
            id_space=id_space,
            id_subspace=id_subspace,
            force_id=force_id,
            force_upload=force_upload,
            check_response=check_response,
            upload_method=upload_method,
        )
        return self.display_only(
            inst,
            fewer_diacritics=fewer_diacritics,
            background=background,
            abs_pos=abs_pos,
            final_cursor_pos=final_cursor_pos,
            use_line_feeds=use_line_feeds,
        )

    def get_image_placeholder_mode(
        self,
        id: Union[int, ImageInstance, ImagePlaceholder],
        *,
        fewer_diacritics: Optional[bool] = None,
    ) -> ImagePlaceholderMode:
        if isinstance(id, ImagePlaceholder):
            id = id.image_id
        if isinstance(id, ImageInstance):
            id = id.id
        if fewer_diacritics is None:
            fewer_diacritics = self._config.fewer_diacritics
        return ImagePlaceholderMode(
            allow_256colors_for_image_id=True,
            allow_256colors_for_placement_id=False,
            skip_placement_id_if_zero=True,
            first_column_diacritic_level=tupimage.DiacriticLevel.ROW_COLUMN_ID4THBYTE_IF_NONZERO,
            other_columns_diacritic_level=(
                tupimage.DiacriticLevel.NONE
                if fewer_diacritics
                else tupimage.DiacriticLevel.ROW_COLUMN_ID4THBYTE_IF_NONZERO
            ),
            placeholder_char=self._config.placeholder_char,
        )

    def get_formatting(
        self, background: Optional[BackgroundLike]
    ) -> tupimage.AdditionalFormatting:
        if background is None:
            background = self._config.background
        if isinstance(background, str):
            if background.lower() == "none":
                return None
            else:
                from PIL import ImageColor

                rgb = ImageColor.getrgb(background)
                return b"\033[48;2;%d;%d;%dm" % rgb
        if isinstance(background, int):
            return b"\033[48;5;%dm" % background
        return background

    def display_only(
        self,
        id: Union[int, ImageInstance, ImagePlaceholder],
        *,
        start_col: Optional[int] = None,
        start_row: Optional[int] = None,
        end_col: Optional[int] = None,
        end_row: Optional[int] = None,
        allow_expansion: bool = True,
        fewer_diacritics: Optional[bool] = None,
        background: Optional[BackgroundLike] = None,
        abs_pos: Optional[Tuple[int, int]] = None,
        final_cursor_pos: Optional[FinalCursorPos] = None,
        use_line_feeds: bool = False,
    ) -> ImagePlaceholder:
        placement_id = 0
        if isinstance(id, ImagePlaceholder):
            start_col = start_col or id.start_col
            start_row = start_row or id.start_row
            end_col = end_col or id.end_col
            end_row = end_row or id.end_row
            if not allow_expansion:
                end_col = min(end_col, id.end_col)
                end_row = min(end_row, id.end_row)
            placement_id = id.placement_id
            id = id.image_id
        elif isinstance(id, ImageInstance):
            start_col = start_col or 0
            start_row = start_row or 0
            end_col = end_col or id.cols
            end_row = end_row or id.rows
            if not allow_expansion:
                end_col = min(end_col, id.cols)
                end_row = min(end_row, id.rows)
            id = id.id
        else:
            start_col = start_col or 0
            start_row = start_row or 0
            if end_col is None or end_row is None:
                raise ValueError(
                    "end_col and end_row must be specified when id is an int"
                )
            if not allow_expansion:
                raise ValueError(
                    "Cannot specify allow_expansion=False when id is an int. "
                    "Use ImageInstance returned by get_image_instance instead."
                )

        mode = self.get_image_placeholder_mode(id, fewer_diacritics=fewer_diacritics)

        formatting = self.get_formatting(background)

        if abs_pos is None:
            self.term.print_placeholder(
                image_id=id,
                placement_id=placement_id,
                start_col=start_col,
                start_row=start_row,
                end_col=end_col,
                end_row=end_row,
                mode=mode,
                formatting=formatting,
                use_line_feeds=use_line_feeds,
            )
        else:
            if use_line_feeds:
                raise ValueError(
                    "Cannot specify use_line_feeds=True when abs_pos is specified"
                )
            if abs_pos[0] < 0 or abs_pos[1] < 0:
                raise ValueError(
                    "Absolute position must be non-negative (unless"
                    f" clipping is enabled): {abs_pos}"
                )
            self.term.print_placeholder(
                image_id=id,
                placement_id=placement_id,
                start_col=start_col,
                start_row=start_row,
                end_col=end_col,
                end_row=end_row,
                pos=abs_pos,
                mode=mode,
                formatting=formatting,
            )
        self._move_cursor_to_final_position(
            end_col - start_col,
            end_row - start_row,
            final_cursor_pos,
            use_line_feeds=use_line_feeds,
        )
        return ImagePlaceholder(
            image_id=id,
            placement_id=placement_id,
            start_col=start_col,
            start_row=start_row,
            end_col=end_col,
            end_row=end_row,
        )

    def cleanup_old_databases(
        self, max_age: Optional[datetime.timedelta] = None
    ) -> List[str]:
        """Remove database files older than the specified age.

        Args:
            max_age (int, optional): Maximum age in days. If None, uses
            `max_db_age_days` from the config.

        Returns:
            list: Paths of removed database files.
        """
        if max_age is None:
            max_age = datetime.timedelta(days=self._config.max_db_age_days)
        removed: List[str] = []
        db_dir = self._config.id_database_dir
        try:
            files = sorted(os.listdir(db_dir))
        except FileNotFoundError:
            return removed
        now = datetime.datetime.now()
        for fname in files:
            if not fname.endswith(".db"):
                continue
            path = os.path.join(db_dir, fname)
            if not os.path.isfile(path):
                continue
            # Skip current database
            if os.path.abspath(path) == os.path.abspath(self.id_manager.database_file):
                continue
            atime = datetime.datetime.fromtimestamp(os.path.getatime(path))
            if now - atime > max_age:
                try:
                    os.remove(path)
                    removed.append(path)
                except Exception:
                    pass
        return removed

    def cleanup_current_database(self, max_num_ids: Optional[int] = None) -> None:
        """Clean up the current database by removing old IDs from the current subspace."""
        if max_num_ids is None:
            max_num_ids = self._config.max_num_ids
        self.id_manager.cleanup(self.id_space, self.id_subspace, max_ids=max_num_ids)
        # Clean up the upload history too.
        self.id_manager.cleanup_uploads(max_uploads=max_num_ids)

    def _move_cursor_to_final_position(
        self,
        cols: int,
        rows: int,
        final_cursor_pos: Optional[FinalCursorPos],
        use_line_feeds: bool = False,
    ):
        if final_cursor_pos is None:
            final_cursor_pos = self.final_cursor_pos

        if final_cursor_pos == "bottom-right":
            return
        elif final_cursor_pos == "top-right":
            if use_line_feeds:
                raise ValueError(
                    "Cannot specify use_line_feeds=True when final_cursor_pos is"
                    " top-right"
                )
            self.term.move_cursor(up=rows - 1)
        elif final_cursor_pos == "top-left":
            if use_line_feeds:
                raise ValueError(
                    "Cannot specify use_line_feeds=True when final_cursor_pos is"
                    " top-left"
                )
            self.term.move_cursor(up=rows - 1, left=cols)
        elif final_cursor_pos == "bottom-left":
            if use_line_feeds:
                self.term.write(b"\n")
            else:
                self.term.move_cursor(left=cols)
                # This sequence moves the cursor down, maybe creating a newline.
                self.term.write(b"\033D")
        else:
            raise ValueError(f"Invalid final_cursor_pos: {final_cursor_pos}")
