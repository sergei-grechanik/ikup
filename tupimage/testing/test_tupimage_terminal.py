import tupimage
from tupimage import TupimageTerminal
from tupimage.testing import TestingContext, screenshot_test
from PIL import Image


@screenshot_test
def upload_and_display_from_file(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_reupload=True)
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
        print(f" (method={method})", end="", flush=True)
        ctx.take_screenshot(
            "Wikipedias and tuxes, using different ID settings,"
            f" method={method}"
        )


@screenshot_test
def upload_and_display_from_image(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_reupload=True)
    img1 = Image.open(ctx.get_wikipedia_png())
    img2 = Image.open(ctx.get_tux_png())
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
        print(f" (method={method})", end="", flush=True)
        ctx.take_screenshot(
            "Wikipedias and tuxes, using different ID settings,"
            f" method={method}"
        )


@screenshot_test
def upload_and_display_jpeg(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_reupload=True)
    img1 = ctx.get_castle_jpg()
    img2 = Image.open(ctx.get_castle_jpg())
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
            "Jpeg castles using different ID settings, method={method}"
        )


@screenshot_test
def upload_and_display_unsupported_jpeg(ctx: TestingContext):
    tupiterm = TupimageTerminal(config="DEFAULT", force_reupload=True)
    tupiterm.supported_formats = ["png"]
    img1 = ctx.get_castle_jpg()
    img2 = Image.open(ctx.get_castle_jpg())
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
            "Jpeg castles using different ID settings, method={method}, jpegs"
            " are supposed to be converted"
        )
