import io
import os
import dataclasses
from dataclasses import dataclass
from typing import Optional, Union, Callable, Tuple, BinaryIO, List
import select
from tupimage import GraphicsCommand, GraphicsResponse
import fcntl
import termios
import struct
import tty

class GraphicsTerminal:
    def __init__(self, tty_filename: Optional[str]=None, tty_out: Optional[BinaryIO]=None, tty_in: Optional[BinaryIO]=None):
        self.num_tmux_layers: int = 0
        if tty_out is None and tty_filename is None:
            tty_filename = "/dev/tty"
        self.tty_in: Optional[BinaryIO] = tty_in
        self.tty_out: BinaryIO = tty_out
        if tty_filename is not None:
            fd = os.open(tty_filename, os.O_RDWR | os.O_NOCTTY)
            self.tty_out = os.fdopen(fd, "wb", buffering=0)
            self.tty_in = os.fdopen(fd, "rb", buffering=0)
        self.old_term_settings = []

    def write(self, string: Union[str, bytes]):
        if isinstance(string, str):
            string = string.encode("utf-8")
        self.tty_out.write(string)

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

    def send_command(self, command: GraphicsCommand):
        self.start_graphics_command()
        command.content_to_stream(self.tty_out)
        self.end_graphics_command()

    def receive_response(self, timeout: float) -> GraphicsResponse:
        buffer = b""
        is_graphics_response = False
        start_time = time.time()
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
        resp_and_message = response[3:-2].split(b";", 2)
        if len(resp_and_message) > 1:
            res.message = resp_and_message[1]
            res.is_ok = resp_and_message[1] == b"OK"
        for part in resp_and_message[0].split(b","):
            try:
                if part.startswith(b"i="):
                    res.image_id = int(part[2:])
                elif part.startswith(b"I="):
                    res.image_number = int(part[2:])
            except ValueError:
                pass
        return res

    def push_tty_settings(self):
        self.old_term_settings.append(termios.tcgetattr(self.tty_in.fileno()))

    def pop_tty_settings(self):
        termios.tcsetattr(self.tty_in.fileno(), termios.TCSADRAIN, self.old_term_settings.pop())

    def wait_keypress(self) -> bytes:
        self.push_tty_settings()
        try:
            tty.setraw(self.tty_in.fileno())
            result = b""
            while len(result) < 256:
                result += self.tty_in.read(1)
                ready, _, _ = select.select([self.tty_in], [], [], 0)
                if not ready:
                    break
        finally:
            self.pop_tty_settings()
        return result

    def detect_tmux(self):
        if os.environ.get("TMUX"):
            self.num_tmux_layers = max(1, self.num_tmux_layers)
        else:
            self.num_tmux_layers = 0

    def reset(self):
        self.tty_out.write(b"\033c")
        self.tty_out.flush()

    def _get_sizes(self) -> Tuple[int, int, int, int]:
        try:
            return struct.unpack(
                'HHHH',
                fcntl.ioctl(self.tty_out.fileno(), termios.TIOCGWINSZ,
                            struct.pack('HHHH', 0, 0, 0, 0)))
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
        return (width/cols, height/lines)
