import fcntl
import os
import select
import struct
import termios
import copy
import random
import time
from typing import BinaryIO, Optional, Tuple, Union

from tupimage import (
    GraphicsCommand,
    GraphicsResponse,
    TransmitCommand,
    PlacementData,
    PutCommand,
)
from tupimage.placeholder import ImagePlaceholderMode, ImagePlaceholder


class TtySettingsGuard:
    def __init__(self, term: "GraphicsTerminal"):
        self.term = term

    def __enter__(self):
        self.term.push_tty_settings()

    def __exit__(self, type, value, traceback):
        self.term.pop_tty_settings()


class GraphicsCommandGuard:
    def __init__(self, term: "GraphicsTerminal"):
        self.term = term

    def __enter__(self):
        self.term.start_graphics_command()

    def __exit__(self, type, value, traceback):
        self.term.end_graphics_command()


class GraphicsTerminal:
    def __init__(
        self,
        tty_filename: Optional[str] = None,
        tty_out: Optional[BinaryIO] = None,
        tty_in: Optional[BinaryIO] = None,
        autosplit_max_size: int = 2816,
        force_placeholders: bool = False,
    ):
        self.num_tmux_layers: int = 0
        if tty_out is None and tty_filename is None:
            tty_filename = "/dev/tty"
        self.tty_in: Optional[BinaryIO] = tty_in
        self.tty_out: BinaryIO = tty_out
        if tty_filename is not None:
            fd = os.open(tty_filename, os.O_RDWR | os.O_NOCTTY)
            self.tty_out = os.fdopen(fd, "wb", buffering=0)
            self.tty_in = os.fdopen(fd, "rb", buffering=0)
        self.autosplit_max_size: int = autosplit_max_size
        self.force_placeholders: bool = force_placeholders
        self.old_term_settings = []
        self.tracked_cursor_position: Optional[Tuple[int, int]] = None

    def clone_with(
        self,
        autosplit_max_size: Optional[int] = None,
        force_placeholders: Optional[bool] = None,
        num_tmux_layers: Optional[int] = None,
    ):
        res = copy.copy(self)
        res.old_term_settings = []
        if autosplit_max_size is not None:
            res.autosplit_max_size = autosplit_max_size
        if force_placeholders is not None:
            res.force_placeholders = force_placeholders
        if num_tmux_layers is not None:
            res.num_tmux_layers = num_tmux_layers
        return res

    def write(self, string: Union[str, bytes]):
        if isinstance(string, str):
            string = string.encode("utf-8")
        self.tty_out.write(string)
        self.tracked_cursor_position = None

    def start_graphics_command(self):
        string = b"\033_G"
        for i in range(self.num_tmux_layers):
            string = b"\033Ptmux;" + string.replace(b"\033", b"\033\033")
        self.tty_out.write(string)

    def end_graphics_command(self):
        string = b"\033\\"
        for i in range(self.num_tmux_layers):
            string = string.replace(b"\033", b"\033\033") + b"\033\\"
        self.tty_out.write(string)
        self.tty_out.flush()

    def guard_graphics_command(self) -> GraphicsCommandGuard:
        return GraphicsCommandGuard(self)

    def send_command_raw(self, command: GraphicsCommand):
        with self.guard_graphics_command():
            command.content_to_stream(self.tty_out)

    def print_placeholder_for_put(
        self,
        put_command: PutCommand,
        mode: ImagePlaceholderMode = ImagePlaceholderMode.default(),
    ):
        placement_id = put_command.placement_id
        if placement_id is None:
            placement_id = 0
        term_cols, term_rows = self.get_size()
        cur_x, cur_y = self.get_cursor_position_tracked()
        cols = min(put_command.cols, term_cols - cur_x)
        rows = put_command.rows
        if term_rows - cur_y < rows:
            if put_command.do_not_move_cursor:
                rows = term_rows - cur_y
            else:
                newlines = rows - (term_rows - cur_y)
                self.tty_out.write(b"\033[%dS" % newlines)
                self.move_cursor(up=newlines)
        if cols <= 0 or rows <= 0:
            return
        placeholder = ImagePlaceholder(
            image_id=put_command.image_id,
            placement_id=placement_id,
            end_column=cols,
            end_row=rows,
        )
        cur_x, cur_y = self.tracked_cursor_position
        self.tracked_cursor_position = None
        placeholder.to_stream_at_cursor(self.tty_out, mode=mode)
        if put_command.do_not_move_cursor:
            self.move_cursor_abs(col=cur_x, row=cur_y)
        elif cur_x + cols >= term_cols:
            # Newline
            self.tty_out.write(b"\033E")
            self.set_tracked_cursor_position(0, cur_y + rows)
        else:
            self.set_tracked_cursor_position(cur_x + cols, cur_y + rows - 1)
        self.tty_out.flush()

    def send_command(
        self,
        command: GraphicsCommand,
        autosplit: bool = True,
        force_placeholders: bool = None,
    ):
        if force_placeholders is None:
            force_placeholders = self.force_placeholders
        if force_placeholders:
            if (
                isinstance(command, TransmitCommand)
                and command.placement is not None
                and not command.placement.virtual
            ):
                command = command.clone_with()
                command.placement.virtual = True
                if command.placement.placement_id is None:
                    command.placement.placement_id = random.randint(
                        1, 2**24 - 1
                    )
            if isinstance(command, PutCommand) and not command.virtual:
                command = command.clone_with(virtual=True)
                if command.placement_id is None:
                    command.placement_id = random.randint(1, 2**24 - 1)
        if autosplit and isinstance(command, TransmitCommand):
            for subcommand in command.split(self.autosplit_max_size):
                self.send_command_raw(subcommand)
        else:
            self.send_command_raw(command)
        if force_placeholders:
            if (
                isinstance(command, TransmitCommand)
                and command.placement is not None
            ):
                self.print_placeholder_for_put(command.get_put_command())
            if isinstance(command, PutCommand):
                self.print_placeholder_for_put(command)

    def set_immediate_input_noecho(self):
        settings = list(termios.tcgetattr(self.tty_in.fileno()))
        settings[3] &= ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(self.tty_in.fileno(), termios.TCSADRAIN, settings)

    def receive_response(self, timeout: float = 10) -> GraphicsResponse:
        with self.guard_tty_settings():
            self.set_immediate_input_noecho()
            buffer = b""
            is_graphics_response = False
            end_time = time.time() + timeout
            while True:
                ready, _, _ = select.select([self.tty_in], [], [], timeout)
                if ready:
                    buffer += self.tty_in.read(1)
                    if is_graphics_response:
                        if buffer.endswith(b"\033\\"):
                            break
                    else:
                        if buffer.endswith(b"\033_G"):
                            is_graphics_response = True
                timeout = end_time - time.time()
                if timeout < 0:
                    return GraphicsResponse(is_valid=False, non_response=buffer)
            # Now parse the response
            res = GraphicsResponse(is_valid=True)
            non_response, response = buffer.split(b"\033_G", 2)
            res.non_response = non_response
            resp_and_message = response[:-2].split(b";", 2)
            if len(resp_and_message) > 1:
                res.message = resp_and_message[1].decode("utf-8")
                res.is_ok = resp_and_message[1] == b"OK"
            for part in resp_and_message[0].split(b","):
                try:
                    if part.startswith(b"i="):
                        res.image_id = int(part[2:])
                    elif part.startswith(b"I="):
                        res.image_number = int(part[2:])
                    elif part.startswith(b"p="):
                        res.placement_id = int(part[2:])
                    else:
                        key_and_val = part.split(b"=", 2)
                        res.additional_data[key_and_val[0].decode("utf-8")] = (
                            key_and_val[1].decode("utf-8")
                            if len(key_and_val) > 1
                            else None
                        )
                except ValueError:
                    pass
            return res

    def dump_unexpected_responses(self):
        while True:
            res = self.receive_response(timeout=0.01)
            if not res.is_valid:
                break
            self.write(f"Unexpected response: {res.message}\n")

    def get_cursor_position(self, timeout: float = 2.0) -> Tuple[int, int]:
        with self.guard_tty_settings():
            self.set_immediate_input_noecho()
            self.tty_out.write(b"\033[6n")
            buffer = b""
            end_time = time.time() + timeout
            is_response = False
            while True:
                ready, _, _ = select.select([self.tty_in], [], [], timeout)
                if ready:
                    buffer += self.tty_in.read(1)
                    if is_response:
                        if buffer.endswith(b"R"):
                            break
                    else:
                        if buffer.endswith(b"\033["):
                            is_response = True
                            buffer = b""
                timeout = end_time - time.time()
                if timeout < 0:
                    raise TimeoutError(
                        "No response to cursor position request: %r" % buffer
                    )
            # Now parse the response
            parts = buffer[:-1].split(b";")
            if len(parts) != 2:
                raise ValueError(
                    "Invalid response to cursor position request: %r" % buffer
                )
            y, x = parts
            self.tracked_cursor_position = (int(x) - 1, int(y) - 1)
        return self.tracked_cursor_position

    def get_cursor_position_tracked(
        self, timeout: float = 2.0
    ) -> Tuple[int, int]:
        if self.tracked_cursor_position is None:
            self.get_cursor_position(timeout=timeout)
        return self.tracked_cursor_position

    def push_tty_settings(self):
        self.old_term_settings.append(termios.tcgetattr(self.tty_in.fileno()))

    def pop_tty_settings(self):
        termios.tcsetattr(
            self.tty_in.fileno(),
            termios.TCSADRAIN,
            self.old_term_settings.pop(),
        )

    def guard_tty_settings(self) -> TtySettingsGuard:
        return TtySettingsGuard(self)

    def wait_keypress(self) -> bytes:
        with self.guard_tty_settings():
            self.set_immediate_input_noecho()
            result = b""
            while len(result) < 256:
                result += self.tty_in.read(1)
                ready, _, _ = select.select([self.tty_in], [], [], 0)
                if not ready:
                    break
            return result

    def detect_tmux(self):
        term = os.environ.get("TERM", "")
        if os.environ.get("TMUX") and ("screen" in term or "tmux" in term):
            self.num_tmux_layers = max(1, self.num_tmux_layers)
        else:
            self.num_tmux_layers = 0

    def reset(self):
        self.tty_out.write(b"\033c")
        self.tty_out.flush()
        self.tracked_cursor_position = (0, 0)

    def _get_sizes(self) -> Tuple[int, int, int, int]:
        try:
            fileno = (
                self.tty_in.fileno()
                if self.tty_in is not None
                else self.tty_out.fileno()
            )
            return struct.unpack(
                "HHHH",
                fcntl.ioctl(
                    fileno,
                    termios.TIOCGWINSZ,
                    struct.pack("HHHH", 0, 0, 0, 0),
                ),
            )
        except OSError:
            return 0, 0, 0, 0

    def get_size(self) -> Optional[Tuple[int, int]]:
        lines, cols, _, _ = self._get_sizes()
        if lines == 0 or cols == 0:
            return None
        return (cols, lines)

    def get_cell_size(self) -> Optional[Tuple[int, int]]:
        lines, cols, width, height = self._get_sizes()
        if lines == 0 or cols == 0 or width == 0 or height == 0:
            return None
        return (width / cols, height / lines)

    def set_tracked_cursor_position(
        self,
        x: int,
        y: int,
        columns: Optional[int] = None,
        lines: Optional[int] = None,
    ):
        if columns is None or lines is None:
            columns, lines = self.get_size()
        self.tracked_cursor_position = (
            min(x, columns - 1),
            min(y, lines - 1),
        )

    def move_cursor(
        self,
        *,
        right: Optional[int] = None,
        down: Optional[int] = None,
        left: Optional[int] = None,
        up: Optional[int] = None,
    ):
        if up is not None:
            if down is not None:
                raise ValueError("Cannot specify both up and down")
            down = -up
        if left is not None:
            if right is not None:
                raise ValueError("Cannot specify both left and right")
            right = -left
        if down:
            if down > 0:
                self.tty_out.write(b"\033[%dB" % down)
            else:
                self.tty_out.write(b"\033[%dA" % -down)
        if right:
            if right > 0:
                self.tty_out.write(b"\033[%dC" % right)
            else:
                self.tty_out.write(b"\033[%dD" % -right)
        self.tty_out.flush()
        if self.tracked_cursor_position is not None:
            self.set_tracked_cursor_position(
                self.tracked_cursor_position[0] + (right or 0),
                self.tracked_cursor_position[1] + (down or 0),
            )

    def move_cursor_abs(
        self,
        *,
        row: Optional[int] = None,
        col: Optional[int] = None,
        pos: Optional[Tuple[int, int]] = None,
    ):
        if pos is not None:
            if row is not None or col is not None:
                raise ValueError("Cannot specify both pos and row/col")
            col, row = pos
        if row is not None:
            self.tty_out.write(b"\033[%dd" % (row + 1))
        if col is not None:
            self.tty_out.write(b"\033[%dG" % (col + 1))
        self.tty_out.flush()
        if self.tracked_cursor_position is not None:
            self.set_tracked_cursor_position(
                col or self.tracked_cursor_position[0],
                row or self.tracked_cursor_position[1],
            )
        elif row is not None and col is not None:
            self.set_tracked_cursor_position(
                col,
                row,
            )

    def set_margins(self, top: int, bottom: int):
        self.tty_out.write(b"\033[%d;%dr" % (top + 1, bottom + 1))
        self.tty_out.flush()
        self.tracked_cursor_position = None

    def scroll_down(self, lines: int = 1):
        self.tty_out.write(b"\033[%dS" % lines)
        self.tty_out.flush()
        self.tracked_cursor_position = None

    def scroll_up(self, lines: int = 1):
        self.tty_out.write(b"\033[%dT" % lines)
        self.tty_out.flush()
        self.tracked_cursor_position = None
