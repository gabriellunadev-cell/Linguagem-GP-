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
4. Nesta medição Android/Termux ARM64, a prova estrita não foi concluída por limite de passos/timeout. A revalidação posterior no VPS x86_64 está documentada separadamente em `ENGINEERING_STATUS.md`; não misturar esses resultados.

## Método e reprodutibilidade

- VM: `build/gpvm-native`, executando bytecodes já existentes.
- Métrica de tempo: `time.perf_counter()` ao redor de cada processo nativo.
- Memória: `GPVM_MEMORY_REPORT`, com heap do alocador, heap gerenciado e RSS atual/pico reportados pela própria VM.
- Aritmética: `tests/fixtures/bytecode_v2/arithmetic.gbc`, cinco execuções.
- Probe: `build/probe_parser_direct.gbc`, três execuções.
- Seed: `artifacts/bootstrap/gp_frontend_runner.gbc`, fonte expandida fornecida via `--source-input -`.
- Relatórios brutos locais: `build/perf-baseline/` (artefatos de medição, não necessários ao runtime).

## Perfil exploratório na VPS x86_64 — 2026-11-08

Este perfil foi coletado durante a prova N+1→N+2 no VPS, após a implementação do índice esparso UTF-8. Foram 397 amostras de CPU; a distribuição observada foi `execute_code` ~51,05%, `gp_gc_mark_value` ~17,28%, `json_string` ~3,57% e `token_eq` ~2,38%. A função `utf8_decode_one` deixou de aparecer entre os principais consumidores no perfil posterior à otimização.

O perfil sugere que a marcação do coletor de lixo e o loop principal da VM são os próximos alvos de investigação. A amostra é curta e exploratória, não é benchmark estatístico nem prova de aceleração global. Não comparar diretamente estes percentuais ou tempos com o baseline medido no Android ARM64; uma comparação válida exige repetir o mesmo harness e condições na mesma arquitetura/hardware.

## Experimento de limiar do GC na VPS x86_64 — 2026-11-08

Workload sintético de 50.000 iterações, com substituição repetida de listas e concatenação de texto; três execuções por limiar. O limiar é o mínimo adaptativo (`--gc-threshold`), não um limite absoluto de heap.

| Limiar mínimo | Mediana | Ciclos GC | Heap pico | RSS pico |
|---|---:|---:|---:|---:|
| 1 MiB | 0,7425 s | 3 | 10,50 MiB | 20,38 MiB |
| 4 MiB | 0,6390 s | 0 | 32,46 MiB | 37,88 MiB |

Os testes de 8, 16 e 32 MiB não apresentaram vantagem estável de tempo; mantiveram o heap alto por mais tempo. O ganho de ~14% no microbenchmark de 4 MiB não se repetiu de forma convincente na prova completa: N→N+1 fez 1.041 coletas contra 1.053 em 1 MiB (redução de ~1,1%), mas o heap pico subiu para 136,52 MiB e o RSS pico para 176,49 MiB, contra 75,56/92,44 MiB no padrão. O N+1 gerado permaneceu byte a byte idêntico; a medição foi encerrada antes do segundo estágio e não constitui uma prova 4 MiB N→N+1→N+2.

**Decisão:** manter 1 MiB como padrão. O limiar de 4 MiB melhora apenas o microbenchmark curto, mas quase não reduz coletas no frontend completo e consome muito mais memória. A próxima otimização deve atuar no custo da marcação (`gp_gc_mark_value`) e na execução do bytecode, não em adiar coletas de forma ampla.

## Próximos passos

1. Separar medições do lexer, parser, análise semântica e geração de GP-IR, mantendo a execução dos programas de benchmark na VM C.
2. Medir quantidade de concatenações, objetos/string allocations e custo de lookup por fase.
3. Implementar otimizações pequenas e reversíveis, com testes de regressão e comparação diferencial.
4. Repetir a linha de base após cada otimização e somente então reexecutar a prova estrita de bootstrap.

## Meta de versão

A meta de produto passa a ser **GP 1.1**. A versão 1.0.0 permanece como portão intermediário obrigatório de estabilidade, qualidade, segurança e distribuição; não será pulada para acelerar o número da versão.
