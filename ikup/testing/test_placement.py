import math

import ikup
from ikup import PutCommand, TransmitCommand, Quietness
from ikup.testing import TestingContext, screenshot_test


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def movecursor(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, cols=20)
    )
    ctx.take_screenshot("Wikipedia logo. May be slightly stretched in kitty.")
    term.move_cursor(up=9)
    term.send_command(
        cmd.clone_with(image_id=2)
        .set_filename(ctx.get_column_png())
        .set_placement(rows=10, cols=5)
    )
    term.move_cursor(up=9)
    term.send_command(
        PutCommand(image_id=1, rows=10, cols=20, quiet=Quietness.QUIET_UNLESS_ERROR)
    )
    term.move_cursor(up=9)
    term.send_command(
        PutCommand(image_id=1, rows=5, cols=10, quiet=Quietness.QUIET_UNLESS_ERROR)
    )
    term.move_cursor(left=10, down=1)
    term.send_command(
        PutCommand(image_id=1, rows=5, cols=10, quiet=Quietness.QUIET_UNLESS_ERROR)
    )
    ctx.take_screenshot("Wikipedia logo and some columns.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def nomovecursor(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, cols=20, do_not_move_cursor=True)
    )
    ctx.take_screenshot(
        "Wikipedia logo (slightly stretched in kitty). The cursor should be at"
        " the top left corner."
    )
    term.move_cursor(right=20)
    term.send_command(
        cmd.clone_with(image_id=2)
        .set_filename(ctx.get_column_png())
        .set_placement(rows=10, cols=5, do_not_move_cursor=True)
    )
    term.move_cursor(right=5)
    term.send_command(
        PutCommand(
            image_id=1,
            rows=10,
            cols=20,
            quiet=Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor(right=20)
    term.send_command(
        PutCommand(
            image_id=1,
            rows=5,
            cols=10,
            quiet=Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor(down=5)
    term.send_command(
        PutCommand(
            image_id=1,
            rows=5,
            cols=10,
            quiet=Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    ctx.take_screenshot(
        "Wikipedia logo and some columns. The cursor should be at the top left"
        " corner of the last column image."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def multisize(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(1, 5):
        start_col = 0
        for c in range(1, 10):
            term.move_cursor_abs(col=start_col)
            term.send_command(
                PutCommand(
                    image_id=1,
                    rows=r,
                    cols=c,
                    quiet=Quietness.QUIET_UNLESS_ERROR,
                    do_not_move_cursor=True,
                )
            )
            start_col += c
        term.move_cursor_abs(col=0)
        term.move_cursor(down=r)
    ctx.take_screenshot(
        "A grid of penguins of various sizes. On kitty they may be stretched."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def oob(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_ruler_png()))
    for r in range(24):
        term.move_cursor_abs(row=r, col=80 - (24 - r))
        term.send_command(
            PutCommand(
                image_id=1,
                rows=1,
                cols=24,
                quiet=Quietness.QUIET_UNLESS_ERROR,
                do_not_move_cursor=True,
            )
        )
    term.move_cursor_abs(row=0, col=0)
    ctx.take_screenshot("A ruler that goes off the screen. Not to scale.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def oob_down(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(3):
        term.send_command(
            PutCommand(
                image_id=1,
                rows=10,
                cols=20,
                quiet=Quietness.QUIET_UNLESS_ERROR,
                do_not_move_cursor=False,
            )
        )
    ctx.take_screenshot("Three penguins, arranged diagonally. The top one is cut off.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def oob_down_nomovecursor(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png()))
    for r in range(3):
        term.send_command(
            PutCommand(
                image_id=1,
                rows=10,
                cols=20,
                quiet=Quietness.QUIET_UNLESS_ERROR,
                do_not_move_cursor=True,
            )
        )
        term.move_cursor(down=10)
    ctx.take_screenshot(
        "Three penguins arranged vertically. The bottom one is cut off because"
        " the terminal shouldn't introduce new lines when C=1."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def scrolling(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(cmd.clone_with(image_id=1).set_filename(ctx.get_wikipedia_png()))
    term.send_command(cmd.clone_with(image_id=2).set_filename(ctx.get_tux_png()))
    for y in [10, 20]:
        term.move_cursor_abs(row=y, col=0)
        for i in range(80):
            if i % 3 == 0:
                term.write(str(i % 10))
            else:
                term.send_command(
                    PutCommand(
                        image_id=i % 3,
                        rows=1,
                        cols=1,
                        quiet=Quietness.QUIET_UNLESS_ERROR,
                    )
                )
    for y in range(11, 20):
        term.move_cursor_abs(row=y, col=0)
        term.write(str(y % 10))
    term.move_cursor_abs(row=12, col=1)
    term.send_command(
        PutCommand(
            image_id=1,
            rows=7,
            cols=14,
            quiet=Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.move_cursor_abs(row=12, col=15)
    term.send_command(
        PutCommand(
            image_id=2,
            rows=7,
            cols=14,
            quiet=Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot(
        "The initial state of the scrolling test: wiki logo and tux between two"
        " rows of small images and numbers"
    )
    term.set_margins(top=11, bottom=19)
    for i in range(3):
        term.scroll_down()
        ctx.take_screenshot(f"Scrolled down (moved the content down) {i + 1} times")
    for i in range(6):
        term.scroll_up()
        ctx.take_screenshot(f"Scrolled up (moved the content up) {i + 1} times")
    term.scroll_up(5)
    ctx.take_screenshot("Scrolled up 6 more lines")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def numbers(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.DIRECT,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    for step in [3, 4]:
        image_id = 0
        for y in range(24):
            for x in range(0, 80, step):
                image_id += 1
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
                        cols=step,
                        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                    )
                )
        ctx.take_screenshot(
            f"Screen filled with numbers. Each one is {step} columns wide."
        )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def image_ids(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.DIRECT,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    image_ids = []
    byte_values = [0, 1, 128, 255]
    for b3 in byte_values:
        for b2 in byte_values:
            for b1 in byte_values:
                for b0 in byte_values:
                    image_ids.append(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    idx = 0
    for y in range(24):
        for x in range(0, 80, 5):
            idx += 1
            if idx >= len(image_ids):
                break
            image_id = image_ids[idx]
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
                    cols=5,
                    quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                )
            )
    ctx.take_screenshot(f"Images with different ids.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def placement_ids(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.DIRECT,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    image_ids = []
    byte_values = [0, 1, 128, 255]
    for b3 in byte_values:
        for b2 in byte_values:
            for b1 in byte_values:
                for b0 in byte_values:
                    image_ids.append(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    idx = 0
    for y in range(24):
        for x in range(0, 80, 5):
            idx += 1
            if idx >= len(image_ids):
                break
            image_id = image_ids[idx]
            term.send_command(
                cmd.clone_with(image_id=image_id).set_data(
                    ctx.to_png(
                        ctx.text_to_image(str(image_id), colorize_by_id=image_id)
                    )
                )
            )
            # Placement IDs may be only 24-bit.
            term.send_command(
                PutCommand(
                    image_id=image_id,
                    placement_id=image_id & 0x00FFFFFF,
                    rows=1,
                    cols=5,
                    quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                )
            )
    ctx.take_screenshot(f"Images with different ids and placement ids.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def overwrite_with_spaces(ctx: TestingContext, placeholder: bool = False) -> None:
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1)
        .set_filename(ctx.get_transparency_png())
        .set_placement(rows=20, cols=40)
    )
    term.move_cursor(up=14, left=30)
    term.write("\033[48;5;1m\033[38;5;2m")
    for i in range(10):
        term.write(" " * 15 + "X" * 5)
        term.move_cursor(left=20, down=1)
    if placeholder:
        ctx.take_screenshot(
            "Dice with a red square in the middle (hiding part of image). The"
            " right 1/3 of the square is covered with green Xs."
        )
    else:
        ctx.take_screenshot(
            "Dice with a square patch of red backround in the middle"
            " (underneath the image). The right 1/3 of the square is covered"
            " with green Xs. The Xs may behave differently in different"
            " terminals."
        )


@screenshot_test
def no_id_no_number(ctx: TestingContext) -> None:
    term = ctx.term
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    cmd.set_placement(rows=10, cols=20)
    term.send_command(cmd.clone_with().set_filename(ctx.get_tux_png()))
    term.move_cursor(up=9)
    term.send_command(cmd.clone_with().set_filename(ctx.get_wikipedia_png()))
    term.write("\n")
    term.send_command(cmd.clone_with().set_filename(ctx.get_transparency_png()))
    ctx.take_screenshot("Tux, wiki, and then dice on the next line.")


@screenshot_test
def no_columns(ctx: TestingContext) -> None:
    term = ctx.term
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    cmd.set_placement(rows=7)
    term.send_command(cmd.clone_with().set_filename(ctx.get_small_arrow_png()))
    term.write("\n")
    term.send_command(cmd.clone_with().set_filename(ctx.get_wikipedia_png()))
    term.write("\n")
    term.send_command(cmd.clone_with().set_filename(ctx.get_transparency_png()))
    ctx.take_screenshot(
        "Small arrow, wiki, and dice. 7 rows each, the number of columns is inferred"
    )


@screenshot_test
def no_rows(ctx: TestingContext) -> None:
    term = ctx.term
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    cmd.set_placement(cols=20)
    term.send_command(cmd.clone_with().set_filename(ctx.get_transparency_png()))
    term.move_cursor_abs(row=0)
    term.send_command(cmd.clone_with().set_filename(ctx.get_wikipedia_png()))
    term.move_cursor_abs(row=0)
    term.send_command(cmd.clone_with().set_filename(ctx.get_small_arrow_png()))
    term.write(" ")
    ctx.take_screenshot(
        "Dice, wiki, and small arrow. 20 columns each, the number of rows is"
        " inferred"
    )


@screenshot_test
def no_size(ctx: TestingContext) -> None:
    term = ctx.term
    cmd = TransmitCommand(
        medium=ikup.TransmissionMedium.DIRECT,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    )
    cmd.set_placement()
    term.send_command(
        cmd.clone_with().set_data(
            ctx.to_png(ctx.text_to_image(("Sample multiline text\n" * 10)[:-1]))
        )
    )
    pos = term.get_cursor_position()
    term.move_cursor_abs(row=0)
    term.send_command(
        cmd.clone_with().set_data(
            ctx.to_png(ctx.text_to_image(("Blah blah blah\n" * 5)[:-1]))
        )
    )
    term.move_cursor_abs(pos=pos)
    term.write("\n")
    term.send_command(
        cmd.clone_with().set_data(ctx.to_png(ctx.text_to_image("Long text " * 8)))
    )
    ctx.take_screenshot("Text boxes, the number of rows/columns is inferred")


@screenshot_test
def subimage(ctx: TestingContext) -> None:
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=1,
            medium=ikup.TransmissionMedium.FILE,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            format=ikup.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    cmd = PutCommand(
        image_id=1,
        src_x=100,
        src_y=50,
        src_w=200,
        src_h=100,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(cmd)
    term.write("\n80 cols x 5 rows:\n")
    term.send_command(cmd.clone_with(rows=5, cols=80))
    term.write("\n4 rows and 6 cols:\n")
    term.send_command(cmd.clone_with(rows=4))
    term.move_cursor(up=3)
    term.send_command(cmd.clone_with(cols=6))
    ctx.take_screenshot("Same subimage of wikipedia, different sizes")


@screenshot_test
def subimage_no_size(ctx: TestingContext) -> None:
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=1,
            medium=ikup.TransmissionMedium.FILE,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            format=ikup.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    cmd = PutCommand(
        image_id=1,
        src_x=300,
        src_y=300,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(cmd)
    term.write("\n80 cols x 5 rows:\n")
    term.send_command(cmd.clone_with(rows=5, cols=80))
    term.write("\n4 rows and 6 cols:\n")
    term.send_command(cmd.clone_with(rows=4))
    term.move_cursor(up=3)
    term.send_command(cmd.clone_with(cols=6))
    ctx.take_screenshot("Same subimage of wikipedia, different sizes")


@screenshot_test
def subimage_slice_horizontally(ctx: TestingContext) -> None:
    term = ctx.term
    for file in [
        ctx.get_wikipedia_png(),
        ctx.get_tux_png(),
        ctx.get_small_arrow_png(),
    ]:
        term.reset()
        term.send_command(
            TransmitCommand(
                image_id=1,
                medium=ikup.TransmissionMedium.FILE,
                quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                format=ikup.Format.PNG,
            ).set_filename(file)
        )
        cmd = PutCommand(image_id=1, rows=2, quiet=ikup.Quietness.QUIET_UNLESS_ERROR)
        _, height = ctx.get_image_size(file)
        slice_h = (height + 9) // 10
        for i in range(0, 10):
            term.send_command(cmd.clone_with(src_y=i * slice_h, src_h=slice_h))
            term.write("\n")
        ctx.take_screenshot(
            "An image sliced horizontally, may be stretched, but without gaps"
        )


@screenshot_test
def subimage_slice_vertically(ctx: TestingContext) -> None:
    term = ctx.term
    for file in [
        ctx.get_ruler_png(),
        ctx.get_tux_png(),
        ctx.get_small_arrow_png(),
    ]:
        term.reset()
        term.send_command(
            TransmitCommand(
                image_id=1,
                medium=ikup.TransmissionMedium.FILE,
                quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                format=ikup.Format.PNG,
            ).set_filename(file)
        )
        cmd = PutCommand(image_id=1, cols=2, quiet=ikup.Quietness.QUIET_UNLESS_ERROR)
        width, _ = ctx.get_image_size(file)
        slice_w = (width + 9) // 10
        for i in range(0, 10):
            term.send_command(cmd.clone_with(src_x=i * slice_w, src_w=slice_w))
            term.move_cursor_abs(row=0)
        ctx.take_screenshot(
            "An image sliced vertically, may be stretched, but without gaps"
        )


@screenshot_test
def subimage_oob(ctx: TestingContext) -> None:
    term = ctx.term
    trcmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    ).set_filename(ctx.get_small_arrow_png())
    term.send_command(trcmd)
    putcmd = PutCommand(
        image_id=1,
        src_x=0,
        src_y=0,
        src_w=100,
        src_h=100,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(putcmd)
    term.write(". <- bottom-right corner")
    ctx.take_screenshot(
        "Small arrow, subimage, w and h are way out of bounds, but we expect"
        " them to be truncated and there will not be much empty space"
    )
    term.reset()
    term.send_command(trcmd)
    term.send_command(putcmd.clone_with(rows=10, cols=20))
    term.write(". <- bottom-right corner")
    ctx.take_screenshot(
        "Small arrow, subimage, w and h are way out of bounds. rows and columns"
        " are explicitly specified, the behavior is the same"
    )


@screenshot_test
def subimage_thin(ctx: TestingContext) -> None:
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=1,
            medium=ikup.TransmissionMedium.FILE,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            format=ikup.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=200,
            src_h=3,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("1\n")
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=200,
            src_h=3,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("2\n")
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=200,
            src_h=3,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("3\n")
    ctx.take_screenshot(
        "A very thin vertical slice of wiki repeated 3 times. Note the alignment."
    )
    term.reset()
    term.write("123\n")
    term.send_command(
        TransmitCommand(
            image_id=1,
            medium=ikup.TransmissionMedium.FILE,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            format=ikup.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=100,
            src_x=200,
            src_w=2,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor(right=1)
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=100,
            src_x=200,
            src_w=2,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor(right=1)
    term.send_command(
        PutCommand(
            image_id=1,
            src_y=100,
            src_x=200,
            src_w=2,
            quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor(right=1)
    ctx.take_screenshot(
        "A very thin vertical slice of wiki repeated 3 times. Note the alignment."
    )


@screenshot_test
def subimage_oob_xy(ctx: TestingContext) -> None:
    term = ctx.term
    trcmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    ).set_filename(ctx.get_small_arrow_png())
    term.send_command(trcmd)
    putcmd = PutCommand(
        image_id=1,
        src_x=150,
        src_y=150,
        src_w=100,
        src_h=100,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(putcmd)
    term.write(". <- bottom-right corner")
    ctx.take_screenshot(
        "Both x and y are oob. Most probably the image will be empty, but most"
        " importantly the terminal shouldn't crash or hang."
    )


@screenshot_test
def subimage_negative_xy(ctx: TestingContext) -> None:
    term = ctx.term
    trcmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    ).set_filename(ctx.get_small_arrow_png())
    term.send_command(trcmd)
    putcmd = PutCommand(
        image_id=1,
        src_x=-100,
        src_y=-100,
        src_w=200,
        src_h=200,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(putcmd)
    term.write(". <- bottom-right corner")
    ctx.take_screenshot(
        "Both x and y are negative. The image may be empty or just the image"
        " without additional margins, but most importantly the terminal"
        " shouldn't crash or hang."
    )


@screenshot_test
def subimage_negative_wh(ctx: TestingContext) -> None:
    term = ctx.term
    trcmd = TransmitCommand(
        image_id=1,
        medium=ikup.TransmissionMedium.FILE,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
        format=ikup.Format.PNG,
    ).set_filename(ctx.get_small_arrow_png())
    term.send_command(trcmd)
    putcmd = PutCommand(
        image_id=1,
        src_x=10,
        src_y=10,
        src_w=-9,
        src_h=-9,
        quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
    )
    term.send_command(putcmd)
    term.write(". <- bottom-right corner")
    ctx.take_screenshot(
        "Both w and h are negative. The image may be empty or display some part"
        " of the image, but most importantly the terminal shouldn't crash or"
        " hang."
    )


@screenshot_test
def alpha(ctx: TestingContext) -> None:
    term = ctx.term
    for color in [
        (0, 0, 0),
        (255, 255, 255),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
    ]:
        term.send_command(
            TransmitCommand(
                image_id=1,
                medium=ikup.TransmissionMedium.DIRECT,
                quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
                format=ikup.Format.PNG,
            ).set_data(ctx.to_png(ctx.alpha_test_image(320, 160, color)))
        )
        for y in range(3):
            term.write(f"\033[49m")
            term.write(" " * 80 + "\n")
        for y in range(4):
            term.write(f"\033[48;2;0;0;0m")
            term.write(" " * 80 + "\n")
        for y in range(4):
            term.write(f"\033[48;2;255;255;255m")
            term.write(" " * 80 + "\n")
        for y in range(3):
            term.write(f"\033[48;2;255;0;0m")
            term.write(" " * 80 + "\n")
        for y in range(3):
            term.write(f"\033[48;2;0;255;0m")
            term.write(" " * 80 + "\n")
        for y in range(3):
            term.write(f"\033[48;2;0;0;255m")
            term.write(" " * 80 + "\n")
        term.move_cursor(up=20)
        term.send_command(
            PutCommand(
                image_id=1,
                rows=20,
                cols=80,
                quiet=ikup.Quietness.QUIET_UNLESS_ERROR,
            )
        )
        ctx.take_screenshot(
            f"Rainbow background and a gradient going from transparent to solid, color {color}"
        )
        term.reset()
