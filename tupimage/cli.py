import argparse
from tupimage.utils import *


def icat(args):
    pass


def main():
    parser = argparse.ArgumentParser(description="")
    subparsers = parser.add_subparsers(dest="command")

    parser_icat = subparsers.add_parser(
        "icat", help="A CLI compatible with the icat kitten."
    )
    parser_icat.add_argument(
        "--place",
        type=validate_place,
        help=(
            "Where on the screen to display the image. The syntax is"
            " <width>x<height>@<left>x<top>."
        ),
    )
    parser_icat.add_argument(
        "--scale-up",
        action="store_true",
        help="Scale up images smaller than the specified area.",
    )
    parser_icat.add_argument(
        "--background",
        nargs="?",
        default="none",
        type=str,
        help="Background color.",
    )
    parser_icat.add_argument(
        "--mirror",
        nargs="?",
        default="none",
        choices=["none", "both", "horizontal", "vertical"],
        help="Mirror the image.",
    )
    parser_icat.add_argument(
        "--clear",
        action="store_true",
        help="Remove all images currently displayed on the screen.",
    )
    parser_icat.add_argument(
        "--transfer-mode",
        nargs="?",
        default="detect",
        choices=["detect", "file", "memory", "stream"],
        help="Mechanism to use to transfer images to the terminal.",
    )
    parser_icat.add_argument(
        "--detect-support",
        action="store_true",
        help="Detect support for image display in the terminal.",
    )
    parser_icat.add_argument(
        "--detection-timeout",
        nargs="?",
        default=10,
        type=int,
        help=(
            "Time to wait for a response when detecting image display support."
        ),
    )
    parser_icat.add_argument(
        "--print-window-size",
        action="store_true",
        help="Print out the window size and quit.",
    )
    parser_icat.add_argument(
        "--stdin",
        nargs="?",
        default="detect",
        choices=["detect", "no", "yes"],
        help="Read image data from STDIN.",
    )
    parser_icat.add_argument("--silent", action="store_true", help="Not used")
    parser_icat.add_argument(
        "--engine", nargs="?", default="auto", type=str, help="Not used"
    )
    parser_icat.add_argument(
        "--z-index",
        "-z",
        nargs="?",
        default=0,
        type=int,
        help="Z-index of the image.",
    )
    parser_icat.add_argument(
        "--loop",
        "-l",
        nargs="?",
        default=-1,
        type=int,
        help="Number of times to loop animations.",
    )
    parser_icat.add_argument(
        "--hold",
        action="store_true",
        help="Wait for a key press before exiting.",
    )
    parser_icat.add_argument(
        "--unicode-placeholder",
        action="store_true",
        help="Use the Unicode placeholder method to display the images.",
    )
    parser_icat.add_argument(
        "--passthrough",
        nargs="?",
        default="detect",
        choices=["detect", "none", "tmux"],
        help=(
            "Surround graphics commands with escape sequences for passthrough."
        ),
    )
    parser_icat.add_argument(
        "--image-id",
        nargs="?",
        default=None,
        type=int,
        help="The image id to use.",
    )
    parser_icat.set_defaults(func=icat)

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
