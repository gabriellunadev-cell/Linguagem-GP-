# Plano de autossuficiência — Gabriel Programming

Atualizado em: 2026-11-08
Estado de referência: GP 0.8.51, Android/Termux ARM64.

## Objetivo verificável

A GP será considerada autossuficiente quando o fluxo normal de desenvolvimento — compilar, validar, empacotar, executar, testar e reconstruir o próprio compilador — puder ser conduzido por ferramentas escritas em GP e pelo runtime nativo da GP, sem depender de Python, Node.js ou outro interpretador de linguagem como parte do toolchain.

O sistema operacional, o linker/compilador C usado para produzir o primeiro runtime nativo e bibliotecas de plataforma podem continuar sendo dependências de bootstrap explicitamente documentadas. Isso não é o mesmo que depender de Python para compilar cada programa GP. O objetivo é eliminar dependências ocultas e manter uma cadeia de bootstrap reproduzível.

## Diagnóstico confirmado em 0.8.51

### O que já é GP

- Lexer, parser, análise semântica e geração de GP-IR implementados em fontes GP.
- O frontend auto-hospedado pode compilar fontes GP e emitir GP-IR canônico.
- O runner do frontend pode executar na VM C nativa.
- O encoder GGPC v2 nativo em C valida GP-IR e gera bytecode.
- O bytecode final pode ser executado pela VM C nativa.
- A prova N → N+1 → N+2 passa e os artefatos N+1/N+2 são idênticos.

### O que ainda depende do host Python

1. CLI e orquestração: `gp_compile.py` coordena leitura da fonte, opções, módulos, frontend, encoder, publicação e execução.
2. Bootstrap inicial: `generate_selfhosted_runner_artifact()` chama `compile_source()` do compilador Python para produzir o estágio N.
3. Resolução de módulos: a expansão recursiva de imports é feita em `gp_compile.py` e `gpcompiler/modules.py` antes de o frontend GP receber a fonte.
4. Adaptação e transporte: Python chama a VM C, envia stdin, recolhe GP-IR e coordena o encoder.
5. Ferramentas de engenharia: testes, corpus diferencial, fuzzing e prova de bootstrap são orquestrados por scripts Python.

Portanto, executar o frontend GP na VM C não significa ainda que o toolchain inteiro seja independente de Python.

### Limites atuais da biblioteca/runtime GP

A VM de referência e a VM C expõem hoje um conjunto pequeno de builtins de runtime: `entrada_fonte`, `tamanho`, `adicionar` e `remover`; `mostrar` é tratado pelo próprio pipeline de execução. Ainda não existe uma biblioteca padrão suficiente para o compilador GP gerenciar arquivos, caminhos, módulos, processos, argumentos de CLI, hashes e artefatos por conta própria.

## Arquitetura-alvo

- **GP Core:** sintaxe, tipos, funções, estruturas, coleções, módulos, erros e semântica versionados.
- **GP Runtime:** VM C nativa como implementação de referência de execução no Android ARM64, com contratos equivalentes na VM Python de referência.
- **GP Standard Library:** módulos oficiais para texto/Unicode, coleções, arquivos, caminhos, entrada/saída, argumentos CLI, hashing, tempo e processos. APIs com efeitos externos devem receber capacidades explícitas e limites.
- **GP Module System:** resolução e carregamento de módulos implementados no toolchain GP, com limites contra ciclos, traversal, arquivos excessivos e imports ambíguos.
- **GP Compiler:** frontend, análise, IR, encoder e emissão do bytecode controlados por fontes GP e interfaces estáveis.
- **GP Build Driver:** ferramenta GP que coordena compilação, validação, publicação atômica, execução e relatórios.
- **Bootstrap Seed:** artefato binário mínimo, versionado, com origem, hash e fontes exatas documentadas. O seed é usado para gerar N+1; N+1 gera N+2; os artefatos e hashes devem coincidir. O seed não pode ser regenerado silenciosamente por Python durante o fluxo normal.
- **Host de plataforma:** sistema operacional, ABI, linker e runtime C mínimo. A fronteira de plataforma deve ser pequena, explícita e testada.

## Sequência de execução

### Fase 1 — congelar e auditar o bootstrap
- [ ] Definir o contrato do artefato seed e separar seus hashes das dependências Python históricas.
- [ ] Registrar a fonte GP exata que originou o seed, versão do formato, hash do bytecode e toolchain de origem.
- [ ] Fazer a prova de bootstrap consumir um seed fixo sem chamar `compile_source()`.
- [ ] Rejeitar seed ausente, corrompido ou incompatível; nunca regenerar silenciosamente por fallback Python.

### Fase 2 — construir a biblioteca padrão mínima
- [ ] Definir módulos e contratos de texto/Unicode, coleções, erros e conversões.
- [ ] Implementar I/O e arquivos com capacidades explícitas, caminhos confinados quando aplicável, limites de tamanho e erros previsíveis.
- [ ] Implementar argumentos CLI, caminhos, hashing e publicação atômica.
- [ ] Manter testes diferenciais entre VM Python e VM C.

### Fase 3 — transferir o sistema de módulos
- [ ] Mover resolução, grafo de dependências e namespaces para um módulo/toolchain GP.
- [ ] Preservar limites atuais: profundidade 32, 128 módulos, 4 MiB por arquivo e 16 MiB por grafo, ajustando apenas com evidência.
- [ ] Cobrir ciclos, links simbólicos, traversal, duplicatas, permissões e arquivos especiais.

### Fase 4 — construir o driver do compilador em GP
- [ ] Criar CLI GP para compilar, inspecionar IR, executar, testar e publicar bytecode.
- [ ] Substituir a orquestração Python por chamadas internas ao runtime/encoder nativo.
- [ ] Preservar diagnósticos, limites, timeouts, publicação atômica e códigos de saída.
- [ ] Manter Python somente como oráculo de testes durante a transição, não como dependência de produção.

### Fase 5 — bootstrap e distribuição independentes
- [ ] N (seed) gera N+1; N+1 gera N+2; N+1 e N+2 são idênticos.
- [ ] Repetir o bootstrap em instalação limpa Android ARM64 sem Python instalado.
- [ ] Repetir em outra plataforma suportada antes de declarar portabilidade.
- [ ] Documentar como reconstruir o seed e como verificar a cadeia de confiança.

## Critérios para declarar independência

A afirmação "GP compila a si mesma sem Python" só será permitida quando o compilador GP, iniciado pelo seed documentado e executado no runtime nativo, reconstruir seu próprio toolchain e compilar projetos reais em ambiente limpo sem invocar Python. A VM Python poderá continuar existindo como referência de testes, mas não poderá estar no caminho de produção.

A versão 1.0.0 ainda exige os demais portões em `RELEASE_CRITERIA_1.0.0.md`. Autossuficiência não será inferida apenas de um bootstrap parcial ou de uma VM nativa.

## Próximo marco técnico

O próximo marco é a Fase 1: congelar um seed verificável e provar que o ciclo N → N+1 → N+2 parte dele sem executar o compilador Python. Só depois avançar para APIs de sistema e o driver GP, com testes pequenos e reversíveis em cada etapa.

## Medição de desempenho do bootstrap — 2026-11-08

A primeira tentativa estrita não concluiu dentro da janela operacional. O processo foi interrompido sem alterar o seed ou descartar código. A investigação reproduziu o custo com limites controlados:

- Fonte expandida do frontend: 136.757 caracteres e 2.823 linhas.
- VM Python de referência: ao compilar essa própria fonte com limite de 10.000.000 instruções, atingiu o limite em 41,57 s. Portanto, a carga atual exige mais de 10 milhões de instruções GP.
- VM C nativa: com limite de 1.000.000 de instruções, encerrou corretamente pelo limite e reportou pico de 14,57 MiB de memória gerenciada, 184.097 objetos gerenciados alocados e 0 ciclos de GC.
- VM C nativa: com limite de 10.000.000 e timeout de 90 s, não concluiu a etapa N → N+1 dentro do timeout.

Esses resultados indicam custo elevado do próprio frontend auto-hospedado, e não um bloqueio do canal de execução. A inspeção encontrou dois candidatos a otimização que ainda precisam de profiling isolado: construção de lexemas por concatenação repetida de caracteres no lexer e buscas lineares repetidas nas tabelas de símbolos da análise semântica. Não tratar esses candidatos como causa comprovada até medir cada um separadamente.

### Próxima ação de engenharia

1. Criar benchmarks isolados para lexer, parser, análise semântica e geração de IR, com contagem de instruções e alocações.
2. Otimizar primeiro o caminho de lexemas e a consulta de símbolos, preservando semântica e diagnósticos.
3. Rodar corpus diferencial Python/C e suíte de regressão após cada mudança.
4. Só então repetir N → N+1 → N+2 com orçamento de passos e timeout documentados.

### Baseline nativa detalhada — 2026-11-08

A medição isolada da VM C foi registrada em [`PERFORMANCE_BASELINE_2026-11-08.md`](PERFORMANCE_BASELINE_2026-11-08.md). O probe de parser executou 878.748 instruções em mediana de 1,1885 s, com heap GP pico de 11.355.760 B. O frontend completo, com 136.757 caracteres, atingiu o limite de 1.000.000 passos em 2,9168 s, após alocar 184.097 objetos e alcançar 14,57 MiB de heap contabilizado; os ensaios com 3.000.000 e 10.000.000 passos excederam os timeouts definidos. Isso reforça a necessidade de profiling por fase antes de qualquer alteração no lexer ou na tabela de símbolos.
