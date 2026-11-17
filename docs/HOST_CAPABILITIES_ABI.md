# GP Host Capabilities ABI v1

## Objetivo

O Host ABI é a fronteira estável entre bytecode GP e recursos determinísticos do runtime. Ele permite que a VM Python e a VM C ofereçam as mesmas operações sem fazer o programa depender de Python, sistema operacional, filesystem ou rede.

A chamada é representada pelo builtin GP `host_chamar(identificador, argumentos)`, que é baixado para o `CALL` já existente no GP-IR. Os identificadores são versionados:

```gp
numero raiz = host_chamar("gp.core.v1.math.sqrt", [81])
numero media = host_chamar("gp.core.v1.statistics.mean", [[2, 4, 6, 8]])
numero divisor = host_chamar("gp.core.v1.math.gcd", [18, 24])
mostrar(raiz, media, divisor)
```

Não há mudança no GP-IR v1 nem no contêiner GGPC v2. O contrato é explícito no nome do builtin e no prefixo `gp.core.v1.`. Uma futura mudança incompatível deve usar um novo prefixo ABI, nunca reinterpretar silenciosamente o v1.

## Regras normativas

- ABI version: `1`; prefix: `gp.core.v1.`.
- Cada execução permite no máximo 1.024 chamadas, 16 argumentos por chamada, listas de até 10.000 elementos, profundidade 8 e textos até 1 MiB.
- Valores numéricos comuns devem ser finitos e inteiros devem permanecer no intervalo seguro de ±(2^53 − 1).
- `math.is_finite` é a exceção: aceita número não finito para que o programa possa testá-lo.
- Capacidades são allowlist fechada, determinísticas e sem efeitos colaterais. Identificadores desconhecidos são rejeitados.
- Nenhuma capacidade ABI v1 abre shell, subprocessos, filesystem, rede, imports dinâmicos ou execução de código.
- O orçamento é reiniciado a cada chamada de execução da VM.

## Catálogo v1

| Identificador | Argumentos | Resultado |
| --- | --- | --- |
| `gp.core.v1.math.sqrt` | número | número |
| `gp.core.v1.math.sin`, `cos`, `tan` | número | número |
| `gp.core.v1.math.log` | número[, base] | número |
| `gp.core.v1.math.log10`, `abs`, `floor`, `ceil`, `exp` | número | número |
| `gp.core.v1.math.factorial` | inteiro de 0 a 18 | número |
| `gp.core.v1.math.gcd`, `lcm` | 2 a 16 inteiros | número |
| `gp.core.v1.math.hypot` | 2 a 16 números | número |
| `gp.core.v1.math.is_finite` | número | lógico |
| `gp.core.v1.statistics.mean`, `median` | lista numérica não vazia | número |
| `gp.core.v1.statistics.pvariance`, `pstdev` | lista numérica não vazia | número |
| `gp.core.v1.statistics.variance`, `stdev` | lista numérica com pelo menos 2 itens | número |

## Runtimes

- VM Python: despacho através de `gpcompiler/host_abi.py`.
- VM C: despacho fechado em `gp_host_abi.inc`, sem libpython e sem chamadas externas.
- Frontend auto-hospedado em GP: valida a forma do builtin e gera o mesmo `CALL`.
- GP Bridge: publica versão, limites e catálogo no endpoint `/api/health`.
- Programas que usam somente Host ABI v1 não precisam da flag `--python-interop`.

A extensão `py_chamar` continua separada: continua desligada por padrão, é executada na VM Python de referência e respeita sua própria allowlist. Ela não faz parte do Host ABI e não é suportada pela VM C.

## Compatibilidade e evolução

O ABI v1 preserva o bytecode v2 e usa o namespace reservado do builtin `host_chamar`. Um novo conjunto de operações compatíveis pode ser acrescentado ao catálogo v1; uma alteração incompatível de representação, semântica ou tipos exige um novo prefixo versionado. Runtimes devem rejeitar identificadores que não implementem em vez de executar uma alternativa dinâmica.

## Exemplo com biblioteca

```gp
usar "biblioteca/host.gp" como nativo

numero raiz = nativo.raiz_quadrada(81)
numero divisor = nativo.mdc(18, 24)
numero media = nativo.media([2, 4, 6, 8])
mostrar(raiz, divisor, media)
```
