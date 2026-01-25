import colorsys
import io
import json
import os
import subprocess
import shutil
import time
import urllib.request
import zlib
from typing import Callable, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from ikup import GraphicsTerminal
import ikup


def take_screenshot(
    filename: str, num_pixels: int = 480 * 288, window_id: Optional[str] = None
):
    if window_id is None:
        window_id = os.getenv("WINDOWID")
        if window_id is None:
            raise RuntimeError("WINDOWID not set")
    res = subprocess.run(
        [
            "import",
            "-depth",
            "8",
            "-resize",
            "{}@".format(num_pixels),
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
    __test__ = False
    all_tests: List[Tuple[str, Callable[["TestingContext"], None]]] = []

    def __init__(
        self,
        term: GraphicsTerminal,
        *,
        output_dir: str,
        data_dir: str,
        term_size: Tuple[int, int] = (80, 24),
        screenshot_pixels: int = 480 * 288,
        pause_after_screenshot: bool = False,
        pause_before_test: bool = False,
        take_screenshots: bool = True,
        reset_before_test: bool = True,
        window_id: Optional[str] = None,
    ):
        self.term: GraphicsTerminal = term
        self.output_dir: str = output_dir
        self.data_dir: str = data_dir
        self.screenshot_pixels: int = screenshot_pixels
        os.makedirs(self.data_dir, exist_ok=True)
        self.current_test_data: dict = {}
        self.screenshot_index: int = 0
        self.test_name: Optional[str] = None
        self.pause_after_screenshot = pause_after_screenshot
        self.pause_before_test = pause_before_test
        self.take_screenshots: bool = take_screenshots
        self.reset_before_test: bool = reset_before_test
        self.window_id: Optional[str] = window_id
        self.init_image_downloaders()

    def image_downloader(
        self, url: str, name: Optional[str] = None
    ) -> Callable[[], str]:
        if name is None:
            name = url.split("/")[-1]

        def download() -> str:
            path = os.path.abspath(os.path.join(self.data_dir, name))
            if not os.path.exists(path):
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": f"ikup/{ikup.__version__} (github.com/sergei-grechanik/ikup)",
                        "Accept": "*/*",
                    },
                )
                with urllib.request.urlopen(req) as resp, open(path, "wb") as f:
                    shutil.copyfileobj(resp, f)
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
        self.get_small_arrow_png = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/b/ba/Arrow-up.png"
        )
        self.get_castle_jpg = self.image_downloader(
            "https://upload.wikimedia.org/wikipedia/commons/1/10/"
            "Neuschwanstein_Castle_from_Marienbr%C3%BCcke_Bridge.jpg"
        )

    def write(self, string: Union[str, bytes]) -> None:
        self.term.write(string)

    def test(self, name: str) -> TestManager:
        return TestManager(self, name)

    def _start_test(self, name: str) -> None:
        self.test_name = name
        os.makedirs(os.path.join(self.output_dir, self.test_name), exist_ok=True)
        self.current_test_data = {"name": name, "screenshots": [], "errors": []}
        self.screenshot_index = 0
        if self.term.shellscript_out is not None:
            self.term.shellscript_out.write(f"\n\n# {name}")
            self.term.shellscript_out.write(" {{{\n\n")
        if self.pause_before_test:
            if self.reset_before_test:
                self.term.reset()
            self.term.write(f"Test: {name}\n")
            self.wait_for_keypress()
        if self.reset_before_test:
            self.term.reset()

    def _end_test(self):
        self.test_name = None
        json_file = os.path.join(self.output_dir, "report.json")
        if not os.path.exists(json_file):
            with open(json_file, "w") as f:
                json.dump([], f)
        with open(json_file, "r+") as f:
            lst = json.load(f)
            lst.append(self.current_test_data)
            f.seek(0)
            json.dump(lst, f, indent=4)
        if self.term.shellscript_out is not None:
            self.term.shellscript_out.write("# End of test }}}\n")

    def get_image_size(self, filename: str) -> Tuple[int, int]:
        img = Image.open(filename)
        return img.size

    def generate_image(self, width: int, height: int) -> Image.Image:
        import numpy

        data = numpy.random.random_sample(size=(height, width, 3))
        img = Image.fromarray((data * 255).astype(numpy.uint8), "RGB")
        return img

    def alpha_test_image(
        self, width: int, height: int, color: Tuple[int, int, int]
    ) -> Image.Image:
        img = Image.new("RGBA", (width, height))
        d = ImageDraw.Draw(img)
        for x in range(width):
            alpha = int(x / width * 255)
            d.line([(x, 0), (x, height)], fill=color + (alpha,))
        return img

    def text_to_image(
        self, text: str, pad: int = 2, colorize_by_id: Optional[int] = None
    ) -> Image.Image:
        bg_color: Union[str, Tuple[int, int, int]] = "black"
        if colorize_by_id is not None:
            byte4 = (colorize_by_id & 0xFF000000) >> 24
            r = (colorize_by_id & 0xFF0000) >> 16
            g = (colorize_by_id & 0x00FF00) >> 8
            b = colorize_by_id & 0x0000FF
            h, _, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            bg_color_float = colorsys.hsv_to_rgb(h, 0.3 + byte4 / 255 * 0.7, 0.5)
            rf, gf, bf = bg_color_float
            bg_color = (int(rf * 255), int(gf * 255), int(bf * 255))
        img = Image.new("RGB", (1, 1))
        d = ImageDraw.Draw(img)
        font = ImageFont.truetype("DejaVuSansMono.ttf", 16)
        _, _, width, height = d.textbbox((0, 0), text, font=font)
        img = Image.new(
            "RGB", (int(width + pad * 2), int(height + pad * 2)), color=bg_color
        )
        d = ImageDraw.Draw(img)
        d.text((pad, pad), text, fill="white", font=font)
        d.rectangle(
            [(0, 0), (width + pad * 2 - 1, height + pad * 2 - 1)],
            outline="grey",
        )
        return img

    def add_border(
        self,
        img: Union[Image.Image, str],
        color: Tuple[int, int, int] = (0, 255, 0),
        width: int = 2,
    ) -> Image.Image:
        """Add a colored border around an image."""
        if isinstance(img, str):
            img = Image.open(img)
        img = img.copy()
        d = ImageDraw.Draw(img)
        w, h = img.size
        for i in range(width):
            d.rectangle([(i, i), (w - 1 - i, h - 1 - i)], outline=color)
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

    def dump_unexpected_responses(self):
        resps = self.term.receive_multiple_responses()
        if resps:
            print(f"Received {len(resps)} unexpected responses:")
            for resp in resps[:5]:
                print(resp)
            if len(resps) > 5:
                print("...")

    def wait_for_keypress(self):
        key = self.term.wait_for_keypress()
        if key == b"\x03":
            self.term.write(b"\033[0m")
            raise KeyboardInterrupt()

    def take_screenshot(
        self, description: Optional[str] = None, diff_threshold: Optional[float] = None
    ):
        sleep_time = 0.4
        if self.test_name is None:
            raise RuntimeError("No test running")
        self.dump_unexpected_responses()
        self.term.out_display.flush()
        if self.term.shellscript_out is not None:
            self.term.shellscript_out.write(f"\n# Screenshot: {description}\n")
            self.term.shellscript_out.write("sleep {sleep_time}\n\n")
        rel_filename = os.path.join(
            self.test_name,
            f"screenshot-{self.screenshot_index}.png",
        )
        filename = os.path.join(self.output_dir, rel_filename)
        if self.take_screenshots:
            # TODO: Instead of sleeping it might be better to send some kind of redraw
            # command with a confirmation response.
            time.sleep(sleep_time)
            take_screenshot(
                filename,
                num_pixels=self.screenshot_pixels,
                window_id=self.window_id,
            )
            self.current_test_data["screenshots"].append(
                {
                    "filename": rel_filename,
                    "index": self.screenshot_index,
                    "description": description or "",
                    **({"diff_threshold": diff_threshold} if diff_threshold else {}),
                }
            )
        self.screenshot_index += 1
        if self.pause_after_screenshot:
            self.wait_for_keypress()

    def take_screenshot_verbose(self, description: Optional[str] = None) -> None:
        if description is not None:
            self.term.write(description)
        self.take_screenshot(description)

    def assert_equal(self, lhs, rhs):
        if lhs != rhs:
            message = f"Assertion failed: {lhs} != {rhs}"
            self.current_test_data["errors"].append(message)
            self.term.write(message + "\n")

    def assert_true(self, value: bool, description: Optional[str] = None) -> None:
        if not value:
            message = "Assertion failed" + (": " + description if description else "")
            self.current_test_data["errors"].append(message)
            self.term.write(message + "\n")

    def print_results(self):
        print("Output dir: " + os.path.relpath(self.output_dir))


def screenshot_test(func=None, suffix: Optional[str] = None, params: dict = {}):
    def decorator(func):
        name = func.__module__ + "." + func.__name__
        if suffix is not None:
            name += "_" + suffix
        if name.startswith("ikup.testing."):
            name = name[len("ikup.testing.") :]

        def wrapper(ctx):
            with ctx.test(name):
                return func(ctx, **params)

        TestingContext.all_tests.append((name, lambda ctx: wrapper(ctx)))
        return func

    if func:
        return decorator(func)
    return decorator
