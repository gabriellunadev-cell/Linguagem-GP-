funcao somar_com_controle(numero limite) -> numero {
    numero cursor = 0
    numero soma = 0
    enquanto (cursor < limite) {
        cursor = cursor + 1
        se (cursor == 2) { continuar }
        se (cursor == 5) { quebrar }
        soma = soma + cursor
    }
    retornar soma
}
numero outer = 0
numero total = 0
numero inner = 0
enquanto (outer < 3) {
    outer = outer + 1
    inner = 0
    enquanto (inner < 5) {
        inner = inner + 1
        se (inner == 2) { continuar }
        senao { total = total + outer * inner }
        se (inner == 4) { quebrar }
    }
}
numero for_total = 0
para (numero i = 0; i < 7; i = i + 1) {
    se (i == 2) { continuar }
    se (i == 5) { quebrar }
    se (i == 3) { for_total = for_total + i * 2 }
    senao { for_total = for_total + i }
}
mostrar(total, outer, for_total, somar_com_controle(8))
