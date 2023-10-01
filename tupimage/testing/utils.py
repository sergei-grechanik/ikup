import os
import subprocess
import termios
import time
import urllib.request
from typing import Callable, List, Optional, Tuple, Union
from PIL import Image, ImageDraw
import numpy as np
import io
import zlib

from tupimage import GraphicsTerminal


def take_screenshot(filename: str, width: int = 320, height: int = 192):
    window_id = os.getenv("WINDOWID")
    if window_id is None:
        raise RuntimeError("WINDOWID not set")
    res = subprocess.run(
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
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Screenshot capture failed: {res.stderr}")


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
    all_tests: List[Tuple[str, Callable[["TestingContext"], None]]] = []

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
        self.report_file: Optional[TextIO] = None
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
        if self.report_file is None:
            self.report_file = open(
                os.path.join(self.output_dir, "report.html"), "w", buffering=1
            )
        self.screenshot_index = 0
        self.report_file.write(f"<h2>{name}</h2>\n")
        self.term.reset()

    def _end_test(self):
        self.test_name = None

    def compare_images(self, filename: str, ref_filename: str) -> float:
        # Load the images with Pillow and compare them using mse.
        # This is not the best way to compare images, but it's good enough for
        # our purposes.
        img1 = Image.open(filename)
        img2 = Image.open(ref_filename)
        if img1.size != img2.size:
            return 1.0
        img1 = np.array(img1).astype(np.float32) / 255.0
        img2 = np.array(img2).astype(np.float32) / 255.0
        return np.mean(np.square(img1 - img2))

    def generate_image(self, width: int, height: int) -> bytes:
        #  xx, yy = np.meshgrid(np.arange(0, width), np.arange(0, height))
        #  np.stack((xx, yy), axis=-1)
        data = np.random.random_sample(size=(height, width, 3))
        img = Image.fromarray((data * 255).astype(np.uint8), "RGB")
        return img

    def text_to_image(self, text: str, pad: int = 2) -> bytes:
        img = Image.new("RGB", (1, 1))
        d = ImageDraw.Draw(img)
        width, height = d.textsize(text)
        img = Image.new("RGB", (width + pad * 2, height + pad * 2))
        d = ImageDraw.Draw(img)
        d.text((pad, pad), text, fill="white")
        d.rectangle(
            [(0, 0), (width + pad * 2 - 1, height + pad * 2 - 1)],
            outline="grey",
        )
        return img

    def to_png(self, img: Image.Image) -> bytes:
        bytesio = io.BytesIO()
        img.save(bytesio, format="PNG")
        return bytesio.getvalue()

    def to_rgb(
        self,
        img: Union[Image.Image, str],
        bits: int = 24,
        compress: bool = False,
    ) -> bytes:
        if isinstance(img, str):
            img = Image.open(img)
        if bits == 24:
            if img.mode != "RGB":
                img = img.convert("RGB")
        elif bits == 32:
            if img.mode != "RGBA":
                img = img.convert("RGBA")
        else:
            raise ValueError(f"Invalid number of bits: {bits}")
        res = img.tobytes()
        if compress:
            res = zlib.compress(res)
        return res

    def to_rgb_and_wh(
        self,
        img: Union[Image.Image, str],
        bits: int = 24,
        compress: bool = False,
    ) -> Tuple[bytes, int, int]:
        if isinstance(img, str):
            img = Image.open(img)
        w, h = img.size
        data = self.to_rgb(img, bits=bits, compress=compress)
        return data, w, h

    def take_screenshot(self, description: Optional[str] = None):
        if self.test_name is None:
            raise RuntimeError("No test running")
        self.term.tty_out.flush()
        time.sleep(0.5)
        rel_filename = os.path.join(
            self.test_name,
            f"screenshot-{self.screenshot_index}.png",
        )
        filename = os.path.join(self.output_dir, rel_filename)
        take_screenshot(
            filename, width=self.screenshot_width, height=self.screenshot_height
        )
        reference_img = ""
        status = ""
        diffscore = 0.0
        if self.reference_dir:
            reference_img = os.path.join(self.reference_dir, rel_filename)
            if not os.path.exists(reference_img):
                status = "No reference screenshot"
            else:
                diffscore = self.compare_images(filename, reference_img)
                status = f"Diff score: {diffscore:.6f}"
        self.report_file.write(f"<h3>{self.screenshot_index} {status}</h3>\n")
        if description is not None:
            self.report_file.write(f"<p>{description}</p>\n")
        self.report_file.write(f'<img src="{rel_filename}">\n')
        if reference_img and diffscore != 0.0:
            rel_reference_img = os.path.relpath(reference_img, self.output_dir)
            self.report_file.write(f'<img src="{rel_reference_img}">\n')
        self.screenshot_index += 1
        if self.pause_after_screenshot:
            key = self.term.wait_keypress()
            if key == b"\x03":
                self.term.write(b"\033[0m")
                raise KeyboardInterrupt()

    def assert_equal(self, lhs, rhs):
        if lhs != rhs:
            raise AssertionError(f"{lhs} != {rhs}")

    def assert_true(self, value: bool, description: Optional[str] = None):
        if not value:
            raise AssertionError(
                "Assertion failed" + (": " + description if description else "")
            )

    def print_results(self):
        print("Output dir: " + os.path.relpath(self.output_dir))
        print("Report: file://" + os.path.abspath(self.report_file.name))


def screenshot_test(func=None, suffix: Optional[str] = None, params: dict = {}):
    def decorator(func):
        name = func.__name__
        if suffix is not None:
            name += "_" + suffix

        def wrapper(ctx):
            with ctx.test(name):
                return func(ctx, **params)

        TestingContext.all_tests.append((name, lambda ctx: wrapper(ctx)))
        return func

    if func:
        return decorator(func)
    return decorator
