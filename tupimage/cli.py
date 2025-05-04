import argparse
import os
import sys
import time
from datetime import datetime
from typing import Optional, List

import tupimage
from tupimage.id_manager import IDSpace, IDSubspace
from tupimage.tupimage_terminal import ImageInstance
from tupimage.utils import *


class CLIArgumentsError(Exception):
    """Custom exception for CLI argument errors."""

    pass


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


def dump_config(command: str, provenance: bool, skip_default: bool):
    _ = command
    tupiterm = tupimage.TupimageTerminal()
    toml_str = tupiterm._config.to_toml_string(
        with_provenance=provenance, skip_default=skip_default
    )
    print(toml_str, end="")


def status(command: str):
    _ = command
    tupiterm = tupimage.TupimageTerminal()
    print(f"Config file: {tupiterm._config_file}")
    print(f"num_tmux_layers: {tupiterm.num_tmux_layers}")
    print(f"inside_ssh: {tupiterm.inside_ssh}")
    print(f"terminal_name: {tupiterm._terminal_name}")
    print(f"terminal_id: {tupiterm._terminal_id}")
    print(f"session_id: {tupiterm._session_id}")
    print(f"database_file: {tupiterm.id_manager.database_file}")
    print(f"Default ID space: {tupiterm.get_id_space()}")
    print(f"Default subspace: {tupiterm.get_subspace()}")
    print(f"Total IDs in the session db: {tupiterm.id_manager.count()}")
    print(
        f"IDs in the subspace: {tupiterm.id_manager.count(tupiterm.get_id_space(), tupiterm.get_subspace())}"
    )
    print(f"Supported formats: {tupiterm.get_supported_formats()}")
    print(f"Default uploading method: {tupiterm.get_upload_method()}")
    maxcols, maxrows = tupiterm.get_max_cols_and_rows()
    print(f"Max size in cells (cols x rows): {maxcols} x {maxrows}")
    cellw, cellh = tupiterm.get_cell_size()
    print(f"(Assumed) cell size in pixels (w x h): {cellw} x {cellh}")

    print(f"\nAll databases in {tupiterm._config.id_database_dir}")
    assert tupiterm._config.id_database_dir
    db_files = []
    for db_name in os.listdir(tupiterm._config.id_database_dir):
        db_path = os.path.join(tupiterm._config.id_database_dir, db_name)
        if os.path.isfile(db_path) and db_name.endswith(".db"):
            atime = os.path.getatime(db_path)
            size_kib = os.path.getsize(db_path) // 1024
            db_files.append((db_name, atime, size_kib))

    # Sort by atime in descending order
    db_files.sort(key=lambda x: x[1], reverse=True)

    for db_name, atime, size_kib in db_files:
        print(f"  {db_name}  (atime: {time.ctime(atime)}, size: {size_kib} KiB)")


def printerr(tupiterm: tupimage.TupimageTerminal, msg):
    tupiterm.term.out_display.flush()
    print(msg, file=sys.stderr, flush=True)


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


def handle_command(
    command: str,
    images: List[str],
    rows: Optional[int],
    cols: Optional[int],
    force_upload: bool,
    no_upload: bool,
    out_display: str,
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    use_line_feeds: str,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
    upload_method: Optional[str],
):
    tupiterm = tupimage.TupimageTerminal(
        out_display=out_display if out_display else None,
        config_overrides={
            "force_upload": force_upload,
            "max_cols": max_cols,
            "max_rows": max_rows,
            "scale": scale,
            "id_space": id_space,
            "id_subspace": id_subspace,
            "upload_method": upload_method,
            "provenance": "set via command line",
        },
    )
    if dump_config:
        print(tupiterm._config.to_toml_string(with_provenance=True), end="")
    errors = False

    if use_line_feeds == "auto" and not tupiterm.term.out_display.isatty():
        use_line_feeds = "yes"

    if len(images) > 1 and force_id is not None:
        raise CLIArgumentsError(
            "Cannot use --force-id and specify multiple images at the same time."
        )

    for image in images:
        # Handle the case where image is an id, not a filename.
        if not os.path.exists(image):
            id = parse_as_id(image)
            if id is not None:
                if force_id is not None:
                    raise CLIArgumentsError(
                        "Cannot use --force-id and specify an ID at the same time."
                    )
                # image is ImageInstance from now on (containing id, rows and cols).
                image = tupiterm.get_image_instance(id)
                if image is None:
                    printerr(
                        tupiterm,
                        f"error: ID is not assigned or assignment is broken: {id}",
                    )
                    errors = True
                    continue
        # Handle the command itself. Don't stop on errors.
        try:
            if command == "display" and not no_upload:
                tupiterm.upload_and_display(
                    image,
                    rows=rows,
                    cols=cols,
                    use_line_feeds=(use_line_feeds == "yes"),
                    force_id=force_id,
                )
            elif command == "upload":
                tupiterm.upload(
                    image,
                    rows=rows,
                    cols=cols,
                    force_id=force_id,
                )
            elif command == "get-id" or (command == "display" and no_upload):
                if isinstance(image, ImageInstance):
                    instance = image
                else:
                    instance = tupiterm.assign_id(
                        image,
                        rows=rows,
                        cols=cols,
                        force_id=force_id,
                    )
                if command == "get-id":
                    print(instance.id)
                if command == "display":
                    tupiterm.display_only(
                        instance,
                        use_line_feeds=(use_line_feeds == "yes"),
                    )
        except (FileNotFoundError, OSError) as e:
            printerr(tupiterm, f"error: Failed to upload {image}: {e}")
            errors = True
    if errors:
        sys.exit(1)


def display(
    command: str,
    images: List[str],
    rows: Optional[int],
    cols: Optional[int],
    force_upload: bool,
    no_upload: bool,
    out_display: str,
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    use_line_feeds: str,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
    upload_method: Optional[str],
):
    handle_command(
        command=command,
        images=images,
        rows=rows,
        cols=cols,
        force_upload=force_upload,
        no_upload=no_upload,
        out_display=out_display,
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds=use_line_feeds,
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=upload_method,
    )


def upload(
    command: str,
    images: List[str],
    rows: Optional[int],
    cols: Optional[int],
    force_upload: bool,
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
    upload_method: Optional[str],
):
    handle_command(
        command=command,
        images=images,
        rows=rows,
        cols=cols,
        force_upload=force_upload,
        no_upload=False,
        out_display="",
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds="no",
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=upload_method,
    )


def get_id(
    command: str,
    images: List[str],
    rows: Optional[int],
    cols: Optional[int],
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
):
    handle_command(
        command=command,
        images=images,
        rows=rows,
        cols=cols,
        force_upload=False,
        no_upload=True,
        out_display="",
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds="no",
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=None,
    )


def placeholder(
    command: str,
    id: List[str],
    rows: int,
    cols: int,
    out_display: str,
    dump_config: bool,
    use_line_feeds: str,
):
    _ = command
    tupiterm = tupimage.TupimageTerminal(
        out_display=out_display if out_display else None,
        config_overrides={
            "provenance": "set via command line",
        },
    )
    if dump_config:
        print(tupiterm._config.to_toml_string(with_provenance=True), end="")

    id_int = parse_as_id(id[0])
    if id_int is None:
        printerr(tupiterm, f"error: ID is incorrect: {id[0]}")
        exit(1)

    if use_line_feeds == "auto" and not tupiterm.term.out_display.isatty():
        use_line_feeds = "yes"

    tupiterm.display_only(
        id_int,
        end_col=cols,
        end_row=rows,
        use_line_feeds=(use_line_feeds == "yes"),
    )


def foreach(
    command: str,
    images: List[str],
    all: bool,
    dump_config: bool,
    use_line_feeds: str = "no",
    older: Optional[str] = None,
    newer: Optional[str] = None,
    last: Optional[int] = None,
    except_last: Optional[int] = None,
    max_cols: Optional[str] = None,
    max_rows: Optional[str] = None,
    out_display: str = "",
    verbose: bool = False,
    quiet: bool = False,
    upload_method: Optional[str] = None,
):
    query_specified = older or newer or last or except_last
    if (images or query_specified) and all:
        raise CLIArgumentsError(
            "Cannot use --all and specify images/ids or queries at the same time."
        )

    if not (images or query_specified) and not all:
        if command == "list":
            all = True
        else:
            raise CLIArgumentsError(
                "You must specify images/ids or a query or use --all to affect all images."
            )

    if images and query_specified:
        raise CLIArgumentsError(
            "Cannot specify images/ids and queries at the same time."
        )

    # Parse query arguments.
    older_dt = datetime.fromisoformat(older) if older else None
    newer_dt = datetime.fromisoformat(newer) if newer else None

    tupiterm = tupimage.TupimageTerminal(
        out_display=out_display if out_display else None,
        config_overrides={
            "max_cols": max_cols,
            "max_rows": max_rows,
            "upload_method": upload_method,
            "provenance": "set via command line",
        },
    )
    if dump_config:
        print(tupiterm._config.to_toml_string(with_provenance=True), end="")
    max_cols_int, max_rows_int = tupiterm.get_max_cols_and_rows()

    if use_line_feeds == "auto" and not tupiterm.term.out_display.isatty():
        use_line_feeds = "yes"

    # A set of IDs and filenames we haven't encountered yet.
    not_encountered = []
    # Split `images` into a list of image filenames and a list of IDs.
    image_filenames = []
    image_ids = []
    for image in images:
        if not os.path.exists(image):
            id = parse_as_id(image)
            if id is not None:
                image_ids.append(id)
                not_encountered.append(id)
                continue
        # Note that we need to absolutize the path.
        image = os.path.abspath(image)
        image_filenames.append(image)
        not_encountered.append(image)

    # The filtered list of image infos.
    image_infos = []

    # Get all image infos from the ID manager and filter them.
    # TODO: It's better to build sql queries, of course.
    index = 0
    for iminfo in tupiterm.id_manager.get_all():
        if all:
            image_infos.append(iminfo)
            continue
        matches = False
        # Check if the ID is in the list.
        id = iminfo.id
        if id in image_ids:
            not_encountered = [x for x in not_encountered if x != id]
            matches = True
        # Then check if the filename is in the list.
        if image_filenames:
            inst = ImageInstance.from_info(iminfo)
            if inst and inst.path in image_filenames:
                not_encountered = [x for x in not_encountered if x != inst.path]
                matches = True
        # If the image matched an ID or a filename, add it to the list.
        if matches:
            image_infos.append(iminfo)
            continue
        # Then check the query.
        if not query_specified:
            continue
        if newer_dt and iminfo.atime <= newer_dt:
            # Images are sorted by atime, so we can stop here.
            break
        if older_dt and iminfo.atime >= older_dt:
            continue
        index += 1
        if last and index > last:
            break
        if except_last and index <= except_last:
            continue
        image_infos.append(iminfo)

    # Whether we should exit with an error code.
    errors = False

    # Print errors if some of the explicitly specified images were not found.
    for img in not_encountered:
        if isinstance(img, int):
            printerr(tupiterm, f"error: ID not found in the db: {img}")
        else:
            printerr(tupiterm, f"error: Image not found in the db: {img}")
        errors = True

    # Note that if we mix images and text, we should write to the same stream object,
    # otherwise there is a risk of buffering issues.
    write = tupiterm.term.write

    # Now process the images.
    for iminfo in image_infos:
        inst = ImageInstance.from_info(iminfo)
        id = iminfo.id

        if command == "forget":
            tupiterm.id_manager.del_id(id)

        if command == "dirty":
            tupiterm.id_manager.mark_dirty(id)

        if command == "reupload" or command == "fix":
            if inst is None:
                printerr(
                    tupiterm, f"error: ID is not assigned or assignment is broken: {id}"
                )
                errors = True
                continue
            # 'fix' is like 'reupload', but avoids unnecessary uploads.
            if command == "fix" and not tupiterm.needs_uploading(id):
                continue
            # Don't fail other uploads if one fails, but print the error message
            try:
                tupiterm.upload(inst, force_upload=True, update_atime=False)
            except (FileNotFoundError, OSError) as e:
                printerr(tupiterm, f"error: Failed to upload {id} {inst.path}: {e}")
                errors = True
                continue

        if quiet:
            continue

        # If it's not a verbose mode of 'list', just print some basic info.
        if not verbose:
            if command != "list":
                write(f"{command} ")
            if inst is None:
                write(f"{id}\t?x?\t{iminfo.description}\n")
                continue
            write(f"{id}\t{inst.cols}x{inst.rows}\t{inst.path}\n")
            continue

        # Otherwise print more details and several rows of the image.
        space = str(IDSpace.from_id(id))
        subspace_byte = IDSpace.get_subspace_byte(id)
        ago = time_ago(iminfo.atime)
        write(
            f"\033[1mID: {id}\033[0m = 0x{id:08x} id_space: {space} subspace_byte: {subspace_byte} = 0x{subspace_byte:02x} atime: {iminfo.atime} ({ago})\n"
        )
        write(f"  {iminfo.description}\n")
        if tupiterm.needs_uploading(id):
            write(f"  \033[1mNEEDS UPLOADING\033[0m to {tupiterm._terminal_id}\n")
        uploads = tupiterm.id_manager.get_upload_infos(id)
        for upload in uploads:
            needs_uploading = ""
            if tupiterm.needs_uploading(upload):
                needs_uploading = "(Needs reuploading) "
            write(
                f"  {needs_uploading}Uploaded to {upload.terminal}"
                f" at {upload.upload_time} ({time_ago(upload.upload_time)})"
                f"  size: {upload.size} bytes"
                f" bytes_ago: {upload.bytes_ago} uploads_ago: {upload.uploads_ago}\n"
            )
            if upload.id != id:
                write(
                    f"    \033[1m\033[38;5;1mINVALID ID! {upload.id} != {id}\033[0m\n"
                )
            if upload.description != iminfo.description:
                write(
                    f"    \033[1m\033[38;5;1mINVALID DESCRIPTION! {upload.description} != {iminfo.description}\033[0m\n"
                )
        if inst is None:
            write(
                f"    \033[1m\033[38;5;1mCOULD NOT PARSE THE IMAGE DESCRIPTION!\033[0m\n"
            )
        else:
            tupiterm.display_only(
                inst,
                end_col=max_cols_int,
                end_row=max_rows_int,
                allow_expansion=False,
                use_line_feeds=(use_line_feeds == "yes"),
            )
            if inst.cols > max_cols_int or inst.rows > max_rows_int:
                write(
                    f"  Note: cropped to {min(inst.cols, max_cols_int)}x{min(inst.rows, max_rows_int)}\n"
                )
        write("-" * min(max_cols_int, 80) + "\n")

    if errors:
        exit(1)


def main_unwrapped():
    parser = argparse.ArgumentParser(
        description="", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    parser_dump_config = subparsers.add_parser(
        "dump-config",
        help="Dump the config state.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_status = subparsers.add_parser(
        "status",
        help="Display the status.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_list = subparsers.add_parser(
        "list",
        help="List all known images or known images matching the criteria.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_display = subparsers.add_parser(
        "display",
        help="Display an image. (default)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_upload = subparsers.add_parser(
        "upload",
        help="Upload an image without displaying.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_get_id = subparsers.add_parser(
        "get-id",
        help="Assign an id to an image without displaying or uploading it.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_placeholder = subparsers.add_parser(
        "placeholder",
        help="Print a placeholder for the given id, rows and columns.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_forget = subparsers.add_parser(
        "forget",
        help="Forget all matching images. Don't delete them from the terminal though.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_dirty = subparsers.add_parser(
        "dirty",
        help="Mark all matching images as dirty (not uploaded to any terminal).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_reupload = subparsers.add_parser(
        "reupload",
        help="Reupload all matching images to the current terminal.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser_fix = subparsers.add_parser(
        "fix",
        help="Reupload all dirty matching images to the current terminal.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Command-specific arguments.

    # Arguments unique to dump-config
    parser_dump_config.add_argument(
        "--no-provenance",
        "-n",
        action="store_false",
        dest="provenance",
        help="Exclude the provenance of settings as comments.",
    )
    parser_dump_config.add_argument(
        "--skip-default",
        "-d",
        action="store_true",
        help="Skip unchanged options (with 'default' provenance).",
    )

    # Arguments unique to list
    parser_list.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="verbose",
        help="Show more details for each image.",
    )
    parser_list.add_argument(
        "--max-cols",
        metavar="W",
        type=str,
        default="auto",
        help="Maximum number of columns to display each listed image. 'auto' to use the terminal width.",
    )
    parser_list.add_argument(
        "--max-rows",
        metavar="H",
        type=str,
        default="4",
        help="Maximum number of rows to display each listed image. 'auto' to use the terminal height.",
    )

    # --dump-config is available for all commands.
    for p in [
        parser_display,
        parser_upload,
        parser_get_id,
        parser_placeholder,
        parser_forget,
        parser_dirty,
        parser_reupload,
        parser_fix,
        parser_list,
    ]:
        p.add_argument(
            "--dump-config",
            action="store_true",
            dest="dump_config",
            help="Dump the config to stdout before executing the action.",
        )

    # Placeholder printing arguments.
    for p in [parser_placeholder]:
        p.add_argument("id", nargs=1, type=str)
        p.add_argument(
            "--cols",
            "-c",
            metavar="W",
            type=int,
            required=True,
            help="Number of columns of the placeholder.",
        )
        p.add_argument(
            "--rows",
            "-r",
            metavar="H",
            type=int,
            required=True,
            help="Number of rows of the placeholder.",
        )

    # Arguments related to image/id and their size (rows/cols) specification. These are
    # common for display, upload, and id assignment.
    for p in [parser_display, parser_upload, parser_get_id]:
        p.add_argument(
            "images",
            nargs="*",
            type=str,
            help="Image files to upload/display or known image IDs in the form of 'id:1234' or 'id:0xABC'.",
        )
        p.add_argument(
            "--cols",
            "-c",
            metavar="W",
            type=int,
            default=None,
            help="Number of columns to fit the image to.",
        )
        p.add_argument(
            "--rows",
            "-r",
            metavar="H",
            type=int,
            default=None,
            help="Number of rows to fit the image to.",
        )
        p.add_argument(
            "--max-cols",
            metavar="W",
            type=str,
            default=None,
            help="Maximum number of columns when computing the image size. 'auto' to use the terminal width.",
        )
        p.add_argument(
            "--max-rows",
            metavar="H",
            type=str,
            default=None,
            help="Maximum number of rows when computing the image size. 'auto' to use the terminal width.",
        )
        p.add_argument(
            "--scale",
            "-s",
            metavar="S",
            type=float,
            default=None,
            help="Scale images by this factor when automatically computing the image size (multiplied with global_scale from config).",
        )

    # --force-upload is common for all commands that do uploading, but it's mutually
    # exclusive with --no-upload, which doesn't make sense for the upload command.
    for p in [parser_upload]:
        p.add_argument(
            "--force-upload", "-f", action="store_true", help="Force (re)upload."
        )
    for p in [parser_display]:
        group = p.add_mutually_exclusive_group()
        group.add_argument(
            "--force-upload", "-f", action="store_true", help="Force (re)upload."
        )
        group.add_argument(
            "--no-upload",
            "-n",
            action="store_true",
            help="Disable uploading (just assign ID and display placeholder).",
        )

    # Arguments that are common for commands that upload images.
    for p in [parser_upload, parser_display, parser_reupload, parser_fix]:
        p.add_argument(
            "--upload-method",
            "-m",
            metavar="{auto,file,stream,...}",
            type=str,
            default=None,
            help="The upload method to use.",
        )

    # Arguments that are common for commands that display images or placeholders.
    for p in [parser_display, parser_placeholder, parser_list]:
        p.add_argument(
            "--out-display",
            "-o",
            metavar="FILE",
            type=str,
            default="",
            help="The tty/file/pipe to print the image placeholder to. If not specified, stdout will be used.",
        )
        p.add_argument(
            "--use-line-feeds",
            choices=["auto", "yes", "no"],
            default="auto",
            help="Use line feeds instead of cursor movement commands (auto: enable if output is not a TTY and there is no explicit positioning).",
        )

    # Arguments that specify image filtering criteria.
    for p in [parser_forget, parser_dirty, parser_reupload, parser_fix, parser_list]:
        p.add_argument(
            "images",
            nargs="*",
            type=str,
            help="Image files or known image IDs in the form of 'id:1234' or 'id:0xABC'.",
        )
        p.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Explicitly affect all images.",
        )
        p.add_argument(
            "--older",
            metavar="TIME",
            type=int,
            help="Affect images that were last touched before TIME.",
        )
        p.add_argument(
            "--newer",
            metavar="TIME",
            type=int,
            help="Affect images that were last touched after TIME.",
        )
        p.add_argument(
            "--last",
            "-l",
            metavar="N",
            type=int,
            help="Affect only N most recently touched images matching the criteria.",
        )
        p.add_argument(
            "--except-last",
            "-e",
            metavar="N",
            type=int,
            help="Affect images except for the N most recently touched ones.",
        )

    # Some commands will print the affected image IDs, but they can be quieted.
    for p in [parser_forget, parser_dirty, parser_reupload, parser_fix]:
        p.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            dest="quiet",
            help="Don't print affected image IDs.",
        )

    # Less important ID-related options.
    for p in [parser_display, parser_upload, parser_get_id]:
        p.add_argument(
            "--force-id",
            metavar="ID",
            type=int,
            default=None,
            help="Force the assigned id to be ID. The existing image with this ID will be forgotten.",
        )
        p.add_argument(
            "--id-space",
            metavar="{" + ",".join(str(v) for v in IDSpace.all_values()) + "}",
            default=None,
            help="The name of the ID space to use for automatically assigned IDs.",
        )
        p.add_argument(
            "--id-subspace",
            metavar="BEGIN:END",
            default=None,
            help="The range of the most significand byte for automatically assigned IDs, BEGIN <= msb < END.",
        )

    # Handle the default command case.
    all_commands = subparsers.choices.keys()
    contains_help = False
    for arg in sys.argv[1:]:
        if arg in ["-h", "--help"]:
            contains_help = True
        if arg in all_commands:
            break
    else:
        # It's not a known command.
        if not contains_help and len(sys.argv) > 1:
            # If it doesn't contain help, add the display command.
            sys.argv.insert(1, "display")
        else:
            # Otherwise show the help.
            sys.argv.insert(1, "--help")

    # Parse the arguments
    args = parser.parse_args()

    # Execute the function associated with the chosen subcommand
    if args.command == "dump-config":
        dump_config(**vars(args))
    elif args.command == "status":
        status(**vars(args))
    elif args.command == "display":
        display(**vars(args))
    elif args.command == "upload":
        upload(**vars(args))
    elif args.command == "get-id":
        get_id(**vars(args))
    elif args.command == "placeholder":
        placeholder(**vars(args))
    elif args.command in ("forget", "dirty", "reupload", "fix", "list"):
        foreach(**vars(args))
    else:
        print(f"error: Command not implemented: {args.command}", file=sys.stderr)
        sys.exit(2)


def main():
    try:
        main_unwrapped()
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)
    except CLIArgumentsError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        # For known errors coming from incorrectly specified options just print the
        # error message and exit with code 2.
        if (
            "Unsupported transmission" in str(e)
            or "Unsupported upload method" in str(e)
            or "Invalid format for IDSubspace" in str(e)
            or "Invalid IDSubspace" in str(e)
            or "Invalid IDSpace" in str(e)
        ):
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        else:
            raise e


if __name__ == "__main__":
    main()
