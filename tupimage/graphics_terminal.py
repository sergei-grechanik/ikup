import io
import os
import dataclasses
from dataclasses import dataclass
from typing import Optional, Union, Callable, Tuple, TextIO, List
import select
from tupimage import GraphicsCommand, GraphicsResponse

@dataclass
class GraphicsTerminal:
    stream: TextIO
    num_tmux_layers: int = 0

    def start_graphics_command(self):
        string = "\033_G"
        for i in range(self.num_tmux_layers):
            string = "\033Ptmux;" + string.replace("\033", "\033\033")
        self.stream.write(string)

    def end_graphics_command(self):
        string = "\033\\"
        for i in range(self.num_tmux_layers):
            string = string.replace("\033", "\033\033") + "\033\\"
        self.stream.write(string)
        self.stream.flush()

    def send_command(self, command: GraphicsCommand):
        self.start_graphics_command()
        command.content_to_stream(self.stream)
        self.end_graphics_command()

    def receive_response(self, timeout: float) -> GraphicsResponse:
        buffer = ""
        is_graphics_response = False
        start_time = time.time()
        end_time = time.time() + timeout
        while True:
            ready, _, _ = select.select([self.stream], [], [], timeout)
            if ready:
                buffer += self.stream.read(1)
                if is_graphics_response:
                    if buffer.endswith("\033\\"):
                        break
                else:
                    if buffer.endswith("\033_G"):
                        is_graphics_response = True
            timeout = end_time - time.time()
            if timeout < 0:
                return GraphicsResponse(is_valid=False, non_response=buffer)
        # Now parse the response
        res = GraphicsResponse(is_valid=True)
        non_response, response = buffer.split("\033_G", 2)
        res.non_response = non_response
        resp_and_message = response[3:-2].split(";", 2)
        if len(resp_and_message) > 1:
            res.message = resp_and_message[1]
            res.is_ok = resp_and_message[1] == "OK"
        for part in resp_and_message[0].split(","):
            try:
                if part.startswith("i="):
                    res.image_id = int(part[2:])
                elif part.startswith("I="):
                    res.image_number = int(part[2:])
            except ValueError:
                pass
        return res

    def detect_tmux(self):
        if os.environ.get("TMUX"):
            self.num_tmux_layers = max(1, self.num_tmux_layers)
        else:
            self.num_tmux_layers = 0

    def reset(self):
        self.stream.write("\033c")
