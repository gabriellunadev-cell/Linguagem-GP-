estrutura Pessoa {
    texto nome;
    numero idade;
}
Pessoa pessoa = Pessoa{nome: "Ana", idade: 37}
pessoa.idade = 38
mostrar(pessoa.nome, pessoa.idade)
