estrutura Endereco {
    texto cidade;
    numero cep;
}
estrutura Pessoa {
    texto nome;
    numero idade;
    logico ativa;
    Endereco endereco;
}

funcao atualizar_idade(Pessoa pessoa, numero nova_idade) -> numero {
    pessoa.idade = nova_idade
    retornar pessoa.idade
}

Endereco local = Endereco("Cabo Frio", 28900)
Pessoa pessoa = Pessoa("Ana", 29, verdadeiro, local)
mostrar("Cadastro:", pessoa.nome, pessoa.idade, pessoa.ativa)
mostrar("Endereco:", pessoa.endereco.cidade, pessoa.endereco.cep)
mostrar("Idade atualizada:", atualizar_idade(pessoa, 30))
pessoa.nome = "Ana Luna"
pessoa.endereco.cep = 289001
mostrar("Atualizado:", pessoa.nome, pessoa.idade, pessoa.endereco.cep)
