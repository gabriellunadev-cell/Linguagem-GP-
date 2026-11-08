programa "GP 0.2 — recursos da linguagem"

funcao somar(numero a, numero b) -> numero {
    retornar a + b
}

funcao fatorial(numero n) -> numero {
    se (n <= 1) {
        retornar 1
    }
    retornar n * fatorial(n - 1)
}

lista numero valores = [10, 20, 30]
numero total = 0

para (numero i = 0; i < 3; i = i + 1) {
    total = somar(total, valores[i])
}

numero contador = 0
enquanto (contador < 2) {
    contador = contador + 1
}

estrutura Pessoa {
    texto nome;
    numero idade;
}

Pessoa gabriel = Pessoa { nome: "Gabriel Luna", idade: 29 }
gabriel.idade = gabriel.idade + 1

mostrar("Total:", total)
mostrar("Fatorial de 5:", fatorial(5))
mostrar("Contador:", contador)
mostrar("Pessoa:", gabriel.nome, "-", gabriel.idade)
