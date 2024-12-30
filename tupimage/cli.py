import argparse
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import tupimage
from tupimage.id_manager import IDFeatures
from tupimage.utils import *


def time_ago(dt: datetime) -> str:
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()
    minutes = seconds / 60
    hours = minutes / 60
    days = hours / 24
    weeks = days / 7
    months = days / 30
    years = days / 365

    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    elif minutes < 60:
        return f"{int(minutes)} minutes ago"
    elif hours < 24:
        return f"{int(hours)} hours ago"
    elif days < 7:
        return f"{int(days)} days ago"
    elif weeks < 4:
        return f"{int(weeks)} weeks ago"
    elif months < 12:
        return f"{int(months)} months ago"
    else:
        return f"{int(years)} years ago"


def icat(args):
    pass


def dump_config(args):
    tupiterm = tupimage.TupimageTerminal()
    print(tupiterm._config.to_toml_string(), end="")


def status(args):
    tupiterm = tupimage.TupimageTerminal()
    print(f"Config file: {tupiterm._config_file}")
    print(f"num_tmux_layers: {tupiterm.num_tmux_layers}")
    print(f"inside_ssh: {tupiterm.inside_ssh}")
    print(f"terminal_name: {tupiterm._terminal_name}")
    print(f"terminal_id: {tupiterm._terminal_id}")
    print(f"session_id: {tupiterm._session_id}")
    print(f"database_file: {tupiterm.id_manager.database_file}")
    print(f"Default ID space: {tupiterm.get_id_features()}")
    print(f"Default subspace: {tupiterm.get_subspace()}")
    print(f"Total IDs in the session db: {tupiterm.id_manager.count()}")
    print(
        f"IDs in the subspace: {tupiterm.id_manager.count(tupiterm.get_id_features(), tupiterm.get_subspace())}"
    )
    print(f"Supported formats: {tupiterm.get_supported_formats()}")
    print(f"Default uploading method: {tupiterm.get_upload_method()}")
    maxcols, maxrows = tupiterm.get_max_cols_and_rows()
    print(f"Max size in cells (cols x rows): {maxcols} x {maxrows}")
    cellw, cellh = tupiterm.get_cell_size()
    print(f"(Assumed) cell size in pixels (w x h): {cellw} x {cellh}")

    print(f"\nOther databases in {tupiterm._config.id_database_dir}")
    assert tupiterm._config.id_database_dir
    db_files = []
    for db_name in os.listdir(tupiterm._config.id_database_dir):
        db_path = os.path.join(tupiterm._config.id_database_dir, db_name)
        if os.path.isfile(db_path):
            atime = os.path.getatime(db_path)
            size_kib = os.path.getsize(db_path) // 1024
            db_files.append((db_name, atime, size_kib))

    # Sort by atime in descending order
    db_files.sort(key=lambda x: x[1], reverse=True)

    for db_name, atime, size_kib in db_files:
        print(f"  {db_name}  (atime: {time.ctime(atime)}, size: {size_kib} KiB)")


def printerr(tupiterm: tupimage.TupimageTerminal, msg):
    print(msg, file=sys.stderr)


def parse_as_id(image: str) -> Optional[int]:
    """Parse the argument as an ID of one of the following forms:
    - A decimal number
    - A hexadecimal number starting with '0x'
    - 'id:' followed by a number
    """
    if image.startswith("id:"):
        return parse_as_id(image[3:])
    try:
        if image.startswith("0x"):
            return int(image, 16)
        return int(image)
    except ValueError:
        return None


def display(args):
    tupiterm = tupimage.TupimageTerminal()
    errors = False
    for image in args.images:
        if not os.path.exists(image):
            id = parse_as_id(image)
            if id is not None:
                inst = tupiterm.get_image_instance(id)
                if inst is None:
                    printerr(
                        tupiterm, f"ID is not assigned or assignment is broken: {id}"
                    )
                    errors = True
                    continue
                tupiterm.upload_and_display(inst)
                continue
        try:
            tupiterm.upload_and_display(image)
        except FileNotFoundError:
            printerr(tupiterm, f"File not found: {image}")
            errors = True
    if errors:
        sys.exit(1)


def list_images(command, max_cols, max_rows):
    _ = command
    tupiterm = tupimage.TupimageTerminal(
        config_overrides={"max_cols": max_cols, "max_rows": max_rows}
    )
    max_cols, max_rows = tupiterm.get_max_cols_and_rows()
    for iminfo in tupiterm.id_manager.get_all():
        id = iminfo.id
        space = str(IDFeatures.from_id(id))
        subspace_byte = IDFeatures.get_subspace_byte(id)
        ago = time_ago(iminfo.atime)
        print(
            f"\033[1mID: {id}\033[0m ({hex(id)}) space: {space} subspace_byte: {subspace_byte} atime: {iminfo.atime} ({ago})"
        )
        print(f"  {iminfo.description}")
        uploads = tupiterm.id_manager.get_upload_infos(id)
        for upload in uploads:
            needs_uploading = ""
            if tupiterm.needs_uploading(id):
                needs_uploading = "\033[1mNEEDS UPLOADING\033[0m "
            print(
                f"  {needs_uploading}Uploaded to {upload.terminal}"
                f" at {upload.upload_time} ({time_ago(upload.upload_time)})"
                f"  size: {upload.size} bytes"
                f" bytes_ago: {upload.bytes_ago} uploads_ago: {upload.uploads_ago}"
            )
            if upload.id != id:
                print(f"    \033[1m\033[38;5;1mINVALID ID! {upload.id} != {id}\033[0m")
            if upload.description != iminfo.description:
                print(
                    f"    \033[1m\033[38;5;1mINVALID DESCRIPTION! {upload.description} != {iminfo.description}\033[0m"
                )
            inst = tupiterm.get_image_instance(id)
            if inst is None:
                print(
                    f"    \033[1m\033[38;5;1mCOULD NOT PARSE THE IMAGE DESCRIPTION!\033[0m"
                )
            else:
                if inst.cols > max_cols or inst.rows > max_rows:
                    print(
                        f"  Note: cropped to {min(inst.cols, max_cols)}x{min(inst.rows, max_rows)}"
                    )
                tupiterm.display_only(
                    inst, end_col=max_cols, end_row=max_rows, allow_expansion=False
                )
            print("-" * min(max_cols, 80))


def main():
    parser = argparse.ArgumentParser(
        description="", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_dump_config = subparsers.add_parser(
        "dump-config", help="Dump the config state."
    )

    parser_status = subparsers.add_parser("status", help="Display the status.")

    parser_display = subparsers.add_parser("display", help="Display an image.")

    parser_upload = subparsers.add_parser(
        "upload", help="Upload an image without displaying."
    )

    parser_assign_id = subparsers.add_parser(
        "assign-id",
        help="Assigns an id to an image without displaying or uploading it.",
    )

    parser_list = subparsers.add_parser(
        "list",
        help="List all known images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_list.add_argument(
        "--max-cols",
        type=str,
        default="auto",
        help="Maximum number of columns to display each listed image. 'auto' to use the terminal width.",
    )
    parser_list.add_argument(
        "--max-rows",
        type=str,
        default="4",
        help="Maximum number of rows to display each listed image. 'auto' to use the terminal height.",
    )

    for p in [parser_display, parser_upload, parser_assign_id]:
        p.add_argument("images", nargs="*", type=str)

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
        help=("Time to wait for a response when detecting image display support."),
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
        help=("Surround graphics commands with escape sequences for passthrough."),
    )
    parser_icat.add_argument(
        "--image-id",
        nargs="?",
        default=None,
        type=int,
        help="The image id to use.",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Execute the function associated with the chosen subcommand
    if args.command == "icat":
        icat(args)
    elif args.command == "dump-config":
        dump_config(args)
    elif args.command == "status":
        status(args)
    elif args.command == "display":
        display(args)
    elif args.command == "list":
        list_images(**vars(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
