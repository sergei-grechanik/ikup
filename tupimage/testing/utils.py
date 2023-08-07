import os
import subprocess
from typing import List, Optional, Callable
from tupimage import GraphicsTerminal
from functools import wraps
from typing import Tuple, Union
import time
import termios
import tty
import urllib.request


def take_screenshot(filename: str, width: int = 320, height: int = 192):
    window_id = os.getenv("WINDOWID")
    if window_id is None:
        raise RuntimeError("WINDOWID not set")
    subprocess.run(
        [
            "import",
            "-depth",
            "8",
            "-resize",
            "{}x{}".format(width, height),
            "-window",
            window_id,
            filename,
        ],
        check=True,
    )


class TestManager:
    def __init__(self, testing_context: "TestingContext", name: str):
        self.testing_context = testing_context
        self.name = name

    def __enter__(self):
        self.testing_context._start_test(self.name)
        return self.testing_context

    def __exit__(self, type, value, traceback):
        self.testing_context._end_test()


class TestingContext:
    all_tests: List[Callable[["TestingContext"], None]] = []

    def __init__(
        self,
        term: GraphicsTerminal,
        output_dir: str,
        reference_dir: str,
        data_dir: str,
        term_size: Tuple[int, int] = (80, 24),
        screenshot_cell_size: Tuple[int, int] = (4, 8),
        pause_after_screenshot: bool = False,
    ):
        self.term: GraphicsTerminal = term
        self.output_dir: str = output_dir
        self.reference_dir: str = reference_dir
        self.data_dir: str = data_dir
        self.screenshot_width: int = term_size[0] * screenshot_cell_size[0]
        self.screenshot_height: int = term_size[1] * screenshot_cell_size[1]
        os.makedirs(self.data_dir, exist_ok=True)
        self.screenshot_index: int = 0
        self.test_name: Optional[str] = None
        self.pause_after_screenshot = pause_after_screenshot
        self.init_image_downloaders()

    def image_downloader(
        self, url: str, name: Optional[str] = None
    ) -> Callable[[], str]:
        if name is None:
            name = url.split("/")[-1]

        def download() -> str:
            path = os.path.abspath(os.path.join(self.data_dir, name))
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
            return path

        return download

    def init_image_downloaders(self):
        self.get_wikipedia_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/en/thumb/8/80/"
            "Wikipedia-logo-v2.svg/440px-Wikipedia-logo-v2.svg.png"
        )
        self.get_tux_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/a/af/Tux.png"
        )
        self.get_transparency_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/4/47/"
            "PNG_transparency_demonstration_1.png"
        )
        self.get_column_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/9/95/Column6.png"
        )
        self.get_horizontal_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/2/2a/"
            "Horizontal_hemiola.png"
        )
        self.get_ruler_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/3/38/Screen_Ruler.png"
        )
        self.get_diagonal_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/5/5d/Linear_Graph.png"
        )
        self.get_castle_jpg = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/1/10/"
            "Neuschwanstein_Castle_from_Marienbr%C3%BCcke_Bridge.jpg"
        )

    def write(self, string: Union[str, bytes]):
        self.term.write(string)

    def test(self, name: str) -> TestManager:
        return TestManager(self, name)

    def _start_test(self, name: str):
        self.test_name = name
        os.makedirs(
            os.path.join(self.output_dir, self.test_name), exist_ok=True
        )
        self.screenshot_index = 0
        self.term.reset()

    def _end_test(self):
        self.test_name = None

    def take_screenshot(self, description: Optional[str] = None):
        if self.test_name is None:
            raise RuntimeError("No test running")
        self.term.tty_out.flush()
        time.sleep(0.05)
        filename = os.path.join(
            self.output_dir,
            self.test_name,
            f"screenshot-{self.screenshot_index}.jpg",
        )
        take_screenshot(
            filename, width=self.screenshot_width, height=self.screenshot_height
        )
        self.screenshot_index += 1
        if self.pause_after_screenshot:
            self.term.wait_keypress()


def screenshot_test(func):
    @wraps(func)
    def wrapper(ctx, *args, **kwargs):
        with ctx.test(func.__name__):
            return func(ctx, *args, **kwargs)

    wrapper.is_screenshot_test = True
    TestingContext.all_tests.append(wrapper)
    return wrapper
