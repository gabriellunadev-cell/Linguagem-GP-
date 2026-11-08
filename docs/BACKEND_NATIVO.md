# Backend nativo GP — prévia experimental

## Objetivo

O comando `gpn` faz compilação ahead-of-time (AOT) de um subconjunto GP:

`fonte GP → AST → análise semântica → C → Clang → ELF64 AArch64`

Ele executa o resultado diretamente no Android, sem usar a VM Python durante a execução do binário.

## Requisitos no Termux

- Python 3
- Clang
- linker e bibliotecas de desenvolvimento disponibilizados pelo ambiente Termux

## Uso

    ./bin/gpn exemplos/native_basico.gp -o build/gp-native-demo --run

Para gerar sem executar:

    ./bin/gpn exemplos/native_basico.gp -o build/gp-native-demo

O código C intermediário é salvo ao lado do executável com sufixo `.native.c`. O caminho pode ser alterado com `--emit-c`.

## Subconjunto atual

- Tipos `numero`, `texto` e `logico`.
- Variáveis globais simples com inicializador literal.
- Variáveis locais.
- Funções tipadas e chamadas estáticas.
- Expressões aritméticas, comparações e lógica.
- `mostrar` para valores numéricos, texto e lógico.
- `se/senao`, `enquanto`, `para`, `retornar`, `quebrar` e `continuar`.
- Módulos locais de funções após expansão no front-end.

## Ainda não suportado nesse backend

- Arrays, estruturas, indexação e atribuição em campos.
- `tamanho`, `adicionar` e `remover`.
- Importações aninhadas, pacotes e carregamento dinâmico.
- Concatenação dinâmica de textos e gerenciamento de memória GP.
- Reflexão, closures e recursos avançados de runtime.

Para recursos fora desse subconjunto, use `gpc` para gerar bytecode e `gpvm` para executar pela VM de referência.

## Segurança e portabilidade

O código C gerado é compilado com o Clang instalado no dispositivo. O executável resultante é específico para a ABI/ambiente Android usados na compilação. Não execute arquivos GP ou binários de origem desconhecida como se fossem confiáveis. O backend não é uma sandbox.

## Próximas etapas

Expandir a cobertura semântica e de runtime, introduzir ABI estável, tratar memória e erros de forma padronizada e comparar resultados com a VM Python. A implementação de uma VM nativa GP que carregue diretamente o bytecode continua pendente.
