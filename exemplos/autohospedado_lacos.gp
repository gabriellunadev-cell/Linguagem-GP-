numero externo = 0
numero interno = 0
numero total = 0

enquanto (externo < 3) {
    externo = externo + 1
    interno = 0
    enquanto (interno < 4) {
        interno = interno + 1
        se (interno == 2) { continuar }
        se (interno == 4) { quebrar }
        total = total + externo * interno
    }
}

numero soma_para = 0
para (numero indice = 0; indice < 7; indice = indice + 1) {
    se (indice == 2) { continuar }
    se (indice == 5) { quebrar }
    soma_para = soma_para + indice
}

mostrar("Aninhados:", total, externo, "Para:", soma_para)
