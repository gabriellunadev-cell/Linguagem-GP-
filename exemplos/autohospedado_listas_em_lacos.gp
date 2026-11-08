estrutura Pessoa {
    texto nome;
    numero idade;
}

lista Pessoa pessoas = [
    Pessoa("Ana", 29),
    Pessoa("Bia", 26)
]

numero indice = 0
numero total_idades = 0

enquanto (indice < tamanho(pessoas)) {
    indice = indice + 1
    se (indice == 1) { continuar }
    total_idades = total_idades + pessoas[indice - 1].idade
    se (indice == 2) { quebrar }
}

mostrar("Total:", total_idades)
mostrar("Primeira:", pessoas[0].nome)
