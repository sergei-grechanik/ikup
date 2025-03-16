import json
import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, TextIO, Tuple
import random

import numpy as np
from PIL import Image


DEFAULT_DIFF_THRESHOLD = 0.01


@dataclass
class ScreenshotComparison:
    test_name: str = ""
    index: int = 0
    filename: str = ""
    description: str = ""
    ref_filename: str = ""
    ref_description: str = ""
    diffmap_filename: str = ""
    diffscore: float = float("inf")
    diff_threshold: float = DEFAULT_DIFF_THRESHOLD


@dataclass
class ComparisonReport:
    tests_with_errors: List[dict] = field(default_factory=list)
    no_reference_tests: List[dict] = field(default_factory=list)
    missing_tests: List[dict] = field(default_factory=list)
    incompatible_tests: List[Tuple[dict, dict]] = field(default_factory=list)
    screenshots: List[ScreenshotComparison] = field(default_factory=list)

    def print_summary(self, out: TextIO) -> bool:
        success = True;
        if self.tests_with_errors:
            out.write("Tests with errors:\n")
            for test in self.tests_with_errors:
                out.write(f"  {test['name']}\n")
            success = False
        if self.no_reference_tests:
            out.write("Tests without reference:\n")
            for test in self.no_reference_tests:
                out.write(f"  {test['name']}\n")
            success = False
        if self.missing_tests:
            out.write("Reference tests that didn't run:\n")
            for test in self.missing_tests:
                out.write(f"  {test['name']}\n")
            success = False
        if self.incompatible_tests:
            out.write("Incompatible tests:\n")
            for test, _ in self.incompatible_tests:
                out.write(f"  {test['name']}\n")
            success = False
        for screenshot in self.screenshots:
            if screenshot.diffscore >= screenshot.diff_threshold:
                out.write(
                    f"Failed screenshot {screenshot.test_name} {screenshot.index} diff = {screenshot.diffscore:.6f}\n"
                )
                success = False
        out.write("Worst 5 screenshots:\n")
        for screenshot in self.screenshots[:5]:
            out.write(
                f"  {screenshot.test_name} {screenshot.index} diff = {screenshot.diffscore:.6f}\n"
            )
        return success

    def screenshots_to_html(self, screenshots: List[dict]) -> str:
        html = ""
        for screenshot in screenshots:
            html += f"<h4>{screenshot['index']}</h4>\n"
            html += f"<p>{screenshot['description']}</p>\n"
            filename = screenshot["filename"]
            html += f'<img src="{filename}">\n'
        return html

    def to_html(self) -> str:
        html = ""
        if self.tests_with_errors:
            html += '<h2 style="color: red">Tests with errors</h2>\n'
            for test in self.tests_with_errors:
                html += f"<h3>{test['name']}</h3>\n"
                for error in test["errors"]:
                    html += f"<p>{error}</p>\n"
        if self.missing_tests:
            html += '<h2 style="color: red">Reference tests that didn\'t run</h2>\n'
            for test in self.missing_tests:
                html += f"<h3>{test['name']}</h3>\n"
        if self.no_reference_tests:
            html += '<h2 style="color: red">Tests without reference</h2>\n'
            for test in self.no_reference_tests:
                html += f"<h3>{test['name']}</h3>\n"
                html += self.screenshots_to_html(test["screenshots"])
        if self.incompatible_tests:
            html += '<h2 style="color: red">Incompatible tests</h2>\n'
            for test, ref_test in self.incompatible_tests:
                html += f"<h3>{test['name']}</h3>\n"
                test_shots = test["screenshots"]
                ref_shots = ref_test["screenshots"]
                if len(test_shots) < len(ref_shots):
                    html += (
                        "<p>Test has fewer screenshots than reference. Missing"
                        " reference screenshots:</p>\n"
                    )
                    html += self.screenshots_to_html(ref_shots[len(test_shots) :])
                if len(test_shots) > len(ref_shots):
                    html += (
                        "<p>Test has more screenshots than reference. Extra"
                        " test screenshots:</p>\n"
                    )
                    html += self.screenshots_to_html(test_shots[len(ref_shots) :])
        if self.screenshots:
            html += "<h2>Screenshots</h2>\n"
            for screenshot in self.screenshots:
                if screenshot.diffscore < screenshot.diff_threshold:
                    html += '<h3 style="color: green">(PASSED) '
                else:
                    html += '<h3 style="color: red">(FAILED) '
                html += f"{screenshot.test_name} {screenshot.index}</h3>\n"
                html += f"<p><b>diff = {screenshot.diffscore:.6f}</b></p>\n"
                html += f"<p>{screenshot.description}</p>\n"
                if screenshot.description != screenshot.ref_description:
                    html += f"<p><b>Reference has a different description</b>:"
                    html += f" {screenshot.ref_description}</p>\n"
                html += f'<img src="{screenshot.filename}">\n'
                html += f'<img src="{screenshot.diffmap_filename}">\n'
                html += f'<img src="{screenshot.ref_filename}">\n'
        return html


def get_output_dir_and_json(path: str) -> Tuple[str, List[dict]]:
    directory = ""
    json_path = ""
    if os.path.isdir(path):
        directory = path
        if directory[-1] == "/":
            directory = directory[:-1]
        json_path = os.path.join(path, "report.json")
    else:
        directory = os.path.dirname(path)
        json_path = path
    with open(json_path, "r") as f:
        json_data = json.load(f)
    if not isinstance(json_data, list):
        json_data = [json_data]
    for test in json_data:
        if test["name"].startswith("test_"):
            test["name"] = test["name"][5:]
        for screenshot in test["screenshots"]:
            screenshot["filename"] = os.path.join(directory, screenshot["filename"])
    return directory, json_data


def compare_images(
    filename: str,
    ref_filename: str,
    diffmap_filename: Optional[str] = None,
) -> float:
    img = Image.open(filename).convert("RGB")
    refimg = Image.open(ref_filename).convert("RGB")

    # Resize the images to the same size.
    # TODO: We may want to crop instead of resizing to avoid distortion.
    size = refimg.size
    img = img.resize(size)

    img = np.array(img).astype(np.float32) / 255.0
    refimg = np.array(refimg).astype(np.float32) / 255.0

    W = 80
    cw = size[0] / W
    ch = cw

    # Compute the diffscore.
    meaningful_pixels = 0
    sum_of_squares = 0
    x = 0
    while x < size[0]:
        y = 0
        while y < size[1]:
            cell1 = img[int(y) : int(y + ch), int(x) : int(x + cw)]
            cell2 = refimg[int(y) : int(y + ch), int(x) : int(x + cw)]
            if np.max(cell1) < 0.001 and np.max(cell2) < 0.001:
                y += ch
                continue
            meaningful_pixels += ch * cw
            sum_of_squares += np.sum((cell1 - cell2) ** 2)
            y += ch
        x += cw
    diffscore = math.sqrt(sum_of_squares / meaningful_pixels)

    # Build the diff image.
    diffmap = np.clip(np.abs(img - refimg), 0.0, 1.0)
    if diffmap_filename:
        diffmap = (diffmap * 255).astype(np.uint8)
        Image.fromarray(diffmap).save(diffmap_filename)

    return diffscore


def create_screenshot_comparison_report(
    out: str, ref: str, diffmap_dir: Optional[str] = None
) -> ComparisonReport:
    out_dir, out_json_data = get_output_dir_and_json(out)
    ref_dir, ref_json_data = get_output_dir_and_json(ref)
    if diffmap_dir is None:
        diffmap_dir = out_dir + ".diffmaps"
    os.makedirs(diffmap_dir, exist_ok=True)
    out_by_name = {t["name"]: t for t in out_json_data}
    ref_by_name = {t["name"]: t for t in ref_json_data}
    report = ComparisonReport()
    for ref_test in ref_json_data:
        if ref_test["name"] not in out_by_name:
            report.missing_tests.append(ref_test)
    for test in out_json_data:
        print("Processing", test["name"])
        if test["errors"]:
            report.tests_with_errors.append(test)
        if test["name"] not in ref_by_name:
            report.no_reference_tests.append(test)
            continue
        ref_test = ref_by_name[test["name"]]
        if len(test["screenshots"]) != len(ref_test["screenshots"]):
            report.incompatible_tests.append((test, ref_test))
        index = 0
        for screenshot, ref_screenshot in zip(
            test["screenshots"], ref_test["screenshots"]
        ):
            diff_threshold = screenshot.get("diff_threshold", DEFAULT_DIFF_THRESHOLD)
            diffmap_filename = os.path.join(
                diffmap_dir, f"diffmap-{test['name']}-{index}.png"
            )
            diffscore = compare_images(
                screenshot["filename"],
                ref_screenshot["filename"],
                diffmap_filename,
            )
            report.screenshots.append(
                ScreenshotComparison(
                    test_name=test["name"],
                    index=index,
                    filename=screenshot["filename"],
                    description=screenshot["description"],
                    ref_filename=ref_screenshot["filename"],
                    ref_description=ref_screenshot["description"],
                    diffscore=diffscore,
                    diffmap_filename=diffmap_filename,
                    diff_threshold=diff_threshold
                )
            )
            index += 1
    report.screenshots.sort(key=lambda s: s.diffscore, reverse=True)
    return report
