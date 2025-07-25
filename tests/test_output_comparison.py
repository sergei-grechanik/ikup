import pytest
from ikup.testing.output_comparison import (
    parse_chunks_from_content,
    process_test_chunk,
    compare,
    evaluate_assertion,
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
    "assertion_basic_pass": {
        "input": """
========== TEST assertions
id 123
name hello
value 45
""",
        "reference": r"""
========== TEST assertions
id [[id:\d+]]
name [[name:\w+]]
{{:ASSERT: int(id) > 100}}
{{:ASSERT: len(name) == 5}}
value [[value:\d+]]
{{:ASSERT: int(value) < 50}}
""",
        "should_fail": False,
    },
    ####################################################################################
    "assertion_basic_fail": {
        "input": """
========== TEST assertions
id 50
name hello
""",
        "reference": r"""
========== TEST assertions
id [[id:\d+]]
{{:ASSERT: int(id) > 100}}
name [[name:\w+]]
""",
        "should_fail": True,
        "error_pattern": "Assertion failed at reference line 4",
    },
    ####################################################################################
    "assertion_string_operations": {
        "input": """
========== TEST string ops
path /tmp/test.png
format PNG
size 1024KB
""",
        "reference": r"""
========== TEST string ops
path [[path:.*]]
format [[format:\w+]]
{{:ASSERT: startswith(path, '/tmp/')}}
{{:ASSERT: format == 'PNG'}}
size [[size:.*]]
{{:ASSERT: endswith(size, 'KB')}}
{{:ASSERT: contains(size, '1024')}}
""",
        "should_fail": False,
    },
    ####################################################################################
    "assertion_evaluation_error": {
        "input": """
========== TEST eval error
name hello
""",
        "reference": r"""
========== TEST eval error
name [[name:\w+]]
{{:ASSERT: undefined_function(name)}}
""",
        "should_fail": True,
        "error_pattern": "Assertion evaluation failed",
    },
    ####################################################################################
    "assertion_with_skip_lines": {
        "input": """
========== TEST skip and assert
start 42
junk1
junk2
target 84
end 126
""",
        "reference": r"""
========== TEST skip and assert
start [[x:\d+]]
{{:ASSERT: int(x) == 42}}
{{:SKIP_LINES:}}
target [[y:\d+]]
{{:ASSERT: int(y) == int(x) * 2}}
end [[z:\d+]]
{{:ASSERT: int(z) == int(x) + int(y)}}
""",
        "should_fail": False,
    },
    ####################################################################################
}


def test_evaluate_assertion():
    """Test the evaluate_assertion function directly."""
    variables = {
        "id": "123",
        "name": "hello",
        "count": "42",
        "path": "/tmp/test.png",
        "format": "PNG",
    }

    # Test basic expressions
    assert evaluate_assertion("int(id) > 100", variables) == True
    assert evaluate_assertion("int(id) < 100", variables) == False
    assert evaluate_assertion("len(name) == 5", variables) == True
    assert evaluate_assertion('name == "hello"', variables) == True

    # Test string operations
    assert evaluate_assertion('startswith(path, "/tmp/")', variables) == True
    assert evaluate_assertion('endswith(path, ".png")', variables) == True
    assert evaluate_assertion('contains(path, "test")', variables) == True

    # Test complex expressions
    assert evaluate_assertion("int(id) > 100 and len(name) == 5", variables) == True
    assert evaluate_assertion("int(count) in [40, 41, 42, 43]", variables) == True

    # Test failure cases
    with pytest.raises(AssertionError, match="Assertion evaluation failed"):
        evaluate_assertion("undefined_func(id)", variables)

    with pytest.raises(AssertionError, match="Assertion evaluation failed"):
        evaluate_assertion("int(name)", variables)  # Can't convert "hello" to int


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
