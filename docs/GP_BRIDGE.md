# GP Bridge — serviço local de integração

O GP Bridge expõe a CLI oficial do compilador para o GP Programinha. Ele não implementa uma segunda versão da linguagem: recebe código ou um projeto GP, cria um workspace temporário e invoca `gp_compile.py`.

## Iniciar

No Termux, dentro do repositório da linguagem:

```bash
python3 gp_ide_server.py
```

O serviço fica disponível somente em `http://127.0.0.1:8765`. O servidor não aceita bind em `0.0.0.0`.

No Programinha, use o endereço padrão nas configurações de integração.

## Endpoints

- `GET /api/health`: estado do serviço, versão do compilador, versão da Bridge e limites de projeto.
- `POST /api/compile`: compila um único arquivo sem imports.
- `POST /api/run`: compila e executa um único arquivo sem imports pela VM Python de referência.
- `POST /api/compile-project`: compila o arquivo principal e todos os módulos enviados.
- `POST /api/run-project`: compila e executa o projeto completo pela VM Python de referência.

## Corpo da API de projeto

```json
{
  "entryFile": "app/principal.gp",
  "files": [
    {
      "path": "app/principal.gp",
      "source": "usar \"lib/matematica.gp\" como math\nmostrar(math.somar(19, 23))"
    },
    {
      "path": "app/lib/matematica.gp",
      "source": "funcao somar(numero a, numero b) -> numero {\n    retornar a + b\n}"
    }
  ]
}
```

Os caminhos enviados em `files[].path` são relativos à raiz do projeto. Imports são interpretados em relação ao arquivo que os declara, conforme as regras do compilador GP. Um caminho como `../lib/base.gp` é permitido quando sua resolução permanece dentro da raiz e o arquivo correspondente está presente no projeto.

## Limites e validação

- Corpo HTTP máximo: 20 MiB.
- Até 128 arquivos por projeto.
- Até 4 MiB UTF-8 por arquivo e 16 MiB somados de fontes.
- Timeout de compilação: 30 segundos.
- Timeout de execução: 10 segundos; limite da VM: 1.000.000 de instruções.
- Caminhos absolutos, segmentos de arquivo vazios, `.` e `..` em caminhos enviados, duplicidades e caminhos fora do workspace são rejeitados.
- Imports absolutos, imports com barra invertida, imports que escapem da raiz e módulos ausentes são rejeitados antes de chamar o compilador.
- A validação percorre também os imports dos módulos alcançáveis a partir do arquivo principal.
- Os arquivos são criados em diretório temporário isolado e removidos ao final da chamada.
- A API de arquivo único rejeita imports: envie o conjunto completo pelos endpoints de projeto.

## Segurança operacional

- O serviço escuta exclusivamente em `127.0.0.1` e valida Host e origem CORS.
- CORS é limitado às origens locais de desenvolvimento. Para outra origem explicitamente controlada, configure `GP_BRIDGE_ORIGINS` com uma lista separada por vírgulas.
- O compilador é iniciado com lista de argumentos, sem shell.
- Não existem endpoints genéricos de shell, leitura arbitrária de arquivos, rede, administração ou acesso a credenciais.
- Não publique a porta, não faça proxy reverso para a internet e não exponha o Bridge em `0.0.0.0`.

A Bridge 0.2 não altera a versão da linguagem, que permanece em GP 0.8.52. A execução ainda usa a VM Python de referência; seleção do runtime nativo e depuração interativa ficam para etapas posteriores.
