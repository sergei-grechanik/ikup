import os
import re
import sys
import string
import unicodedata
from typing import Dict, Tuple, List, Optional, Pattern, Match, Any

# Each chunk is a tuple of (lines, line_numbers).
TestChunks = Dict[str, Tuple[List[str], List[int]]]


def escape(s: str) -> str:
    escaped = []
    for char in s:
        if char.isprintable() and unicodedata.combining(char) == 0:
            escaped.append(char)
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\t")
        else:
            codepoint = ord(char)
            if codepoint <= 0xFF:
                escaped.append(f"\\x{codepoint:02x}")
            elif codepoint <= 0xFFFF:
                escaped.append(f"\\u{codepoint:04x}")
            else:
                escaped.append(f"\\U{codepoint:08x}")
    return "".join(escaped)


def evaluate_assertion(assertion: str, variables: Dict[str, str]) -> bool:
    """Evaluate an assertion expression with captured variables.

    Args:
        assertion: The assertion expression to evaluate
        variables: Dictionary of captured variables

    Returns:
        True if assertion passes, False otherwise

    Raises:
        AssertionError: If assertion fails or has evaluation errors
    """
    # Safe evaluation context with restricted builtins
    safe_globals = {
        "__builtins__": {},
        "len": len,
        "int": int,
        "str": str,
        "float": float,
        "min": min,
        "max": max,
        "abs": abs,
        "bool": bool,
        "isinstance": isinstance,
        "startswith": lambda s, prefix: str(s).startswith(prefix),
        "endswith": lambda s, suffix: str(s).endswith(suffix),
        "contains": lambda s, substr: substr in str(s),
    }

    try:
        result = eval(assertion, safe_globals, variables)
        return bool(result)
    except Exception as e:
        raise AssertionError(f"Assertion evaluation failed: {assertion} - {e}")


def transform_captured_var(func_name: str, args: str, variables: Dict[str, str]) -> str:
    """Transform captured variables based on function name and arguments."""
    if func_name == "rgb":
        val = int(variables[args])
        b = val & 0xFF
        g = (val >> 8) & 0xFF
        r = (val >> 16) & 0xFF
        return f"{r};{g};{b}"
    elif func_name == "hex":
        return f"{int(variables[args]):08x}"

    raise ValueError(f"Unknown function '{func_name}' with args '{args}'")


def parse_chunks(file_path: str) -> TestChunks:
    """Parse a file into test chunks based on '========== TEST' headers.

    Args:
        file_path: Path to the file to parse

    Returns:
        Dictionary mapping test names to tuples of (lines, line_numbers)

    Raises:
        ValueError: If duplicate test names are found
    """
    with open(file_path, "r", errors="backslashreplace") as f:
        content = f.read()
    return parse_chunks_from_content(content)


def parse_chunks_from_content(content: str) -> TestChunks:
    """Parse string content into test chunks with line number tracking.

    Args:
        content: Input string to parse

    Returns:
        Dictionary mapping test names to tuples of (lines, line_numbers)

    Raises:
        ValueError: If duplicate test names are found
    """
    chunks: TestChunks = {}
    current_test: Optional[str] = None
    lines: List[str] = []
    line_numbers: List[int] = []

    # Process each line with its original line number
    for line_num, line in enumerate(content.split("\n"), 1):
        line = line.rstrip("\n")
        if line.startswith("========== TEST "):
            test_name = line
            if current_test:
                chunks[current_test] = (lines.copy(), line_numbers.copy())
                lines.clear()
                line_numbers.clear()
            if test_name in chunks:
                raise ValueError(
                    f"Duplicate test name '{test_name}' at line {line_num}"
                )
            current_test = test_name
        elif current_test is not None:
            # Capture all lines including leading empty ones
            lines.append(line)
            line_numbers.append(line_num)
    if current_test is not None:
        # Strip trailing empty lines from both input and reference
        while lines and not lines[-1].strip():
            lines.pop()
            line_numbers.pop()
        chunks[current_test] = (lines, line_numbers)
    return chunks


def process_ref_line(line: str, variables: Dict[str, str]) -> Tuple[str, List[str]]:
    """Process a reference line with variables and regex patterns into a regex pattern.

    Args:
        line: Reference line to process
        variables: Current set of captured variables

    Returns:
        Tuple of (compiled_regex_pattern, list_of_captured_variables)

    Raises:
        ValueError: If undefined variable is referenced
    """
    parts: List[str] = []
    captures: List[str] = []
    # Split line into literal text and pattern tokens while preserving order
    tokens = re.split(r"(\{\{.*?\}\}|\[\[.*?\]\])", line)

    for token in tokens:
        if not token:
            continue
        if token.startswith("[[") and token.endswith("]]"):
            content = token[2:-2]
            if "?:" in content:
                var, regex = content.split("?:", 1)
                if var in variables or var in captures:
                    content = var
                else:
                    content = f"{var}:{regex}"
            if ":" in content:
                var, regex = content.split(":", 1)
                parts.append(f"(?P<{var}>{regex})")
                captures.append(var)
            else:
                # Check if variable was captured earlier in this line
                if content in captures:
                    parts.append(f"(?P={content})")
                elif content in variables:
                    parts.append(re.escape(variables[content]))
                elif content.endswith(")"):
                    # Handle function-like syntax
                    func_name, args = content[:-1].split("(", 1)
                    val = transform_captured_var(func_name, args, variables)
                    parts.append(re.escape(val))
                else:
                    raise ValueError(f"Undefined variable '{content}'")
        elif token.startswith("{{") and token.endswith("}}"):
            parts.append(f"(?:{token[2:-2]})")
        else:
            parts.append(re.escape(token))

    return "^" + "".join(parts) + "$", captures


def process_test_chunk(
    test: str,
    ref_lines: List[str],
    ref_nums: List[int],
    inp_lines: List[str],
    inp_nums: List[int],
) -> List[str]:
    """Compare a single test chunk between reference and input.

    Args:
        test: Test name for error reporting
        ref_lines: Reference lines to match against
        ref_nums: Original line numbers for reference lines
        inp_lines: Input lines to check
        inp_nums: Original line numbers for input lines

    Returns:
        List of error messages (empty if no errors)
    """
    variables: Dict[str, str] = {}
    errors: List[str] = []
    i = j = 0  # Pointers for input/reference lines

    while j < len(ref_lines):
        if ref_lines[j] == "{{:SKIP_LINES:}}":
            if j + 1 >= len(ref_lines):
                # Skip all remaining input lines
                return []

            target_line = ref_lines[j + 1]
            found = False
            starti = i
            pattern = None
            while i < len(inp_lines):
                try:
                    pattern, captures = process_ref_line(target_line, variables)
                    match = re.fullmatch(pattern, inp_lines[i])
                    if match:
                        found = True
                        break
                except:
                    pass
                i += 1

            if not found:
                errors.append(
                    f"{test}\n"
                    f"Failed to find line matching:\n{escape(target_line)}\n"
                    f"Starting from {inp_nums[starti]}:\n{escape(inp_lines[starti])}\n"
                )
                return errors
            # Continue processing after successful skip

            # After successful skip, continue processing from next line
            j += 1  # We already processed the SKIP_LINES marker
            continue

        # Handle assertion lines
        if ref_lines[j].startswith("{{:ASSERT:") and ref_lines[j].endswith("}}"):
            assertion_expr = ref_lines[j][10:-2].strip()  # Remove {{:ASSERT: and }}
            try:
                if not evaluate_assertion(assertion_expr, variables):
                    errors.append(
                        f"{test}\n"
                        f"Assertion failed at reference line {ref_nums[j]}:\n"
                        f"{escape(ref_lines[j])}\n"
                        f"Expression: {assertion_expr}\n"
                        f"Variables: {variables}"
                    )
                    return errors
            except AssertionError as e:
                errors.append(
                    f"{test}\n"
                    f"Assertion error at reference line {ref_nums[j]}:\n"
                    f"{escape(ref_lines[j])}\n"
                    f"Error: {e}"
                )
                return errors

            # Assertion lines don't consume input lines, move to next reference line
            j += 1
            continue

        if i >= len(inp_lines):
            if j >= len(ref_lines):
                break
            errors.append(
                f"{test}\n"
                "Unexpected end of input at line {inp_nums[-1]}\n"
                f"Reference line {ref_nums[j]}:\n{escape(ref_lines[j])}",
            )
            return errors
        # Continue processing remaining lines after skip

        error = None
        captures = {}
        try:
            pattern, captures = process_ref_line(ref_lines[j], variables)
            match = re.fullmatch(pattern, inp_lines[i])
        except ValueError as e:
            error = str(e)
            match = None

        if not match:
            error_msg = [
                f"{test}",
                "Failed to match:",
            ]
            if error:
                error_msg.append(f"Error: {error}")
            error_msg.extend(
                [
                    f"Reference line {ref_nums[j]}:\n{escape(ref_lines[j])}",
                    f"Input line {inp_nums[i]}:\n{escape(inp_lines[i])}",
                ]
            )
            if variables:
                error_msg.append("Variables:")
                error_msg.extend(f"  {k}: {escape(v)}" for k, v in variables.items())

            errors.append("\n".join(error_msg))
            return errors

        for var in captures:
            variables[var] = match.group(var)

        i += 1
        j += 1

    return errors


def compare(input_content: str, ref_content: str) -> Dict[str, Any]:
    """Compare input content against reference content with test chunking.

    Args:
        input_content: Content to validate
        ref_content: Reference content with patterns

    Returns:
        Dictionary with:
        - errors: List of error messages
        - missing_tests: Tests in reference not found in input
        - extra_tests: Tests in input not in reference
        - failed: Overall validation status
    """
    try:
        input_chunks = parse_chunks_from_content(input_content)
        ref_chunks = parse_chunks_from_content(ref_content)
    except ValueError as e:
        return {
            "errors": [str(e)],
            "missing_tests": [],
            "extra_tests": [],
            "failed": True,
        }

    errors = []
    missing_tests = []
    failed = False

    # Check reference tests against input
    for test in ref_chunks:
        if test not in input_chunks:
            missing_tests.append(test)
            continue

        ref_lines, ref_nums = ref_chunks[test]
        inp_lines, inp_nums = input_chunks[test]
        chunk_errors = process_test_chunk(
            test, ref_lines, ref_nums, inp_lines, inp_nums
        )
        if chunk_errors:
            errors.extend(chunk_errors)
            failed = True

    # Check for extra tests in input
    extra_tests = list(set(input_chunks.keys()) - set(ref_chunks.keys()))

    return {
        "errors": errors,
        "missing_tests": missing_tests,
        "extra_tests": extra_tests,
        "failed": failed or bool(missing_tests) or bool(extra_tests),
    }


def compare_directories(input_dir: str, ref_dir: str) -> Dict[str, Any]:
    """Compare directories containing test output files.

    Args:
        input_dir: Directory containing test output files
        ref_dir: Directory containing reference files

    Returns:
        Dictionary with comparison results
    """
    if not os.path.isdir(input_dir):
        return {
            "errors": [f"Input directory '{input_dir}' not found"],
            "missing_tests": [],
            "extra_tests": [],
            "failed": True,
        }

    if not os.path.isdir(ref_dir):
        return {
            "errors": [f"Reference directory '{ref_dir}' not found"],
            "missing_tests": [],
            "extra_tests": [],
            "failed": True,
        }

    # Get all test files
    input_files = {f for f in os.listdir(input_dir) if f.endswith(".out")}
    ref_files = {f for f in os.listdir(ref_dir) if f.endswith(".reference")}

    # Convert to test names for comparison
    input_tests = {f[:-4] for f in input_files}  # Remove .out
    ref_tests = {f[:-10] for f in ref_files}  # Remove .reference

    errors = []
    missing_tests = []
    extra_tests = []
    failed = False

    # Compare files that exist in both directories
    for test_name in ref_tests:
        if test_name not in input_tests:
            missing_tests.append(test_name)
            continue

        input_file = os.path.join(input_dir, f"{test_name}.out")
        ref_file = os.path.join(ref_dir, f"{test_name}.reference")

        try:
            with open(input_file, "r", errors="backslashreplace") as f:
                input_content = f.read()
            with open(ref_file, "r", errors="backslashreplace") as f:
                ref_content = f.read()

            result = compare(input_content, ref_content)
            if result["failed"]:
                errors.extend(result["errors"])
                # Also include missing/extra tests as errors for file-level mismatches
                if result["missing_tests"]:
                    for missing_test in result["missing_tests"]:
                        errors.append(f"Missing test in {test_name}: {missing_test}")
                if result["extra_tests"]:
                    for extra_test in result["extra_tests"]:
                        errors.append(f"Extra test in {test_name}: {extra_test}")
                failed = True

        except Exception as e:
            errors.append(f"Error comparing {test_name}: {e}")
            failed = True

    # Find extra tests in input
    extra_tests = list(input_tests - ref_tests)

    return {
        "errors": errors,
        "missing_tests": missing_tests,
        "extra_tests": extra_tests,
        "failed": failed or bool(missing_tests) or bool(extra_tests),
    }


def main() -> None:
    """Command line interface entry point for comparison tool.

    Handles file I/O and result reporting. Exits with status code 1
    if any discrepancies are found.
    """
    if len(sys.argv) != 3:
        print("Usage: compare.py input_file_or_dir reference_file_or_dir")
        sys.exit(1)

    input_path = sys.argv[1]
    ref_path = sys.argv[2]

    # Check if we're comparing directories or files
    if os.path.isdir(input_path) and os.path.isdir(ref_path):
        result = compare_directories(input_path, ref_path)
    elif os.path.isfile(input_path) and os.path.isfile(ref_path):
        try:
            with open(input_path, errors="backslashreplace") as f:
                input_content = f.read()
            with open(ref_path) as f:
                ref_content = f.read()
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)

        result = compare(input_content, ref_content)
    else:
        print("Error: Both arguments must be files or both must be directories")
        sys.exit(1)

    for error in result["errors"]:
        print(error)

    if result["missing_tests"]:
        print("Missing tests in input:")
        for test in result["missing_tests"]:
            print(f" {test}")
        print()

    if result["extra_tests"]:
        print("Extra tests in input not present in reference:")
        for test in result["extra_tests"]:
            print(f" {test}")

    if result["errors"] or result["missing_tests"] or result["extra_tests"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
