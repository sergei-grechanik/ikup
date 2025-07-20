import argparse
import os
import sys
import time
from datetime import datetime
from typing import Optional, List

import ikup
from ikup.id_manager import IDSpace, IDSubspace
from ikup.ikup_terminal import ImageInfo, ImageInstance, ValidationError
from ikup.utils import *

HELP_PRINT = """\
The --print (-p) option takes a string argument which may use the following
format specifiers:

    %%  A literal %
    %i  The image ID (decimal)
    %x  The image ID (hexadecimal), with leading zeros, but without '0x'
    %c  The number of columns of the image or '?' if not known
    %r  The number of rows of the image or '?' if not known
    %p  The path to the image file or '/dev/null' if not known
    %P  The path to the image file or the description if not known
    %m  The modified time of the (original) image or '?' if not known
    %a  The access time of the image/ID in the ID database
    %D  The description of the image (likely json)

It may also use escape sequences: \\\\, \\n, \\t, \\r, \\e
"""


additional_help_topics = {"print": HELP_PRINT}


def help(command: str, topic: Optional[str]):
    _ = command
    if not topic:
        print("Use 'ikup help <topic>' to get more information about a topic.")
        print("Available help topics:")
        for t in additional_help_topics:
            print(f"  {t}")
        return

    matching = []
    for t in additional_help_topics:
        if t == topic:
            print(additional_help_topics[t])
            return
        if t.startswith(topic):
            matching.append(t)

    if not matching:
        print(f"error: No help topic found for '{topic}'.")
        print("Available help topics:")
        for t in additional_help_topics:
            print(f"  {t}")
        return

    if len(matching) > 1:
        print(f"error: Multiple help topics match prefix '{topic}':")
        for t in matching:
            print(f"  {t}")
        return

    print(f"Help for topic '{matching[0]}':")
    print(additional_help_topics[matching[0]])


class CLIArgumentsError(Exception):
    """Custom exception for CLI argument errors."""

    pass


class UseConfig:
    """A placeholder class to indicate that the value from the config should be used.

    The only reason for its existence is to print nicer `default: use config` in the
    help message instead of `default: None`."""

    def __str__(self):
        return "use config"


def positive_int(value):
    """argparse type function for positive integers."""
    try:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(f"must be a positive integer, got {value}")
        return ivalue
    except ValueError:
        raise argparse.ArgumentTypeError(f"must be an integer, got '{value}'")


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


def format_info_string(
    string: str, info: ImageInfo, inst: Optional[ImageInstance]
) -> str:
    parts = []
    i = 0
    cur_start = 0
    while i < len(string):
        if string[i] == "\\" and i + 1 < len(string):
            parts.append(string[cur_start:i])
            i += 1
            esc = string[i]
            cur_start = i + 1
            if esc == "\\":
                parts.append("\\")
            elif esc == "n":
                parts.append("\n")
            elif esc == "t":
                parts.append("\t")
            elif esc == "r":
                parts.append("\r")
            elif esc == "e":
                parts.append("\033")
            else:
                raise CLIArgumentsError(f"Unknown escape sequence: \\{esc}")
        if string[i] == "%" and i + 1 < len(string):
            parts.append(string[cur_start:i])
            i += 1
            fmt = string[i]
            cur_start = i + 1
            if fmt == "%":
                parts.append("%")
            elif fmt == "i":
                parts.append(str(info.id))
            elif fmt == "x":
                parts.append(f"{info.id:08x}")
            elif fmt == "c":
                parts.append(str(inst.cols) if inst else "?")
            elif fmt == "r":
                parts.append(str(inst.rows) if inst else "?")
            elif fmt == "p":
                parts.append(inst.path if inst else "/dev/null")
            elif fmt == "P":
                parts.append(inst.path if inst else info.description)
            elif fmt == "m":
                parts.append(inst.mtime.isoformat() if inst else "?")
            elif fmt == "a":
                parts.append(info.atime.isoformat())
            elif fmt == "D":
                parts.append(info.description)
            else:
                raise CLIArgumentsError(f"Unknown format specifier: %{fmt}")
        i += 1
    parts.append(string[cur_start:i])
    return "".join(parts)


def dump_config(command: str, provenance: bool, skip_default: bool):
    _ = command
    ikupterm = ikup.IkupTerminal()
    toml_str = ikupterm._config.to_toml_string(
        with_provenance=provenance, skip_default=skip_default
    )
    print(toml_str, end="")


def status(command: str):
    _ = command
    ikupterm = ikup.IkupTerminal()
    print(f"Config file: {ikupterm._config_file}")
    print(f"num_tmux_layers: {ikupterm.num_tmux_layers}")
    print(f"inside_ssh: {ikupterm.inside_ssh}")
    print(f"terminal_name: {ikupterm._terminal_name}")
    print(f"terminal_id: {ikupterm._terminal_id}")
    print(f"session_id: {ikupterm._session_id}")
    print(f"database_file: {ikupterm.id_manager.database_file}")
    print(f"Default ID space: {ikupterm.get_id_space()}")
    print(f"Default subspace: {ikupterm.get_subspace()}")
    print(f"Total IDs in the session db: {ikupterm.id_manager.count()}")
    print(
        f"IDs in the subspace: {ikupterm.id_manager.count(ikupterm.get_id_space(), ikupterm.get_subspace())}"
    )
    print(f"Supported formats: {ikupterm.get_supported_formats()}")
    print(f"Default uploading method: {ikupterm.get_upload_method()}")
    print(f"Allow concurrent uploads: {ikupterm.get_allow_concurrent_uploads()}")
    maxcols, maxrows = ikupterm.get_max_cols_and_rows()
    print(f"Max size in cells (cols x rows): {maxcols} x {maxrows}")
    cellw, cellh = ikupterm.get_cell_size()
    print(f"(Assumed) cell size in pixels (w x h): {cellw} x {cellh}")

    print(f"\nAll databases in {ikupterm._config.id_database_dir}")
    assert ikupterm._config.id_database_dir
    db_files = []
    for db_name in os.listdir(ikupterm._config.id_database_dir):
        db_path = os.path.join(ikupterm._config.id_database_dir, db_name)
        if os.path.isfile(db_path) and db_name.endswith(".db"):
            atime = os.path.getatime(db_path)
            size_kib = os.path.getsize(db_path) // 1024
            db_files.append((db_name, atime, size_kib))

    # Sort by atime in descending order
    db_files.sort(key=lambda x: x[1], reverse=True)

    for db_name, atime, size_kib in db_files:
        print(f"  {db_name}  (atime: {time.ctime(atime)}, size: {size_kib} KiB)")


def printerr(ikupterm: ikup.IkupTerminal, msg):
    ikupterm.term.out_display.flush()
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
    out_command: str,
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    use_line_feeds: str,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
    upload_method: Optional[str],
    allow_concurrent_uploads: Optional[str],
    mark_uploaded: Optional[str],
):
    ikupterm = ikup.IkupTerminal(
        out_display=out_display if out_display else None,
        out_command=out_command if out_command else None,
        config_overrides={
            "force_upload": force_upload,
            "max_cols": max_cols,
            "max_rows": max_rows,
            "scale": scale,
            "id_space": id_space,
            "id_subspace": id_subspace,
            "upload_method": upload_method,
            "provenance": "set via command line",
            "allow_concurrent_uploads": allow_concurrent_uploads,
            "mark_uploaded": mark_uploaded,
        },
    )
    if dump_config:
        print(ikupterm._config.to_toml_string(with_provenance=True), end="")
    errors = False

    if use_line_feeds == "auto" and not ikupterm.term.out_display.isatty():
        use_line_feeds = "true"

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
                image = ikupterm.get_image_instance(id)
                if image is None:
                    printerr(
                        ikupterm,
                        f"error: ID is not assigned or assignment is broken: {id}",
                    )
                    errors = True
                    continue
        # Handle the command itself. Don't stop on errors.
        try:
            if command == "display" and not no_upload:
                ikupterm.upload_and_display(
                    image,
                    rows=rows,
                    cols=cols,
                    use_line_feeds=(use_line_feeds == "true"),
                    force_id=force_id,
                )
            elif command == "upload":
                ikupterm.upload(
                    image,
                    rows=rows,
                    cols=cols,
                    force_id=force_id,
                )
            elif command == "get-id" or (command == "display" and no_upload):
                if isinstance(image, ImageInstance):
                    instance = image
                else:
                    instance = ikupterm.assign_id(
                        image,
                        rows=rows,
                        cols=cols,
                        force_id=force_id,
                    )
                if command == "get-id":
                    print(instance.id)
                if command == "display":
                    ikupterm.display_only(
                        instance,
                        use_line_feeds=(use_line_feeds == "true"),
                    )
        except (FileNotFoundError, OSError) as e:
            printerr(ikupterm, f"error: Failed to upload {image}: {e}")
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
    out_command: str,
    max_cols: Optional[str],
    max_rows: Optional[str],
    scale: Optional[float],
    dump_config: bool,
    use_line_feeds: str,
    force_id: Optional[int],
    id_space: Optional[str],
    id_subspace: Optional[str],
    upload_method: Optional[str],
    allow_concurrent_uploads: Optional[str],
    mark_uploaded: Optional[str],
):
    handle_command(
        command=command,
        images=images,
        rows=rows,
        cols=cols,
        force_upload=force_upload,
        no_upload=no_upload,
        out_display=out_display,
        out_command=out_command,
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds=use_line_feeds,
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=upload_method,
        allow_concurrent_uploads=allow_concurrent_uploads,
        mark_uploaded=mark_uploaded,
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
    out_command: str,
    allow_concurrent_uploads: Optional[str],
    mark_uploaded: Optional[str],
):
    handle_command(
        command=command,
        images=images,
        rows=rows,
        cols=cols,
        force_upload=force_upload,
        no_upload=False,
        out_display="",
        out_command=out_command,
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds="false",
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=upload_method,
        allow_concurrent_uploads=allow_concurrent_uploads,
        mark_uploaded=mark_uploaded,
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
        out_command="",
        max_cols=max_cols,
        max_rows=max_rows,
        scale=scale,
        dump_config=dump_config,
        use_line_feeds="false",
        force_id=force_id,
        id_space=id_space,
        id_subspace=id_subspace,
        upload_method=None,
        allow_concurrent_uploads=None,
        mark_uploaded=None,
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
    ikupterm = ikup.IkupTerminal(
        out_display=out_display if out_display else None,
        config_overrides={
            "provenance": "set via command line",
        },
    )
    if dump_config:
        print(ikupterm._config.to_toml_string(with_provenance=True), end="")

    id_int = parse_as_id(id[0])
    if id_int is None:
        printerr(ikupterm, f"error: ID is incorrect: {id[0]}")
        exit(1)

    if use_line_feeds == "auto" and not ikupterm.term.out_display.isatty():
        use_line_feeds = "true"

    ikupterm.display_only(
        id_int,
        end_col=cols,
        end_row=rows,
        use_line_feeds=(use_line_feeds == "true"),
    )


def foreach(
    command: str,
    images: List[str],
    all: bool,
    dump_config: bool,
    _print: Optional[str],
    use_line_feeds: str = "false",
    older: Optional[str] = None,
    newer: Optional[str] = None,
    last: Optional[int] = None,
    except_last: Optional[int] = None,
    max_cols: Optional[str] = None,
    max_rows: Optional[str] = None,
    out_display: str = "",
    out_command: str = "",
    verbose: bool = False,
    quiet: bool = False,
    upload_method: Optional[str] = None,
    allow_concurrent_uploads: Optional[str] = None,
    mark_uploaded: Optional[str] = None,
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

    ikupterm = ikup.IkupTerminal(
        out_display=out_display if out_display else None,
        out_command=out_command if out_command else None,
        config_overrides={
            "max_cols": max_cols,
            "max_rows": max_rows,
            "upload_method": upload_method,
            "provenance": "set via command line",
            "allow_concurrent_uploads": allow_concurrent_uploads,
            "mark_uploaded": mark_uploaded,
        },
    )
    if dump_config:
        print(ikupterm._config.to_toml_string(with_provenance=True), end="")
    max_cols_int, max_rows_int = ikupterm.get_max_cols_and_rows()

    if use_line_feeds == "auto" and not ikupterm.term.out_display.isatty():
        use_line_feeds = "true"

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
    for iminfo in ikupterm.id_manager.get_all():
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
            printerr(ikupterm, f"error: ID not found in the db: {img}")
        else:
            printerr(ikupterm, f"error: Image not found in the db: {img}")
        errors = True

    # Note that if we mix images and text, we should write to the same stream object,
    # otherwise there is a risk of buffering issues.
    write = ikupterm.term.write

    # Now process the images.
    for iminfo in image_infos:
        inst = ImageInstance.from_info(iminfo)
        id = iminfo.id

        if command == "forget":
            ikupterm.id_manager.del_id(id)

        if command == "dirty":
            ikupterm.id_manager.mark_dirty(id)

        if command == "reupload" or command == "fix":
            if inst is None:
                printerr(
                    ikupterm, f"error: ID is not assigned or assignment is broken: {id}"
                )
                errors = True
                continue
            # 'fix' is like 'reupload', but avoids unnecessary uploads.
            if command == "fix" and not ikupterm.needs_uploading(id):
                continue
            # Don't fail other uploads if one fails, but print the error message
            try:
                ikupterm.upload(inst, force_upload=True, update_atime=False)
            except (FileNotFoundError, OSError) as e:
                printerr(ikupterm, f"error: Failed to upload {id} {inst.path}: {e}")
                errors = True
                continue

        if quiet:
            continue

        # Format the print string if needed.
        string = ""
        if _print:
            string = format_info_string(_print, iminfo, inst)
        elif not verbose:
            string = format_info_string(f"%i\t%cx%r\t%P", iminfo, inst)

        # If it's not a verbose mode of 'list', just print some basic info.
        if not verbose:
            if command != "list":
                write(f"{command} ")
            write(string + "\n")
            continue

        # Otherwise print more details and several rows of the image.
        space = str(IDSpace.from_id(id))
        subspace_byte = IDSpace.get_subspace_byte(id)
        ago = time_ago(iminfo.atime)
        if string:
            write(string + "\n")
        write(
            f"\033[1mID: {id}\033[0m = 0x{id:08x} id_space: {space} subspace_byte: {subspace_byte} = 0x{subspace_byte:02x} atime: {iminfo.atime} ({ago})\n"
        )
        write(f"  {iminfo.description}\n")
        if ikupterm.needs_uploading(id):
            write(f"  \033[1mNEEDS UPLOADING\033[0m to {ikupterm._terminal_id}\n")
        uploads = ikupterm.id_manager.get_upload_infos(id)
        for upload in uploads:
            write("  ")
            if ikupterm.needs_uploading(upload.id, upload.terminal):
                write("(Needs reuploading) ")
            status = f"Uploaded (status = {upload.status}) to"
            if upload.status == ikup.id_manager.UPLOADING_STATUS_UPLOADED:
                status = "Uploaded to"
            elif upload.status == ikup.id_manager.UPLOADING_STATUS_IN_PROGRESS:
                status = "Uploading in progress to"
            elif upload.status == ikup.id_manager.UPLOADING_STATUS_DIRTY:
                status = "Dirty in"
            write(
                f"{status} {upload.terminal}"
                f" at {upload.upload_time} ({time_ago(upload.upload_time)})"
                f"  size: {upload.size} bytes"
                f" bytes_ago: {upload.bytes_ago} uploads_ago: {upload.uploads_ago}\n"
            )
            if upload.id != id:
                write(
                    f"    \033[1m\033[38;5;1mINVALID ID! {upload.id} != {id}\033[0m\n"
                )
            if upload.description != iminfo.description:
                write(f"    INVALID DESCRIPTION: {upload.description}\n")
        if inst is None:
            write(
                f"    \033[1m\033[38;5;1mCOULD NOT PARSE THE IMAGE DESCRIPTION!\033[0m\n"
            )
        else:
            try:
                ikupterm.display_only(
                    inst,
                    end_col=max_cols_int,
                    end_row=max_rows_int,
                    allow_expansion=False,
                    use_line_feeds=(use_line_feeds == "true"),
                )
            except (ValueError, RuntimeError) as e:
                write(f"  \033[1m\033[38;5;1mCOULD NOT DISPLAY: {e}\033[0m\n")
                errors = True
            if inst.cols > max_cols_int or inst.rows > max_rows_int:
                write(
                    f"  Note: cropped to {min(inst.cols, max_cols_int)}x{min(inst.rows, max_rows_int)}\n"
                )
        write("-" * min(max_cols_int, 80) + "\n")

    if errors:
        exit(1)


def cleanup(command: str):
    _ = command
    ikupterm = ikup.IkupTerminal()
    dbs = ikupterm.cleanup_old_databases()
    if dbs:
        print("Removed old databases:")
        for db in dbs:
            print(f"  {db}")
    ikupterm.cleanup_current_database()


def main_unwrapped():
    parser = argparse.ArgumentParser(
        description="", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-v", "--version", action="version", version="%(prog)s " + ikup.__version__
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_dump_config = subparsers.add_parser(
        "dump-config",
        help="Dump the config state.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_status = subparsers.add_parser(
        "status",
        help="Display the status.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_list = subparsers.add_parser(
        "list",
        help="List all known images or known images matching the criteria.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_display = subparsers.add_parser(
        "display",
        help="Display an image. (default)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_upload = subparsers.add_parser(
        "upload",
        help="Upload an image without displaying.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_get_id = subparsers.add_parser(
        "get-id",
        help="Assign an id to an image without displaying or uploading it.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_placeholder = subparsers.add_parser(
        "placeholder",
        help="Print a placeholder for the given id, rows and columns.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_forget = subparsers.add_parser(
        "forget",
        help="Forget all matching images. Don't delete them from the terminal though.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_dirty = subparsers.add_parser(
        "dirty",
        help="Mark all matching images as dirty (not uploaded to any terminal).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_reupload = subparsers.add_parser(
        "reupload",
        help="Reupload all matching images to the current terminal.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_fix = subparsers.add_parser(
        "fix",
        help="Reupload all dirty matching images to the current terminal.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_cleanup = subparsers.add_parser(
        "cleanup",
        help="Trigger db cleanup.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p_help = subparsers.add_parser(
        "help",
        help="Show additional help.",
    )

    # Command-specific arguments.

    # Arguments unique to help
    p_help.add_argument(
        "topic",
        nargs="?",
        type=str,
        help="The help topic to show. If not specified, show the list of topics.",
    )

    # Arguments unique to dump-config
    p_dump_config.add_argument(
        "--no-provenance",
        "-n",
        action="store_false",
        dest="provenance",
        help="Exclude the provenance of settings as comments.",
    )
    p_dump_config.add_argument(
        "--skip-default",
        "-d",
        action="store_true",
        help="Skip unchanged options (with 'default' provenance).",
    )

    # Arguments unique to list
    p_list.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        dest="verbose",
        help="Show more details for each image.",
    )
    p_list.add_argument(
        "--max-cols",
        metavar="W",
        type=str,
        default="auto",
        help="Maximum number of columns to display each listed image. 'auto' to use the terminal width.",
    )
    p_list.add_argument(
        "--max-rows",
        metavar="H",
        type=str,
        default="4",
        help="Maximum number of rows to display each listed image. 'auto' to use the terminal height.",
    )

    # --dump-config is available for all commands.
    for p in [
        p_display,
        p_upload,
        p_get_id,
        p_placeholder,
        p_forget,
        p_dirty,
        p_reupload,
        p_fix,
        p_list,
    ]:
        p.add_argument(
            "--dump-config",
            action="store_true",
            dest="dump_config",
            help="Dump the config to stdout before executing the action.",
        )

    # Placeholder printing arguments.
    for p in [p_placeholder]:
        p.add_argument("id", nargs=1, type=str)
        p.add_argument(
            "--cols",
            "-c",
            metavar="W",
            type=positive_int,
            required=True,
            help="Number of columns of the placeholder.",
        )
        p.add_argument(
            "--rows",
            "-r",
            metavar="H",
            type=positive_int,
            required=True,
            help="Number of rows of the placeholder.",
        )

    # Arguments related to image/id and their size (rows/cols) specification. These are
    # common for display, upload, and id assignment.
    for p in [p_display, p_upload, p_get_id]:
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
            type=positive_int,
            default=UseConfig(),
            help="Number of columns to fit the image to.",
        )
        p.add_argument(
            "--rows",
            "-r",
            metavar="H",
            type=positive_int,
            default=UseConfig(),
            help="Number of rows to fit the image to.",
        )
        p.add_argument(
            "--max-cols",
            metavar="W",
            type=str,
            default=UseConfig(),
            help="Maximum number of columns when computing the image size. 'auto' to use the terminal width.",
        )
        p.add_argument(
            "--max-rows",
            metavar="H",
            type=str,
            default=UseConfig(),
            help="Maximum number of rows when computing the image size. 'auto' to use the terminal width.",
        )
        p.add_argument(
            "--scale",
            "-s",
            metavar="S",
            type=float,
            default=UseConfig(),
            help="Scale images by this factor when automatically computing the image size (multiplied with global_scale from config).",
        )

    # --force-upload is common for all commands that do uploading, but it's mutually
    # exclusive with --no-upload, which doesn't make sense for the upload command.
    for p in [p_upload]:
        p.add_argument(
            "--force-upload", "-f", action="store_true", help="Force (re)upload."
        )
    for p in [p_display]:
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
    may_upload = [p_upload, p_display, p_reupload, p_fix]
    for p in may_upload:
        p.add_argument(
            "--upload-method",
            "-m",
            metavar="{auto,file,stream,...}",
            type=str,
            default=UseConfig(),
            help="The upload method to use.",
        )
        p.add_argument(
            "--allow-concurrent-uploads",
            choices=["auto", "true", "false"],
            type=str,
            default=UseConfig(),
            help="Whether to allow direct upload of images with different IDs concurrently.",
        )
        p.add_argument(
            "--mark-uploaded",
            choices=["true", "false"],
            type=str,
            default=UseConfig(),
            help="Whether to mark images as uploaded after uploading them. If false, they will be marked as dirty.",
        )

    # Arguments that are common for commands that send graphics commands.
    for p in may_upload:
        p.add_argument(
            "--out-command",
            "-O",
            metavar="FILE",
            type=str,
            default="",
            help="The tty/file/pipe to send graphics commands to. If not specified, /dev/tty will be used.",
        )

    # Arguments that are common for commands that display images or placeholders.
    for p in [p_display, p_placeholder, p_list]:
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
            choices=["auto", "true", "false"],
            default="auto",
            help="Use line feeds instead of cursor movement commands (auto: enable if output is not a TTY and there is no explicit positioning).",
        )

    # Arguments that specify image filtering criteria.
    for p in [p_forget, p_dirty, p_reupload, p_fix, p_list]:
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
        p.add_argument(
            "--print",
            "-p",
            metavar="FORMAT",
            type=str,
            help="Print information according to FORMAT. Run `ikup help print` for details.",
        )

    # Some commands will print the affected image IDs, but they can be quieted.
    for p in [p_forget, p_dirty, p_reupload, p_fix]:
        p.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            dest="quiet",
            help="Don't print affected image IDs.",
        )

    # Less important ID-related options.
    for p in [p_display, p_upload, p_get_id]:
        p.add_argument(
            "--force-id",
            metavar="ID",
            type=int,
            default=UseConfig(),
            help="Force the assigned id to be ID. The existing image with this ID will be forgotten.",
        )
        p.add_argument(
            "--id-space",
            metavar="{" + ",".join(str(v) for v in IDSpace.all_values()) + "}",
            default=UseConfig(),
            help="The name of the ID space to use for automatically assigned IDs.",
        )
        p.add_argument(
            "--id-subspace",
            metavar="BEGIN:END",
            default=UseConfig(),
            help="The range of the most significand byte for automatically assigned IDs, BEGIN <= msb < END.",
        )

    # Handle the default command case.
    all_commands = subparsers.choices.keys()
    contains_help = False
    contains_version = False
    for arg in sys.argv[1:]:
        if arg in ["-h", "--help"]:
            contains_help = True
        elif arg in ["-v", "--version"]:
            contains_version = True
        if arg in all_commands:
            break
    else:
        # It's not a known command.
        if not contains_help and not contains_version and len(sys.argv) > 1:
            # If it doesn't contain help or version, add the display command.
            sys.argv.insert(1, "display")
        elif contains_help or len(sys.argv) == 1:
            # If there is -h or --help in the arguments or there are no arguments, show
            # the help.
            sys.argv.insert(1, "--help")

    # Parse the arguments
    args = parser.parse_args()
    vardict = vars(args)

    # Replace UseConfig() with None.
    for key, value in vardict.items():
        if isinstance(value, UseConfig):
            vardict[key] = None

    # Rename some arguments for easier access.
    if "print" in vardict:
        vardict["_print"] = vardict.pop("print")

    # Execute the function associated with the chosen subcommand
    if args.command == "dump-config":
        dump_config(**vardict)
    elif args.command == "status":
        status(**vardict)
    elif args.command == "display":
        display(**vardict)
    elif args.command == "upload":
        upload(**vardict)
    elif args.command == "get-id":
        get_id(**vardict)
    elif args.command == "placeholder":
        placeholder(**vardict)
    elif args.command in ("forget", "dirty", "reupload", "fix", "list"):
        foreach(**vardict)
    elif args.command == "cleanup":
        cleanup(**vardict)
    elif args.command == "help":
        help(**vardict)
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
    except (
        CLIArgumentsError,
        NotImplementedError,
        ValidationError,
    ) as e:
        print(
            f"error: {e}",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
