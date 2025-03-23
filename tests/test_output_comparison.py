import pytest
from tupimage.testing.output_comparison import (
    parse_chunks_from_content,
    process_test_chunk,
    compare,
)

TEST_CASES = {
    ####################################################################################
    "basic": {
        "input": """
========== TEST basic
Exact match
Regex match 123
Variable capture test
========== TEST skip test
Some noise
More noise
Target line 42
Check 42
""",
        "reference": r"""
========== TEST skip test
{{:SKIP_LINES:}}
Target line [[num:\d+]]
Check [[num]]
========== TEST basic
Exact match
Regex match {{\d+}}
[[var:Variable (.*) test]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "variable_validation": {
        "input": """
========== TEST vars
start 5
value 5
========== TEST skiptest
junk1
junk2
target 99
validate 99
""",
        "reference": r"""
========== TEST vars
start [[x:\d+]]
[[x]]
========== TEST skiptest
{{:SKIP_LINES:}}
target [[y:\d+]]
validate [[y]]
""",
        "should_fail": True,
        "error_pattern": r"Reference line 4:\n\[\[x]]",
    },
    ####################################################################################
    "error_conditions": {
        "input": """
========== TEST errors
line 1
line 2
========== TEST missing ref test
content
""",
        "reference": """
========== TEST errors
[[undefined_var]]
line 2
========== TEST missing input test
content
""",
        "should_fail": True,
        "error_pattern": "Undefined variable 'undefined_var'",
    },
    ####################################################################################
    "complex_patterns": {
        "input": """
========== TEST complex vars
start 42
value1:99 value2:hello
skip until
target 99 hello
final match 42
========== TEST multiline skip
line1
line2
line3
line4
target 123-456
verify 123 456
""",
        "reference": r"""
========== TEST complex vars
start [[num:\d+]]
[[key:\w+]]:[[x:\d+]] [[key2:\w+]]:[[y:\w+]]
{{:SKIP_LINES:}}
target [[x]] [[y]]
final match [[num]]
========== TEST multiline skip
{{:SKIP_LINES:}}
target [[a:\d+]]-[[b:\d+]]
{{:SKIP_LINES:}}
verify [[a]] [[b]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "duplicate_tests": {
        "input": """
========== TEST duplicate
line1
========== TEST duplicate
line2
""",
        "reference": """
========== TEST duplicate
pattern1
========== TEST duplicate
pattern2
""",
        "should_fail": True,
        "error_pattern": "Duplicate test name '========== TEST duplicate' at line 4",
    },
    ####################################################################################
    "empty_lines": {
        "input": """
========== TEST trailing empty
Line 1
Line 2

========== TEST middle empty
Line 1

Line 2
""",
        "reference": """
========== TEST trailing empty
Line 1
Line 2
========== TEST middle empty
Line 1

Line 2
""",
        "should_fail": False,
    },
    ####################################################################################
    "empty_lines_fail": {
        "input": """
========== TEST middle empty
Line 1


Line 2
""",
        "reference": """
========== TEST middle empty
Line 1

Line 2
""",
        "should_fail": True,
        "error_pattern": "Reference line 5:\nLine 2",
    },
    ####################################################################################
    "empty_lines_beginning_fail": {
        "input": """
========== TEST middle empty

Line 1
Line 2
""",
        "reference": """
========== TEST middle empty
Line 1
Line 2
""",
        "should_fail": True,
        "error_pattern": "Reference line 3:\nLine 1",
    },
    ####################################################################################
    "regex_group_conflict": {
        "input": """
========== TEST group_test
not captured 123 and 567
567
""",
        "reference": r"""
========== TEST group_test
{{not captured (.*)}} and [[v:.*]]
[[v]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "var_group_conflict": {
        "input": """
========== TEST group_test
not captured 123 andand 567
567
not captured 123
""",
        "reference": r"""
========== TEST group_test
[[x:not captured (.*)]] {{((and)*)}} [[v:.*]]
[[v]]
[[x]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "var_same_line": {
        "input": """
========== TEST same line var capture and use
123 and 123
""",
        "reference": r"""
========== TEST same line var capture and use
[[x:\d+]] and [[x]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "var_same_line_redefinition": {
        "input": """
========== TEST same line var capture and use
smth
smth 123 and 123
""",
        "reference": r"""
========== TEST same line var capture and use
[[x:.*]]
[[x]] [[x:\d+]] and [[x]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "func_call": {
        "input": """
========== TEST rgb
id 6027195
rgb 91;247;187
""",
        "reference": r"""
========== TEST rgb
id [[id:.*]]
rgb [[rgb(id)]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "capture_or_use_pass": {
        "input": """
========== TEST capture or use
abcd 12345 12345
use 12345
""",
        "reference": r"""
========== TEST capture or use
abcd [[id?:\d*]] [[id?:\d*]]
use [[id?:\d*]]
""",
        "should_fail": False,
    },
    ####################################################################################
    "capture_or_use_fail": {
        "input": """
========== TEST capture or use
abcd 12345 12345
use 1234
""",
        "reference": r"""
========== TEST capture or use
abcd [[id?:\d*]] [[id?:\d*]]
use [[id?:\d*]]
""",
        "should_fail": True,
    },
    ####################################################################################
    "capture_or_use_fail2": {
        "input": """
========== TEST capture or use
abcd 12345 1234
""",
        "reference": r"""
========== TEST capture or use
abcd [[id?:\d*]] [[id?:\d*]]
""",
        "should_fail": True,
    },
    ####################################################################################
}


@pytest.mark.parametrize("test_case", TEST_CASES.keys())
def test_comparison(test_case):
    data = TEST_CASES[test_case]
    if data["should_fail"]:
        if "error_pattern" in data:
            with pytest.raises(
                (ValueError, AssertionError), match=data["error_pattern"]
            ):
                result = compare(data["input"], data["reference"])
                if result["failed"]:
                    raise AssertionError("\n".join(result["errors"]))
        else:
            with pytest.raises(AssertionError):
                result = compare(data["input"], data["reference"])
                if result["failed"]:
                    raise AssertionError("\n".join(result["errors"]))
    else:
        result = compare(data["input"], data["reference"])
        assert not result["failed"], "\n".join(result["errors"])
        assert not result["missing_tests"], f"Missing tests: {result['missing_tests']}"
        assert not result["extra_tests"], f"Extra tests: {result['extra_tests']}"
