import tupimage
from tupimage import TupimageTerminal
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def upload_and_display_fixed_rows(ctx: TestingContext):
    tupiterm = TupimageTerminal()
    for method in ["file", "direct"]:
        tupiterm.term.reset()
        tupiterm.set(upload_method=method, force_reupload=True)
        for id_color_bits in [24, 8, 0]:
            for id_use_3rd_diacritic in [True, False]:
                if id_color_bits == 0 and not id_use_3rd_diacritic:
                    continue
                tupiterm.set(
                    id_use_3rd_diacritic=id_use_3rd_diacritic,
                    id_color_bits=id_color_bits,
                )
                tupiterm.upload_and_display(
                    ctx.get_wikipedia_png(),
                    rows=8,
                    final_cursor_pos="top-right",
                )
                tupiterm.upload_and_display(
                    ctx.get_tux_png(), rows=8, final_cursor_pos="top-right"
                )
            tupiterm.term.move_cursor(down=7)
            if id_color_bits != 0:
                tupiterm.term.write("\n")
        print(f" (method={method})", end="", flush=True)
        ctx.take_screenshot(
            "Wikipedias and tuxes, using different ID settings,"
            f" method={method}"
        )
