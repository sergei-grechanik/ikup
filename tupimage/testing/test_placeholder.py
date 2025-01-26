import tupimage
from tupimage import (
    DiacriticLevel,
    GraphicsTerminal,
    ImagePlaceholder,
    ImagePlaceholderMode,
    PutCommand,
    TransmitCommand,
)
from tupimage.testing import TestingContext, screenshot_test


@screenshot_test
def image_ids(ctx: TestingContext):
    term = ctx.term
    cmd = TransmitCommand(
        medium=tupimage.TransmissionMedium.DIRECT,
        quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
        format=tupimage.Format.PNG,
    )
    cmd.set_placement(virtual=True, rows=2, cols=5)
    image_ids = []
    byte_values = [0, 255]
    for b2 in byte_values:
        for b1 in byte_values:
            for b0 in byte_values:
                for b3 in byte_values:
                    image_ids.append(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    assert image_ids[0] == 0
    image_ids = image_ids[1:]
    term.write("Uploading images with ids:\n")
    placeholders = []
    for image_id in image_ids:
        term.write(f"{hex(image_id)} ")
        img_str = f"{image_id:08x}"
        img_str = img_str[:2] + "\n" + img_str[2:]
        term.send_command(
            cmd.clone_with(image_id=image_id).set_data(
                ctx.to_png(ctx.text_to_image(img_str, colorize_by_id=image_id))
            )
        )
        placeholders.append(ImagePlaceholder(image_id=image_id, end_col=5, end_row=2))
    term.write("\n")
    ctx.take_screenshot(f"Image ids we are going to use.")
    for firstcol_level in DiacriticLevel:
        if firstcol_level == DiacriticLevel.NONE:
            continue
        for othercol_level in DiacriticLevel:
            term.write("=" * 80 + "\n")
            term.write(f"First column diacritic level: {firstcol_level.name}\n")
            term.write(f"Other column diacritic level: {othercol_level.name}\n")
            mode = ImagePlaceholderMode(
                first_column_diacritic_level=firstcol_level,
                other_columns_diacritic_level=othercol_level,
            )
            total_size = 0
            term.write("Sizes: ")
            for p in placeholders:
                size = sum(len(l) for l in p.to_lines(mode))
                term.write(f"{size} ")
                total_size += size
            term.write(f"\nTotal: {total_size} bytes\n")
            for p in placeholders:
                term.print_placeholder(p, mode=mode)
                term.move_cursor(up=1)
            term.move_cursor(down=1)
            term.write("\n")
            for p in reversed(placeholders):
                term.print_placeholder(p, mode=mode)
                term.move_cursor(up=1)
            term.move_cursor(down=1)
            term.write("\n")
            if firstcol_level in [DiacriticLevel.NONE, DiacriticLevel.ROW]:
                term.write("(The reverse order may look wrong)\n")
            ctx.take_screenshot(
                f"First {firstcol_level.name} other {othercol_level.name}"
            )


@screenshot_test
def full_width(ctx: TestingContext):
    term = ctx.term
    for image_id in [0x123456, 0x12345678]:
        term.write(f"Image id: 0x{image_id:08x}\n")
        cmd = TransmitCommand(
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
            image_id=image_id,
        )
        cmd.set_filename(ctx.get_ruler_png())
        cmd.set_placement(virtual=True, rows=3, cols=80)
        term.send_command(cmd)
        for othercol_level in [
            DiacriticLevel.NONE,
            DiacriticLevel.ROW,
            DiacriticLevel.ROW_COLUMN,
            DiacriticLevel.ROW_COLUMN_ID4THBYTE,
        ]:
            term.write(f"Non-first column diacritic level: {othercol_level.name}\n")
            mode = ImagePlaceholderMode(other_columns_diacritic_level=othercol_level)
            term.print_placeholder(image_id=image_id, end_col=80, end_row=3, mode=mode)
        term.write(f"End")
        ctx.take_screenshot(f"Full-width rulers, image id = 0x{image_id:08x}")
        term.reset()


@screenshot_test
def vertical_stripes(ctx: TestingContext):
    term = ctx.term
    for image_id in [0x123456, 0x12345678]:
        term.write(f"Image id: 0x{image_id:08x}\n")
        cmd = TransmitCommand(
            medium=tupimage.TransmissionMedium.FILE,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
            image_id=image_id,
        )
        cmd.set_filename(ctx.get_ruler_png())
        cmd.set_placement(virtual=True, rows=3, cols=80)
        term.send_command(cmd)

        def formatting(col, row):
            if col % 4 != 0:
                return b""
            return b"\033[48;5;%dm" % (col // 4)

        for othercol_level in [
            DiacriticLevel.NONE,
            DiacriticLevel.ROW,
            DiacriticLevel.ROW_COLUMN,
            DiacriticLevel.ROW_COLUMN_ID4THBYTE,
        ]:
            term.write(f"Non-first column diacritic level: {othercol_level.name}\n")
            mode = ImagePlaceholderMode(other_columns_diacritic_level=othercol_level)
            ImagePlaceholder(
                image_id=image_id, end_col=80, end_row=3
            ).to_stream_at_cursor(
                term.out_display,
                mode=mode,
                formatting=tupimage.CellFormatting(formatting),
            )
            term.write(f"\n")
        ctx.take_screenshot(
            f"Full-width rulers on a striped background, image id = 0x{image_id:08x}"
        )
        cmd = (
            cmd.clone_with(image_id=42)
            .set_filename(ctx.get_column_png())
            .set_placement(virtual=True, rows=18, cols=8)
        )
        term.send_command(cmd)
        term.print_placeholder(
            image_id=42, end_col=8, end_row=18, pos=(36, 0), mode=mode
        )
        ctx.take_screenshot(
            f"Rulers with a column. The column may break the rulers on some"
            f" terminals."
        )
        term.reset()


@screenshot_test
def max_columns(ctx: TestingContext):
    term = ctx.term
    columns = len(tupimage.ROWCOLUMN_DIACRITICS) + 3
    for image_id in [0x123456, 0x12345678]:
        term.write(f"Image id: 0x{image_id:08x}\n")
        cmd = TransmitCommand(
            medium=tupimage.TransmissionMedium.DIRECT,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
            image_id=image_id,
        )
        cmd.set_placement(virtual=True, rows=12, cols=columns)
        text = "\n".join(",".join(str(i) for i in range(122)) for _ in range(12))
        cmd.set_data(ctx.to_png(ctx.text_to_image(text)))
        term.send_command(cmd)
        row = 0
        for firstcol_level in [
            DiacriticLevel.ROW,
            DiacriticLevel.ROW_COLUMN,
            DiacriticLevel.ROW_COLUMN_ID4THBYTE,
        ]:
            for othercol_level in [
                DiacriticLevel.NONE,
                DiacriticLevel.ROW,
                DiacriticLevel.ROW_COLUMN,
                DiacriticLevel.ROW_COLUMN_ID4THBYTE,
            ]:
                mode = ImagePlaceholderMode(
                    first_column_diacritic_level=firstcol_level,
                    other_columns_diacritic_level=othercol_level,
                )
                term.print_placeholder(
                    image_id=image_id,
                    end_col=40,
                    start_row=row,
                    end_row=row + 1,
                    mode=mode,
                )
                term.print_placeholder(
                    image_id=image_id,
                    start_col=columns - 40,
                    end_col=columns,
                    start_row=row,
                    end_row=row + 1,
                    mode=mode,
                )
                row += 1
        term.write("\n")
        ctx.take_screenshot(
            "Long image containing numbers, only the leftmost (~0-19) and"
            " rightmost (~109-121) parts are shown , image id ="
            f" 0x{image_id:08x}."
        )
        term.reset()


@screenshot_test
def max_rows(ctx: TestingContext):
    term = ctx.term
    rows = len(tupimage.ROWCOLUMN_DIACRITICS)
    columns = 7
    for image_id in [0x123456, 0x12345678]:
        term.write(f"Image id: 0x{image_id:08x}\n")
        cmd = TransmitCommand(
            medium=tupimage.TransmissionMedium.DIRECT,
            quiet=tupimage.Quietness.QUIET_UNLESS_ERROR,
            format=tupimage.Format.PNG,
            image_id=image_id,
        )
        cmd.set_placement(virtual=True, rows=rows, cols=columns)
        text = "\n".join(str(i) for i in range(rows // 2))
        cmd.set_data(ctx.to_png(ctx.text_to_image(text)))
        term.send_command(cmd)
        for start_row, end_row in [(0, 10), (rows - 10, rows)]:
            for firstcol_level in [
                DiacriticLevel.ROW_COLUMN,
                DiacriticLevel.ROW_COLUMN_ID4THBYTE,
            ]:
                for othercol_level in [
                    DiacriticLevel.NONE,
                    DiacriticLevel.ROW,
                    DiacriticLevel.ROW_COLUMN,
                    DiacriticLevel.ROW_COLUMN_ID4THBYTE,
                ]:
                    mode = ImagePlaceholderMode(
                        first_column_diacritic_level=firstcol_level,
                        other_columns_diacritic_level=othercol_level,
                    )
                    term.print_placeholder(
                        image_id=image_id,
                        end_col=columns,
                        start_row=start_row,
                        end_row=end_row,
                        mode=mode,
                    )
                    term.move_cursor(up=9)
            term.move_cursor(down=9)
            term.write("\n")
        ctx.take_screenshot(
            "Tall image containing numbers, only the top (~0-4) and"
            " the bottom (~143-147) parts are shown, image id ="
            f" 0x{image_id:08x}."
        )
        term.reset()
        # Show all parts of the image
        for start_row in range(0, rows, 23):
            term.print_placeholder(
                image_id=image_id,
                end_col=6,
                start_row=start_row,
                end_row=start_row + 24,
            )
            term.move_cursor(up=23)
        ctx.take_screenshot(
            f"All parts of the tall image, image id = 0x{image_id:08x}. Columns are slightly cropped"
        )
        term.reset()
