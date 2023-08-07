import click
import datetime
from tupimage.testing import TestingContext, screenshot_test
from tupimage import GraphicsTerminal, TransmitCommand, PutCommand
import tupimage
from typing import List
from fnmatch import fnmatch

@screenshot_test
def test_text_printing(ctx: TestingContext):
    for i in range(24):
        ctx.write(str(i) + "\n")
    ctx.write("This is a text-only test. If it fails, it means there is something wrong with how the terminal is configured (size, colors) or with the screenshot comparison algorithm.\n")
    for i in range(33, 127):
        ctx.write(chr(i))
    ctx.take_screenshot("Some text and all printable ascii characters. The text should be at the bottom of the screen.")

@screenshot_test
def test_text_colors(ctx: TestingContext):
    for i in range(16):
        for j in range(16):
            ctx.write(f"\033[48;5;{i}m\033[38;5;{j}m Aa ")
        ctx.write("\n")
    ctx.take_screenshot("")

@screenshot_test
def test_nonplaceholder(ctx: TestingContext):
    cmd = TransmitCommand(image_id=1, medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_wikipedia_png()).set_placement(rows=10, columns=20))
    ctx.take_screenshot("Wikipedia logo. May be slightly stretched on kitty.")
    ctx.term.move_cursor(up=9)
    ctx.term.send_command(cmd.clone_with(image_id=2).set_filename(ctx.get_column_png()).set_placement(rows=10, columns=5))
    ctx.term.move_cursor(up=9)
    ctx.term.send_command(PutCommand(image_id=1, rows=10, columns=20, quiet=1))
    ctx.term.move_cursor(up=9)
    ctx.term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1))
    ctx.term.move_cursor(left=10, down=1)
    ctx.term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1))
    ctx.take_screenshot("Wikipedia logo and some columns.")

@screenshot_test
def test_nonplaceholder_nomovecursor(ctx: TestingContext):
    cmd = TransmitCommand(image_id=1, medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_wikipedia_png()).set_placement(rows=10, columns=20, do_not_move_cursor=True))
    ctx.take_screenshot("Wikipedia logo (slightly stretched on kitty). The cursor should be at the top left corner.")
    ctx.term.move_cursor(right=20)
    ctx.term.send_command(cmd.clone_with(image_id=2).set_filename(ctx.get_column_png()).set_placement(rows=10, columns=5, do_not_move_cursor=True))
    ctx.term.move_cursor(right=5)
    ctx.term.send_command(PutCommand(image_id=1, rows=10, columns=20, quiet=1, do_not_move_cursor=True))
    ctx.term.move_cursor(right=20)
    ctx.term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1, do_not_move_cursor=True))
    ctx.term.move_cursor(down=5)
    ctx.term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1, do_not_move_cursor=True))
    ctx.take_screenshot("Wikipedia logo and some columns. The cursor should be at the top left corner of the last column image.")

@screenshot_test
def test_nonplaceholder_multisize(ctx: TestingContext):
    cmd = TransmitCommand(medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(1, 5):
        start_col = 0
        for c in range(1, 10):
            ctx.term.move_cursor_abs(col=start_col)
            ctx.term.send_command(PutCommand(image_id=1, rows=r, columns=c, quiet=1, do_not_move_cursor=True))
            start_col += c
        ctx.term.move_cursor_abs(col=0)
        ctx.term.move_cursor(down=r)
    ctx.take_screenshot("A grid of penguins of various sizes. On kitty they may be stretched.")

@screenshot_test
def test_nonplaceholder_oob(ctx: TestingContext):
    cmd = TransmitCommand(medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_ruler_png()))
    for r in range(24):
        ctx.term.move_cursor_abs(row=r, col=80 - (24 - r))
        ctx.term.send_command(PutCommand(image_id=1, rows=1, columns=24, quiet=1, do_not_move_cursor=True))
    ctx.term.move_cursor_abs(row=0, col=0)
    ctx.take_screenshot("A ruler that goes off the screen. Not to scale.")

@screenshot_test
def test_nonplaceholder_oob_down(ctx: TestingContext):
    cmd = TransmitCommand(medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(3):
        ctx.term.send_command(PutCommand(image_id=1, rows=10, columns=20, quiet=1, do_not_move_cursor=False))
    ctx.take_screenshot("Three penguins, arranged diagonally. The top one is cut off.")

@screenshot_test
def test_nonplaceholder_oob_down_nomovecursor(ctx: TestingContext):
    cmd = TransmitCommand(medium=tupimage.TransmissionMedium.FILE, quiet=tupimage.Quietness.QUIET_UNLESS_ERROR, format=tupimage.Format.PNG)
    ctx.term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(3):
        ctx.term.send_command(PutCommand(image_id=1, rows=10, columns=20, quiet=1, do_not_move_cursor=True))
        ctx.term.move_cursor(down=10)
    ctx.take_screenshot("Three penguins arranged vertially. The bottom one is cut off because the terminal shouldn't introduce new lines when C=1.")

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

def is_test_enabled(func, tests: List[str]):
    funcname = func.__name__
    name = funcname[5:] if funcname.startswith("test_") else funcname
    for test in tests:
        if fnmatch(name, test) or fnmatch(funcname, test):
            return True
    return False

@click.command()
@click.option("--term-size", default="80x24", callback=validate_size,
              type=str)
@click.option("--cell-size", "--screenshot-cell-size", default="4x8", callback=validate_size, type=str)
@click.option("--ignore-size", is_flag=True)
@click.option("--output-dir", "--output", "-o", default=None, type=str)
@click.option("--reference-dir", "--reference", "--ref", default=None, type=str)
@click.option("--data-dir", default=None, type=str)
@click.option("--pause", is_flag=True)
@click.argument("tests", nargs=-1, type=str)
def run_tests(term_size, cell_size, ignore_size, output_dir, reference_dir, data_dir, pause, tests):
    term = GraphicsTerminal()
    term.detect_tmux()
    real_term_size = term.get_size()
    real_cell_size = term.get_cell_size()
    if not ignore_size:
        if real_term_size[0] != term_size[0] or real_term_size[1] != term_size[1]:
            raise RuntimeError(f"The actual terminal size ({real_term_size[0]}x{real_term_size[1]}) does not match the expected size ({term_size[0]}x{term_size[1]})")
        if not real_cell_size or abs(real_cell_size[0]/real_cell_size[1] - cell_size[0]/cell_size[1]) > 0.01:
            raise RuntimeError(f"The actual terminal cell proportions ({real_cell_size[0]}x{real_cell_size[1]}) do not match the expected cell size proportions ({cell_size[0]}x{cell_size[1]})")
    if output_dir is None:
        now = datetime.datetime.now()
        date_time_string = now.strftime("%Y%m%d%H%M%S")
        output_dir = f".tupimage-testing/output-{term_size[0]}x{term_size[1]}-{cell_size[0]}x{cell_size[1]}-{date_time_string}"
    if data_dir is None:
        data_dir = f".tupimage-testing/data"
    ctx = TestingContext(term, output_dir=output_dir, reference_dir=reference_dir, data_dir=data_dir, term_size=term_size, screenshot_cell_size=cell_size, pause_after_screenshot=pause)
    for func in TestingContext.all_tests:
        if getattr(func, "is_screenshot_test", False) and is_test_enabled(func, tests):
            func(ctx)
    ctx.term.reset()

if __name__ == "__main__":
    run_tests()
