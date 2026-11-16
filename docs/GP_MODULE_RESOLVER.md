# Resolução de módulos GP — integração do grafo na linguagem

linguagem/resolver_modulos_gp.gp é o resolvedor de produção usado pelo compilador comum e pelo backend auto-hospedado via gpcompiler/source_modules.py. No caminho nativo, a resolução é executada pelo runner GP pré-compilado na VM C; não há chamada a gp_compile.compile_source para recompilar o resolvedor a cada projeto.

## Caminho nativo

1. O host lê os arquivos locais com os limites e verificações de segurança descritos abaixo.
2. O host prepara IDs opacos, arestas, aliases e raízes a partir das declarações usar.
3. O runner GP pré-compilado (validado pelo manifesto e SHA-256) recebe o código do resolvedor e os dados do grafo como entrada explícita.
4. O frontend GP produz GP-IR canônico; o encoder C valida e transforma esse IR em bytecode; a VM C executa o resolvedor.
5. No compilador de referência, `ast_only=True` devolve a fonte original intacta depois da validação do grafo. O parser cria nós `import` na AST; `gpcompiler/modules.py` analisa os módulos como AST, resolve aliases e transforma chamadas qualificadas em símbolos de função antes da análise semântica e do lowering. Não há edição de texto-fonte nesse caminho.
6. A rota auto-hospedada/CLI de compatibilidade ainda utiliza a expansão textual anterior antes de executar o frontend GP; sua migração para o mesmo linker AST permanece pendente.

O limite de instruções padrão do resolvedor nativo é 5.000.000 e pode ser ajustado por GP_MODULE_RESOLVER_MAX_STEPS, limitado a 100.000.000. GP_NATIVE_VM pode selecionar explicitamente o executável C. Se essa variável ou o argumento native_vm forem definidos para um caminho inválido no modo nativo, o build falha fechado; ele não troca silenciosamente para a VM Python. O compilador de referência (compile_source) e a construção do seed selecionam explicitamente prefer_native=False e usam a VM Python como oráculo. Essa separação é necessária para evitar que a construção do próprio runner tente carregar o artefato que está sendo regenerado.

## Responsabilidades da fronteira de host

A fronteira Python continua responsável por descobrir e abrir arquivos locais com segurança. Ela canonicaliza caminhos, rejeita symlink loops e arquivos não regulares, limita cada arquivo a 4 MiB e o grafo a 16 MiB, valida UTF-8 e registra cada instância de namespace. A GP recebe IDs opacos e arestas, então decide:

- validação dos tamanhos das listas e aliases duplicados por origem;
- DFS sobre dependências, detecção de ciclos e limite de profundidade 32;
- deduplicação dos nós visitados;
- ordem topológica pós-ordem (dependências antes do importador).

Após a ordem GP ser devolvida, instâncias repetidas do mesmo arquivo mantêm IDs próprios para aliases independentes. Na rota `ast_only`, o parser mantém cada importação como `ASTNode(kind="import")`; o linker AST produz declarações de função com símbolos qualificados e reescreve somente nós de chamada. O GP-IR v1 resultante usa instruções `CALL` contra esses símbolos, sem adicionar opcode novo nem alterar o contêiner GGPC v2. A rota auto-hospedada antiga ainda remove linhas `usar` e transforma aliases no texto-fonte.

## Verificação

As regressões cobrem o resolvedor GP, ciclos, aliases e limites de filesystem, além da execução modular nas VMs de referência e C. O novo teste `test_reference_backend_links_modules_from_ast_without_source_rewrites` bloqueia `_apply_source_edits` e `_rename_module_calls`, inclui cabeçalho `programa`, valida que o resolvedor de grafo foi chamado e executa a aplicação com saída `20`. O conjunto direcionado de cinco casos passou.

## Linker AST e grafo formal de módulos

`gpcompiler/modules.py` agora constrói um `ModuleLinkPlan` a partir da AST original. Cada importação cria uma unidade distinta com ID, namespace, módulo pai, alias e exports; as arestas registram importador, importado, alias e caminho declarado. O linker gera uma ordem pós-ordem (dependências antes do importador) e resolve chamadas qualificadas e internas reescrevendo apenas nós AST.

O contrato tipado `GP-MODULE-GRAPH v1`, em `gpcompiler/module_graph.py`, é independente do GP-IR. Ele possui envelope estrito, unidades, arestas, exports e ordem de dependência; inclui validação estrutural e fingerprint SHA-256 determinístico. Importar o mesmo arquivo sob aliases diferentes mantém instâncias, namespaces e símbolos separados. Aliases duplicados, unidades órfãs, dependências fora de ordem, exports inválidos e colisões de namespace são rejeitados.

Os limites continuam sendo: 128 instâncias importadas, profundidade 32, 4 MiB por arquivo, 16 MiB por grafo e somente arquivos regulares UTF-8. O linker verifica os limites durante a leitura, não apenas pelo tamanho declarado. O resolvedor GP segue responsável por ordem/ciclos na fronteira de compilação; o `ModuleLinkPlan` formaliza a ligação dos símbolos na AST.

A compatibilidade permanece deliberada: o resultado ainda é reduzido a funções com nomes qualificados no GP-IR v1 e usa `CALL` existente. O formato `GP-MODULE-GRAPH v1` não é inserido no GGPC v2 nem altera o schema estrito GP-IR v1. Uma futura tabela de módulos no runtime exige uma evolução versionada do IR e testes diferenciais Python/C.

## Limites restantes

A rota de referência `compile_source` usa o linker AST e o contrato `GP-MODULE-GRAPH v1`. Os testes incluem importação aninhada, chamada interna, dois aliases para o mesmo arquivo e colisão de namespaces; o teste de integração executa duas instâncias isoladas e obtém saída `14`. O parser auto-hospedado reconhece `usar "arquivo.gp" como alias` e preserva o nó `IMPORT`, mas a rota auto-hospedada/CLI de produção ainda pré-expande imports textualmente. Se essa pré-expansão for contornada, a semântica GP rejeita o import não resolvido e o gerador GP-IR também falha fechado. Portanto, o linker nativo escrito em GP ainda não está concluído; a migração do frontend auto-hospedado e a execução da mesma tabela de módulos na VM C continuam pendentes.


## Bootstrap sem recursão

Durante a regeneração do seed, o compilador de referência precisa resolver o import do lexer antes de existir um runner válido com o novo hash. Por isso compile_source e a montagem inicial de _selfhosted_runner_source selecionam explicitamente o resolvedor Python de referência. Depois que o runner está construído, o caminho nativo passa a usar o artefato verificado, o frontend GP, o encoder C e a VM C. O argumento native_vm é propagado até o resolvedor, de modo que o runner e o executor do grafo usam o mesmo binário C configurado.
