import click
import datetime
from tupimage.testing import TestingContext, screenshot_test
from tupimage import GraphicsTerminal

@screenshot_test
def test_text_printing(ctx: TestingContext):
    for i in range(24):
        ctx.write(str(i))
    ctx.write("This is a text-only test. If it fails, it means there is something wrong with how the terminal is configured (size, colors) or with the screenshot comparison algorithm.\n")
    for i in range(33, 127):
        ctx.write(chr(i))
    ctx.take_screenshot()

@screenshot_test
def test_text_colors(ctx: TestingContext):
    for i in range(16):
        for j in range(16):
            ctx.write(f"\033[48;5;{i}m\033[38;5;{j}m Aa ")
            ctx.write("\n")
    ctx.take_screenshot()

def validate_size(ctx, param, value: str):
    split_value = value.split("x")
    if len(split_value) != 2:
        raise click.BadParameter("Size must be specified as WxH")
    try:
        width = int(split_value[0])
        height = int(split_value[1])
    except ValueError:
        raise click.BadParameter("Size must be integer")
    if width < 1 or height < 1:
        raise click.BadParameter("Size must be positive")
    return (width, height)

@click.command()
@click.option("--term-size", default="80x24", callback=validate_size,
              type=str)
@click.option("--cell-size", "--screenshot-cell-size", default="4x8", callback=validate_size, type=str)
@click.option("--output-dir", "--output", "-o", default=None, type=str)
@click.option("--reference-dir", "--reference", "--ref", default=None, type=str)
@click.option("--data-dir", default=None, type=str)
@click.option("--pause", is_flag=True)
@click.argument("tests", nargs=-1, type=str)
def run_tests(term_size, cell_size, output_dir, reference_dir, data_dir, pause, tests):
    term = GraphicsTerminal()
    term.detect_tmux()
    size = term.get_size()
    if size[0] != term_size[0] or size[1] != term_size[1]:
        raise RuntimeError(f"The actual terminal size ({size[0]}x{size[1]}) does not match the expected size ({term_size[0]}x{term_size[1]})")
    if output_dir is None:
        now = datetime.datetime.now()
        date_time_string = now.strftime("%Y%m%d%H%M%S")
        output_dir = f".tupimage-testing/output-{term_size[0]}x{term_size[1]}-{cell_size[0]}x{cell_size[1]}-{date_time_string}"
    if data_dir is None:
        data_dir = f".tupimage-testing/data"
    ctx = TestingContext(term, output_dir=output_dir, reference_dir=reference_dir, data_dir=data_dir, term_size=term_size, screenshot_cell_size=cell_size)
    for func in TestingContext.all_tests:
        if getattr(func, "is_screenshot_test", False):
            func(ctx)
            if pause:
                ctx.term.wait_keypress()
    ctx.term.reset()

if __name__ == "__main__":
    run_tests()
