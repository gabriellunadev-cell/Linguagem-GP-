# Critérios de lançamento — Gabriel Programming 1.0.0

Este documento define condições verificáveis para declarar a GP estável. A versão 1.0.0 não será marcada apenas por número de funcionalidades: o contrato da linguagem, os formatos, o runtime, a experiência de instalação e os testes precisam estar coerentes.

## 1. Contrato público da linguagem

- [ ] Publicar especificação versionada de sintaxe, palavras-chave, precedência, escopos e regras de declaração.
- [ ] Publicar regras semânticas de tipos, conversões, funções, retorno, estruturas, listas e módulos.
- [ ] Definir o comportamento de erros, códigos de saída e formato dos diagnósticos.
- [ ] Definir compatibilidade de linguagem e política de mudanças incompatíveis.
- [ ] Documentar a biblioteca padrão, incluindo tipos, assinaturas, limites e exemplos.

## 2. Compilador e autohospedagem

- [ ] Frontend GP cobre o subconjunto declarado como 1.0.0 sem depender do parser Python para compilar programas válidos.
- [ ] Resolução de módulos, namespaces e dependências é implementada e validada pelo toolchain GP.
- [ ] Geração de GP-IR é determinística e validada contra o schema publicado.
- [ ] Encoder e decoder têm paridade comprovada entre implementação de referência e nativa.
- [ ] Bootstrap N → N+1 → N+2 é reproduzível, com artefatos e hashes registrados.
- [ ] O processo de construção do compilador está documentado e tem dependências explicitamente declaradas.

## 3. Bytecode e runtime

- [ ] GGPC e GP-IR têm especificações completas, limites, versionamento e política de compatibilidade.
- [ ] Cada opcode suportado tem semântica documentada e testes de referência.
- [ ] A VM Python de referência e a VM C nativa têm paridade em todos os recursos classificados como estáveis.
- [ ] Chamadas, recursão, coleções, estruturas, strings Unicode, módulos e builtins têm testes de sucesso e falha.
- [ ] Limites de instruções, memória, profundidade de chamadas e tamanho de entrada são explícitos.
- [ ] A VM trata bytecode inválido sem corrupção de estado, acesso fora de limites ou encerramento inesperado.

## 4. Segurança, integridade e robustez

- [ ] Entradas externas têm limites e validação em todas as fronteiras.
- [ ] Escritas de bytecode e artefatos finais são atômicas e preservam arquivos anteriores quando a publicação falha.
- [ ] Testes cobrem entradas truncadas, campos desconhecidos, duplicatas, UTF-8 inválido, limites e falhas de I/O.
- [ ] Fuzzing determinístico e diferencial roda com seeds registradas e zero divergências não explicadas.
- [ ] Nenhum teste crítico é ignorado silenciosamente; skips e plataformas não suportadas são documentados.
- [ ] O comportamento em OOM, timeout e interrupção é previsível e seguro.

## 5. Distribuição e experiência de desenvolvimento

- [ ] Instalação limpa em Termux/Android ARM64 documentada e reproduzível.
- [ ] CLI do interpretador, compilador, VM e backend nativo tem ajuda, exemplos e códigos de saída coerentes.
- [ ] O modo nativo identifica claramente o backend e nunca recua silenciosamente para Python.
- [ ] Exemplos de início rápido e projetos completos compilam e executam no ambiente de suporte.
- [ ] README, especificações, roadmap, changelog e notas de migração refletem a implementação real.

## 6. Portão final da versão 1.0.0

A release só pode ser considerada candidata quando:

1. Todos os itens obrigatórios anteriores estiverem concluídos ou explicitamente classificados como fora do escopo 1.0.0.
2. A suíte completa, o corpus diferencial, fuzzing, verificação de hashes e \`git diff --check\` passarem.
3. A prova de bootstrap N → N+1 → N+2 passar na configuração de release.
4. A instalação for validada em ambiente limpo de suporte.
5. Não houver regressões críticas abertas nem divergências Python/C sem explicação.
6. O changelog e as limitações conhecidas forem revisados.

## 7. Princípio de release

Até a aprovação de todos os portões, a GP permanece em versão 0.x experimental. Não publicar tags ou releases automaticamente. A criação de release, commit e push depende de aprovação explícita do mantenedor.
