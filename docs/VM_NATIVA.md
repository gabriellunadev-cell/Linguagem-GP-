# GP Native VM — C/ARM64

## Objetivo

A VM nativa executa diretamente o bytecode GP v2 (.gbc), sem iniciar Python durante a execução do programa.

Fluxo:

fonte .gp → gpc (Python bootstrap) → bytecode GGPC v2 → gpvmn (C/AArch64)

## Execução

    ./bin/gpc exemplos/bytecode_basico.gp -o build/programa.gbc
    ./bin/gpvmn build/programa.gbc

A primeira execução de gpvmn compila gpvm_native.c com Clang e zlib no próprio Termux. Depois, reutiliza o binário até o código C mudar.

Limite configurável:

    ./bin/gpvmn build/programa.gbc --max-steps 500000

Alternativa para compilação manual:

    make native-vm
    ./build/gpvm-native build/programa.gbc

## Formato carregado

- Assinatura binária GGPC
- Versão 2
- Tamanho esperado do payload descomprimido
- CRC32 do payload
- Payload JSON UTF-8 da IR, comprimido em zlib

O runtime verifica assinatura, versão, tamanho, descompressão, CRC32, formato IR e limite de payload antes de começar a executar. A versão atual da VM C exige bytecode v2; a VM Python segue como referência e mantém a leitura do JSON v1 experimental.

## Cobertura implementada

- Constantes, variáveis, tipos básicos e arrays tipados.
- Estruturas GP e acesso/atribuição de campos.
- Indexação de arrays e strings ASCII.
- Operações aritméticas, comparações e lógica.
- Funções, parâmetros, recursividade e namespaces já expandidos pelo compilador.
- Saltos, condicionais, laços, break e continue.
- mostrar, tamanho, adicionar e remover.
- Limite global de instruções e limite de profundidade de chamadas.

## Limites atuais

- A compilação de fonte para bytecode ainda é feita pelo compilador bootstrap Python; somente a execução .gbc é nativa.
- O runtime usa alocação dinâmica simples. Um coletor de lixo/gerenciador de memória formal ainda precisa ser implementado.
- O acesso por índice em texto usa bytes UTF-8; não deve ser usado para indexar texto multibyte até a implementação de índice por ponto de código.
- As mensagens de erro ainda não carregam arquivo, linha e coluna.
- O loader C lê apenas bytecode v2.
- O runtime e o formato permanecem experimentais; não execute bytecode não confiável. CRC32 detecta corrupção acidental, não adulteração maliciosa nem substitui assinatura criptográfica.

## Validação

A suíte compara a saída da VM C e da VM Python em programas com funções recursivas, arrays, estruturas e módulos. Ela também verifica limite de instruções e rejeição de checksum inválido.
