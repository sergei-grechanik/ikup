import tupimage
from tupimage import (
    GraphicsTerminal,
    PutCommand,
    TransmitCommand,
    DeleteCommand,
)
from tupimage.testing import TestingContext, screenshot_test
import numpy as np


@screenshot_test
def test_delete_image(ctx: TestingContext):
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
            columns=20,
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
            columns=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    response = term.receive_response(timeout=3)
    ctx.write(
        f"\nResponse message: {response.message} {response.placement_id}\n"
    )
    ctx.assert_true(
        response.is_err("ENOENT", image_id=12345, placement_id=None),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("ENOENT response, no assertion failures.")
