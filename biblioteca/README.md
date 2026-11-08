# Biblioteca padrão GP

A biblioteca padrão é mantida junto ao repositório da linguagem, compilador e runtimes. As primitivas que exigem comportamento nativo continuam implementadas nos runtimes; este diretório organiza os contratos públicos, exemplos e futuros módulos escritos em GP.

## Contrato atualmente implementado

Consulte [GP_STANDARD_LIBRARY.md](../docs/GP_STANDARD_LIBRARY.md). A primeira superfície inclui:

- `tamanho(valor)`
- `adicionar(lista, valor)`
- `remover(lista, indice)`
- `unir_textos(lista texto)`
- `mostrar(...)` como instrução da linguagem
- `entrada_fonte()` como intrínseco reservado ao frontend auto-hospedado

O exemplo executável está em [biblioteca_padrao.gp](../exemplos/biblioteca_padrao.gp).

## Política

Uma função só entra na biblioteca padrão depois de possuir assinatura e semântica documentadas, paridade entre o interpretador bootstrap e as VMs Python/C aplicáveis, limites explícitos, testes positivos/negativos e exemplo executável. Não duplicar implementação de runtime em módulos GP quando a primitiva ainda depende de suporte nativo.
