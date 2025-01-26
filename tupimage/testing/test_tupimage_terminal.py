import time

from PIL import Image, ImageOps

import tupimage
from tupimage import IDFeatures, IDSubspace, TupimageTerminal
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def upload_and_display_from_file(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=True)
    for method in ["file", "direct"]:
        tupiterm.term.reset()
        tupiterm.upload_method = method
        tupiterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                tupiterm.id_use_3rd_diacritic = id_use_3rd_diacritic
                tupiterm.id_color_bits = id_color_bits
                tupiterm.upload_and_display(
                    ctx.get_wikipedia_png(),
                    rows=8,
                )
                tupiterm.upload_and_display(ctx.get_tux_png(), rows=8)
            tupiterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                tupiterm.term.write("\n")
        print(f" (method={method}, from file)", end="", flush=True)
        ctx.take_screenshot(
            f"Wikipedias and tuxes, using different ID settings, method={method}"
        )


@screenshot_test
def upload_and_display_from_image(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=True)
    img1 = ImageOps.flip(Image.open(ctx.get_wikipedia_png()))
    img2 = ImageOps.flip(Image.open(ctx.get_tux_png()))
    for method in ["file", "direct"]:
        tupiterm.term.reset()
        tupiterm.upload_method = method
        tupiterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                tupiterm.id_use_3rd_diacritic = id_use_3rd_diacritic
                tupiterm.id_color_bits = id_color_bits
                tupiterm.upload_and_display(
                    img1,
                    rows=8,
                )
                tupiterm.upload_and_display(img2, rows=8)
            tupiterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                tupiterm.term.write("\n")
        print(f" (method={method}, from Image objects)", end="", flush=True)
        ctx.take_screenshot(
            "Wikipedias and tuxes flipped, using different ID settings,"
            f" method={method}"
        )


@screenshot_test
def upload_and_display_jpeg(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=True)
    img1 = ctx.get_castle_jpg()
    img2 = ImageOps.flip(Image.open(ctx.get_castle_jpg()))
    for method in ["file", "direct"]:
        tupiterm.term.reset()
        tupiterm.upload_method = method
        tupiterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                tupiterm.id_use_3rd_diacritic = id_use_3rd_diacritic
                tupiterm.id_color_bits = id_color_bits
                tupiterm.upload_and_display(img1, rows=8, cols=20)
                tupiterm.upload_and_display(img2, rows=8, cols=20)
            tupiterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                tupiterm.term.write("\n")
        print(f" (jpeg, method={method})", end="", flush=True)
        ctx.take_screenshot(
            f"Jpeg castles using different ID settings, method={method}"
        )


@screenshot_test
def upload_and_display_unsupported_jpeg(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=True)
    tupiterm.supported_formats = ["png"]
    img1 = ctx.get_castle_jpg()
    img2 = ImageOps.flip(Image.open(ctx.get_castle_jpg()))
    for method in ["file", "direct"]:
        tupiterm.term.reset()
        tupiterm.upload_method = method
        tupiterm.final_cursor_pos = "top-right"
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                tupiterm.id_use_3rd_diacritic = id_use_3rd_diacritic
                tupiterm.id_color_bits = id_color_bits
                tupiterm.upload_and_display(img1, rows=8, cols=20)
                tupiterm.upload_and_display(img2, rows=8, cols=20)
            tupiterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                tupiterm.term.write("\n")
        print(f" (jpeg->png, method={method})", end="", flush=True)
        ctx.take_screenshot(
            f"Jpeg castles using different ID settings, method={method}, jpegs"
            " are supposed to be converted"
        )


@screenshot_test
def id_reclaiming(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=False)
    for i in range(300):
        img = ctx.text_to_image(str(i), colorize_by_id=i * 100)
        for y, idf in enumerate(IDFeatures.all_values()):
            tupiterm.upload_and_display(
                img,
                cols=4,
                rows=4,
                id_color_bits=idf.color_bits,
                id_use_3rd_diacritic=idf.use_3rd_diacritic,
                abs_pos=(min(i * 4, 76), y * 4),
            )
        if i in [254, 255, 260, 299]:
            ctx.take_screenshot(
                f"Demo of ID reclaiming, step {i + 1}, lines 1 and 4 may start"
                " to be overridden with new images from the left"
            )


@screenshot_test
def id_reclaiming_subspace(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_upload=False)
    tupiterm.id_subspace = IDSubspace(100, 104)
    assert IDFeatures(8, True).subspace_size(tupiterm._config.id_subspace) == 1020
    for i in range(1100):
        img = ctx.text_to_image(str(i), colorize_by_id=i * 100)
        for y, idf in enumerate(IDFeatures.all_values()):
            tupiterm.id_color_bits = idf.color_bits
            tupiterm.id_use_3rd_diacritic = idf.use_3rd_diacritic
            if i % 4 == 0:
                tupiterm.upload_and_display(
                    img, cols=4, rows=4, abs_pos=(min(i, 76), y * 4)
                )
            else:
                tupiterm.assign_id(
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
    tupiterm = TupimageTerminal(config="DEFAULT")
    tupiterm.final_cursor_pos = "bottom-left"
    for cols in range(1, 12):
        tupiterm.term.move_cursor_abs(row=0)
        tupiterm.upload_and_display(ctx.get_tux_png(), cols=cols)
        tupiterm.upload_and_display(ctx.get_wikipedia_png(), cols=cols)
        tupiterm.upload_and_display(
            ctx.get_ruler_png(), cols=cols, final_cursor_pos="bottom-right"
        )
    ctx.take_screenshot("The number of cols is specified")


@screenshot_test
def specify_num_rows(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT")
    tupiterm.final_cursor_pos = "top-right"
    # The column is a big file, but it's faster to upload it than to resize it.
    tupiterm.file_max_size = 3 * 1024 * 1024
    for rows in range(1, 7):
        tupiterm.term.move_cursor_abs(col=0)
        tupiterm.upload_and_display(ctx.get_tux_png(), rows=rows)
        tupiterm.upload_and_display(ctx.get_wikipedia_png(), rows=rows)
        tupiterm.upload_and_display(
            ctx.get_column_png(), rows=rows, final_cursor_pos="bottom-left"
        )
    # This test seems to be flaky, so let's wait a bit.
    time.sleep(0.5)
    ctx.take_screenshot("The number of rows is specified")
