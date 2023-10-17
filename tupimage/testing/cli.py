import datetime
from fnmatch import fnmatch
from typing import List
import click

import tupimage
from tupimage import GraphicsTerminal
from tupimage.testing import (
    TestingContext,
    test_basics,
    test_placement,
    test_uploading,
    test_response,
    test_deletion,
)


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


def is_test_enabled(funcname, tests: List[str]):
    name = funcname[5:] if funcname.startswith("test_") else funcname
    for test in tests:
        if fnmatch(name, test) or fnmatch(funcname, test):
            return True
    return False


@click.command()
@click.option("--term-size", default="80x24", callback=validate_size, type=str)
@click.option(
    "--cell-size",
    "--screenshot-cell-size",
    default="4x8",
    callback=validate_size,
    type=str,
)
@click.option("--ignore-size", is_flag=True)
@click.option("--output-dir", "--output", "-o", default=None, type=str)
@click.option("--reference-dir", "--reference", "--ref", default=None, type=str)
@click.option("--data-dir", default=None, type=str)
@click.option("--pause", is_flag=True)
@click.option("--list", "--ls", "-l", is_flag=True)
@click.argument("tests", nargs=-1, type=str)
def run_tests(
    term_size,
    cell_size,
    ignore_size,
    output_dir,
    reference_dir,
    data_dir,
    pause,
    list,
    tests,
):
    term = GraphicsTerminal()
    term.detect_tmux()
    real_term_size = term.get_size()
    real_cell_size = term.get_cell_size()
    if not ignore_size:
        if (
            real_term_size[0] != term_size[0]
            or real_term_size[1] != term_size[1]
        ):
            raise RuntimeError(
                "The actual terminal size"
                f" ({real_term_size[0]}x{real_term_size[1]}) does not match the"
                f" expected size ({term_size[0]}x{term_size[1]})"
            )
        if (
            not real_cell_size
            or abs(
                real_cell_size[0] / real_cell_size[1]
                - cell_size[0] / cell_size[1]
            )
            > 0.01
        ):
            raise RuntimeError(
                "The actual terminal cell proportions"
                f" ({real_cell_size[0]}x{real_cell_size[1]}) do not match the"
                " expected cell size proportions"
                f" ({cell_size[0]}x{cell_size[1]})"
            )
    if output_dir is None:
        now = datetime.datetime.now()
        date_time_string = now.strftime("%Y%m%d%H%M%S")
        output_dir = (
            ".tupimage-testing/output-"
            f"{term_size[0]}x{term_size[1]}-"
            f"{cell_size[0]}x{cell_size[1]}-{date_time_string}"
        )
    if data_dir is None:
        data_dir = f".tupimage-testing/data"
    ctx = TestingContext(
        term,
        output_dir=output_dir,
        reference_dir=reference_dir,
        data_dir=data_dir,
        term_size=term_size,
        screenshot_cell_size=cell_size,
        pause_after_screenshot=pause,
    )
    ran_any_tests = False
    with ctx.term.guard_tty_settings():
        ctx.term.set_immediate_input_noecho()
        for name, func in TestingContext.all_tests:
            if is_test_enabled(name, tests):
                if list:
                    print(name)
                else:
                    ran_any_tests = True
                    func(ctx)
    if not list:
        ctx.term.reset()
        if ran_any_tests:
            ctx.print_results()
        else:
            print("No tests were run.")


if __name__ == "__main__":
    run_tests()
