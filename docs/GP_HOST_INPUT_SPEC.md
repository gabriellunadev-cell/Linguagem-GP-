# GP Host Input — contrato 0.1

**Estado:** rascunho experimental, GP 0.8.36.

## Finalidade

Permitir que o host entregue um texto ao programa GP sem interpolar esse texto no código-fonte do programa temporário, sem variáveis de ambiente implícitas e sem conceder operações de leitura arbitrária do sistema de arquivos ao runtime.

## Intrínseco

entrada_fonte() é uma chamada nativa reservada:

- Não recebe argumentos.
- Retorna texto.
- Retorna somente a fonte que o host forneceu explicitamente para aquela execução.
- Falha em tempo de execução quando o host não forneceu uma fonte.
- A chamada não abre arquivos, não consulta variáveis de ambiente e não permite escolher caminhos.

A análise semântica rejeita qualquer argumento. O frontend GP e o bootstrap Python atribuem retorno texto.

## Limites e validade

- Limite máximo: 16 MiB em bytes UTF-8.
- A entrada precisa ser UTF-8 válido.
- A VM C rejeita bytes NUL na fonte recebida.
- A VM Python exige texto que possa ser codificado em UTF-8 estrito.
- A entrada é vinculada a uma única execução e é descartada ao final.
- Não existe persistência automática da entrada entre execuções.

## APIs do host

Python:

GPVirtualMachine.run_bytes(bytecode, host_source=texto)

CLI Python:

    gp-vm arquivo.gbc --source-input fonte.txt

VM nativa C:

    gpvm-native arquivo.gbc --source-input fonte.txt

A abertura do arquivo ocorre no processo/CLI host antes da execução do bytecode. O programa GP recebe somente o conteúdo textual pela chamada fixa entrada_fonte() e não recebe o caminho.

## Uso no compilador auto-hospedado

O runner do frontend GP declara texto gp_selfhosted_fonte = entrada_fonte(). O Python prepara e compila o runner, mas entrega o código-fonte-alvo como parâmetro de execução da VM. A fonte-alvo deixa de ser serializada como literal dentro do runner temporário.

A expansão de módulos locais, quando necessária, continua sendo feita pelo carregador do host antes da entrada no frontend GP. Isso não concede acesso ao filesystem ao programa GP.

## Limitações atuais

- Existe um único canal textual nomeado implicitamente (entrada_fonte); não há mapa genérico de entradas, stdin interativo ou acesso a arquivos.
- O compilador continua usando Python para preparar e compilar o runner temporário.
- O runner completo do frontend GP já pode ser executado pela VM C via opção experimental runner_backend=native.
- O bytecode do runner é gerado uma vez em artifacts/bootstrap/gp_frontend_runner.gbc, com manifesto que vincula hashes das fontes geradoras; é reutilizado até que alguma fonte de entrada mude.
- A geração inicial/atualização do artefato ainda usa compile_source() do bootstrap Python. A prova de bootstrap em dois estágios continua pendente.
- Este contrato é experimental e ainda não é parte de uma especificação congelada da linguagem GP.


## Estado no ciclo 0.8.36

O runner completo do frontend GP pode ser executado pela VM C usando o artefato GGPC v2 versionado. A geração inicial desse artefato ainda é feita pelo bootstrap Python. A prova N -> N+1 -> N+2 não foi concluída; portanto, a linguagem não é declarada integralmente auto-hospedada.
