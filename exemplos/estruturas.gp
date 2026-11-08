estrutura Pessoa {
    texto nome;
    numero idade;
}
Pessoa pessoa = Pessoa{nome: "Ada", idade: 37}
pessoa.idade = 38
mostrar("Pessoa:", pessoa.nome, pessoa.idade)
