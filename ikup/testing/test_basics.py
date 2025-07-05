import ikup
from ikup import GraphicsTerminal, PutCommand, TransmitCommand
from ikup.testing import TestingContext, screenshot_test


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


@screenshot_test
def text_underline(ctx: TestingContext):
    # Default underline color
    ctx.write(f"\033[4:1mSingle_ ")
    ctx.write(f"\033[4:2mDouble_ ")
    ctx.write(f"\033[4:3mCurly_ ")
    ctx.write(f"\033[4:4mDotted_ ")
    ctx.write(f"\033[4:5mDashed_ ")
    ctx.write(f"\033[4:0mNone gy_ ")
    ctx.write(f"\033[4mSingle_ ")
    ctx.write(f"\033[9mStrike_ ")
    ctx.write(f"\033[0m (fg)\n")

    # Default underline color, different fg
    ctx.write(f"\033[38:5:3m")
    ctx.write(f"\033[4:1mSingle_ ")
    ctx.write(f"\033[4:2mDouble_ ")
    ctx.write(f"\033[4:3mCurly_ ")
    ctx.write(f"\033[4:4mDotted_ ")
    ctx.write(f"\033[4:5mDashed_ ")
    ctx.write(f"\033[4:0mNone gy_ ")
    ctx.write(f"\033[4mSingle_ ")
    ctx.write(f"\033[9mStrike_ ")
    ctx.write(f"\033[0m (fg)\n")

    # 8-bit underline color
    for c in [0, 1, 255]:
        ctx.write(f"\033[58:5:{c}m")
        ctx.write(f"\033[4:1mSingle_ ")
        ctx.write(f"\033[4:2mDouble_ ")
        ctx.write(f"\033[4:3mCurly_ ")
        ctx.write(f"\033[4:4mDotted_ ")
        ctx.write(f"\033[4:5mDashed_ ")
        ctx.write(f"\033[4:0mNone gy_ ")
        ctx.write(f"\033[4mSingle_ ")
        ctx.write(f"\033[9mStrike_ ")
        ctx.write(f"\033[0m({c})\n")

    # 24-bit underline color
    for c in ["0:0:0", "255:0:0", "255:255:255"]:
        ctx.write(f"\033[58:2:{c}m")
        ctx.write(f"\033[4:1mSingle_ ")
        ctx.write(f"\033[4:2mDouble_ ")
        ctx.write(f"\033[4:3mCurly_ ")
        ctx.write(f"\033[4:4mDotted_ ")
        ctx.write(f"\033[4:5mDashed_ ")
        ctx.write(f"\033[4:0mNone gy_ ")
        ctx.write(f"\033[4mSingle_ ")
        ctx.write(f"\033[9mStrike_ ")
        ctx.write(f"\033[0m({c})\n")

    # Change fg color while maintaining underline color.
    for s in [1, 2, 3, 4, 5]:
        ctx.write(f"\033[4:{s}m")
        for decor in ["255:0:0", "0:255:0", "0:0:255", ""]:
            ctx.write(f"\033[58:2:{decor}m" if decor else "\033[59m")
            for fg in ["255:0:0", "0:0:255", ""]:
                ctx.write(f"\033[38:2:{fg}m" if fg else "\033[39m")
                ctx.write("ygg_A ")
        ctx.write("\n")

    # Change underline color while maintaining fg color.
    for s in [1, 2, 3, 4, 5]:
        ctx.write(f"\033[4:{s}m")
        for fg in ["255:0:0", "0:0:255", ""]:
            ctx.write(f"\033[38:2:{fg}m" if fg else "\033[39m")
            for decor in ["255:0:0", "0:255:0", "0:0:255", ""]:
                ctx.write(f"\033[58:2:{decor}m" if decor else "\033[59m")
                ctx.write("ygg_A ")
        ctx.write("\n")

    # The threshold is very small because the underlines are very thin.
    ctx.take_screenshot("", diff_threshold=0.001)
