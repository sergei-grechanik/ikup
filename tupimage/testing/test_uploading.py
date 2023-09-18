import tupimage
from tupimage import GraphicsTerminal, PutCommand, TransmitCommand
from tupimage.testing import TestingContext, screenshot_test
import os
import numpy as np


@screenshot_test
def test_uploading_direct(ctx: TestingContext):
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
            columns=20,
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
            columns=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Wiki and tux, direct uploading.")


@screenshot_test
def test_uploading_direct_random_png(ctx: TestingContext):
    term = ctx.term
    np.random.seed(42)
    cmd = TransmitCommand(
        image_id=1,
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    data = ctx.generate_image(10, 10)
    print(f"size: {len(data)} bytes")
    term.send_command(cmd.clone_with(image_id=100).set_data(data))
    term.send_command(
        PutCommand(
            image_id=100,
            rows=10,
            columns=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Random < 1K image, direct uploading.")
    data = ctx.generate_image(1000, 1000)
    print(f"size: {len(data) // 1024}K")
    term.send_command(cmd.clone_with(image_id=200).set_data(data))
    term.send_command(
        PutCommand(
            image_id=200,
            rows=10,
            columns=20,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        )
    )
    term.write("\n")
    ctx.take_screenshot("Random big image, direct uploading.")
