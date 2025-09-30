import math

import pytest

from ikup.formula import FormulaEvaluationError, evaluate_formula


def _var_provider(mapping):
    def _get(name: str) -> float:
        if name in mapping:
            return mapping[name]
        raise FormulaEvaluationError(f"Unknown variable: {name}")

    return _get


def no_vars(name: str) -> float:
    raise FormulaEvaluationError(f"Unexpected variable access: {name}")


def test_evaluate_formula_simple_arithmetic():
    result = evaluate_formula("1 + 2 * 3", no_vars)
    assert result == [7.0]


def test_evaluate_formula_multiple_results():
    result = evaluate_formula("1 + 2, 3 * 4", no_vars, num_results=2)
    assert result == [3.0, 12.0]


def test_evaluate_formula_with_variables():
    vars_ = {"tc": 120, "cw": 2}
    result = evaluate_formula("tc / cw", _var_provider(vars_))
    assert result == [60.0]


def test_evaluate_formula_functions():
    vars_ = {"height": 11, "ch": 4}
    result = evaluate_formula("floor(height / ch)", _var_provider(vars_))
    assert result == [float(math.floor(11 / 4))]


def test_evaluate_formula_inf_constant():
    result = evaluate_formula("min(10, inf)", no_vars)
    assert result == [10.0]


def test_evaluate_formula_unknown_variable():
    with pytest.raises(FormulaEvaluationError):
        evaluate_formula("tc + 1", no_vars)


def test_evaluate_formula_invalid_syntax():
    with pytest.raises(FormulaEvaluationError):
        evaluate_formula("1 +", no_vars)


def test_evaluate_formula_unsupported_function():
    with pytest.raises(FormulaEvaluationError):
        evaluate_formula("abs(-1)", no_vars)


def test_evaluate_formula_unsupported_operator():
    with pytest.raises(FormulaEvaluationError):
        evaluate_formula("2 ** 3", no_vars)


def test_evaluate_formula_num_results_mismatch():
    with pytest.raises(FormulaEvaluationError):
        evaluate_formula("1, 2", no_vars, num_results=1)


def test_basic_arithmetic():
    """Test basic arithmetic operations."""
    assert evaluate_formula("2 + 3", no_vars) == [5.0]
    assert evaluate_formula("10 - 4", no_vars) == [6.0]
    assert evaluate_formula("6 * 7", no_vars) == [42.0]
    assert evaluate_formula("15 / 3", no_vars) == [5.0]


def test_operator_precedence():
    """Test that operator precedence is respected."""
    assert evaluate_formula("2 + 3 * 4", no_vars) == [14.0]
    assert evaluate_formula("10 - 2 * 3", no_vars) == [4.0]
    assert evaluate_formula("15 / 3 + 2", no_vars) == [7.0]


def test_parentheses():
    """Test parentheses for grouping."""
    assert evaluate_formula("(2 + 3) * 4", no_vars) == [20.0]
    assert evaluate_formula("10 - (2 * 3)", no_vars) == [4.0]
    assert evaluate_formula("(15 / 3) + 2", no_vars) == [7.0]
    assert evaluate_formula("((2 + 3) * 4) / 5", no_vars) == [4.0]


def test_unary_operators():
    """Test unary plus and minus."""
    assert evaluate_formula("-5", no_vars) == [-5.0]
    assert evaluate_formula("+5", no_vars) == [5.0]
    assert evaluate_formula("10 + -3", no_vars) == [7.0]
    assert evaluate_formula("10 - -3", no_vars) == [13.0]


def test_floating_point_numbers():
    """Test floating point number parsing."""
    assert evaluate_formula("3.14", no_vars) == [3.14]
    assert evaluate_formula("0.5 + 0.25", no_vars) == [0.75]
    assert evaluate_formula("inf", no_vars) == [float("inf")]


def test_multiple_results():
    """Test comma-separated expressions."""
    assert evaluate_formula("2 + 3, 4 * 5", no_vars) == [5.0, 20.0]
    assert evaluate_formula("1, 2, 3", no_vars) == [1.0, 2.0, 3.0]
    assert evaluate_formula("10 / 2, 6 - 1", no_vars) == [5.0, 5.0]


def test_num_results_validation():
    """Test num_results parameter validation."""
    # Correct number of results
    assert evaluate_formula("1, 2", no_vars, num_results=2) == [1.0, 2.0]

    # Wrong number of results
    with pytest.raises(FormulaEvaluationError, match="Expected 2 results, got 1"):
        evaluate_formula("1", no_vars, num_results=2)

    with pytest.raises(FormulaEvaluationError, match="Expected 1 results, got 2"):
        evaluate_formula("1, 2", no_vars, num_results=1)


def test_functions_min_max():
    """Test min and max functions."""
    assert evaluate_formula("min(5, 3, 7)", no_vars) == [3.0]
    assert evaluate_formula("max(5, 3, 7)", no_vars) == [7.0]
    assert evaluate_formula("min(10)", no_vars) == [10.0]
    assert evaluate_formula("max(10)", no_vars) == [10.0]
    assert evaluate_formula("min(1 + 2, 3 * 2, 4)", no_vars) == [3.0]


def test_functions_ceil_floor():
    """Test ceil and floor functions."""
    assert evaluate_formula("ceil(3.2)", no_vars) == [4.0]
    assert evaluate_formula("floor(3.7)", no_vars) == [3.0]
    assert evaluate_formula("ceil(-2.3)", no_vars) == [-2.0]
    assert evaluate_formula("floor(-2.3)", no_vars) == [-3.0]


def test_inf():
    """Test handling of infinity."""
    assert evaluate_formula("inf + 1", no_vars) == [float("inf")]
    assert evaluate_formula("inf * 2", no_vars) == [float("inf")]
    assert evaluate_formula("max(inf, 2)", no_vars) == [float("inf")]
    assert evaluate_formula("min(inf, 2)", no_vars) == [2.0]
    assert evaluate_formula("ceil(inf)", no_vars) == [float("inf")]
    assert evaluate_formula("floor(inf)", no_vars) == [float("inf")]
    assert evaluate_formula("ceil(-inf)", no_vars) == [float("-inf")]
    assert evaluate_formula("floor(-inf)", no_vars) == [float("-inf")]


def test_variables():
    """Test variable resolution."""

    def var_resolver(name):
        vars_dict = {"x": 10.0, "y": 5.0, "tc": 80.0, "tr": 24.0, "cw": 8.0, "ch": 16.0}
        if name in vars_dict:
            return vars_dict[name]
        raise ValueError(f"Unknown variable: {name}")

    assert evaluate_formula("x + y", var_resolver) == [15.0]
    assert evaluate_formula("tc / cw", var_resolver) == [10.0]
    assert evaluate_formula("min(x, y)", var_resolver) == [5.0]
    assert evaluate_formula("x, y", var_resolver) == [10.0, 5.0]


def test_complex_expressions():
    """Test complex nested expressions."""

    def var_resolver(name):
        vars_dict = {"a": 2.0, "b": 3.0, "c": 4.0}
        if name in vars_dict:
            return vars_dict[name]
        raise ValueError(f"Unknown variable: {name}")

    # Complex arithmetic with functions and variables
    assert evaluate_formula("max(a * b, c + 1)", var_resolver) == [6.0]
    assert evaluate_formula("ceil((a + b) / c)", var_resolver) == [2.0]
    assert evaluate_formula("min(a, b, c) + max(a, b, c)", var_resolver) == [6.0]


def test_error_cases():
    """Test various error conditions."""

    def no_vars(name):
        raise ValueError(f"No variable: {name}")

    # Division by zero
    with pytest.raises(FormulaEvaluationError, match="division by zero"):
        evaluate_formula("10 / 0", no_vars)

    # Unknown variable
    with pytest.raises(ValueError, match="No variable: unknown_var"):
        evaluate_formula("unknown_var", no_vars)

    # Mismatched parentheses
    with pytest.raises(FormulaEvaluationError, match="Invalid expression"):
        evaluate_formula("(2 + 3", no_vars)

    # Invalid function argument count
    with pytest.raises(FormulaEvaluationError, match="requires at least one argument"):
        evaluate_formula("min()", no_vars)

    with pytest.raises(FormulaEvaluationError, match="requires exactly one argument"):
        evaluate_formula("ceil(1, 2)", no_vars)

    # Invalid tokens
    with pytest.raises(FormulaEvaluationError, match="Unsupported operator"):
        evaluate_formula("2 @ 3", no_vars)

    # Empty expression
    with pytest.raises(FormulaEvaluationError, match="Invalid expression"):
        evaluate_formula("", no_vars)


def test_whitespace_handling():
    """Test that whitespace is properly handled."""

    def no_vars(name):
        raise ValueError(f"No variable: {name}")

    assert evaluate_formula("  2  +  3  ", no_vars) == [5.0]
    assert evaluate_formula("( 2 + 3 ) * 4", no_vars) == [20.0]
    assert evaluate_formula("min( 1 , 2 , 3 )", no_vars) == [1.0]


def test_cli_usage_pattern():
    """Test the specific pattern used in CLI code."""

    def var_resolver(name):
        # Simulate terminal variables
        if name == "tc":
            return 80.0  # terminal columns
        elif name == "tr":
            return 24.0  # terminal rows
        elif name == "cw":
            return 8.0  # cell width
        elif name == "ch":
            return 16.0  # cell height
        raise ValueError(f"Unknown variable: {name}")

    # Test the pattern from CLI: ','.join((cols, rows))
    cols = "30"
    rows = "30"
    formula = ",".join((cols, rows))
    colsf, rowsf = evaluate_formula(formula, var_resolver, num_results=2)
    assert colsf == 30.0
    assert rowsf == 30.0

    # Test with expressions
    cols = "tc / 2"
    rows = "tr"
    formula = ",".join((cols, rows))
    colsf, rowsf = evaluate_formula(formula, var_resolver, num_results=2)
    assert colsf == 40.0
    assert rowsf == 24.0
