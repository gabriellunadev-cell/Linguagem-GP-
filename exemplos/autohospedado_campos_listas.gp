estrutura Pessoa {
    texto nome;
    numero idade;
}

estrutura Equipe {
    lista Pessoa integrantes;
}

lista Pessoa pessoas = [Pessoa("Ana", 29)]
Equipe equipe = Equipe(pessoas)

mostrar("Integrante:", equipe.integrantes[0].nome)
equipe.integrantes[0].idade = 30
mostrar("Idade atualizada:", equipe.integrantes[0].idade)
