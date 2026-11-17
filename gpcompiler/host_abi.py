"""Versioned, portable host-capability ABI for GP runtimes.

The ABI exposes a closed set of deterministic, side-effect-free operations.
It deliberately uses stable string identifiers over the existing GP-IR CALL
instruction, so GGPC v2 and GP-IR v1 remain wire-compatible.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import statistics
from typing import Any, Callable

HOST_ABI_VERSION = 1
HOST_ABI_PREFIX = "gp.core.v1."
HOST_MAX_CALLS_PER_RUN = 1024
HOST_MAX_ARGUMENTS = 16
HOST_MAX_LIST_ITEMS = 10_000
HOST_MAX_VALUE_DEPTH = 8
HOST_MAX_TEXT_BYTES = 1 * 1024 * 1024
HOST_MAX_SAFE_INTEGER = 2**53 - 1


class HostABIError(ValueError):
    """A host capability request violated the ABI contract."""


@dataclass(frozen=True)
class HostCapability:
    identifier: str
    min_arguments: int
    max_arguments: int
    arguments: str
    result: str
    description: str


def _number(value: Any, name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HostABIError(f"{name}: esperado número")
    if isinstance(value, float) and not math.isfinite(value):
        raise HostABIError(f"{name}: número precisa ser finito")
    if isinstance(value, int) and abs(value) > HOST_MAX_SAFE_INTEGER:
        raise HostABIError(f"{name}: inteiro acima do limite seguro")
    return value


def _integer(value: Any, name: str) -> int:
    value = _number(value, name)
    if isinstance(value, float):
        if not value.is_integer():
            raise HostABIError(f"{name}: esperado inteiro")
        value = int(value)
    return value


def _numbers(args: list[Any], name: str, *, minimum: int = 1) -> list[float]:
    if len(args) != 1 or not isinstance(args[0], list):
        raise HostABIError(f"{name}: esperado um argumento que seja lista numérica")
    values = args[0]
    if not minimum <= len(values) <= HOST_MAX_LIST_ITEMS:
        raise HostABIError(f"{name}: lista precisa conter entre {minimum} e {HOST_MAX_LIST_ITEMS} itens")
    return [float(_number(value, name)) for value in values]


def _exact(args: list[Any], count: int, name: str) -> None:
    if len(args) != count:
        raise HostABIError(f"{name}: exige {count} argumento(s)")


def _unary(fn: Callable[[float], Any], name: str) -> Callable[[list[Any]], Any]:
    def call(args: list[Any]) -> Any:
        _exact(args, 1, name)
        return fn(float(_number(args[0], name)))
    return call


def _sqrt(args: list[Any]) -> float:
    _exact(args, 1, "raiz")
    value = float(_number(args[0], "raiz"))
    if value < 0:
        raise HostABIError("raiz: argumento não pode ser negativo")
    return math.sqrt(value)


def _log(args: list[Any]) -> float:
    if len(args) not in (1, 2):
        raise HostABIError("log: exige 1 ou 2 argumentos")
    value = float(_number(args[0], "log"))
    base = math.e if len(args) == 1 else float(_number(args[1], "log"))
    if value <= 0 or base <= 0 or base == 1:
        raise HostABIError("log: argumento/base fora do domínio")
    return math.log(value, base)


def _exp(args: list[Any]) -> float:
    _exact(args, 1, "exp")
    value = float(_number(args[0], "exp"))
    if not -700 <= value <= 700:
        raise HostABIError("exp: argumento fora do limite [-700, 700]")
    return math.exp(value)


def _factorial(args: list[Any]) -> int:
    _exact(args, 1, "fatorial")
    value = _integer(args[0], "fatorial")
    if not 0 <= value <= 18:
        raise HostABIError("fatorial: use um inteiro entre 0 e 18")
    return math.factorial(value)


def _gcd(args: list[Any]) -> int:
    if not 2 <= len(args) <= HOST_MAX_ARGUMENTS:
        raise HostABIError(f"mdc: exige entre 2 e {HOST_MAX_ARGUMENTS} argumentos")
    return math.gcd(*(_integer(value, "mdc") for value in args))


def _lcm(args: list[Any]) -> int:
    if not 2 <= len(args) <= HOST_MAX_ARGUMENTS:
        raise HostABIError(f"mmc: exige entre 2 e {HOST_MAX_ARGUMENTS} argumentos")
    result = math.lcm(*(_integer(value, "mmc") for value in args))
    if result > HOST_MAX_SAFE_INTEGER:
        raise HostABIError("mmc: resultado acima do limite inteiro seguro")
    return result


def _hypot(args: list[Any]) -> float:
    if not 2 <= len(args) <= HOST_MAX_ARGUMENTS:
        raise HostABIError(f"hipotenusa: exige entre 2 e {HOST_MAX_ARGUMENTS} argumentos")
    return math.hypot(*(_number(value, "hipotenusa") for value in args))


def _finite(args: list[Any]) -> bool:
    _exact(args, 1, "numero_finito")
    value = args[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HostABIError("numero_finito: esperado número")
    return math.isfinite(value)


def _mean(args: list[Any]) -> float:
    return statistics.mean(_numbers(args, "media"))


def _median(args: list[Any]) -> int | float:
    return statistics.median(_numbers(args, "mediana"))


def _variance(args: list[Any], *, sample: bool) -> float:
    name = "variancia_amostral" if sample else "variancia_populacional"
    values = _numbers(args, name, minimum=2 if sample else 1)
    return statistics.variance(values) if sample else statistics.pvariance(values)


def _stddev(args: list[Any], *, sample: bool) -> float:
    value = _variance(args, sample=sample)
    return math.sqrt(value)


def _spec(identifier: str, minimum: int, maximum: int, arguments: str, result: str, description: str) -> HostCapability:
    return HostCapability(identifier, minimum, maximum, arguments, result, description)


_CAPABILITY_ROWS: tuple[tuple[HostCapability, Callable[[list[Any]], Any]], ...] = (
    (_spec(HOST_ABI_PREFIX + "math.sqrt", 1, 1, "numero", "numero", "Raiz quadrada"), _sqrt),
    (_spec(HOST_ABI_PREFIX + "math.sin", 1, 1, "numero", "numero", "Seno em radianos"), _unary(math.sin, "seno")),
    (_spec(HOST_ABI_PREFIX + "math.cos", 1, 1, "numero", "numero", "Cosseno em radianos"), _unary(math.cos, "cosseno")),
    (_spec(HOST_ABI_PREFIX + "math.tan", 1, 1, "numero", "numero", "Tangente em radianos"), _unary(math.tan, "tangente")),
    (_spec(HOST_ABI_PREFIX + "math.log", 1, 2, "numero[, numero]", "numero", "Logaritmo natural ou em base informada"), _log),
    (_spec(HOST_ABI_PREFIX + "math.log10", 1, 1, "numero", "numero", "Logaritmo decimal"), _unary(math.log10, "log10")),
    (_spec(HOST_ABI_PREFIX + "math.exp", 1, 1, "numero", "numero", "Exponencial limitada"), _exp),
    (_spec(HOST_ABI_PREFIX + "math.abs", 1, 1, "numero", "numero", "Valor absoluto"), _unary(abs, "absoluto")),
    (_spec(HOST_ABI_PREFIX + "math.floor", 1, 1, "numero", "numero", "Arredondamento para baixo"), _unary(math.floor, "piso")),
    (_spec(HOST_ABI_PREFIX + "math.ceil", 1, 1, "numero", "numero", "Arredondamento para cima"), _unary(math.ceil, "teto")),
    (_spec(HOST_ABI_PREFIX + "math.factorial", 1, 1, "inteiro[0..18]", "numero", "Fatorial limitado"), _factorial),
    (_spec(HOST_ABI_PREFIX + "math.gcd", 2, 16, "inteiros", "numero", "Máximo divisor comum"), _gcd),
    (_spec(HOST_ABI_PREFIX + "math.lcm", 2, 16, "inteiros", "numero", "Mínimo múltiplo comum"), _lcm),
    (_spec(HOST_ABI_PREFIX + "math.hypot", 2, 16, "numeros", "numero", "Norma euclidiana"), _hypot),
    (_spec(HOST_ABI_PREFIX + "math.is_finite", 1, 1, "numero", "logico", "Verifica se o número é finito"), _finite),
    (_spec(HOST_ABI_PREFIX + "statistics.mean", 1, 1, "lista<numero>", "numero", "Média aritmética"), _mean),
    (_spec(HOST_ABI_PREFIX + "statistics.median", 1, 1, "lista<numero>", "numero", "Mediana"), _median),
    (_spec(HOST_ABI_PREFIX + "statistics.pvariance", 1, 1, "lista<numero>", "numero", "Variância populacional"), lambda args: _variance(args, sample=False)),
    (_spec(HOST_ABI_PREFIX + "statistics.variance", 1, 1, "lista<numero>", "numero", "Variância amostral"), lambda args: _variance(args, sample=True)),
    (_spec(HOST_ABI_PREFIX + "statistics.pstdev", 1, 1, "lista<numero>", "numero", "Desvio padrão populacional"), lambda args: _stddev(args, sample=False)),
    (_spec(HOST_ABI_PREFIX + "statistics.stdev", 1, 1, "lista<numero>", "numero", "Desvio padrão amostral"), lambda args: _stddev(args, sample=True)),
)

HOST_CAPABILITIES: dict[str, HostCapability] = {spec.identifier: spec for spec, _ in _CAPABILITY_ROWS}
_HOST_FUNCTIONS: dict[str, Callable[[list[Any]], Any]] = {spec.identifier: fn for spec, fn in _CAPABILITY_ROWS}


def host_capabilities_manifest() -> dict[str, Any]:
    """Return a JSON-safe, stable description of this runtime's ABI surface."""
    return {
        "abiVersion": HOST_ABI_VERSION,
        "prefix": HOST_ABI_PREFIX,
        "defaultEnabled": True,
        "maxCallsPerRun": HOST_MAX_CALLS_PER_RUN,
        "maxArguments": HOST_MAX_ARGUMENTS,
        "maxListItems": HOST_MAX_LIST_ITEMS,
        "capabilities": [asdict(HOST_CAPABILITIES[key]) for key in sorted(HOST_CAPABILITIES)],
    }


class HostABI:
    """Per-program dispatcher for portable, versioned host capabilities."""

    def __init__(self, *, max_calls: int = HOST_MAX_CALLS_PER_RUN) -> None:
        if isinstance(max_calls, bool) or not isinstance(max_calls, int) or not 1 <= max_calls <= HOST_MAX_CALLS_PER_RUN:
            raise ValueError(f"max_calls deve estar entre 1 e {HOST_MAX_CALLS_PER_RUN}")
        self.max_calls = max_calls
        self.calls = 0

    def reset(self) -> None:
        self.calls = 0

    def _normalize(self, value: Any, *, depth: int = 0, budget: list[int] | None = None, allow_nonfinite: bool = False) -> Any:
        if budget is None:
            budget = [HOST_MAX_LIST_ITEMS * 2 + HOST_MAX_ARGUMENTS + 1]
        if depth > HOST_MAX_VALUE_DEPTH:
            raise HostABIError("host_chamar(): profundidade máxima de lista excedida")
        budget[0] -= 1
        if budget[0] < 0:
            raise HostABIError("host_chamar(): quantidade de valores excede o limite")
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                size = len(value.encode("utf-8", errors="strict"))
            except UnicodeEncodeError as exc:
                raise HostABIError("host_chamar(): texto Unicode inválido") from exc
            if size > HOST_MAX_TEXT_BYTES:
                raise HostABIError("host_chamar(): texto acima de 1 MiB")
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if allow_nonfinite and isinstance(value, float) and not math.isfinite(value):
                return value
            return _number(value, "host_chamar")
        if isinstance(value, list):
            if len(value) > HOST_MAX_LIST_ITEMS:
                raise HostABIError("host_chamar(): lista acima de 10.000 itens")
            return [
                self._normalize(item, depth=depth + 1, budget=budget, allow_nonfinite=allow_nonfinite)
                for item in value
            ]
        raise HostABIError("host_chamar(): tipo de valor não suportado pelo ABI")

    def call(self, capability: Any, arguments: Any) -> Any:
        if self.calls >= self.max_calls:
            raise HostABIError("host_chamar(): limite de chamadas por execução excedido")
        if not isinstance(capability, str) or capability not in _HOST_FUNCTIONS:
            raise HostABIError(f"host_chamar(): capacidade ABI v1 desconhecida: {capability!r}")
        if not isinstance(arguments, list):
            raise HostABIError("host_chamar(): segundo argumento precisa ser uma lista")
        if len(arguments) > HOST_MAX_ARGUMENTS:
            raise HostABIError(f"host_chamar(): máximo de {HOST_MAX_ARGUMENTS} argumentos")
        normalized = self._normalize(
            arguments,
            allow_nonfinite=capability == HOST_ABI_PREFIX + "math.is_finite",
        )
        self.calls += 1
        try:
            result = _HOST_FUNCTIONS[capability](normalized)
            return self._normalize(result)
        except HostABIError:
            raise
        except (ArithmeticError, OverflowError, TypeError, ValueError, statistics.StatisticsError) as exc:
            raise HostABIError(f"{capability}: {exc}") from exc
