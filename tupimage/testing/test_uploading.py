import tupimage
from tupimage import GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test
import os
import numpy as np
import time
import tempfile
import shutil


@screenshot_test
def tempfile_png(ctx: TestingContext):
    term = ctx.term
    f, filename = tempfile.mkstemp(prefix="tty-graphics-protocol")
    shutil.copyfile(ctx.get_wikipedia_png(), filename)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.TEMP_FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    ).set_filename(filename).set_placement(
        rows=10,
        cols=20,
    )
    term.send_command(cmd)
    time.sleep(0.2)
    ctx.assert_true(not os.path.exists(filename), f"File {filename} must not exist.")
    ctx.take_screenshot("Wikipedia logo, temporary file uploading.")


@screenshot_test
def direct_png(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    print(f"size: {os.path.getsize(ctx.get_wikipedia_png()) // 1024}K")
    with open(ctx.get_wikipedia_png(), "rb") as f:
        data = f.read()
    term.send_command(cmd.clone_with(image_id=100).set_data(data))
    term.send_command(
        PutCommand(
            image_id=100,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Wikipedia logo, direct uploading.")
    print(f"size: {os.path.getsize(ctx.get_tux_png()) // 1024}K")
    with open(ctx.get_tux_png(), "rb") as f:
        term.send_command(cmd.clone_with(image_id=200).set_data(f))
    term.send_command(
        PutCommand(
            image_id=200,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Wiki and tux, direct uploading.")


@screenshot_test
def direct_jpeg(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    print(f"size: {os.path.getsize(ctx.get_castle_jpg()) // 1024}K")
    with open(ctx.get_castle_jpg(), "rb") as f:
        data = f.read()
    term.send_command(cmd.clone_with(image_id=100).set_data(data))
    term.send_command(
        PutCommand(
            image_id=100,
            rows=10,
            cols=80,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Castle jpeg, direct uploading.")


@screenshot_test
def direct_random_png(ctx: TestingContext):
    term = ctx.term
    np.random.seed(42)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    data = ctx.to_png(ctx.generate_image(10, 10))
    print(f"size: {len(data)} bytes")
    term.send_command(cmd.clone_with(image_id=100).set_data(data))
    term.send_command(
        PutCommand(
            image_id=100,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Random < 1K image, direct uploading.")
    data = ctx.to_png(ctx.generate_image(1000, 1000))
    print(f"size: {len(data) // 1024}K")
    term.send_command(cmd.clone_with(image_id=200).set_data(data))
    term.send_command(
        PutCommand(
            image_id=200,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Random big image, direct uploading.")


@screenshot_test
def direct_rgb(ctx: TestingContext):
    term = ctx.term
    for compress in [False, True]:
        for bits in [24, 32]:
            term.reset()
            cmd = TransmitCommand(
                medium=tupimage.TransmissionMedium.DIRECT,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                format=tupimage.Format.from_bits(bits),
                compression=tupimage.Compression.from_bool(compress),
            )
            data, w, h = ctx.to_rgb_and_wh(
                ctx.get_tux_png(), bits, compress=compress
            )
            print(f"size: {len(data) // 1024}K")
            term.send_command(
                cmd.clone_with(image_id=1, pix_width=w, pix_height=h).set_data(
                    data
                )
            )
            term.send_command(
                PutCommand(
                    image_id=1,
                    rows=10,
                    cols=20,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                )
            )
            term.write("\n")
            data, w, h = ctx.to_rgb_and_wh(
                ctx.get_wikipedia_png(), bits, compress=compress
            )
            print(f"size: {len(data) // 1024}K")
            term.send_command(
                cmd.clone_with(image_id=2, pix_width=w, pix_height=h).set_data(
                    data
                )
            )
            term.send_command(
                PutCommand(
                    image_id=2,
                    rows=10,
                    cols=20,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                )
            )
            ctx.take_screenshot(
                f"Tux and wiki, direct transmission, {bits}-bit data, compress"
                f" = {compress}"
            )


@screenshot_test
def image_number(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_number=42)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, cols=20)
    )
    term.write("\n")
    ctx.take_screenshot(
        "Wikipedia logo, sent with an image number, combined transmit-and-put"
        " command."
    )
    term.send_command(
        cmd.clone_with(image_number=43).set_filename(ctx.get_tux_png())
    )
    term.send_command(
        PutCommand(
            image_number=43,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot(
        "Tux, sent with an image number, separate transmit and put."
    )


@screenshot_test
def image_number_multiple(ctx: TestingContext):
    term = ctx.term
    transmit_cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    put_cmd = PutCommand(
        rows=10,
        cols=20,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
    )
    files = [
        ctx.get_diagonal_png(),
        ctx.get_wikipedia_png(),
        ctx.get_tux_png(),
        ctx.get_transparency_png(),
    ]
    for idx, filename in enumerate(files):
        number = (idx % 3) + 1
        term.send_command(
            transmit_cmd.clone_with(image_number=number).set_filename(filename)
        )
    for idx, filename in enumerate(files):
        number = (idx % 3) + 1
        term.send_command(put_cmd.clone_with(image_number=number))
        term.move_cursor(up=9)
    ctx.take_screenshot(
        "Dice, wiki, tux, dice again, sent with image numbers, separate"
        " transmit and put commands."
    )
    term.move_cursor_abs(row=10, col=0)
    for i in range(2):
        for idx, filename in enumerate(files):
            term.send_command(
                transmit_cmd.clone_with(image_number=idx + 1).set_filename(
                    filename
                )
            )
        for idx, filename in enumerate(files):
            term.send_command(
                put_cmd.clone_with(rows=5, cols=10, image_number=idx + 1)
            )
            term.move_cursor(up=4)
    ctx.take_screenshot(
        "Line, wiki, tux, dice, sent with image numbers, separate transmit and"
        " put commands."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def stress_many_small_images(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    image_id = 0
    for x in range(80):
        for y in range(24):
            image_id += 1
            term.move_cursor_abs(row=y, col=x)
            term.send_command(
                cmd.clone_with(image_id=image_id).set_data(
                    ctx.to_png(
                        ctx.text_to_image(
                            str(image_id), colorize_by_id=image_id
                        )
                    )
                )
            )
            term.send_command(
                PutCommand(
                    image_id=image_id,
                    rows=1,
                    cols=1,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                    do_not_move_cursor=True,
                )
            )
    # Additional delay since the terminal may be slow to render all the images.
    time.sleep(1.5)
    ctx.take_screenshot("Many one-cell images of numbers")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def stress_large_images(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    with tempfile.NamedTemporaryFile("wb") as f:
        # Generate an image of ~20MB (when represented as RGBA).
        data = ctx.to_rgb(ctx.generate_image(10 * 500, 2 * 500), bits=32)
        f.write(data)
        f.flush()
        cmd = TransmitCommand(
            image_id=1,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            pix_width=10 * 500,
            pix_height=2 * 500,
            format=tupimage.Format.RGBA,
        ).set_filename(f.name)
        # Load and display the images. All images are the same but the terminal
        # doesn't know that.
        image_id = 0
        for y in range(10):
            for x in range(4):
                image_id += 1
                term.move_cursor_abs(row=y * 2, col=x * 20)
                term.send_command(cmd.clone_with(image_id=image_id))
                term.send_command(
                    PutCommand(
                        image_id=image_id,
                        rows=2,
                        cols=20,
                        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                        do_not_move_cursor=True,
                    )
                )
                # We add a delay so that the terminal has time to render the
                # image before we load too many of them.
                time.sleep(0.2)
        ctx.take_screenshot(
            "Large images (40 ~grey rectangles). We expect to see all of them."
        )
        # Now just display the same images.
        term.reset()
        image_id = 0
        for y in range(10):
            for x in range(4):
                image_id += 1
                term.move_cursor_abs(row=y * 2, col=x * 20)
                # We are quiet even on error because kitty will delete old
                # images together with metadata.
                term.send_command(
                    PutCommand(
                        image_id=image_id,
                        rows=2,
                        cols=20,
                        quiet=tupimage.Quietness.QUIET_ALWAYS,
                        do_not_move_cursor=True,
                    )
                )
        ctx.take_screenshot(
            "Redisplayed large images. We expect that some of them are missing."
        )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def stress_too_many_images(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    # Create and upload lots of 1-pixel images.
    total_count = 10000
    for i in range(total_count):
        data = ctx.to_rgb(ctx.generate_image(1, 1), bits=24)
        term.send_command(
            TransmitCommand(
                image_id=i + 1,
                medium=tupimage.TransmissionMedium.DIRECT,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                pix_width=1,
                pix_height=1,
                format=tupimage.Format.RGB,
            ).set_data(data)
        )
        term.write(f"{i + 1}\r")
    ctx.take_screenshot("Uploaded many one-pixel images")
    # Now display them, but not all of them, use a step.
    term.reset()
    step = total_count / (80 * 23)
    image_id = 1
    for y in range(23):
        for x in range(80):
            term.move_cursor_abs(row=y, col=x)
            term.send_command(
                PutCommand(
                    image_id=int(image_id),
                    rows=1,
                    cols=1,
                    quiet=tupimage.Quietness.QUIET_ALWAYS,
                    do_not_move_cursor=True,
                )
            )
            image_id += step
    ctx.take_screenshot(
        "Displayed some one-pixel images, some will be missing."
    )


@screenshot_test
def stress_too_many_placements(ctx: TestingContext):
    term = ctx.term.clone_with(force_placeholders=True)
    # Create and upload 1-pixel images and create placements for them.
    total_image_count = 1000
    placements_per_image = 20
    for i in range(total_image_count):
        data = ctx.to_rgb(ctx.generate_image(1, 1), bits=24)
        term.send_command(
            TransmitCommand(
                image_id=i + 1,
                medium=tupimage.TransmissionMedium.DIRECT,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                pix_width=1,
                pix_height=1,
                format=tupimage.Format.RGB,
            ).set_data(data)
        )
    for j in range(placements_per_image):
        for i in range(total_image_count):
            term.write(f"img {i + 1} placement {j + 1}    \r")
            term.send_command(
                PutCommand(
                    image_id=i + 1,
                    placement_id=j + 1,
                    virtual=True,
                    rows=1,
                    cols=1,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                )
            )
    ctx.term.reset()
    # Now display them, but not all of them, use a step.
    step = total_image_count / (80 * 23 / 5)
    image_id = 1
    for y in range(23):
        for x in range(80):
            t = x + y * 80
            placement_id = ((t % 5) + 1) * 4
            image_id = int(step * ((t // 5) + 1))
            term.move_cursor_abs(row=y, col=x)
            term.print_placeholder(
                image_id=image_id,
                placement_id=placement_id,
                end_row=1,
                end_col=1,
            )
    ctx.take_screenshot(
        "Attempting to display 5 different placements for some of the images."
        " Many placements may be missing."
    )
