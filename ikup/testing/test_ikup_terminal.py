import time

from PIL import Image, ImageOps

import ikup
from ikup import IDSpace, IDSubspace, IkupTerminal
from ikup.testing import TestingContext, screenshot_test


@screenshot_test
def upload_and_display_from_file(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=True)
    for method in ["file", "direct"]:
        ikupterm.term.reset()
        ikupterm.upload_method = method
        ikupterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                ikupterm.id_space = IDSpace(id_color_bits, id_use_3rd_diacritic)
                ikupterm.upload_and_display(
                    ctx.get_wikipedia_png(),
                    rows=8,
                )
                ikupterm.upload_and_display(ctx.get_tux_png(), rows=8)
            ikupterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                ikupterm.term.write("\n")
        print(f" (method={method}, from file)", end="", flush=True)
        ctx.take_screenshot(
            f"Wikipedias and tuxes, using different ID settings, method={method}"
        )


@screenshot_test
def upload_and_display_from_image(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=True)
    img1 = ImageOps.flip(Image.open(ctx.get_wikipedia_png()))
    img2 = ImageOps.flip(Image.open(ctx.get_tux_png()))
    for method in ["file", "direct"]:
        ikupterm.term.reset()
        ikupterm.upload_method = method
        ikupterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                ikupterm.id_space = IDSpace(id_color_bits, id_use_3rd_diacritic)
                ikupterm.upload_and_display(
                    img1,
                    rows=8,
                )
                ikupterm.upload_and_display(img2, rows=8)
            ikupterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                ikupterm.term.write("\n")
        print(f" (method={method}, from Image objects)", end="", flush=True)
        ctx.take_screenshot(
            "Wikipedias and tuxes flipped, using different ID settings,"
            f" method={method}"
        )


@screenshot_test
def upload_and_display_jpeg(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=True)
    img1 = ctx.get_castle_jpg()
    img2 = ImageOps.flip(Image.open(ctx.get_castle_jpg()))
    for method in ["file", "direct"]:
        ikupterm.term.reset()
        ikupterm.upload_method = method
        ikupterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                ikupterm.id_space = IDSpace(id_color_bits, id_use_3rd_diacritic)
                ikupterm.upload_and_display(img1, rows=8, cols=20)
                ikupterm.upload_and_display(img2, rows=8, cols=20)
            ikupterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                ikupterm.term.write("\n")
        # This test seems to overwhelm the terminal, wait a little longer than usual.
        time.sleep(1.0)
        print(f" (jpeg, method={method})", end="", flush=True)
        ctx.take_screenshot(
            f"Jpeg castles using different ID settings, method={method}"
        )


@screenshot_test
def upload_and_display_unsupported_jpeg(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=True)
    ikupterm.supported_formats = ["png"]
    img1 = ctx.get_castle_jpg()
    img2 = ImageOps.flip(Image.open(ctx.get_castle_jpg()))
    for method in ["file", "direct"]:
        ikupterm.term.reset()
        ikupterm.upload_method = method
        ikupterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                ikupterm.id_space = IDSpace(id_color_bits, id_use_3rd_diacritic)
                ikupterm.upload_and_display(img1, rows=8, cols=20)
                ikupterm.upload_and_display(img2, rows=8, cols=20)
            ikupterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                ikupterm.term.write("\n")
        print(f" (jpeg->png, method={method})", end="", flush=True)
        # This test seems to overwhelm the terminal, wait a little longer than usual.
        time.sleep(1.0)
        ctx.take_screenshot(
            f"Jpeg castles using different ID settings, method={method}, jpegs"
            " are supposed to be converted"
        )


@screenshot_test
def id_reclaiming(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=False)
    for i in range(300):
        img = ctx.text_to_image(str(i), colorize_by_id=i * 100)
        for y, idf in enumerate(IDSpace.all_values()):
            ikupterm.upload_and_display(
                img,
                cols=4,
                rows=4,
                id_space=idf,
                abs_pos=(min(i * 4, 76), y * 4),
            )
        if i in [254, 255, 260, 299]:
            time.sleep(0.2)
            ctx.take_screenshot(
                f"Demo of ID reclaiming, step {i + 1}, lines 1 and 4 may start"
                " to be overridden with new images from the left"
            )


@screenshot_test
def id_reclaiming_subspace(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT", force_upload=False)
    ikupterm.id_subspace = IDSubspace(100, 104)
    assert IDSpace(8, True).subspace_size(ikupterm._config.id_subspace) == 1020
    for i in range(1100):
        img = ctx.text_to_image(str(i), colorize_by_id=i * 100)
        for y, idf in enumerate(IDSpace.all_values()):
            ikupterm.id_space = idf
            if i % 4 == 0:
                ikupterm.upload_and_display(
                    img, cols=4, rows=4, abs_pos=(min(i, 76), y * 4)
                )
            else:
                ikupterm.assign_id(
                    img,
                    cols=4,
                    rows=4,
                )
        if i in [3, 4, 1019, 1020, 1099]:
            ctx.take_screenshot(
                f"Demo of ID reclaiming, smaller subspace, step {i + 1}, now"
                " even line 2 gets eventually overridden (the corresponding"
                " subspace is of size 1020)"
            )


@screenshot_test
def specify_num_columns(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT")
    ikupterm.final_cursor_pos = "bottom-left"
    for cols in range(1, 12):
        ikupterm.term.move_cursor_abs(row=0)
        ikupterm.upload_and_display(ctx.get_tux_png(), cols=cols)
        ikupterm.upload_and_display(ctx.get_wikipedia_png(), cols=cols)
        ikupterm.upload_and_display(
            ctx.get_ruler_png(), cols=cols, final_cursor_pos="bottom-right"
        )
    ctx.take_screenshot("The number of cols is specified")


@screenshot_test
def specify_num_rows(ctx: TestingContext):
    ikupterm = IkupTerminal(config="DEFAULT")
    ikupterm.final_cursor_pos = "top-right"
    # The column is a big file, but it's faster to upload it than to resize it.
    ikupterm.file_max_size = 3 * 1024 * 1024
    for rows in range(1, 7):
        ikupterm.term.move_cursor_abs(col=0)
        ikupterm.upload_and_display(ctx.get_tux_png(), rows=rows)
        ikupterm.upload_and_display(ctx.get_wikipedia_png(), rows=rows)
        ikupterm.upload_and_display(
            ctx.get_column_png(), rows=rows, final_cursor_pos="bottom-left"
        )
    # This test seems to be flaky, so let's wait a bit.
    time.sleep(0.5)
    ctx.take_screenshot("The number of rows is specified")
