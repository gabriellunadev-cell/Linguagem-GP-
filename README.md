# GP — Gabriel Programming

> GP 0.8.52 validada no Termux/Android ARM64: 245 testes (238 da linguagem + 7 do GP Bridge), corpus diferencial 6/6, fuzz 64 sem divergências e bootstrap N→N+1→N+2 reproduzível (N+1 == N+2, SHA-256 registrado). A biblioteca inicial inclui `unir_textos(lista texto)` e serialização GP-IR em lote. A autohospedagem integral ainda é um objetivo, não um recurso concluído. Consulte ENGINEERING_STATUS.md e docs/RELEASE_CRITERIA_1.0.0.md.

Linguagem proprietária do projeto Gabriel Luna, com prioridade de desenvolvimento e execução no Android ARM64.

## Estado de engenharia

O CLI separa a VM que executa o frontend auto-hospedado (`--runner-vm`) da VM que executa o programa compilado (`--run-vm`). O modo nativo pode usar a VM C para o runner, o encoder GGPC v2 e a execução do alvo. A fonte do runner e o GP-IR do encoder são transmitidos por stdin com limites explícitos, sem arquivos temporários de texto. A orquestração, a resolução de módulos e a geração inicial do artefato bootstrap ainda têm dependências Python; a autohospedagem integral não foi concluída.

## Especificações e estabilidade

- [GP-IR v1](docs/GP_IR_SPEC.md): formato intermediário, validação e versionamento independente.
- [Bytecode v2](docs/BYTECODE_V2_SPEC.md): contêiner binário e envelope.
- [Critérios da versão 1.0.0](docs/RELEASE_CRITERIA_1.0.0.md): requisitos verificáveis para estabilização e release.
- [Plano de autossuficiência](docs/SELF_HOSTING.md): diagnóstico e etapas para eliminar a dependência de Python do toolchain.

A GP permanece em versão 0.x enquanto os portões de estabilidade do documento 1.0.0 não forem satisfeitos.
- [GP Host Input](docs/GP_HOST_INPUT_SPEC.md): entrada textual explícita fornecida pelo host.
- [Biblioteca padrão](docs/GP_STANDARD_LIBRARY.md): contratos iniciais, incluindo `unir_textos`.

## Estado atual

**GP Core 0.4 + toolchain nativo experimental (ciclo 0.8.52: 238 testes aprovados; `unir_textos` e serialização em lote implementados; prova de bootstrap otimizada em validação; autohospedagem integral ainda pendente).**

Existem três caminhos no projeto:

- `gp.py`: interpretador bootstrap da linguagem.
- `gpc` / `gpvm`: compilador de bytecode e VM de referência Python.
- `gpc --self-hosted`: backend experimental que usa o lexer, parser, analisador semântico e gerador de IR escritos em GP para compilar um subconjunto da linguagem.
- `gpn`: backend experimental GP → C → Clang, para gerar executáveis ARM64 no próprio Termux.

### Recursos implementados no bootstrap

- Lexer e parser próprios.
- Tipos `numero`, `texto`, `logico` e `lista`.
- Funções, parâmetros, retorno, recursividade e escopos.
- Condicionais, laços, arrays, estruturas e módulos locais.
- Biblioteca padrão inicial, incluindo `unir_textos(lista texto)` para montagem eficiente de texto.

### Recursos implementados no compilador de bytecode 0.4

- AST formal.
- Análise semântica de funções, escopos, tipos básicos e estruturas.
- Construção de estruturas, validação, leitura e alteração de campos.
- Módulos locais de funções com alias e namespace.
- IR e VM de pilha com chamadas, recursividade e controle de fluxo.
- Arrays tipados e operações de coleção.
- Contêiner binário GP v2 comprimido com assinatura, versão, tamanho e CRC32.
- Loaders Python/C validam destinos absolutos e operandos de contagem como inteiros JSON reais; versões externas/internas precisam coincidir.
- Os dois loaders validam schemas e tipos por opcode, limites de payload/JSON, duplicidade de chaves, escapes e stream zlib exato. O contrato documentado está em docs/BYTECODE_V2_SPEC.md (rascunho 0.7, não congelado).
- Compatibilidade com bytecode JSON experimental v1 permanece no decoder Python; o formato binário v2 continua experimental e ainda requer especificação formal e validação estrutural completa por opcode.
- Compatibilidade de leitura com bytecode JSON experimental v1.
- Limite configurável de instruções na VM.

### Backend auto-hospedado experimental

O modo --self-hosted executa o frontend escrito em GP para a fonte alvo e recebe um documento JSON estruturado de registros do IR. Cada ponto de lowering cria diretamente registros da estrutura `InstrucaoIR_GP`; instruções, saltos, constantes, funções e metadados de estruturas são mantidos em listas tipadas, sem montar linhas intermediárias `OPCODE|campo`. Validação, resolução de rótulos e serialização JSON trabalham sobre os campos tipados. Números, contagens e destinos são emitidos como números JSON, constantes lógicas como booleanos, nulo como null e literais de texto como strings JSON. O leitor do envelope textual legado permanece disponível, isolado para compatibilidade. O runner que hospeda o frontend é gerado inicialmente pelo bootstrap Python e armazenado em GGPC v2 com manifesto e hash. O CLI permite executar esse runner na VM C com `--runner-vm native` (a VM Python permanece como padrão). Nesse caminho, o frontend GP emite GP-IR JSON bruto e o encoder C valida e codifica diretamente; as APIs Python de compatibilidade continuam convertendo documentos em IRProgram/IRFunction. A expansão de módulos e a orquestração ainda dependem do host Python. Portanto, trata-se de auto-hospedagem parcial, não de um compilador totalmente independente.

O backend auto-hospedado já cobre declarações escalares e de estruturas, construtores posicionais, leitura/atribuição de campos (inclusive encadeados), estruturas aninhadas, parâmetros de função com estruturas, arrays tipados, listas de estruturas, listas em campos de estruturas, parâmetros e retornos lista<T>, indexação e builtins de coleção. Também conecta mostrar, se/senao, enquanto, para, funções, chamadas, retornos, quebrar e continuar. Imports locais de módulos de funções com alias, inclusive imports aninhados, são suportados: os dois compiladores expandem o grafo, preservam namespaces hierárquicos e aplicam limites por módulo/grafo. Estruturas exportadas, dependências externas e recursos avançados da biblioteca padrão ainda não estão conectados ao backend auto-hospedado.

## Fixtures de bytecode v2

O diretório tests/fixtures/bytecode_v2 mantém seis binários dourados e suas fontes GP. O test runner carrega esses mesmos arquivos nas VMs Python e C ARM64, verifica SHA-256 e compara a saída. Uma fixture de catálogo cobre os 32 opcodes reconhecidos; uma matriz determinística aplica 66 mutações estruturais e outra aplica 48 flips de bit com seed fixo 0x47505632. Ambos os loaders devem rejeitar todos os casos. Consulte docs/BYTECODE_V2_SPEC.md para o rascunho de formato e docs/BYTECODE_V2_SPEC.md, seção 8, para a corpus. Os binários e a especificação permanecem experimentais.

Executar o harness diferencial limitado:

    make fuzz-bytecode FUZZ_ITERATIONS=64 FUZZ_SEED=0x47505632 FUZZ_TIMEOUT=2 FUZZ_REPORT=build/fuzz-reports/latest.json

O harness compara os loaders/VMs Python e C em mutações válidas e inválidas; limites e interpretação dos resultados estão em docs/BYTECODE_V2_SPEC.md, seção 11. Este smoke fuzzing não substitui fuzzing guiado por cobertura.

## Backend nativo experimental

O comando `gpn` converte uma parte da linguagem GP para C e usa o Clang do Termux para gerar um executável Android ARM64. O subconjunto atual inclui tipos básicos, funções, expressões, saída, condicionais e laços. Arrays, estruturas, indexação e funções de coleção ainda não estão implementados nesse backend.

## Validar o projeto

Executar a sequência reproduzível de checks, regeneração do corpus, suíte de testes, fuzzing, hashes e verificação de diff:

    make validate

Os componentes também podem ser executados separadamente com make check, make test, make differential-corpus e make fuzz-bytecode.

## Integração com o GP Programinha

O editor visual fica em um repositório separado: [GP Programinha](https://github.com/gabriellunadev-cell/Gp-ai-programacao). Para compilar e executar código GP a partir dele, inicie o serviço local neste repositório:

    cd ~/gabriel-luna-gp
    make bridge

O serviço fica restrito a 127.0.0.1:8765, usa a CLI oficial do compilador, cria um workspace temporário por chamada e não expõe shell ou leitura arbitrária de arquivos. A API, os limites e os controles de CORS estão documentados em [docs/GP_BRIDGE.md](docs/GP_BRIDGE.md). O contrato é validado por tests/test_ide_bridge.py e incluído em make validate.

A biblioteca padrão é mantida neste mesmo repositório, com contratos em [docs/GP_STANDARD_LIBRARY.md](docs/GP_STANDARD_LIBRARY.md) e índice em [biblioteca/README.md](biblioteca/README.md).

## Executar no Termux

    cd ~/gabriel-luna-gp

Interpretar o exemplo completo do bootstrap:

    ./bin/gp exemplos/recursos_02.gp

Compilar e executar bytecode pelo bootstrap:

    ./bin/gpc exemplos/bytecode_basico.gp --run

Exercitar a biblioteca padrão inicial (`tamanho`, `adicionar`, `remover` e `unir_textos`) nos três runtimes:

    ./bin/gp exemplos/biblioteca_padrao.gp
    ./bin/gpc exemplos/biblioteca_padrao.gp --run
    ./bin/gpc exemplos/biblioteca_padrao.gp --self-hosted --runner-vm native --run --run-vm native

Contrato e matriz de disponibilidade: [docs/GP_STANDARD_LIBRARY.md](docs/GP_STANDARD_LIBRARY.md).

Compilar e executar pelo backend auto-hospedado experimental:

    ./bin/gpc exemplos/autohospedado_funcoes.gp --self-hosted --dump-ir --run

Executar o frontend auto-hospedado, o encoder e o programa final usando a VM C nativa:

    make native-vm
    ./bin/gpc exemplos/autohospedado_funcoes.gp --self-hosted --runner-vm native --run --run-vm native

O parâmetro `--runner-vm native` escolhe a VM C para executar o compilador escrito em GP e ativa o encoder C por padrão. `--run-vm native` escolhe separadamente a VM C para executar o bytecode do programa compilado. Os parâmetros `--run-max-steps` e `--run-timeout-seconds` limitam a execução do programa final. O padrão continua sendo a VM Python para preservar compatibilidade.

Compilar e executar arrays tipados e indexação pelo backend auto-hospedado:

    ./bin/gpc exemplos/autohospedado_arrays.gp --self-hosted --dump-ir --run

Compilar e executar quebrar/continuar, incluindo laços aninhados:

    ./bin/gpc exemplos/autohospedado_lacos.gp --self-hosted --dump-ir --run

Compilar estruturas, construtores, campos e parâmetros de função estruturados:

    ./bin/gpc exemplos/autohospedado_estruturas.gp --self-hosted --dump-ir --run

Compilar funções que recebem e retornam listas tipadas:

    ./bin/gpc exemplos/autohospedado_listas_funcoes.gp --self-hosted --dump-ir --run

Compilar funções e coleções de estruturas:

    ./bin/gpc exemplos/autohospedado_listas_estruturas.gp --self-hosted --dump-ir --run

Compilar campos que armazenam listas de estruturas:

    ./bin/gpc exemplos/autohospedado_campos_listas.gp --self-hosted --dump-ir --run

Combinar listas de estruturas, indexação e controle de laços:

    ./bin/gpc exemplos/autohospedado_listas_em_lacos.gp --self-hosted --dump-ir --run

Executar um arquivo de bytecode já compilado:

    ./bin/gpvm exemplos/bytecode_arrays.gbc

Compilar um programa que importa módulo local:

    ./bin/gpc exemplos/modulos/aplicacao.gp --run

Gerar e executar binário nativo ARM64:

    ./bin/gpn exemplos/native_basico.gp -o build/gp-native-demo --run

Executar todos os testes:

    make test

Verificar sintaxe Python:

    make check

## Exemplo — funções

    funcao fatorial(numero n) -> numero {
        se (n <= 1) {
            retornar 1
        }
        retornar n * fatorial(n - 1)
    }

    mostrar("Fatorial:", fatorial(5))

Saída:

    Fatorial: 120

## Exemplo — estruturas

    estrutura Pessoa {
        texto nome;
        numero idade;
    }

    Pessoa pessoa = Pessoa{nome: "Ada", idade: 37}
    pessoa.idade = 38
    mostrar(pessoa.nome, pessoa.idade)

## Exemplo — módulos

Arquivo `matematica.gp`:

    funcao somar(numero a, numero b) -> numero {
        retornar a + b
    }

Programa principal:

    usar "matematica.gp" como math
    mostrar(math.somar(19, 23))

Módulos do Core 0.4 devem ser arquivos locais e exportar funções. O caminho é relativo ao arquivo que importa. Imports aninhados são suportados com limites de profundidade 32, até 128 módulos, 4 MiB por arquivo e 16 MiB por grafo; ciclos e aliases duplicados são rejeitados. Dependências externas e exportação de estruturas ainda não estão implementadas.

## Pipeline de bytecode

    Código GP
       |
       v
    Lexer + Parser
       |
       v
    Expansão de módulos locais
       |
       v
    AST formal
       |
       v
    Análise semântica
       |
       v
    IR
       |
       v
    Bytecode binário GP (.gbc)
       |
       v
    GP Virtual Machine (Python de referência)

## Pipeline nativo experimental

    Código GP
       |
       v
    AST + análise semântica
       |
       v
    Backend C
       |
       v
    Clang do Termux
       |
       v
    Executável ELF64 AArch64 para Android

## Formato e segurança

O bytecode v2 é um contêiner binário comprimido em zlib. O cabeçalho contém assinatura, versão, tamanho esperado e CRC32 do conteúdo descomprimido. A IR interna ainda é JSON. CRC32 detecta corrupção acidental, não adulteração maliciosa. O formato não é uma sandbox.

## Limites conhecidos

- A VM de bytecode ainda é implementada em Python. O backend GP→C nativo é apenas um subconjunto experimental, não uma VM GP nativa completa.
- O bytecode binário contém IR JSON comprimida; ainda não é uma codificação compacta direta de opcodes.
- Módulos suportam imports locais aninhados de funções, mas ainda não pacotes, dependências externas ou exportação de estruturas.
- O backend nativo ainda não suporta arrays, estruturas, indexação ou funções de coleção.
- A AST ainda não preserva spans completos de arquivo/linha/coluna para diagnósticos semânticos.
- A VM C possui coletor mark-and-sweep inicial para textos, arrays e estruturas; buffers auxiliares permanecem no alocador rastreado.
- Ainda faltam depurador, formatador, gerenciador de pacotes e suíte extensa de conformidade.
- A linguagem ainda não está congelada para produção nem é auto-hospedada.

O Android é o ambiente principal de desenvolvimento e execução. A VPS permanece opcional e complementar.
