estrutura Pessoa {
    texto nome;
    numero idade;
}
funcao identidade(numero valor) -> numero {
    retornar valor
}
numero a = 8
numero b = 3
numero soma = a + b
numero subtracao = a - b
numero produto = a * b
numero divisao = a / b
numero resto = a % b
logico igual = a == b
logico diferente = a != b
logico maior = a > b
logico menor = a < b
logico maior_igual = a >= b
logico menor_igual = a <= b
logico conjuncao = verdadeiro && falso
logico disjuncao = verdadeiro || falso
logico negacao = !falso
numero negativo = -a
lista numero numeros = [1, 2, 3]
numeros[1] = 9
numero item = numeros[1]
lista texto vazia = []
Pessoa pessoa = Pessoa{nome: "GP", idade: 8}
pessoa.idade = pessoa.idade + 1
texto nome = pessoa.nome
numero resultado = identidade(5)
para (numero cursor = 0; cursor < 1; identidade(2)) {
    cursor = 1
}
mostrar(soma, subtracao, produto, resto)
mostrar(item, tamanho(numeros), tamanho(vazia), pessoa.nome, nome, pessoa.idade, resultado)
