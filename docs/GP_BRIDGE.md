# GP Bridge — serviço local de integração

O GP Bridge expõe a CLI oficial do compilador para o GP Programinha. Ele não implementa uma segunda versão da linguagem: recebe uma fonte, cria um workspace temporário e invoca `gp_compile.py`.

## Iniciar

No Termux, dentro do repositório da linguagem:

```bash
python3 gp_ide_server.py
```

O serviço fica disponível somente em `http://127.0.0.1:8765`. O servidor não aceita bind em `0.0.0.0`.

No Programinha, use o endereço padrão nas configurações de integração.

## Endpoints

- `GET /api/health`: estado do serviço e disponibilidade do compilador.
- `POST /api/compile`: compila a fonte e retorna stdout, stderr, código de saída e duração.
- `POST /api/run`: compila e executa pela VM Python de referência.

## Limites da versão inicial

- Fonte máxima: 1 MiB por chamada.
- Nome de arquivo GP simples, sem caminhos.
- Timeout de compilação: 20 segundos.
- Timeout de execução: 5 segundos; limite de instruções da VM: 1.000.000.
- Workspace temporário removido ao final da chamada.
- CORS limitado às origens locais de desenvolvimento do Programinha por padrão. Para outra origem explicitamente controlada, configure `GP_BRIDGE_ORIGINS` com uma lista separada por vírgulas.
- Runtime nativo, projetos com múltiplos arquivos e gestão persistente de projetos ainda não estão habilitados na API inicial.

O serviço deve permanecer local. Não publique a porta, não faça proxy reverso para a internet e não adicione endpoints genéricos de shell ou leitura de arquivos.
