"""Controlled Python standard-library capabilities exposed to hybrid GP programs.

Only explicitly registered, side-effect-free functions are callable. This module
never imports a module named by GP source and never evaluates Python source.
"""
from __future__ import annotations

import hashlib
import math
import statistics
import textwrap
import unicodedata
from typing import Any, Callable

MAX_CALLS_PER_RUN = 1024
MAX_ARGUMENTS = 16
MAX_LIST_ITEMS = 10_000
MAX_VALUE_DEPTH = 8
MAX_TEXT_BYTES = 1 * 1024 * 1024
MAX_SAFE_INTEGER = 2**53


class PythonInteropError(ValueError):
    """A request to the Python host capability layer was rejected."""


def _arity(args: list[Any], allowed: int | tuple[int, ...], name: str) -> None:
    choices = (allowed,) if isinstance(allowed, int) else allowed
    if len(args) not in choices:
        expected = " ou ".join(str(item) for item in choices)
        raise PythonInteropError(f"{name}() exige {expected} argumento(s)")


def _number(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PythonInteropError(f"{name}: esperado numero")
    if isinstance(value, float) and not math.isfinite(value):
        raise PythonInteropError(f"{name}: número precisa ser finito")
    if isinstance(value, int) and abs(value) > MAX_SAFE_INTEGER:
        raise PythonInteropError(f"{name}: inteiro acima do limite seguro")
    return value


def _integer(value: Any, name: str) -> int:
    number = _number(value, name)
    if isinstance(number, float):
        if not number.is_integer():
            raise PythonInteropError(f"{name}: esperado inteiro")
        number = int(number)
    return number


def _numbers_list(value: Any, name: str, *, minimum: int = 1) -> list[float]:
    if not isinstance(value, list):
        raise PythonInteropError(f"{name}: esperado lista de números")
    if not minimum <= len(value) <= MAX_LIST_ITEMS:
        raise PythonInteropError(
            f"{name}: lista precisa conter entre {minimum} e {MAX_LIST_ITEMS} itens"
        )
    return [float(_number(item, name)) for item in value]


def _math_unary(fn: Callable[[float], Any], name: str, args: list[Any]) -> Any:
    _arity(args, 1, name)
    return fn(_number(args[0], name))


def _math_sqrt(args: list[Any]) -> float:
    value = _number(args[0], "math.sqrt") if len(args) == 1 else None
    _arity(args, 1, "math.sqrt")
    if value < 0:
        raise PythonInteropError("math.sqrt(): argumento não pode ser negativo")
    return math.sqrt(value)


def _math_log(args: list[Any]) -> float:
    _arity(args, (1, 2), "math.log")
    value = float(_number(args[0], "math.log"))
    base = math.e if len(args) == 1 else float(_number(args[1], "math.log"))
    if value <= 0 or base <= 0 or base == 1:
        raise PythonInteropError("math.log(): base e argumento fora do domínio")
    return math.log(value, base)


def _math_exp(args: list[Any]) -> float:
    _arity(args, 1, "math.exp")
    value = float(_number(args[0], "math.exp"))
    if not -700 <= value <= 700:
        raise PythonInteropError("math.exp(): argumento fora do limite [-700, 700]")
    return math.exp(value)


def _math_factorial(args: list[Any]) -> int:
    _arity(args, 1, "math.factorial")
    value = _integer(args[0], "math.factorial")
    if not 0 <= value <= 18:
        raise PythonInteropError("math.factorial(): use um inteiro entre 0 e 18")
    return math.factorial(value)


def _math_gcd(args: list[Any]) -> int:
    _arity(args, (1, 2, 3, 4, 5, 6, 7, 8), "math.gcd")
    return math.gcd(*(_integer(item, "math.gcd") for item in args))


def _math_lcm(args: list[Any]) -> int:
    _arity(args, (1, 2, 3, 4, 5, 6, 7, 8), "math.lcm")
    return math.lcm(*(_integer(item, "math.lcm") for item in args))


def _math_hypot(args: list[Any]) -> float:
    _arity(args, (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16), "math.hypot")
    return math.hypot(*(_number(item, "math.hypot") for item in args))


def _statistics_call(fn: Callable[..., Any], name: str, args: list[Any], minimum: int) -> Any:
    _arity(args, 1, name)
    return fn(_numbers_list(args[0], name, minimum=minimum))


def _sha256(args: list[Any]) -> str:
    _arity(args, 1, "hashlib.sha256")
    value = args[0]
    if not isinstance(value, str):
        raise PythonInteropError("hashlib.sha256(): esperado texto")
    raw = value.encode("utf-8", errors="strict")
    if len(raw) > MAX_TEXT_BYTES:
        raise PythonInteropError("hashlib.sha256(): texto acima de 1 MiB")
    return hashlib.sha256(raw).hexdigest()


def _normalize_unicode(args: list[Any]) -> str:
    _arity(args, 2, "unicodedata.normalize")
    form, value = args
    if form not in ("NFC", "NFD", "NFKC", "NFKD"):
        raise PythonInteropError("unicodedata.normalize(): forma deve ser NFC, NFD, NFKC ou NFKD")
    if not isinstance(value, str):
        raise PythonInteropError("unicodedata.normalize(): esperado texto")
    return unicodedata.normalize(form, value)


def _dedent(args: list[Any]) -> str:
    _arity(args, 1, "textwrap.dedent")
    if not isinstance(args[0], str):
        raise PythonInteropError("textwrap.dedent(): esperado texto")
    return textwrap.dedent(args[0])


def _shorten(args: list[Any]) -> str:
    _arity(args, (2, 3), "textwrap.shorten")
    value, width = args[0], _integer(args[1], "textwrap.shorten")
    placeholder = args[2] if len(args) == 3 else "[...]"
    if not isinstance(value, str) or not isinstance(placeholder, str):
        raise PythonInteropError("textwrap.shorten(): texto e placeholder precisam ser texto")
    if not 1 <= width <= MAX_TEXT_BYTES:
        raise PythonInteropError("textwrap.shorten(): largura fora do limite")
    return textwrap.shorten(value, width=width, placeholder=placeholder)


SAFE_FUNCTIONS: dict[str, Callable[[list[Any]], Any]] = {
    "math.sqrt": _math_sqrt,
    "math.sin": lambda args: _math_unary(math.sin, "math.sin", args),
    "math.cos": lambda args: _math_unary(math.cos, "math.cos", args),
    "math.tan": lambda args: _math_unary(math.tan, "math.tan", args),
    "math.log": _math_log,
    "math.log10": lambda args: _math_unary(math.log10, "math.log10", args),
    "math.exp": _math_exp,
    "math.fabs": lambda args: _math_unary(math.fabs, "math.fabs", args),
    "math.floor": lambda args: _math_unary(math.floor, "math.floor", args),
    "math.ceil": lambda args: _math_unary(math.ceil, "math.ceil", args),
    "math.factorial": _math_factorial,
    "math.gcd": _math_gcd,
    "math.lcm": _math_lcm,
    "math.hypot": _math_hypot,
    "math.isfinite": lambda args: _math_unary(math.isfinite, "math.isfinite", args),
    "statistics.mean": lambda args: _statistics_call(statistics.mean, "statistics.mean", args, 1),
    "statistics.median": lambda args: _statistics_call(statistics.median, "statistics.median", args, 1),
    "statistics.pstdev": lambda args: _statistics_call(statistics.pstdev, "statistics.pstdev", args, 1),
    "statistics.pvariance": lambda args: _statistics_call(statistics.pvariance, "statistics.pvariance", args, 1),
    "statistics.stdev": lambda args: _statistics_call(statistics.stdev, "statistics.stdev", args, 2),
    "statistics.variance": lambda args: _statistics_call(statistics.variance, "statistics.variance", args, 2),
    "hashlib.sha256": _sha256,
    "unicodedata.normalize": _normalize_unicode,
    "textwrap.dedent": _dedent,
    "textwrap.shorten": _shorten,
}


class PythonInterop:
    """Per-execution budget and allowlisted Python standard-library dispatcher."""

    def __init__(self, *, max_calls: int = MAX_CALLS_PER_RUN) -> None:
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or not 1 <= max_calls <= MAX_CALLS_PER_RUN:
            raise ValueError(f"max_calls deve estar entre 1 e {MAX_CALLS_PER_RUN}")
        self.max_calls = max_calls
        self.calls = 0

    @property
    def allowlist(self) -> tuple[str, ...]:
        return tuple(sorted(SAFE_FUNCTIONS))

    def reset(self) -> None:
        self.calls = 0

    def _normalize(self, value: Any, *, depth: int, budget: list[int]) -> Any:
        if depth > MAX_VALUE_DEPTH:
            raise PythonInteropError("py_chamar(): profundidade máxima de lista excedida")
        budget[0] -= 1
        if budget[0] < 0:
            raise PythonInteropError("py_chamar(): quantidade de valores excede o limite")
        if value is None or isinstance(value, (bool, str)):
            if isinstance(value, str):
                try:
                    size = len(value.encode("utf-8", errors="strict"))
                except UnicodeEncodeError as exc:
                    raise PythonInteropError("py_chamar(): texto contém Unicode inválido") from exc
                if size > MAX_TEXT_BYTES:
                    raise PythonInteropError("py_chamar(): texto acima de 1 MiB")
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _number(value, "py_chamar")
        if isinstance(value, list):
            if len(value) > MAX_LIST_ITEMS:
                raise PythonInteropError("py_chamar(): lista acima de 10.000 itens")
            return [
                self._normalize(item, depth=depth + 1, budget=budget)
                for item in value
            ]
        raise PythonInteropError(
            "py_chamar(): somente valores GP simples e listas podem atravessar a ponte"
        )

    def call(self, capability: Any, arguments: Any) -> Any:
        if self.calls >= self.max_calls:
            raise PythonInteropError("py_chamar(): limite de chamadas Python por execução excedido")
        if not isinstance(capability, str) or capability not in SAFE_FUNCTIONS:
            raise PythonInteropError(
                f"py_chamar(): capacidade Python não autorizada: {capability!r}"
            )
        if not isinstance(arguments, list):
            raise PythonInteropError("py_chamar(): segundo argumento precisa ser uma lista")
        if len(arguments) > MAX_ARGUMENTS:
            raise PythonInteropError(f"py_chamar(): máximo de {MAX_ARGUMENTS} argumentos")
        normalized = self._normalize(arguments, depth=0, budget=[MAX_LIST_ITEMS])
        self.calls += 1
        try:
            result = SAFE_FUNCTIONS[capability](normalized)
            return self._normalize(result, depth=0, budget=[MAX_LIST_ITEMS])
        except PythonInteropError:
            raise
        except (ArithmeticError, OverflowError, TypeError, ValueError, statistics.StatisticsError) as exc:
            raise PythonInteropError(f"{capability}: {exc}") from exc
