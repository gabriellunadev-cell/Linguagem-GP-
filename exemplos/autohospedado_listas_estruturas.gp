estrutura Pessoa {
    texto nome;
    numero idade;
}

funcao primeiro_nome(lista Pessoa pessoas) -> texto {
    retornar pessoas[0].nome
}

funcao adicionar_pessoa(lista Pessoa pessoas) -> lista Pessoa {
    pessoas = adicionar(pessoas, Pessoa("Bia", 26))
    retornar pessoas
}

lista Pessoa pessoas = [Pessoa("Ana", 29)]
mostrar("Primeira pessoa:", primeiro_nome(pessoas))

lista Pessoa ampliada = adicionar_pessoa(pessoas)
mostrar("Nova lista:", tamanho(ampliada), ampliada[1].nome)
