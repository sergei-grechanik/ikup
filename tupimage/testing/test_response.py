import tupimage
from tupimage import (
    GraphicsTerminal,
    PutCommand,
    TransmitCommand,
    GraphicsResponse,
)
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def test_response_ok_transmit(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
    )
    # Image id.
    term.send_command(
        cmd.clone_with(image_id=42).set_filename(ctx.get_tux_png())
    )
    response = term.receive_response(timeout=3)
    ctx.assert_equal(response, GraphicsResponse.ok_response(image_id=42))
    # Image number. The generated image id may be random.
    term.send_command(
        cmd.clone_with(image_number=12345).set_filename(ctx.get_wikipedia_png())
    )
    response = term.receive_response(timeout=3)
    ctx.assert_true(response.image_id is not None)
    ctx.assert_true(response.image_id != 0)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(
            image_number=12345, image_id=response.image_id
        ),
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_ok_direct_transmit(ctx: TestingContext):
    term = ctx.term
    # Direct uploading.
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
        image_id=100,
    )
    with open(ctx.get_wikipedia_png(), "rb") as f:
        cmd.set_data(f.read())
    cmds = list(cmd.split(term.autosplit_max_size))
    ctx.write(f"Need to send {len(cmds)} direct uploading commands\n")
    half = len(cmds) // 2
    for i in range(half):
        term.send_command(cmds[i])
    semiresponse = term.receive_response(timeout=1)
    ctx.assert_true(
        not semiresponse.is_valid,
        "There should be no response until all data is sent",
    )
    for i in range(half, len(cmds)):
        term.send_command(cmds[i])
    response = term.receive_response(timeout=3)
    ctx.assert_equal(response, GraphicsResponse.ok_response(image_id=100))
    # Direct uploading with image number.
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
        image_number=200,
    )
    with open(ctx.get_tux_png(), "rb") as f:
        cmd.set_data(f.read())
    cmds = list(cmd.split(term.autosplit_max_size))
    ctx.write(f"Need to send {len(cmds)} direct uploading commands\n")
    half = len(cmds) // 2
    for i in range(half):
        term.send_command(cmds[i])
    semiresponse = term.receive_response(timeout=1)
    ctx.assert_true(
        not semiresponse.is_valid,
        "There should be no response until all data is sent",
    )
    for i in range(half, len(cmds)):
        term.send_command(cmds[i])
    response = term.receive_response(timeout=3)
    ctx.assert_true(response.image_id is not None)
    ctx.assert_true(response.image_id != 0)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(
            image_number=200, image_id=response.image_id
        ),
    )
    ctx.write("All done\n")
    ctx.take_screenshot("No assertion failures")


@screenshot_test(suffix="fixed_placement_id", params={"placement_id": 123})
@screenshot_test
def test_response_ok_put(ctx: TestingContext, placement_id=None):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
    )
    # Transmit+put, image id.
    term.send_command(
        cmd.clone_with(image_id=42)
        .set_filename(ctx.get_tux_png())
        .set_placement(rows=10, columns=20, placement_id=placement_id)
    )
    term.move_cursor(up=9)
    response = term.receive_response(timeout=3)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(image_id=42, placement_id=placement_id),
    )
    # Transmit+put, image number.
    term.send_command(
        cmd.clone_with(image_number=12345)
        .set_filename(ctx.get_wikipedia_png())
        .set_placement(rows=10, columns=20, placement_id=placement_id)
    )
    term.write("\n")
    response = term.receive_response(timeout=3)
    image_id = response.image_id
    ctx.assert_true(response.image_id is not None)
    ctx.assert_true(response.image_id != 0)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(
            image_number=12345, image_id=image_id, placement_id=placement_id
        ),
    )
    # Avoid using the same placement_id.
    if placement_id is not None:
        placement_id += 1
    # Just put, image id.
    term.send_command(
        PutCommand(
            image_id=42,
            rows=5,
            columns=10,
            quiet=tupimage.Quietness.VERBOSE,
            placement_id=placement_id,
        )
    )
    term.move_cursor(up=4)
    response = term.receive_response(timeout=3)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(image_id=42, placement_id=placement_id),
    )
    # Just put, image number.
    term.send_command(
        PutCommand(
            image_number=12345,
            rows=5,
            columns=10,
            quiet=tupimage.Quietness.VERBOSE,
            placement_id=placement_id,
        )
    )
    term.write("\n")
    response = term.receive_response(timeout=3)
    # Same image_id as before.
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(
            image_number=12345, image_id=image_id, placement_id=placement_id
        ),
    )
    ctx.take_screenshot("Ok responses")


@screenshot_test(suffix="fixed_placement_id", params={"placement_id": 123})
@screenshot_test
def test_response_ok_direct_transmit_and_put(
    ctx: TestingContext, placement_id=None
):
    term = ctx.term
    # Direct uploading + put.
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
        image_id=100,
    )
    cmd.set_placement(rows=10, columns=20, placement_id=placement_id)
    with open(ctx.get_wikipedia_png(), "rb") as f:
        cmd.set_data(f.read())
    cmds = list(cmd.split(term.autosplit_max_size))
    ctx.write(f"Need to send {len(cmds)} direct uploading commands\n")
    half = len(cmds) // 2
    for i in range(half):
        term.send_command(cmds[i])
    ctx.write("Sent half of the commands.\n")
    semiresponse = term.receive_response(timeout=1)
    ctx.assert_true(
        not semiresponse.is_valid,
        f"There should be no response until all data is sent: {semiresponse}",
    )
    ctx.take_screenshot("No image here yet")
    for i in range(half, len(cmds)):
        term.send_command(cmds[i])
    response = term.receive_response(timeout=3)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(image_id=100, placement_id=placement_id),
    )
    ctx.write("\n")
    ctx.take_screenshot("Wikipedia logo.")
    # Same with image number.
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
        image_number=12345,
    )
    cmd.set_placement(rows=10, columns=20, placement_id=placement_id)
    with open(ctx.get_tux_png(), "rb") as f:
        cmd.set_data(f.read())
    cmds = list(cmd.split(term.autosplit_max_size))
    ctx.write(f"Need to send {len(cmds)} direct uploading commands\n")
    half = len(cmds) // 2
    for i in range(half):
        term.send_command(cmds[i])
    ctx.write("Sent half of the commands.\n")
    semiresponse = term.receive_response(timeout=1)
    ctx.assert_true(
        not semiresponse.is_valid,
        f"There should be no response until all data is sent: {semiresponse}",
    )
    ctx.take_screenshot("No image here yet")
    for i in range(half, len(cmds)):
        term.send_command(cmds[i])
    response = term.receive_response(timeout=3)
    ctx.assert_equal(
        response,
        GraphicsResponse.ok_response(
            image_id=response.image_id,
            image_number=12345,
            placement_id=placement_id,
        ),
    )
    ctx.take_screenshot("Tux.")


@screenshot_test
def test_response_ok_two_responses(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.VERBOSE,
        format=tupimage.Format.PNG,
    )
    term.send_command(
        cmd.clone_with(image_id=43).set_filename(ctx.get_tux_png())
    )
    term.send_command(
        cmd.clone_with(image_id=44).set_filename(ctx.get_tux_png())
    )
    response1 = term.receive_response(timeout=3)
    response2 = term.receive_response(timeout=3)
    ctx.assert_equal(response1, GraphicsResponse.ok_response(image_id=43))
    ctx.assert_equal(response2, GraphicsResponse.ok_response(image_id=44))
    term.write("All done\n")
    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_error_transmit(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    # Image id.
    term.write("Image id is specified, file doesn't exist\n")
    term.send_command(
        cmd.clone_with(image_id=42).set_filename("__nonexistent__")
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err("EBADF", image_id=42), f"Wrong response: {response}"
    )
    # Image number.
    term.write("Image number is specified, file doesn't exist\n")
    term.send_command(
        cmd.clone_with(image_number=23456).set_filename("__nonexistent__")
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err(
            "EBADF", image_id=response.image_id, image_number=23456
        ),
        f"Wrong response: {response}",
    )
    # Control characters in the file name.
    term.write("Control characters in filename, file doesn't exist\n")
    term.send_command(
        cmd.clone_with(image_id=42).set_filename("\007\033[31m__nonexistent__")
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err("EBADF", image_id=42), f"Wrong response: {response}"
    )
    ctx.assert_true(
        "\007" not in response.message and "\033" not in response.message,
        "The response mustn't contain control characters",
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_error_transmit_urandom(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    term.write("Image id is specified, file doesn't exist\n")
    term.send_command(cmd.clone_with(image_id=42).set_filename("/dev/urandom"))
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err("EBADF", image_id=42)
        or response.is_err("EPERM", image_id=42),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test(suffix="fixed_placement_id", params={"placement_id": 123})
@screenshot_test
def test_response_error_transmit_and_put(
    ctx: TestingContext, placement_id=None
):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.FILE,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    cmd.set_placement(rows=10, columns=20, placement_id=placement_id)
    # Image id.
    term.write("Image id is specified, file doesn't exist\n")
    term.send_command(
        cmd.clone_with(image_id=42).set_filename("__nonexistent__")
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err("EBADF", image_id=42, placement_id=placement_id),
        f"Wrong response: {response}",
    )
    # Image number.
    term.write("Image number is specified, file doesn't exist\n")
    term.send_command(
        cmd.clone_with(image_number=23456).set_filename("__nonexistent__")
    )
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err(
            "EBADF",
            image_id=response.image_id,
            image_number=23456,
            placement_id=placement_id,
        ),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_error_direct_transmit(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    # Fake non-png data.
    data = ctx.to_rgb(ctx.generate_image(100, 100))
    # Image id.
    term.write("Image id is specified, bad png data\n")
    term.send_command(cmd.clone_with(image_id=42).set_data(data))
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    # st will return EBADF, kitty will return EBADPNG.
    ctx.assert_true(
        response.is_err("EBAD", image_id=42), f"Wrong response: {response}"
    )
    ctx.take_screenshot("No assertion failures")
    # Image number.
    term.write("Image number is specified, bad png data\n")
    term.send_command(cmd.clone_with(image_number=23456).set_data(data))
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err("EBAD", image_id=response.image_id, image_number=23456),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test(suffix="fixed_placement_id", params={"placement_id": 123})
@screenshot_test
def test_response_error_direct_transmit_and_put(
    ctx: TestingContext, placement_id=None
):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    cmd.set_placement(rows=10, columns=20, placement_id=placement_id)
    # Fake non-png data.
    data = ctx.to_rgb(ctx.generate_image(100, 100))
    # Image id.
    term.write("Image id is specified, bad png data\n")
    term.send_command(cmd.clone_with(image_id=42).set_data(data))
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    # st will return EBADF, kitty will return EBADPNG.
    ctx.assert_true(
        response.is_err("EBAD", image_id=42, placement_id=placement_id),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("No assertion failures")
    # Image number.
    term.write("Image number is specified, bad png data\n")
    term.send_command(cmd.clone_with(image_number=23456).set_data(data))
    response = term.receive_response(timeout=3)
    ctx.write(f"Response message: {response.message}\n")
    ctx.assert_true(
        response.is_err(
            "EBAD",
            image_id=response.image_id,
            image_number=23456,
            placement_id=placement_id,
        ),
        f"Wrong response: {response}",
    )
    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_error_syntax_no_response(ctx: TestingContext):
    term = ctx.term

    ctx.write("Empty command. No response is expected.")
    term.write("\033_G\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("Almost empty command. No response is expected.")
    term.write("\033_G;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("Almost empty command with a payload. No response is expected.")
    term.write("\033_G;abcd\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("No = after key. No response is expected.")
    term.write("\033_Ga;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("No value after =. No response is expected.")
    term.write("\033_Ga=;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("No , after a=t. No response is expected.")
    term.write("\033_Ga=transmit;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("A non-printed char in the command. No response is expected.")
    term.write("\033_G\007;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.write("A \\n in the command. No response is expected")
    term.write("\033_G\na=t;\033\\\n")
    response = term.receive_response(timeout=0.5)
    ctx.assert_true(not response.is_valid)

    ctx.take_screenshot("No assertion failures")


@screenshot_test
def test_response_error_syntax_image_id(ctx: TestingContext):
    term = ctx.term

    ctx.write("Empty command modulo image id.")
    term.write("\033_Gi=1234\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Empty command modulo image id and some payload.")
    term.write("\033_Gi=1234;abcd\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Syntax error (missing key).")
    term.write("\033_Gi=1234,a=;abcd\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Invalid action")
    term.write("\033_Gi=1234,a=X;abcd\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Invalid transmission.")
    term.write("\033_Gi=1234,a=t,t=X;abcd\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Undecodable payload.")
    term.write("\033_Gi=1234,a=t,t=d,f=100;@#$%\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.write("Undecodable payload as filename.")
    term.write("\033_Gi=1234,a=t,t=f,f=100;@#$%\033\\\n")
    response = term.receive_response(timeout=0.2)
    ctx.write(f"Response message: {response.message}\n")

    ctx.take_screenshot("No assertion failures")
