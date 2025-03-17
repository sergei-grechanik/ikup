import os
import shutil
import tempfile
import time
from multiprocessing import shared_memory

import numpy as np

import tupimage
from tupimage import DeleteCommand, GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test

SPLIT_PAYLOAD_SIZE = 2816


@screenshot_test
def tempfile_png(ctx: TestingContext):
    term = ctx.term
    f, filename = tempfile.mkstemp(prefix="tty-graphics-protocol")
    shutil.copyfile(ctx.get_wikipedia_png(), filename)
    cmd = (
        TransmitCommand(
            image_id=1,
            medium=tupimage.TransmissionMedium.TEMP_FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        )
        .set_filename(filename)
        .set_placement(
            rows=10,
            cols=20,
        )
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
            data, w, h = ctx.to_rgb_and_wh(ctx.get_tux_png(), bits, compress=compress)
            print(f"size: {len(data) // 1024}K")
            term.send_command(
                cmd.clone_with(image_id=1, pix_width=w, pix_height=h).set_data(data)
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
                cmd.clone_with(image_id=2, pix_width=w, pix_height=h).set_data(data)
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
def shm_png(ctx: TestingContext):
    term = ctx.term
    # Test with an offset, and make it divisible by the page size.
    page_size = os.sysconf("SC_PAGE_SIZE")
    offset = page_size

    term.reset()
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.SHARED_MEMORY,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    with open(ctx.get_wikipedia_png(), "rb") as f:
        data = f.read()
    size = len(data)
    shm = shared_memory.SharedMemory(create=True, size=offset + len(data))
    shm.buf[offset : offset + len(data)] = data
    shm.close()
    term.send_command(
        cmd.clone_with(image_id=1, offset=offset, size=size).set_filename(shm.name)
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
    ctx.take_screenshot_verbose("Wikipedia, png via shared memory")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def direct_default(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    term.reset()
    # No action, no transmission type, no format - this is a direct transmission of
    # 32-bit rgb data.
    data, w, h = ctx.to_rgb_and_wh(ctx.get_tux_png(), 32)
    cmd = TransmitCommand(
        omit_action=True,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        image_id=0x12345678,
        pix_width=w,
        pix_height=h,
    )
    term.write(repr(cmd.content_to_bytes()) + "\n")
    term.send_command(cmd.set_data(data))
    term.send_command(
        PutCommand(
            image_id=0x12345678,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot(f"Tux and wiki, default transmission (direct, 32-bit data)")


@screenshot_test
def shm_rgb(ctx: TestingContext):
    term = ctx.term
    # Test with an offset, and make it divisible by the page size.
    page_size = os.sysconf("SC_PAGE_SIZE")
    offset = page_size
    for compress in [False, True]:
        for bits in [24, 32]:
            term.reset()
            cmd = TransmitCommand(
                medium=tupimage.TransmissionMedium.SHARED_MEMORY,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                format=tupimage.Format.from_bits(bits),
                compression=tupimage.Compression.from_bool(compress),
            )
            data, w, h = ctx.to_rgb_and_wh(ctx.get_tux_png(), bits, compress=compress)
            # If we don't compress, the size can be inferred from width and height.
            size = None if not compress else len(data)
            # Note that we don't unlink because the terminal does that for us. Currently
            # python will complain about the shared memory being leaked, which is a
            # bug in python.
            # TODO: In 3.13 there is a new track=False parameter to SharedMemory.
            shm = shared_memory.SharedMemory(create=True, size=offset + len(data))
            shm.buf[offset : offset + len(data)] = data
            shm.close()
            term.send_command(
                cmd.clone_with(
                    image_id=1, pix_width=w, pix_height=h, offset=offset, size=size
                ).set_filename(shm.name)
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
            ctx.take_screenshot_verbose(
                f"Tux, shared memory, {bits}-bit data, compress = {compress}"
            )


@screenshot_test
def shm_rgb(ctx: TestingContext):
    term = ctx.term
    # Test with an offset, and make it divisible by the page size.
    page_size = os.sysconf("SC_PAGE_SIZE")
    offset = page_size
    for compress in [False, True]:
        for bits in [24, 32]:
            term.reset()
            cmd = TransmitCommand(
                medium=tupimage.TransmissionMedium.SHARED_MEMORY,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                format=tupimage.Format.from_bits(bits),
                compression=tupimage.Compression.from_bool(compress),
            )
            data, w, h = ctx.to_rgb_and_wh(ctx.get_tux_png(), bits, compress=compress)
            # If we don't compress, the size can be inferred from width and height.
            size = None if not compress else len(data)
            # Note that we don't unlink because the terminal does that for us. Currently
            # python will complain about the shared memory being leaked, which is a
            # bug in python.
            # TODO: In 3.13 there is a new track=False parameter to SharedMemory.
            shm = shared_memory.SharedMemory(create=True, size=offset + len(data))
            shm.buf[offset : offset + len(data)] = data
            shm.close()
            term.send_command(
                cmd.clone_with(
                    image_id=1, pix_width=w, pix_height=h, offset=offset, size=size
                ).set_filename(shm.name)
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
            ctx.take_screenshot_verbose(
                f"Tux, shared memory, {bits}-bit data, compress = {compress}"
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
    term.send_command(cmd.clone_with(image_number=43).set_filename(ctx.get_tux_png()))
    term.send_command(
        PutCommand(
            image_number=43,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Tux, sent with an image number, separate transmit and put.")


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
                transmit_cmd.clone_with(image_number=idx + 1).set_filename(filename)
            )
        for idx, filename in enumerate(files):
            term.send_command(put_cmd.clone_with(rows=5, cols=10, image_number=idx + 1))
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
                        ctx.text_to_image(str(image_id), colorize_by_id=image_id)
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
        term.clear_screen()
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
        time.sleep(0.2)
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
    term.clear_screen()
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
    # The threshold is high because there is a grid issue in st.
    ctx.take_screenshot("Displayed some one-pixel images, some will be missing.",
                        diff_threshold=0.05)


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
    ctx.term.clear_screen()
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
    # The threshold is high because the placements that are missing are not always the
    # same, plus there is a grid issue in st. It's not a very good test.
    ctx.take_screenshot(
        "Attempting to display 5 different placements for some of the images."
        " Many placements may be missing.",
        diff_threshold=0.06,
    )


@screenshot_test(suffix="nomore", params={"nomore": True})
@screenshot_test
def direct_interrupted(ctx: TestingContext, nomore: bool = False):
    term = ctx.term

    image_id = 125 if nomore else 126

    # A command to upload and display an image using direct transmission.
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
        image_id=image_id,
    )
    cmd.set_placement(rows=10, cols=20)
    with open(ctx.get_tux_png(), "rb") as f:
        cmd.set_data(f.read())
    cmds = list(cmd.split(max_payload_size=SPLIT_PAYLOAD_SIZE))

    # Send half of the commands.
    half = len(cmds) // 2
    for i in range(half):
        term.send_command(cmds[i])
    ctx.write("Sent half of the commands.\n")

    if nomore:
        # Send a "no more" command (m=0).
        term.send_command(
            TransmitCommand(
                image_id=image_id,
                quiet=tupimage.Quietness.QUIET_ALWAYS,
                more=False,
            )
        )
        ctx.write("Sent m=0 command.\n")
        ctx.take_screenshot("After sending half of the commands and the m=0.")
    else:
        # Send a deletion command.
        term.send_command(
            DeleteCommand(
                what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
                delete_data=True,
                image_id=image_id,
                quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            )
        )
        ctx.write("Sent deletion command.\n")
        ctx.take_screenshot(
            "After sending half of the commands and the deletion command."
        )

    # Now send all the commands.
    for chunk in cmds:
        term.send_command(chunk)
    ctx.write("\nSent all of the commands.\n")
    ctx.take_screenshot("After sending all of the commands. Tux should be seen.")
