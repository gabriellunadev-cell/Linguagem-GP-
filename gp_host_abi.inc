/*
 * GP Host Capabilities ABI v1.
 *
 * Stable identifiers live in gpcompiler/host_abi.py. Keep this native
 * dispatcher behavior-compatible with that registry. Calls enter through
 * the existing GP-IR CALL builtin "host_chamar"; no bytecode version bump.
 */
#define GP_HOST_MAX_CALLS 1024u
#define GP_HOST_MAX_ARGUMENTS 16u
#define GP_HOST_MAX_LIST_ITEMS 10000u
#define GP_HOST_MAX_SAFE_INTEGER 9007199254740991.0

static int gp_host_arity(VM *vm, int count, int minimum, int maximum, const char *name) {
    if (count < minimum || count > maximum) {
        char message[192];
        if (minimum == maximum)
            snprintf(message, sizeof(message), "%s: exige %d argumento(s)", name, minimum);
        else
            snprintf(message, sizeof(message), "%s: exige entre %d e %d argumentos", name, minimum, maximum);
        vm_error(vm, message);
        return 0;
    }
    return 1;
}

static int gp_host_number(VM *vm, Value value, double *out, const char *name, int allow_nonfinite) {
    if (value.type != V_NUMBER ||
        (!allow_nonfinite && (!isfinite(value.number) || fabs(value.number) > GP_HOST_MAX_SAFE_INTEGER))) {
        char message[192];
        snprintf(message, sizeof(message), "%s: esperado número finito dentro do intervalo seguro", name);
        vm_error(vm, message);
        return 0;
    }
    *out = value.number;
    return 1;
}

static int gp_host_integer(VM *vm, Value value, int64_t *out, const char *name) {
    double number = 0;
    if (!gp_host_number(vm, value, &number, name, 0)) return 0;
    if (floor(number) != number) {
        char message[160];
        snprintf(message, sizeof(message), "%s: esperado inteiro", name);
        vm_error(vm, message);
        return 0;
    }
    *out = (int64_t)number;
    return 1;
}

static int gp_host_numbers(VM *vm, Value value, size_t minimum, double **out, size_t *length, const char *name) {
    if (value.type != V_ARRAY || !value.array) {
        vm_error(vm, "host_chamar(): capacidade estatística exige lista numérica");
        return 0;
    }
    Array *array = value.array;
    if (array->len < minimum || array->len > GP_HOST_MAX_LIST_ITEMS) {
        char message[192];
        snprintf(message, sizeof(message), "%s: lista precisa conter entre %zu e %u itens",
                 name, minimum, GP_HOST_MAX_LIST_ITEMS);
        vm_error(vm, message);
        return 0;
    }
    if (array->len > SIZE_MAX / sizeof(double)) {
        vm_error(vm, "host_chamar(): lista excede o limite de memória");
        return 0;
    }
    double *values = (double *)malloc(array->len * sizeof(double));
    if (!values) {
        vm_error(vm, "host_chamar(): memória insuficiente para a lista numérica");
        return 0;
    }
    for (size_t i = 0; i < array->len; i++) {
        if (!gp_host_number(vm, array->items[i], &values[i], name, 0)) {
            free(values);
            return 0;
        }
    }
    *out = values;
    *length = array->len;
    return 1;
}

static int gp_host_compare_double(const void *left, const void *right) {
    double a = *(const double *)left, b = *(const double *)right;
    return (a > b) - (a < b);
}

static uint64_t gp_host_abs_i64(int64_t value) {
    return value < 0 ? (uint64_t)(-value) : (uint64_t)value;
}

static uint64_t gp_host_gcd_u64(uint64_t a, uint64_t b) {
    while (b) {
        uint64_t remainder = a % b;
        a = b;
        b = remainder;
    }
    return a;
}

static int gp_host_result(VM *vm, double value, Value *out, const char *name) {
    if (!isfinite(value)) {
        char message[160];
        snprintf(message, sizeof(message), "%s: resultado fora do intervalo finito", name);
        vm_error(vm, message);
        return 0;
    }
    *out = number_value(value);
    return 1;
}

static int gp_host_call(VM *vm, const char *identifier, Value *args, int count, Value *out) {
    if (!identifier || strlen(identifier) > 128) {
        vm_error(vm, "host_chamar(): identificador de capacidade inválido");
        return 0;
    }
    if (vm->host_call_count >= GP_HOST_MAX_CALLS) {
        vm_error(vm, "host_chamar(): limite de 1024 chamadas por execução excedido");
        return 0;
    }
    if (count < 0 || (unsigned int)count > GP_HOST_MAX_ARGUMENTS) {
        vm_error(vm, "host_chamar(): máximo de 16 argumentos por capacidade");
        return 0;
    }
    vm->host_call_count++;

    double x = 0, y = 0, result = 0;
    int64_t integer = 0;
    const char *name = identifier;

    if (!strcmp(identifier, "gp.core.v1.math.is_finite")) {
        if (!gp_host_arity(vm, count, 1, 1, name) ||
            !gp_host_number(vm, args[0], &x, name, 1)) return 0;
        *out = bool_value(isfinite(x));
        return 1;
    }
    if (!strcmp(identifier, "gp.core.v1.math.sqrt")) {
        if (!gp_host_arity(vm, count, 1, 1, name) ||
            !gp_host_number(vm, args[0], &x, name, 0)) return 0;
        if (x < 0) { vm_error(vm, "raiz: argumento não pode ser negativo"); return 0; }
        return gp_host_result(vm, sqrt(x), out, name);
    }
    if (!strcmp(identifier, "gp.core.v1.math.sin") ||
        !strcmp(identifier, "gp.core.v1.math.cos") ||
        !strcmp(identifier, "gp.core.v1.math.tan") ||
        !strcmp(identifier, "gp.core.v1.math.log10") ||
        !strcmp(identifier, "gp.core.v1.math.abs") ||
        !strcmp(identifier, "gp.core.v1.math.floor") ||
        !strcmp(identifier, "gp.core.v1.math.ceil") ||
        !strcmp(identifier, "gp.core.v1.math.exp")) {
        if (!gp_host_arity(vm, count, 1, 1, name) ||
            !gp_host_number(vm, args[0], &x, name, 0)) return 0;
        if (!strcmp(identifier, "gp.core.v1.math.sin")) result = sin(x);
        else if (!strcmp(identifier, "gp.core.v1.math.cos")) result = cos(x);
        else if (!strcmp(identifier, "gp.core.v1.math.tan")) result = tan(x);
        else if (!strcmp(identifier, "gp.core.v1.math.log10")) {
            if (x <= 0) { vm_error(vm, "log10: argumento precisa ser maior que zero"); return 0; }
            result = log10(x);
        } else if (!strcmp(identifier, "gp.core.v1.math.abs")) result = fabs(x);
        else if (!strcmp(identifier, "gp.core.v1.math.floor")) result = floor(x);
        else if (!strcmp(identifier, "gp.core.v1.math.ceil")) result = ceil(x);
        else {
            if (x < -700 || x > 700) { vm_error(vm, "exp: argumento fora do limite [-700, 700]"); return 0; }
            result = exp(x);
        }
        return gp_host_result(vm, result, out, name);
    }
    if (!strcmp(identifier, "gp.core.v1.math.log")) {
        if (!gp_host_arity(vm, count, 1, 2, name) ||
            !gp_host_number(vm, args[0], &x, name, 0)) return 0;
        y = 2.71828182845904523536;
        if (count == 2 && !gp_host_number(vm, args[1], &y, name, 0)) return 0;
        if (x <= 0 || y <= 0 || y == 1) { vm_error(vm, "log: argumento/base fora do domínio"); return 0; }
        return gp_host_result(vm, log(x) / log(y), out, name);
    }
    if (!strcmp(identifier, "gp.core.v1.math.factorial")) {
        if (!gp_host_arity(vm, count, 1, 1, name) ||
            !gp_host_integer(vm, args[0], &integer, name)) return 0;
        if (integer < 0 || integer > 18) { vm_error(vm, "fatorial: use um inteiro entre 0 e 18"); return 0; }
        result = 1;
        for (int64_t i = 2; i <= integer; i++) result *= (double)i;
        *out = number_value(result);
        return 1;
    }
    if (!strcmp(identifier, "gp.core.v1.math.gcd") || !strcmp(identifier, "gp.core.v1.math.lcm")) {
        if (!gp_host_arity(vm, count, 2, 16, name)) return 0;
        int is_lcm = !strcmp(identifier, "gp.core.v1.math.lcm");
        uint64_t accumulator = 0;
        for (int i = 0; i < count; i++) {
            if (!gp_host_integer(vm, args[i], &integer, name)) return 0;
            uint64_t value = gp_host_abs_i64(integer);
            if (!i) accumulator = value;
            else if (!is_lcm) accumulator = gp_host_gcd_u64(accumulator, value);
            else {
                uint64_t divisor = gp_host_gcd_u64(accumulator, value);
                uint64_t reduced = divisor ? accumulator / divisor : 0;
                if (value && reduced > (uint64_t)GP_HOST_MAX_SAFE_INTEGER / value) {
                    vm_error(vm, "mmc: resultado acima do limite inteiro seguro");
                    return 0;
                }
                accumulator = reduced * value;
            }
        }
        if (accumulator > (uint64_t)GP_HOST_MAX_SAFE_INTEGER) {
            vm_error(vm, "resultado inteiro acima do limite seguro");
            return 0;
        }
        *out = number_value((double)accumulator);
        return 1;
    }
    if (!strcmp(identifier, "gp.core.v1.math.hypot")) {
        if (!gp_host_arity(vm, count, 2, 16, name)) return 0;
        result = 0;
        for (int i = 0; i < count; i++) {
            if (!gp_host_number(vm, args[i], &x, name, 0)) return 0;
            result = hypot(result, x);
        }
        return gp_host_result(vm, result, out, name);
    }
    if (!strcmp(identifier, "gp.core.v1.statistics.mean") ||
        !strcmp(identifier, "gp.core.v1.statistics.median") ||
        !strcmp(identifier, "gp.core.v1.statistics.pvariance") ||
        !strcmp(identifier, "gp.core.v1.statistics.variance") ||
        !strcmp(identifier, "gp.core.v1.statistics.pstdev") ||
        !strcmp(identifier, "gp.core.v1.statistics.stdev")) {
        int is_sample = !strcmp(identifier, "gp.core.v1.statistics.variance") ||
                        !strcmp(identifier, "gp.core.v1.statistics.stdev");
        if (!gp_host_arity(vm, count, 1, 1, name)) return 0;
        double *values = NULL;
        size_t length = 0;
        if (!gp_host_numbers(vm, args[0], is_sample ? 2u : 1u, &values, &length, name)) return 0;
        if (!strcmp(identifier, "gp.core.v1.statistics.mean")) {
            result = 0;
            for (size_t i = 0; i < length; i++)
                result += (values[i] - result) / (double)(i + 1);
        } else if (!strcmp(identifier, "gp.core.v1.statistics.median")) {
            qsort(values, length, sizeof(double), gp_host_compare_double);
            result = length % 2 ? values[length / 2]
                : values[length / 2 - 1] / 2.0 + values[length / 2] / 2.0;
        } else {
            double mean = 0, sum_squares = 0;
            for (size_t i = 0; i < length; i++) {
                double delta = values[i] - mean;
                mean += delta / (double)(i + 1);
                sum_squares += delta * (values[i] - mean);
            }
            result = sum_squares / (double)(length - (is_sample ? 1u : 0u));
            if (!strcmp(identifier, "gp.core.v1.statistics.pstdev") ||
                !strcmp(identifier, "gp.core.v1.statistics.stdev")) result = sqrt(result);
        }
        free(values);
        return gp_host_result(vm, result, out, name);
    }

    vm_error(vm, "host_chamar(): capacidade GP Host ABI v1 desconhecida");
    return 0;
}
