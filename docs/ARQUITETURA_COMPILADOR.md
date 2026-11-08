# Arquitetura do compilador GP — Core 0.4

## Pipeline de bytecode

1. Lexer e parser do bootstrap.
2. Conversão para AST formal.
3. Expansão de módulos locais de funções e resolução de namespace.
4. Análise semântica: assinaturas, tipos, escopos, construtores e campos.
5. Lowering para instruções IR.
6. Serialização em contêiner binário GP v2.
7. Execução pela VM de referência Python.

## Bytecode GP v2

Cabeçalho big-endian:
- Assinatura: `GGPC`
- Versão: uint16 (2)
- Tamanho descomprimido: uint32
- CRC32 do payload descomprimido: uint32
- Payload: JSON UTF-8 da IR comprimido com zlib

O decodificador ainda aceita o contêiner JSON experimental v1. A camada de IR é deliberadamente legível nesta fase de desenvolvimento.

## Instruções implementadas

- Valores e variáveis: CONST, LOAD, DECLARE, STORE, POP
- Aritmética e lógica: NEG, NOT, ADD, SUB, MUL, DIV, MOD, EQ, NE, GT, LT, GE, LE, AND, OR
- Saída: PRINT
- Controle: JUMP, JUMP_IF_FALSE, CALL, RETURN
- Arrays: BUILD_ARRAY, MAKE_TYPED_ARRAY, GET_INDEX, SET_INDEX
- Estruturas: BUILD_STRUCT, GET_FIELD, SET_FIELD

## Backend nativo experimental

O comando `gpn` converte AST GP em C e invoca Clang para produzir um executável nativo. É um backend AOT de subconjunto, não um interpretador do bytecode GP. Atualmente aceita tipos básicos, funções, expressões, saída, condicionais e laços. Não aceita arrays, estruturas, indexação, funções de coleção nem todos os recursos do bootstrap.

## Segurança e limites

- O decodificador verifica assinatura, versão, tamanho e CRC32.
- O tamanho máximo do payload descomprimido é limitado.
- A VM tem limite configurável de instruções.
- A VM valida valores tipados, parâmetros, retornos, campos e índices.
- CRC32 não fornece autenticidade criptográfica.
- O bytecode não é sandbox; não execute artefatos desconhecidos como código confiável.
- A VM principal ainda roda sobre Python. O backend nativo é parcial e não representa o runtime definitivo.
