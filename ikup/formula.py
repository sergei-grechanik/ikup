"""Formula evaluation helpers."""

from __future__ import annotations

import ast
import math
import operator
from typing import Callable, List, Optional, Dict, Any


class FormulaEvaluationError(ValueError):
    """Raised when there is an error when executing a formula."""


_ALLOWED_BINOPS: Dict[Any, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}

_ALLOWED_UNARYOPS: Dict[Any, Callable[[float], float]] = {
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
}


def evaluate_formula(
    formula: str,
    variables: Callable[[str], float],
    num_results: Optional[int] = None,
) -> List[float]:
    """Evaluate a mathematical formula with given variables."""

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
        raise FormulaEvaluationError(f"Invalid expression: {exc}") from exc

    def _to_float(value: float) -> float:
        try:
            return float(value)
        except Exception as exc:
            raise FormulaEvaluationError(
                f"Non-numeric value in formula: {value!r}"
            ) from exc

    def _eval_scalar(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise FormulaEvaluationError(f"Unsupported constant: {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id in _CONSTANTS:
                return _CONSTANTS[node.id]
            value = variables(node.id)
            return _to_float(value)
        if isinstance(node, ast.BinOp):
            op = type(node.op)
            if op not in _ALLOWED_BINOPS:
                raise FormulaEvaluationError(f"Unsupported operator: {op.__name__}")
            left = _eval_scalar(node.left)
            right = _eval_scalar(node.right)
            try:
                return _ALLOWED_BINOPS[op](left, right)
            except Exception as exc:
                raise FormulaEvaluationError(
                    f"Error while executing operator {op.__name__}: {exc}"
                ) from exc
        if isinstance(node, ast.UnaryOp):
            unary_op = type(node.op)
            if unary_op not in _ALLOWED_UNARYOPS:
                raise FormulaEvaluationError(
                    f"Unsupported operator: {unary_op.__name__}"
                )
            operand = _eval_scalar(node.operand)
            func = _ALLOWED_UNARYOPS[unary_op]
            return func(operand)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise FormulaEvaluationError("Unsupported function call")
            func_name = node.func.id
            if func_name not in _ALLOWED_FUNCTIONS:
                raise FormulaEvaluationError(f"Unsupported function: {func_name}")
            if node.keywords:
                raise FormulaEvaluationError("Keyword arguments are not supported")
            args = [_eval_scalar(arg) for arg in node.args]
            if func_name in ("ceil", "floor"):
                if len(args) != 1:
                    raise FormulaEvaluationError(
                        f"{func_name}() requires exactly one argument"
                    )
                if math.isinf(args[0]):
                    return args[0]
            if func_name in ("min", "max"):
                if not args:
                    raise FormulaEvaluationError(
                        f"{func_name}() requires at least one argument"
                    )
                if len(args) == 1:
                    return _to_float(args[0])
            try:
                func = _ALLOWED_FUNCTIONS[func_name]
                return _to_float(func(*args))
            except Exception as exc:
                raise FormulaEvaluationError(
                    f"Error while executing function '{func_name}': {exc}"
                ) from exc
        raise FormulaEvaluationError(
            f"Unsupported expression in formula: {ast.dump(node)}"
        )

    def _eval(node: ast.AST) -> List[float]:
        if isinstance(node, ast.Tuple):
            if not node.elts:
                raise FormulaEvaluationError("Tuple in formula cannot be empty")
            return [_eval_scalar(elt) for elt in node.elts]
        return [_eval_scalar(node)]

    results = _eval(expression.body)

    if num_results is not None and len(results) != num_results:
        raise FormulaEvaluationError(
            f"Expected {num_results} results, got {len(results)}"
        )

    return [float(value) for value in results]


__all__ = ["FormulaEvaluationError", "evaluate_formula"]
