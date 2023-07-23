
import os
import subprocess
from typing import List, Optional, Callable
from tupimage import GraphicsTerminal
from functools import wraps

def take_screenshot(filename: str, width: int=320, height: int=192):
    window_id = os.getenv('WINDOWID')
    if window_id is None:
        raise RuntimeError("WINDOWID not set")
    subprocess.run(['import', '-depth', '8', '-resize', '{}x{}'.format(width, height), '-window', window_id, filename], check=True)

class TestManager:
    def __init__(self, testing_context: 'TestingContext', name: str):
        self.testing_context = testing_context
        self.name = name

    def __enter__(self):
        self.testing_context._start_test(self.name)
        return self.testing_context

    def __exit__(self, type, value, traceback):
        self.testing_context._end_test()

class TestingContext:
    def __init__(self, term: GraphicsTerminal, output_dir: str, reference_dir: str, data_dir: str, term_width: int=80, term_height: int=24, screenshot_cell_width: int=4, screenshot_cell_height: int=8):
        self.term: GraphicsTerminal = term
        sefl.output_dir: str = output_dir
        self.reference_dir: str = reference_dir
        self.data_dir: str = data_dir
        self.term_width: int = term_width
        self.term_height: int = term_height
        self.screenshot_width: int = term_width * screenshot_cell_width
        self.screenshot_height: int = term_height * screenshot_cell_height
        os.makedirs(self.data_dir, exist_ok=True)
        self.screenshot_index: int = 0
        self.test_name: Optional[str] = None
        self.init_image_downloaders()

    def image_downloader(self, url: str, name: Optional[str] = None) -> Callable[[], str]:
        if name is None:
            name = url.split('/')[-1]
        def download() -> str:
            path = os.path.join(self.data_dir, name)
            if not os.path.exists(path):
                urllib.request.urlretrieve(url, path)
            return path
        return download

    def init_image_downloaders(self):
        wikipedia_png = image_downloader("https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/440px-Wikipedia-logo-v2.svg.png")
        transparency_png = image_downloader(
                "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png")
        column_png =
            image_downloader(
                "https://upload.wikimedia.org/wikipedia/commons/9/95/Column6.png")
        horizontal_png =
            image_downloader(
                "https://upload.wikimedia.org/wikipedia/commons/2/2a/Horizontal_hemiola.png")
        diagonal_png =
            image_downloader(
                "https://upload.wikimedia.org/wikipedia/commons/5/5d/Linear_Graph.png")
        castle_jpg = image_downloader("https://upload.wikimedia.org/wikipedia/commons/1/10/Neuschwanstein_Castle_from_Marienbr%C3%BCcke_Bridge.jpg")

    def test(self, name: str) -> TestManager:
        return TestManager(self, name)

    def _start_test(self, name: str):
        self.test_name = name
        os.makedirs(os.path.join(self.output_dir, self.test_name), exist_ok=True)
        self.screenshot_index = 0
        self.term.reset()

    def _end_test(self):
        self.test_name = None

    def take_screenshot(self):
        if self.test_name is None:
            raise RuntimeError("No test running")
        filename = os.path.join(self.output_dir, self.test_name, f"screenshot-{self.screenshot_index}.png")
        take_screenshot(filename, width=self.screenshot_width, height=self.screenshot_height)
        self.screenshot_index += 1

def screenshot_test(func):
    @wraps(func)
    def wrapper(ctx, *args, **kwargs):
        with ctx.test(func.__name__):
            return func(ctx, *args, **kwargs)
    return wrapper
