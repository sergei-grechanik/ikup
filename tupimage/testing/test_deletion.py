import tupimage
from tupimage import DeleteCommand, GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def image_with_data(ctx: TestingContext):
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=12345,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_id=12345,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Wikipedia image.")
    term.send_command(
        DeleteCommand(
            image_id=12345,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )
    ctx.take_screenshot("Deleted the image.")
    # Check that we cannot create a placement for this image.
    term.send_command(
        PutCommand(
            image_id=12345,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"\nResponse message: {response.message}\n")
    ctx.assert_true(
        response.is_err("ENOENT", image_id=12345, placement_id=None),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("ENOENT response, no assertion failures.")


@screenshot_test
def image_preserve_data(ctx: TestingContext):
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=12345,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_id=12345,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.write("\n")
    ctx.take_screenshot("Wikipedia image.")
    term.send_command(
        DeleteCommand(
            image_id=12345,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=False,
        )
    )
    ctx.take_screenshot("Deleted the image.")
    # Check that we still can create a placement for this image.
    term.send_command(
        PutCommand(
            image_id=12345,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Recreated the image.")


@screenshot_test
def image_with_data_two_placements(ctx: TestingContext):
    term = ctx.term
    term.send_command(
        TransmitCommand(
            image_id=12345,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_id=12345,
            placement_id=42,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.move_cursor(up=9)
    term.send_command(
        PutCommand(
            image_id=12345,
            placement_id=40,
            rows=10,
            cols=10,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Two wikipedia images.")
    term.send_command(
        DeleteCommand(
            image_id=12345,
            placement_id=42,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )
    ctx.take_screenshot("Deleted the left image.")
    # Check that we can still create a placement for this image.
    term.send_command(
        PutCommand(
            image_id=12345,
            placement_id=42,
            rows=5,
            cols=10,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Created another placement with the same id.")
    term.send_command(
        DeleteCommand(
            image_id=12345,
            placement_id=42,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )
    term.send_command(
        DeleteCommand(
            image_id=12345,
            placement_id=40,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )
    ctx.take_screenshot("Deleted both placements.")
    # Check that we cannot create placements anymore.
    term.send_command(
        PutCommand(
            image_id=12345,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"\nResponse message: {response.message}\n")
    ctx.assert_true(
        response.is_err("ENOENT", image_id=12345, placement_id=None),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("ENOENT response, no assertion failures.")


@screenshot_test(suffix="direct_transmission", params={"direct": True})
@screenshot_test
def image_by_number(ctx: TestingContext, direct: bool = False):
    term = ctx.term
    if direct:
        term = term.clone_with(force_direct_transmission=True)
    term.send_command(
        TransmitCommand(
            image_number=1234,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_wikipedia_png())
    )
    term.send_command(
        PutCommand(
            image_number=1234,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.move_cursor(up=9)
    term.send_command(
        TransmitCommand(
            image_number=42,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_tux_png())
    )
    term.send_command(
        PutCommand(
            image_number=42,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.move_cursor(up=9)
    term.send_command(
        TransmitCommand(
            image_number=42,
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
        ).set_filename(ctx.get_transparency_png())
    )
    term.send_command(
        PutCommand(
            image_number=42,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.move_cursor(up=9)
    ctx.take_screenshot("Three images.")
    term.send_command(
        DeleteCommand(
            image_number=42,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_NUMBER,
            delete_data=True,
        )
    )
    ctx.take_screenshot("Deleted the rightmost image.")
    term.send_command(
        DeleteCommand(
            image_number=1234,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_NUMBER,
            delete_data=True,
        )
    )
    ctx.take_screenshot("The rightmost and leftmost images are deleted.")
    term.send_command(
        PutCommand(
            image_number=42,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Created another tux.")
    term.send_command(
        DeleteCommand(
            image_number=42,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_NUMBER,
            delete_data=True,
        )
    )
    # Kitty doesn't always refresh immediately after the deletion, force redraw.
    term.write("\n")
    ctx.take_screenshot("Deleted everything.")
    # We don't check that we cannot create placements anymore, because there
    # might be pre-existing placements with the same image number. There is no
    # way to reliably delete them.


@screenshot_test
def everything(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    ).set_placement(rows=10, cols=20)
    term.send_command(cmd.clone_with(image_id=42).set_filename(ctx.get_wikipedia_png()))
    term.move_cursor(up=9)
    term.send_command(cmd.clone_with(image_id=43).set_filename(ctx.get_tux_png()))
    term.move_cursor(up=9)
    term.send_command(
        cmd.clone_with(image_id=44).set_filename(ctx.get_transparency_png())
    )
    term.write("\n")
    term.send_command(
        PutCommand(
            image_id=43,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        ),
        force_placeholders=True,
    )
    term.move_cursor(up=9)
    ctx.take_screenshot("Wiki, tux, dice, then tux using placeholders")
    term.send_command(
        DeleteCommand(
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.VISIBLE_PLACEMENTS,
            delete_data=True,
        )
    )
    ctx.take_screenshot("Deleted all images except for the placeholder.")
    # Check that we can create a placement for the 43 image.
    term.send_command(
        PutCommand(
            image_id=43,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    ctx.take_screenshot("Two tuxes.")
    # Check that we cannot create a placement for the 42 image.
    term.send_command(
        PutCommand(
            image_id=42,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"\nResponse message: {response.message}\n")
    ctx.assert_true(
        response.is_err("ENOENT", image_id=42, placement_id=None),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("ENOENT response, no assertion failures.")


@screenshot_test
def underneath_text_restoration(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    # First create some placeholder images.
    id1 = 0x12345678
    id2 = 0xFF000000
    term.send_command(
        cmd.clone_with(image_id=id1)
        .set_placement(rows=19, cols=40, virtual=True)
        .set_filename(ctx.get_transparency_png())
    )
    term.send_command(
        cmd.clone_with(image_id=id2)
        .set_placement(rows=19, cols=40, virtual=True)
        .set_filename(ctx.get_diagonal_png())
    )
    term.print_placeholder(image_id=id1, end_col=40, end_row=19, pos=(0, 0))
    term.print_placeholder(image_id=id2, end_col=40, end_row=19, pos=(40, 0))
    # Also add some text. Include wide characters.
    term.move_cursor_abs(col=0, row=20)
    term.write("Hello 😀😁😂😃😄😅 " * 10)
    ctx.take_screenshot("Just two placeholder images and some text.")

    # Now upload some images for classic placements.
    id3 = 0xFF0000FF
    id4 = 42
    term.send_command(cmd.clone_with(image_id=id3).set_filename(ctx.get_tux_png()))
    term.send_command(
        cmd.clone_with(image_id=id4).set_filename(ctx.get_wikipedia_png())
    )

    # Create some classic placements.
    term.move_cursor_abs(col=0, row=0)
    term.send_command(
        PutCommand(
            image_id=id3,
            placement_id=1,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=6, row=6)
    term.send_command(
        PutCommand(
            image_id=id4,
            placement_id=1,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=12, row=12)
    term.send_command(
        PutCommand(
            image_id=id3,
            placement_id=2,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=18, row=18)
    term.send_command(
        PutCommand(
            image_id=id1,
            placement_id=1,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )

    # Create more classic placements.
    term.move_cursor_abs(col=70, row=0)
    term.send_command(
        PutCommand(
            image_id=id4,
            placement_id=2,
            rows=6,
            cols=12,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    # This one overrides the previous one. It's intentional.
    term.move_cursor_abs(col=70, row=4)
    term.send_command(
        PutCommand(
            image_id=id4,
            placement_id=2,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=70, row=8)
    term.send_command(
        PutCommand(
            image_id=id3,
            placement_id=3,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=70, row=12)
    term.send_command(
        PutCommand(
            image_id=id4,
            placement_id=3,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=70, row=16)
    term.send_command(
        PutCommand(
            image_id=id4,
            placement_id=4,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )
    term.move_cursor_abs(col=70, row=20)
    term.send_command(
        PutCommand(
            image_id=id1,
            placement_id=2,
            rows=10,
            cols=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            do_not_move_cursor=True,
        )
    )

    ctx.take_screenshot("Classic placements over placeholders.")

    # Now delete some placements.
    term.send_command(
        DeleteCommand(
            image_id=id4,
            placement_id=1,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )
    term.send_command(
        DeleteCommand(
            image_id=id4,
            placement_id=3,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )

    ctx.take_screenshot("Deleted one wiki on the left and one on the right.")

    # Now delete all penguins.
    term.send_command(
        DeleteCommand(
            image_id=id3,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.IMAGE_OR_PLACEMENT_BY_ID,
            delete_data=True,
        )
    )

    ctx.take_screenshot("Deleted all tuxes.")

    # Now delete everything visible.
    term.send_command(
        DeleteCommand(
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            what=tupimage.WhatToDelete.VISIBLE_PLACEMENTS,
            delete_data=True,
        )
    )

    ctx.take_screenshot("Deleted all classic placements.")
