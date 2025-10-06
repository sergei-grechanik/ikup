"""Formula evaluation helpers."""

from __future__ import annotations

import ast
import math
import operator
from typing import Callable, List, Optional, Dict, Any


class FormulaEvaluationError(ValueError):
    """Raised when there is an error when executing a formula."""


_ALLOWED_BINOPS: Dict[Any, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_ALLOWED_UNARYOPS: Dict[Any, Callable[[Any], Any]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_ALLOWED_FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "min": min,
    "max": max,
    "ceil": math.ceil,
    "floor": math.floor,
}

_CONSTANTS = {
    "inf": math.inf,
    "_": None,
    "None": None,
    "none": None,
}


def evaluate_formula(
    formula: str,
    variables: Callable[[str], float],
    num_results: Optional[int] = None,
) -> List[float]:
    """Evaluate a mathematical formula with given variables. Never returns None."""
    res = evaluate_formula_maybe(formula, variables, num_results)
    if any(value is None for value in res):
        raise FormulaEvaluationError(f"Formula evaluated to None: {formula!r}")
    return [value for value in res if value is not None]


def evaluate_formula_maybe(
    formula: str,
    variables: Callable[[str], float],
    num_results: Optional[int] = None,
) -> List[Optional[float]]:
    """Evaluate a mathematical formula with given variables. May return None."""

    formula_stripped = formula.strip()
    if not formula_stripped:
        raise FormulaEvaluationError("Invalid expression")

    # A shortcut for formulas that are just a number.
    if num_results == 1:
        try:
            value = float(formula_stripped)
            return [value]
        except ValueError:
            pass

    try:
        expression = ast.parse(formula_stripped, mode="eval")
    except SyntaxError as exc:
        raise FormulaEvaluationError(
            f"Invalid expression in {formula!r}: {exc}"
        ) from exc

    def _eval_scalar(node: ast.AST) -> Optional[float]:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise FormulaEvaluationError(
                f"Unsupported constant: {node.value!r} in {ast.unparse(node)}"
            )
        if isinstance(node, ast.Name):
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            return variables(node.id)
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in _ALLOWED_BINOPS:
                raise FormulaEvaluationError(
                    f"Unsupported operator: {op.__name__} in {ast.unparse(node)}"
                )
            left = _eval_scalar(node.left)
            right = _eval_scalar(node.right)
            try:
                return _ALLOWED_BINOPS[op](left, right)
            except Exception as exc:
                raise FormulaEvaluationError(
                    f"Error while executing operator {op.__name__} in {ast.unparse(node)}: {exc}"
                ) from exc
        if isinstance(node, ast.UnaryOp):
            unary_op = type(node.op)
            if unary_op not in _ALLOWED_UNARYOPS:
                raise FormulaEvaluationError(
                    f"Unsupported operator: {unary_op.__name__} in {ast.unparse(node)}"
                )
            operand = _eval_scalar(node.operand)
            func = _ALLOWED_UNARYOPS[unary_op]
            return func(operand)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaEvaluationError(
                    "Unsupported function call in {ast.unparse(node)}"
                )
            func_name = node.func.id
            if node.keywords:
                raise FormulaEvaluationError(
                    "Keyword arguments are not supported in {ast.unparse(node)}"
                )
            # `first` and `second` are special lazy functions that return the first or
            # second argument, evaluating only the necessary argument.
            if func_name in ("first", "second"):
                if len(node.args) != 2:
                    raise FormulaEvaluationError(
                        f"{func_name}() requires exactly two arguments in {ast.unparse(node)}"
                    )
                if func_name == "first":
                    return _eval_scalar(node.args[0])
                if func_name == "second":
                    return _eval_scalar(node.args[1])
            if func_name not in _ALLOWED_FUNCTIONS:
                raise FormulaEvaluationError(f"Unsupported function: {func_name}")
            args = [_eval_scalar(arg) for arg in node.args]
            if func_name in ("ceil", "floor"):
                if len(args) != 1:
                    raise FormulaEvaluationError(
                        f"{func_name}() requires exactly one argument in {ast.unparse(node)}"
                    )
                if args[0] and math.isinf(args[0]):
                    return args[0]
            if func_name in ("min", "max"):
                if not args:
                    raise FormulaEvaluationError(
                        f"{func_name}() requires at least one argument in {ast.unparse(node)}"
                    )
                if len(args) == 1:
                    return args[0]
            try:
                func = _ALLOWED_FUNCTIONS[func_name]
                return func(*args)
            except Exception as exc:
                raise FormulaEvaluationError(
                    f"Error while executing function '{func_name}' in {ast.unparse(node)}: {exc}"
                ) from exc
        raise FormulaEvaluationError(
            f"Unsupported expression in formula: {ast.unparse(node)}"
        )

    def _eval(node: ast.AST) -> List[Optional[float]]:
        if isinstance(node, ast.Tuple):
            return [_eval_scalar(elt) for elt in node.elts]
        return [_eval_scalar(node)]

    results = _eval(expression.body)

    if num_results is not None and len(results) != num_results:
        raise FormulaEvaluationError(
            f"Expected {num_results} results, got {len(results)} in formula {formula!r}"
        )

    return results
