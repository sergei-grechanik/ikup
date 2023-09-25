import tupimage
from tupimage import GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_display_movecursor(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, columns=20)
    )
    ctx.take_screenshot("Wikipedia logo. May be slightly stretched in kitty.")
    term.move_cursor(up=9)
    term.send_command(
        cmd.clone_with(image_id=2)
        .set_filename(ctx.get_column_png())
        .set_placement(rows=10, columns=5)
    )
    term.move_cursor(up=9)
    term.send_command(PutCommand(image_id=1, rows=10, columns=20, quiet=1))
    term.move_cursor(up=9)
    term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1))
    term.move_cursor(left=10, down=1)
    term.send_command(PutCommand(image_id=1, rows=5, columns=10, quiet=1))
    ctx.take_screenshot("Wikipedia logo and some columns.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_display_nomovecursor(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, columns=20, do_not_move_cursor=True)
    )
    ctx.take_screenshot(
        "Wikipedia logo (slightly stretched in kitty). The cursor should be at"
        " the top left corner."
    )
    term.move_cursor(right=20)
    term.send_command(
        cmd.clone_with(image_id=2)
        .set_filename(ctx.get_column_png())
        .set_placement(rows=10, columns=5, do_not_move_cursor=True)
    )
    term.move_cursor(right=5)
    term.send_command(
        PutCommand(
            image_id=1, rows=10, columns=20, quiet=1, do_not_move_cursor=True
        )
    )
    term.move_cursor(right=20)
    term.send_command(
        PutCommand(
            image_id=1, rows=5, columns=10, quiet=1, do_not_move_cursor=True
        )
    )
    term.move_cursor(down=5)
    term.send_command(
        PutCommand(
            image_id=1, rows=5, columns=10, quiet=1, do_not_move_cursor=True
        )
    )
    ctx.take_screenshot(
        "Wikipedia logo and some columns. The cursor should be at the top left"
        " corner of the last column image."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_multisize(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png())
    )
    for r in range(1, 5):
        start_col = 0
        for c in range(1, 10):
            term.move_cursor_abs(col=start_col)
            term.send_command(
                PutCommand(
                    image_id=1,
                    rows=r,
                    columns=c,
                    quiet=1,
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
def test_oob(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1).set_filename(ctx.get_ruler_png())
    )
    for r in range(24):
        term.move_cursor_abs(row=r, col=80 - (24 - r))
        term.send_command(
            PutCommand(
                image_id=1, rows=1, columns=24, quiet=1, do_not_move_cursor=True
            )
        )
    term.move_cursor_abs(row=0, col=0)
    ctx.take_screenshot("A ruler that goes off the screen. Not to scale.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_oob_down(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png())
    )
    for r in range(3):
        term.send_command(
            PutCommand(
                image_id=1,
                rows=10,
                columns=20,
                quiet=1,
                do_not_move_cursor=False,
            )
        )
    ctx.take_screenshot(
        "Three penguins, arranged diagonally. The top one is cut off."
    )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_oob_down_nomovecursor(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1).set_filename(ctx.get_tux_png())
    )
    for r in range(3):
        term.send_command(
            PutCommand(
                image_id=1,
                rows=10,
                columns=20,
                quiet=1,
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
def test_scrolling(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=1).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        cmd.clone_with(image_id=2).set_filename(ctx.get_tux_png())
    )
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
                        columns=1,
                        quiet=1,
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
            columns=14,
            quiet=1,
        )
    )
    term.move_cursor_abs(row=12, col=15)
    term.send_command(
        PutCommand(
            image_id=2,
            rows=7,
            columns=14,
            quiet=1,
        )
    )
    ctx.take_screenshot(
        "The initial state of the scrolling test: wiki logo and tux between two"
        " rows of small images and numbers"
    )
    term.set_margins(top=11, bottom=19)
    for i in range(3):
        term.scroll_up()
        ctx.take_screenshot(
            f"Scrolled up (moved the content down) {i + 1} times"
        )
    for i in range(6):
        term.scroll_down()
        ctx.take_screenshot(
            f"Scrolled down (moved the content up) {i + 1} times"
        )
    term.scroll_down(5)
    ctx.take_screenshot("Scrolled down 6 more lines")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_numbers(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    for step in [3, 4]:
        image_id = 0
        for y in range(24):
            for x in range(0, 80, step):
                image_id += 1
                term.send_command(
                    cmd.clone_with(image_id=image_id).set_data(
                        ctx.to_png(ctx.text_to_image(str(image_id)))
                    )
                )
                term.send_command(
                    PutCommand(
                        image_id=image_id,
                        rows=1,
                        columns=step,
                        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                    )
                )
        ctx.take_screenshot(
            f"Screen filled with numbers. Each one is {step} columns wide."
        )


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_image_ids(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
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
                    ctx.to_png(ctx.text_to_image(str(image_id)))
                )
            )
            term.send_command(
                PutCommand(
                    image_id=image_id,
                    rows=1,
                    columns=5,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                )
            )
    ctx.take_screenshot(f"Images with different ids.")


@screenshot_test(suffix="placeholder", params={"placeholder": True})
@screenshot_test
def test_placement_ids(ctx: TestingContext, placeholder: bool = False):
    term = ctx.term.clone_with(force_placeholders=placeholder)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
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
                    ctx.to_png(ctx.text_to_image(str(image_id)))
                )
            )
            # Placement IDs may be only 24-bit.
            term.send_command(
                PutCommand(
                    image_id=image_id,
                    placement_id=image_id & 0x00FFFFFF,
                    rows=1,
                    columns=5,
                    quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
                )
            )
    ctx.take_screenshot(f"Images with different ids and placement ids.")
