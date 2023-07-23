from .utils import TestingContext, screenshot_test
from tupimage import GraphicsTerminal

@screenshot_test
def test_text_printing(ctx: TestingContext):
    for i in range(24):
        ctx.term.stream.write(str(i))
    ctx.term.stream.write("This is a text-only test. If it fails, it means there is something wrong with how the terminal is configured (size, colors) or with the screenshot comparison algorithm.\n")
    for i in range(33, 127):
        ctx.term.stream.write(chr(i))
    for i in range(16):
        for j in range(16):
            ctx.term.stream.write(f"\033[48;5;{i}m\033[38;5;{j}m Aa ")
            ctx.term.stream.write("\n")
    ctx.take_screenshot()

def main():
    term = GraphicsTerminal()
    ctx = TestingContext(term)
    pass
