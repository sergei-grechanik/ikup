import tupimage
from tupimage import GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def text_printing(ctx: TestingContext):
    for i in range(24):
        ctx.write(str(i) + "\n")
    ctx.write(
        "This is a text-only test. If it fails, it means there is something"
        " wrong with how the terminal is configured (size, colors) or with the"
        " screenshot comparison algorithm.\n"
    )
    for i in range(33, 127):
        ctx.write(chr(i))
    ctx.take_screenshot(
        "Some text and all printable ascii characters. The text should be at"
        " the bottom of the screen."
    )


@screenshot_test
def text_colors(ctx: TestingContext):
    for i in range(16):
        for j in range(16):
            ctx.write(f"\033[48;5;{i}m\033[38;5;{j}m Aa ")
        ctx.write("\n")
    ctx.take_screenshot("")
