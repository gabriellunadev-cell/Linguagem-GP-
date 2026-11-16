# GP + Python — execução híbrida

A GP pode usar Python como camada auxiliar para acelerar o desenvolvimento e reutilizar funções consolidadas da biblioteca padrão. O programa continua escrito em GP e compilado para GGPC v2; a chamada permitida é executada pelo host Python durante a execução na VM de referência.

## Exemplo

\`\`\`gp
numero raiz = py_chamar("math.sqrt", [81])
numero media = py_chamar("statistics.mean", [[2, 4, 6, 8]])
texto digest = py_chamar("hashlib.sha256", ["Gabriel Programming"])
mostrar("Raiz:", raiz)
mostrar("Média:", media)
mostrar("SHA-256:", digest)
\`\`\`

Compile e execute com a integração explicitamente habilitada:

\`\`\`bash
python3 gp_compile.py programa.gp --run --run-vm python --python-interop
\`\`\`

Para executar um bytecode que já foi compilado:

\`\`\`bash
python3 gp_vm.py programa.gbc --python-interop
\`\`\`

O interpretador bootstrap também aceita:

\`\`\`bash
python3 gp.py programa.gp --python-interop
\`\`\`


## Biblioteca GP de conveniência

O projeto inclui biblioteca/python.gp. Um programa pode importar os wrappers:

~~~gp
usar "biblioteca/python.gp" como py
numero raiz = py.raiz_quadrada(81)
numero media = py.media([2, 4, 6, 8])
mostrar(raiz, media)
~~~

O módulo não amplia a allowlist: apenas oferece nomes GP mais curtos para as mesmas capacidades autorizadas.

## Capacidades autorizadas

A ponte não importa módulos com base no texto enviado pelo programa. Ela consulta uma tabela estática e fechada de funções:

- \`math\`: sqrt, sin, cos, tan, log, log10, exp, fabs, floor, ceil, factorial, gcd, lcm, hypot e isfinite.
- \`statistics\`: mean, median, pstdev, pvariance, stdev e variance.
- \`hashlib\`: sha256.
- \`unicodedata\`: normalize.
- \`textwrap\`: dedent e shorten.

Chame sempre pelo nome completo, por exemplo \`py_chamar("math.sqrt", [81])\`. Os argumentos são uma lista GP de valores escalares ou listas aninhadas.

## Limites e segurança

- A integração fica desligada por padrão e requer \`--python-interop\` ou a opção equivalente no GP Programinha.
- Máximo de 1.024 chamadas por execução.
- Máximo de 16 argumentos por chamada.
- Listas limitadas a 10.000 itens e profundidade 8.
- Textos limitados a 1 MiB por valor.
- Somente números finitos e inteiros dentro do intervalo seguro são aceitos.
- \`math.factorial\` aceita valores de 0 a 18 para manter resultados exatos na faixa numérica compartilhada.
- Valores de retorno são validados antes de voltar à GP.

Não há \`eval\`, \`exec\`, importação dinâmica, reflexão, acesso a arquivos, subprocessos, shell ou rede. Uma função que não esteja explicitamente na tabela é rejeitada.

## Fronteira de execução atual

A ponte está disponível na VM Python de referência e no interpretador bootstrap. A VM C nativa continua independente de Python e rejeita \`py_chamar\`; a flag \`--python-interop\` não pode ser combinada com \`--run-vm native\`. A rota de compilação auto-hospedada em GP ainda não reconhece esse builtin nesta primeira etapa.

Essa separação é intencional: programas GP sem chamadas Python continuam portáveis para Linux, ARM64, Windows e os demais runtimes que implementem o bytecode. Programas que usam \`py_chamar\` devem escolher o runtime híbrido Python.
