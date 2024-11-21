import argparse
import datetime
import os
import warnings
from fnmatch import fnmatch
from typing import List

import tupimage
from tupimage import GraphicsTerminal
from tupimage.testing import TestingContext
from tupimage.utils import validate_size

# isort: off
from tupimage.testing import (
    test_basics,
    test_placement,
    test_uploading,
    test_response,
    test_deletion,
    test_placeholder,
    test_tupimage_terminal,
)

# isort: on


def is_test_matching(funcname, tests: List[str]) -> bool:
    name = funcname[5:] if funcname.startswith("test_") else funcname
    for test in tests:
        if fnmatch(name, test) or fnmatch(funcname, test):
            return True
    return False


def list_tests(args):
    if not args.tests:
        args.tests = ["*"]
    for name, func in TestingContext.all_tests:
        if is_test_matching(name, args.tests) and not is_test_matching(
            name, args.exclude
        ):
            print(name)


def run(args):
    warnings.filterwarnings("ignore")
    term = GraphicsTerminal()
    term.detect_tmux()
    real_term_size = term.get_size()
    real_cell_size = term.get_cell_size()
    if args.dump_shell_script:
        term.shellscript_out = open(args.dump_shell_script, "w")
        term.shellscript_out.write("#!/bin/sh\n\n")
    if not args.ignore_size:
        if (
            real_term_size[0] != args.term_size[0]
            or real_term_size[1] != args.term_size[1]
        ):
            raise RuntimeError(
                "The actual terminal size"
                f" ({real_term_size[0]}x{real_term_size[1]}) does not match the"
                f" expected size ({args.term_size[0]}x{args.term_size[1]})"
            )
        if (
            not real_cell_size
            or abs(
                real_cell_size[0] / real_cell_size[1]
                - args.cell_size[0] / args.cell_size[1]
            )
            > 0.01
        ):
            raise RuntimeError(
                "The actual terminal cell proportions"
                f" ({real_cell_size[0]}x{real_cell_size[1]}) do not match the"
                " expected cell size proportions"
                f" ({args.cell_size[0]}x{args.cell_size[1]})"
            )
    if args.output_dir is None:
        now = datetime.datetime.now()
        date_time_string = now.strftime("%Y%m%d%H%M%S")
        os.makedirs(".tupimage-testing", exist_ok=True)
        output_dir_name = (
            "output-"
            f"{args.term_size[0]}x{args.term_size[1]}-"
            f"{args.cell_size[0]}x{args.cell_size[1]}-{date_time_string}"
        )
        latest_link = ".tupimage-testing/latest"
        if os.path.lexists(latest_link) and os.path.islink(latest_link):
            os.remove(latest_link)
        if not os.path.lexists(latest_link):
            os.symlink(output_dir_name, latest_link)
        args.output_dir = f".tupimage-testing/{output_dir_name}"
    if os.path.exists(args.output_dir) and os.listdir(args.output_dir):
        raise RuntimeError(
            f"Output directory {args.output_dir} already exists and is not empty."
        )
    if args.data_dir is None:
        args.data_dir = f".tupimage-testing/data"
    ctx = TestingContext(
        term,
        output_dir=args.output_dir,
        data_dir=args.data_dir,
        term_size=args.term_size,
        screenshot_cell_size=args.cell_size,
        pause_after_screenshot=args.pause,
        take_screenshots=not args.no_screenshots,
        reset_before_test=not args.no_reset,
    )
    if not args.tests:
        args.tests = ["*"]
    ran_any_tests = False
    with ctx.term.guard_tty_settings():
        ctx.term.set_immediate_input_noecho()
        skipping = True
        for name, func in TestingContext.all_tests:
            if skipping and args.start:
                if is_test_matching(name, args.start or []):
                    skipping = False
                else:
                    continue
            if is_test_matching(name, args.tests) and not is_test_matching(
                name, args.exclude or []
            ):
                ran_any_tests = True
                func(ctx)
                ctx.dump_unexpected_responses()
    if not args.no_reset:
        ctx.term.reset()
    if ran_any_tests:
        ctx.print_results()
    else:
        print("No tests were run.")


def compare(args):
    outdir = os.path.dirname(args.output)
    if outdir:
        os.chdir(outdir)
    report = tupimage.testing.create_screenshot_comparison_report(
        args.test_output, args.reference
    )
    with open(args.output, "w") as f:
        f.write(report.to_html())


def main():
    parser = argparse.ArgumentParser(description="")
    subparsers = parser.add_subparsers(dest="command")

    parser_run = subparsers.add_parser("run", help="Run tests.")
    parser_run.add_argument("--term-size", default="80x24", type=validate_size)
    parser_run.add_argument("--cell-size", default="4x8", type=validate_size)
    parser_run.add_argument("--ignore-size", action="store_true")
    parser_run.add_argument("--output-dir", "-o", default=None, type=str)
    parser_run.add_argument("--data-dir", default=None, type=str)
    parser_run.add_argument("--pause", action="store_true")
    parser_run.add_argument("--no-screenshots", action="store_true")
    parser_run.add_argument("--no-reset", action="store_true")
    parser_run.add_argument("--dump-shell-script", "--sh", default=None, type=str)
    parser_run.add_argument("--exclude", nargs="*", type=str)
    parser_run.add_argument("--start", nargs="*", type=str)
    parser_run.add_argument("tests", nargs="*", type=str)
    parser_run.set_defaults(func=run)

    parser_list = subparsers.add_parser("list", help="List tests.")
    parser_list.add_argument("--exclude", nargs="*", type=str)
    parser_list.add_argument("tests", nargs="*", type=str)
    parser_list.set_defaults(func=list_tests)

    parser_compare = subparsers.add_parser(
        "compare", help="Compare two test outputs and create a report."
    )
    parser_compare.add_argument("--output", "-o", type=str)
    parser_compare.add_argument("test_output", type=str)
    parser_compare.add_argument("reference", type=str)
    parser_compare.set_defaults(func=compare)

    # Parse the arguments
    args = parser.parse_args()

    # Execute the function associated with the chosen subcommand
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
