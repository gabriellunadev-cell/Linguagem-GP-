# GP — baseline de desempenho da VM C (2026-11-08)

## Escopo

Medição feita no tablet Android/Termux ARM64, usando exclusivamente a VM C já compilada (`build/gpvm-native`) para executar os bytecodes. Nenhum fonte do lexer, parser, análise semântica ou compilador foi modificado durante esta etapa. Python foi usado somente como harness para alimentar a fonte expandida pela entrada padrão e coletar tempo/relatórios; não executou o bytecode nem compilou a fonte medida.

O binário nativo existente foi preservado; não foi recompilado nesta etapa. As medições são uma linha de base local, não uma comparação entre dispositivos.

## Resultados

| Caso | Bytecode / entrada | Execução | Instruções GP | Heap GP pico | RSS de processo pico |
|---|---:|---:|---:|---:|---:|
| Aritmética simples | 225 B | mediana 0,0442 s (5 execuções) | 14 | 36.443 B | 14.204.928 B |
| Probe do parser | 25.938 B | mediana 1,1885 s (3 execuções) | 878.748 | 11.355.760 B | 20.787.200–20.889.600 B |
| Frontend completo — seed N | fonte expandida 136.757 caracteres / 2.823 linhas | timeout em 25 s com teto de 10.000.000 passos | não concluído | relatório final indisponível por timeout | relatório final indisponível por timeout |

### Frontend completo — limites controlados

- Com `--max-steps 1.000.000`, a VM C encerrou pelo limite em 2,9168 s.
- Nesse ponto: 184.097 objetos gerenciados alocados; 184.048 strings; payload de strings de 559.336 B; heap contabilizado no alocador de 15.282.204 B (14,57 MiB); RSS de processo atual de 24.457.216 B e pico de 35.708.928 B.
- A VM registrou zero ciclos de GC. O heap vivo gerenciado era 12.343.112 B.
- Com teto de 3.000.000 passos, a execução excedeu o timeout de 15 s. Com teto de 10.000.000 passos, excedeu o timeout de 25 s.
- O timeout não fornece uma contagem final de instruções nem um relatório de memória de encerramento; não extrapolar esses valores.

## Interpretação

1. O probe do parser conclui 878.748 instruções em aproximadamente 1,19 s e usa cerca de 10,83 MiB de heap GP no pico.
2. O frontend completo tem custo muito superior: já aloca 184 mil objetos antes de atingir 1 milhão de passos, com strings representando a maior parte das alocações gerenciadas observadas.
3. Os dados justificam perfilar concatenação/construção de lexemas e consultas de símbolos, mas ainda não provam que esses pontos sejam os únicos gargalos. A próxima otimização deve ser precedida por benchmarks por fase e testes de equivalência.
4. A prova estrita N → N+1 → N+2 continua **não aprovada** nesta tentativa. Resultados históricos de bootstrap reprodutível não devem ser confundidos com a prova estrita atual, que exige consumir o seed fixo sem regeneração Python.

## Método e reprodutibilidade

- VM: `build/gpvm-native`, executando bytecodes já existentes.
- Métrica de tempo: `time.perf_counter()` ao redor de cada processo nativo.
- Memória: `GPVM_MEMORY_REPORT`, com heap do alocador, heap gerenciado e RSS atual/pico reportados pela própria VM.
- Aritmética: `tests/fixtures/bytecode_v2/arithmetic.gbc`, cinco execuções.
- Probe: `build/probe_parser_direct.gbc`, três execuções.
- Seed: `artifacts/bootstrap/gp_frontend_runner.gbc`, fonte expandida fornecida via `--source-input -`.
- Relatórios brutos locais: `build/perf-baseline/` (artefatos de medição, não necessários ao runtime).

## Próximos passos

1. Separar medições do lexer, parser, análise semântica e geração de GP-IR, mantendo a execução dos programas de benchmark na VM C.
2. Medir quantidade de concatenações, objetos/string allocations e custo de lookup por fase.
3. Implementar otimizações pequenas e reversíveis, com testes de regressão e comparação diferencial.
4. Repetir a linha de base após cada otimização e somente então reexecutar a prova estrita de bootstrap.

## Meta de versão

A meta de produto passa a ser **GP 1.1**. A versão 1.0.0 permanece como portão intermediário obrigatório de estabilidade, qualidade, segurança e distribuição; não será pulada para acelerar o número da versão.
