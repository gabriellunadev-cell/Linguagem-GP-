/*
 * Gabriel Programming — native bytecode VM (experimental).
 * Loads GP bytecode v2 directly: GGPC header + zlib JSON IR.
 * Build: clang -std=c11 -O2 gpvm_native.c -lz -o gpvm-native
 */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <unistd.h>
#include <zlib.h>

#define GP_MAX_PAYLOAD (64u * 1024u * 1024u)
#define GP_MAX_TOKENS  2000000u
#define GP_MAX_DEPTH   512
#define GP_MAX_CALLS   256
#define GP_DEFAULT_STEPS 1000000ull

#define GP_MAX_HEAP_BYTES (256u * 1024u * 1024u)
#define GP_MAX_HOST_SOURCE_BYTES (16u * 1024u * 1024u)
#define GP_MAX_TEXT_JOIN_BYTES (64u * 1024u * 1024u)
enum { GP_ALLOC_NATIVE = 0, GP_ALLOC_MANAGED = 1, GP_ALLOC_STACK = 2, GP_ALLOC_COUNT = 3 };
typedef union GPAllocHeader GPAllocHeader;
union GPAllocHeader { struct { size_t size; GPAllocHeader *prev, *next; unsigned int category; } h; max_align_t align; };
static GPAllocHeader *gp_allocations = NULL;
static size_t gp_heap_bytes = 0, gp_heap_peak = 0;
static size_t gp_alloc_category_live[GP_ALLOC_COUNT] = {0};
static size_t gp_alloc_category_peak[GP_ALLOC_COUNT] = {0};
static unsigned int gp_current_alloc_category = GP_ALLOC_NATIVE;
static void gp_account_category(unsigned int category, size_t old_total, size_t new_total) {
    if (category >= GP_ALLOC_COUNT) category = GP_ALLOC_NATIVE;
    if (new_total >= old_total) {
        size_t added = new_total - old_total;
        gp_alloc_category_live[category] += added;
        if (gp_alloc_category_live[category] > gp_alloc_category_peak[category])
            gp_alloc_category_peak[category] = gp_alloc_category_live[category];
    } else {
        size_t removed = old_total - new_total;
        gp_alloc_category_live[category] = gp_alloc_category_live[category] >= removed
            ? gp_alloc_category_live[category] - removed : 0;
    }
}
static void *gp_malloc(size_t n) {
    if (!n) n=1;
    if (n > SIZE_MAX - sizeof(GPAllocHeader)) return NULL;
    size_t accounted = sizeof(GPAllocHeader) + n;
    if (accounted > GP_MAX_HEAP_BYTES || gp_heap_bytes > GP_MAX_HEAP_BYTES - accounted) return NULL;
    GPAllocHeader *h=(GPAllocHeader *)malloc(accounted); if (!h) return NULL;
    h->h.size=n; h->h.prev=NULL; h->h.next=gp_allocations; h->h.category=gp_current_alloc_category;
    if (gp_allocations) gp_allocations->h.prev=h;
    gp_allocations=h; gp_heap_bytes+=accounted; if (gp_heap_bytes>gp_heap_peak) gp_heap_peak=gp_heap_bytes;
    gp_account_category(h->h.category, 0, accounted);
    return (void *)(h+1);
}
static void *gp_calloc(size_t n,size_t z) {
    if (z && n>SIZE_MAX/z) return NULL;
    size_t bytes=n*z; void *p=gp_malloc(bytes); if (p) memset(p,0,bytes); return p;
}
static void gp_free(void *p) {
    if (!p) return;
    GPAllocHeader *h=((GPAllocHeader *)p)-1;
    if (h->h.prev) h->h.prev->h.next=h->h.next; else gp_allocations=h->h.next;
    if (h->h.next) h->h.next->h.prev=h->h.prev;
    size_t accounted = sizeof(*h) + h->h.size;
    gp_heap_bytes -= accounted; gp_account_category(h->h.category, accounted, 0); free(h);
}
static void *gp_realloc(void *p,size_t n) {
    if (!p) return gp_malloc(n);
    if (!n) { gp_free(p); return NULL; }
    GPAllocHeader *old=((GPAllocHeader *)p)-1;
    if (n > SIZE_MAX - sizeof(*old)) return NULL;
    size_t old_total=sizeof(*old)+old->h.size;
    size_t new_total=sizeof(*old)+n;
    if (gp_heap_bytes < old_total) return NULL;
    size_t other_bytes=gp_heap_bytes-old_total;
    if (new_total > GP_MAX_HEAP_BYTES || other_bytes > GP_MAX_HEAP_BYTES-new_total) return NULL;
    GPAllocHeader *prev=old->h.prev,*next=old->h.next;
    unsigned int category=old->h.category;
    GPAllocHeader *h=(GPAllocHeader *)realloc(old,new_total); if (!h) return NULL;
    h->h.size=n; h->h.prev=prev; h->h.next=next; h->h.category=category;
    if (prev) prev->h.next=h; else gp_allocations=h;
    if (next) next->h.prev=h;
    gp_heap_bytes=other_bytes+new_total; if (gp_heap_bytes>gp_heap_peak) gp_heap_peak=gp_heap_bytes;
    gp_account_category(category, old_total, new_total);
    return (void *)(h+1);
}
static void gp_memory_cleanup(void) {
    GPAllocHeader *h=gp_allocations;
    while (h) { GPAllocHeader *next=h->h.next; free(h); h=next; }
    gp_allocations=NULL; gp_heap_bytes=0;
    memset(gp_alloc_category_live, 0, sizeof(gp_alloc_category_live));
    gp_current_alloc_category = GP_ALLOC_NATIVE;
}
static void gp_heap_report(FILE *out) {
    static const size_t limits[] = {16, 64, 256, 1024, 4096, SIZE_MAX};
    static const char *labels[] = {"<=16", "17-64", "65-256", "257-1024", "1025-4096", ">4096"};
    size_t counts[6] = {0}, bytes[6] = {0};
    for (GPAllocHeader *h = gp_allocations; h; h = h->h.next) {
        size_t total = sizeof(*h) + h->h.size;
        size_t i = 0;
        while (i < 5 && h->h.size > limits[i]) i++;
        counts[i]++;
        bytes[i] += total;
    }
    for (size_t i = 0; i < 6; i++) {
        fprintf(out, "[GP heap bins: %s bytes=%zu allocs=%zu]\n", labels[i], bytes[i], counts[i]);
    }
}
#define malloc(n) gp_malloc(n)
#define calloc(n,s) gp_calloc((n),(s))
#define realloc(p,n) gp_realloc((p),(n))
#define free(p) gp_free(p)

typedef enum { JT_OBJECT, JT_ARRAY, JT_STRING, JT_PRIMITIVE } JType;
typedef struct { JType type; size_t start, end, next; } JToken;
typedef struct { const char *src; size_t len; JToken *tokens; size_t count, cap; char error[256]; } Json;

typedef enum { V_NULL, V_NUMBER, V_STRING, V_BOOL, V_ARRAY, V_STRUCT } VType;
typedef struct Value Value;
typedef struct { Value *items; size_t len, cap; char *element_type; } Array;
typedef struct { char **names; Value *values; char **types; size_t len, cap; char *name; } Struct;
struct Value { VType type; double number; int boolean; char *string; Array *array; Struct *object; };
static size_t gp_stack_capacity_bytes = 0;
static size_t gp_stack_peak_bytes = 0;

typedef struct { char **names; Value *values; char **types; char **element_types; size_t len, cap; } Env;
typedef struct GPGCHeader GPGCHeader;
typedef struct VMRoot VMRoot;
enum { GP_GC_STRING = 1, GP_GC_ARRAY = 2, GP_GC_STRUCT = 3 };
#define GP_GC_MAGIC 0x47504743u
#define GP_GC_STRING_ASCII 1u
struct GPGCHeader {
    GPGCHeader *next;
    size_t size;
    unsigned int kind;
    unsigned int marked;
    unsigned int flags;
    uint32_t magic;
};
struct VMRoot {
    Env *env;
    Value **stack;
    size_t *stack_len;
    VMRoot *next;
};
typedef struct {
    Json json;
    Env globals;
    VMRoot *roots;
    GPGCHeader *gc_objects;
    size_t gc_bytes, gc_peak_bytes, gc_threshold, gc_min_threshold;
    size_t gc_collections, gc_freed_objects, gc_reclaimed_bytes;
    size_t gc_allocated_objects;
    Value ascii_cache[128];
    uint64_t steps, max_steps;
    char *host_source;
    char error[512];
} VM;

static size_t gp_process_current_rss_bytes(void) {
    FILE *status = fopen("/proc/self/status", "r");
    if (!status) return 0;
    char line[256];
    size_t rss_kib = 0;
    while (fgets(line, sizeof(line), status)) {
        if (sscanf(line, "VmRSS: %zu kB", &rss_kib) == 1) break;
    }
    fclose(status);
    if (rss_kib > SIZE_MAX / 1024u) return 0;
    return rss_kib * 1024u;
}

static size_t gp_process_peak_rss_bytes(void) {
    struct rusage usage;
    memset(&usage, 0, sizeof(usage));
    if (getrusage(RUSAGE_SELF, &usage) != 0 || usage.ru_maxrss <= 0) return 0;
#if defined(__APPLE__)
    /* Darwin reports ru_maxrss in bytes; Linux and Android report KiB. */
    return (size_t)usage.ru_maxrss;
#else
    if ((uintmax_t)usage.ru_maxrss > SIZE_MAX / 1024u) return 0;
    return (size_t)usage.ru_maxrss * 1024u;
#endif
}

static void gp_write_memory_report(const char *path, int ok, const VM *vm) {
    if (!path || !*path || !vm) return;
    FILE *out = fopen(path, "w");
    if (!out) return;
    fprintf(out,
        "{\n  \"status\": \"%s\",\n"
        "  \"limit_bytes\": %u,\n"
        "  \"total_heap_peak_bytes\": %zu,\n"
        "  \"total_heap_live_bytes\": %zu,\n"
        "  \"native_peak_bytes\": %zu,\n"
        "  \"native_live_bytes\": %zu,\n"
        "  \"managed_peak_bytes\": %zu,\n"
        "  \"managed_live_bytes\": %zu,\n"
        "  \"managed_payload_peak_bytes\": %zu,\n"
        "  \"managed_payload_live_bytes\": %zu,\n"
        "  \"stack_peak_bytes\": %zu,\n"
        "  \"stack_live_bytes\": %zu,\n"
        "  \"process_rss_bytes\": %zu,\n"
        "  \"process_peak_rss_bytes\": %zu,\n"
        "  \"process_memory_source\": \"procfs VmRSS + getrusage ru_maxrss\"\n}\n",
        ok ? "ok" : "error", (unsigned int)GP_MAX_HEAP_BYTES,
        gp_heap_peak, gp_heap_bytes,
        gp_alloc_category_peak[GP_ALLOC_NATIVE], gp_alloc_category_live[GP_ALLOC_NATIVE],
        gp_alloc_category_peak[GP_ALLOC_MANAGED], gp_alloc_category_live[GP_ALLOC_MANAGED],
        vm->gc_peak_bytes, vm->gc_bytes,
        gp_alloc_category_peak[GP_ALLOC_STACK], gp_alloc_category_live[GP_ALLOC_STACK],
        gp_process_current_rss_bytes(), gp_process_peak_rss_bytes());
    fclose(out);
}

static char *copy_string(const char *s) {
    size_t n = strlen(s);
    char *p = (char *)malloc(n + 1);
    if (!p) return NULL;
    memcpy(p, s, n + 1);
    return p;
}
static void *gp_gc_alloc(VM *vm, size_t size, unsigned int kind) {
    if (size > SIZE_MAX - sizeof(GPGCHeader)) return NULL;
    unsigned int previous_category = gp_current_alloc_category;
    gp_current_alloc_category = GP_ALLOC_MANAGED;
    GPGCHeader *h = (GPGCHeader *)calloc(1, sizeof(GPGCHeader) + size);
    gp_current_alloc_category = previous_category;
    if (!h) return NULL;
    h->size = size;
    h->kind = kind;
    h->magic = GP_GC_MAGIC;
    h->next = vm->gc_objects;
    vm->gc_objects = h;
    vm->gc_bytes += size;
    if (vm->gc_bytes > vm->gc_peak_bytes) vm->gc_peak_bytes = vm->gc_bytes;
    vm->gc_allocated_objects++;
    return (void *)(h + 1);
}
static GPGCHeader *gp_gc_header(const void *payload) {
    if (!payload) return NULL;
    GPGCHeader *h = ((GPGCHeader *)payload) - 1;
    return h->magic == GP_GC_MAGIC ? h : NULL;
}
static void gp_gc_mark_value(Value value);
static void gp_gc_mark_env(Env *env) {
    if (!env) return;
    for (size_t i = 0; i < env->len; i++) gp_gc_mark_value(env->values[i]);
}
static void gp_gc_mark_value(Value value) {
    void *payload = NULL;
    if (value.type == V_STRING) payload = value.string;
    else if (value.type == V_ARRAY) payload = value.array;
    else if (value.type == V_STRUCT) payload = value.object;
    else return;
    GPGCHeader *h = gp_gc_header(payload);
    if (!h || h->marked) return;
    h->marked = 1;
    if (h->kind == GP_GC_ARRAY) {
        Array *a = (Array *)payload;
        for (size_t i = 0; i < a->len; i++) gp_gc_mark_value(a->items[i]);
    } else if (h->kind == GP_GC_STRUCT) {
        Struct *o = (Struct *)payload;
        for (size_t i = 0; i < o->len; i++) gp_gc_mark_value(o->values[i]);
    }
}
static void gp_gc_release(GPGCHeader *h) {
    void *payload = (void *)(h + 1);
    if (h->kind == GP_GC_ARRAY) {
        Array *a = (Array *)payload;
        free(a->items);
        free(a->element_type);
    } else if (h->kind == GP_GC_STRUCT) {
        Struct *o = (Struct *)payload;
        for (size_t i = 0; i < o->len; i++) {
            free(o->names ? o->names[i] : NULL);
            free(o->types ? o->types[i] : NULL);
        }
        free(o->names);
        free(o->types);
        free(o->values);
        free(o->name);
    }
    h->magic = 0;
    free(h);
}
static void gp_gc_collect(VM *vm) {
    for (GPGCHeader *h = vm->gc_objects; h; h = h->next) h->marked = 0;
    gp_gc_mark_env(&vm->globals);
    for (size_t i = 0; i < 128; i++) gp_gc_mark_value(vm->ascii_cache[i]);
    for (VMRoot *r = vm->roots; r; r = r->next) {
        gp_gc_mark_env(r->env);
        if (r->stack && *r->stack && r->stack_len) {
            Value *stack = *r->stack;
            for (size_t i = 0; i < *r->stack_len; i++) gp_gc_mark_value(stack[i]);
        }
    }
    GPGCHeader **link = &vm->gc_objects;
    while (*link) {
        GPGCHeader *h = *link;
        if (h->marked) {
            link = &h->next;
            continue;
        }
        *link = h->next;
        if (vm->gc_bytes >= h->size) vm->gc_bytes -= h->size;
        vm->gc_reclaimed_bytes += h->size;
        vm->gc_freed_objects++;
        gp_gc_release(h);
    }
    vm->gc_collections++;
    size_t adaptive = vm->gc_bytes > (SIZE_MAX - 65536u) / 2
        ? SIZE_MAX : vm->gc_bytes * 2 + 65536u;
    vm->gc_threshold = adaptive > vm->gc_min_threshold ? adaptive : vm->gc_min_threshold;
    if (vm->gc_threshold > GP_MAX_HEAP_BYTES / 2) vm->gc_threshold = GP_MAX_HEAP_BYTES / 2;
}
static void gp_gc_maybe_collect(VM *vm) {
    if (vm->gc_threshold && vm->gc_bytes >= vm->gc_threshold) gp_gc_collect(vm);
}
static void gp_gc_remove_root(VM *vm, VMRoot *root) {
    VMRoot **link = &vm->roots;
    while (*link && *link != root) link = &(*link)->next;
    if (*link) *link = root->next;
}
static void gp_gc_cleanup(VM *vm) {
    GPGCHeader *h = vm->gc_objects;
    while (h) {
        GPGCHeader *next = h->next;
        gp_gc_release(h);
        h = next;
    }
    vm->gc_objects = NULL;
    vm->gc_bytes = 0;
}
static Value null_value(void) { Value v; memset(&v, 0, sizeof(v)); v.type = V_NULL; return v; }
static Value number_value(double n) { Value v = null_value(); v.type = V_NUMBER; v.number = n; return v; }
static Value bool_value(int b) { Value v = null_value(); v.type = V_BOOL; v.boolean = !!b; return v; }
static Value string_value_bytes(VM *vm, const char *bytes, size_t length) {
    Value v = null_value();
    v.type = V_STRING;
    if (length == SIZE_MAX) {
        snprintf(vm->error, sizeof(vm->error), "texto excede o limite de memória");
        return v;
    }
    v.string = (char *)gp_gc_alloc(vm, length + 1, GP_GC_STRING);
    if (!v.string) {
        if (!vm->error[0]) snprintf(vm->error, sizeof(vm->error), "memória insuficiente para texto gerenciado");
        return v;
    }
    if (length) memcpy(v.string, bytes, length);
    v.string[length] = '\0';
    GPGCHeader *header = gp_gc_header(v.string);
    if (header) {
        header->flags = GP_GC_STRING_ASCII;
        for (size_t i = 0; i < length; i++) {
            if ((unsigned char)bytes[i] >= 0x80) {
                header->flags = 0;
                break;
            }
        }
    }
    return v;
}
static Value string_value(VM *vm, char *s) {
    if (!s) s = copy_string("");
    if (!s) {
        Value v = null_value();
        snprintf(vm->error, sizeof(vm->error), "memória insuficiente para texto temporário");
        return v;
    }
    size_t n = strlen(s);
    Value v = string_value_bytes(vm, s, n);
    free(s);
    return v;
}

static void skip_ws(Json *j, size_t *p) {
    while (*p < j->len && (j->src[*p] == ' ' || j->src[*p] == '\n' ||
           j->src[*p] == '\r' || j->src[*p] == '\t')) (*p)++;
}
static int token_new(Json *j, JType type, size_t start) {
    if (j->count >= GP_MAX_TOKENS) { snprintf(j->error, sizeof(j->error), "limite de tokens JSON excedido"); return -1; }
    if (j->count == j->cap) {
        size_t cap = j->cap ? j->cap * 2 : 1024;
        JToken *next = (JToken *)realloc(j->tokens, cap * sizeof(JToken));
        if (!next) { snprintf(j->error, sizeof(j->error), "memória insuficiente para JSON"); return -1; }
        j->tokens = next; j->cap = cap;
    }
    int id = (int)j->count++;
    j->tokens[id].type = type; j->tokens[id].start = start;
    j->tokens[id].end = start; j->tokens[id].next = (size_t)id + 1;
    return id;
}

static int valid_json_primitive(const char *s,size_t n) {
    if ((n==4&&!memcmp(s,"true",4))||(n==5&&!memcmp(s,"false",5))||(n==4&&!memcmp(s,"null",4))) return 1;
    size_t i=0; if (i<n&&s[i]=='-') i++; if (i>=n) return 0;
    if (s[i]=='0') i++; else { if(s[i]<'1'||s[i]>'9') return 0; while(i<n&&s[i]>='0'&&s[i]<='9') i++; }
    if(i<n&&s[i]=='.'){i++;size_t b=i;while(i<n&&s[i]>='0'&&s[i]<='9')i++;if(i==b)return 0;}
    if(i<n&&(s[i]=='e'||s[i]=='E')){i++;if(i<n&&(s[i]=='+'||s[i]=='-'))i++;size_t b=i;while(i<n&&s[i]>='0'&&s[i]<='9')i++;if(i==b)return 0;}
    return i==n;
}
static int utf8_decode_one(const unsigned char *s,size_t n,size_t *used,uint32_t *cp) {
    if(!n)return 0; unsigned char a=s[0];
    if(a<0x80){*used=1;*cp=a;return 1;}
    if(a>=0xc2&&a<=0xdf&&n>=2&&(s[1]&0xc0)==0x80){*used=2;*cp=((uint32_t)(a&31)<<6)|(s[1]&63);return 1;}
    if(a>=0xe0&&a<=0xef&&n>=3&&(s[1]&0xc0)==0x80&&(s[2]&0xc0)==0x80){
        if((a==0xe0&&s[1]<0xa0)||(a==0xed&&s[1]>=0xa0))return 0;
        *used=3;*cp=((uint32_t)(a&15)<<12)|((uint32_t)(s[1]&63)<<6)|(s[2]&63);return 1;
    }
    if(a>=0xf0&&a<=0xf4&&n>=4&&(s[1]&0xc0)==0x80&&(s[2]&0xc0)==0x80&&(s[3]&0xc0)==0x80){
        if((a==0xf0&&s[1]<0x90)||(a==0xf4&&s[1]>=0x90))return 0;
        *used=4;*cp=((uint32_t)(a&7)<<18)|((uint32_t)(s[1]&63)<<12)|((uint32_t)(s[2]&63)<<6)|(s[3]&63);return 1;
    } return 0;
}
static int utf8_validate(const unsigned char *s,size_t n) {
    size_t i=0,u=0;uint32_t cp=0;while(i<n){if(!utf8_decode_one(s+i,n-i,&u,&cp))return 0;i+=u;}return 1;
}
static size_t utf8_length(const char *s) {
    size_t n=strlen(s),i=0,u=0,count=0;uint32_t cp=0;
    while(i<n){if(!utf8_decode_one((const unsigned char *)s+i,n-i,&u,&cp))return SIZE_MAX;i+=u;count++;}return count;
}
static int string_index_value(VM *vm, const char *s, size_t index, Value *out) {
    GPGCHeader *header = gp_gc_header(s);
    if (!header || header->kind != GP_GC_STRING || header->size == 0 || !out) return 0;
    size_t bytes = header->size - 1;
    if (header->flags & GP_GC_STRING_ASCII) {
        if (index >= bytes) return 0;
        unsigned char ch = (unsigned char)s[index];
        Value cached = vm->ascii_cache[ch];
        if (cached.type != V_STRING || !cached.string) {
            char one[1] = {(char)ch};
            cached = string_value_bytes(vm, one, 1);
            if (!cached.string) return 0;
            vm->ascii_cache[ch] = cached;
        }
        *out = cached;
        return 1;
    }
    size_t offset = 0, codepoint = 0;
    while (offset < bytes) {
        size_t used = 0;
        uint32_t cp = 0;
        if (!utf8_decode_one((const unsigned char *)s + offset, bytes - offset, &used, &cp)) return 0;
        if (codepoint == index) {
            *out = string_value_bytes(vm, s + offset, used);
            return out->string != NULL;
        }
        codepoint++;
        offset += used;
    }
    return 0;
}
static int parse_json_value(Json *j, size_t *p, int depth) {
    skip_ws(j, p);
    if (depth > GP_MAX_DEPTH || *p >= j->len) { snprintf(j->error, sizeof(j->error), "JSON truncado ou aninhamento excessivo"); return -1; }
    size_t start = *p;
    char c = j->src[*p];
    if (c == '"') {
        int id = token_new(j, JT_STRING, start); if (id < 0) return -1;
        (*p)++;
        while (*p < j->len) {
            unsigned char x = (unsigned char)j->src[(*p)++];
            if (x == '\\') {
                if (*p >= j->len) {
                    snprintf(j->error, sizeof(j->error), "escape JSON truncado"); return -1;
                }
                char escape = j->src[(*p)++];
                if (escape == '"' || escape == '\\' || escape == '/' ||
                    escape == 'b' || escape == 'f' || escape == 'n' ||
                    escape == 'r' || escape == 't') continue;
                if (escape == 'u') {
                    if (j->len - *p < 4) {
                        snprintf(j->error, sizeof(j->error), "escape Unicode JSON truncado"); return -1;
                    }
                    for (int digit = 0; digit < 4; digit++) {
                        unsigned char h = (unsigned char)j->src[*p + (size_t)digit];
                        if (!((h >= '0' && h <= '9') || (h >= 'a' && h <= 'f') ||
                              (h >= 'A' && h <= 'F'))) {
                            snprintf(j->error, sizeof(j->error), "escape Unicode JSON inválido"); return -1;
                        }
                    }
                    *p += 4;
                    continue;
                }
                snprintf(j->error, sizeof(j->error), "escape JSON inválido"); return -1;
            }
            if (x == '"') {
                j->tokens[id].end = *p; j->tokens[id].next = j->count; return id;
            }
            if (x < 0x20) {
                snprintf(j->error, sizeof(j->error), "caractere de controle não escapado em string JSON"); return -1;
            }
        }
        snprintf(j->error, sizeof(j->error), "string JSON não terminada"); return -1;
    }
    if (c == '{' || c == '[') {
        int object = c == '{';
        int id = token_new(j, object ? JT_OBJECT : JT_ARRAY, start); if (id < 0) return -1;
        (*p)++; skip_ws(j, p);
        char close = object ? '}' : ']';
        if (*p < j->len && j->src[*p] == close) {
            (*p)++; j->tokens[id].end = *p; j->tokens[id].next = j->count; return id;
        }
        for (;;) {
            skip_ws(j, p);
            if (object) {
                if (*p >= j->len || j->src[*p] != '"') { snprintf(j->error, sizeof(j->error), "chave JSON inválida"); return -1; }
                if (parse_json_value(j, p, depth + 1) < 0) return -1;
                skip_ws(j, p);
                if (*p >= j->len || j->src[(*p)++] != ':') { snprintf(j->error, sizeof(j->error), "faltou ':' no objeto JSON"); return -1; }
            }
            if (parse_json_value(j, p, depth + 1) < 0) return -1;
            skip_ws(j, p);
            if (*p >= j->len) { snprintf(j->error, sizeof(j->error), "objeto/array JSON truncado"); return -1; }
            char sep = j->src[(*p)++];
            if (sep == close) break;
            if (sep != ',') { snprintf(j->error, sizeof(j->error), "separador JSON inválido"); return -1; }
        }
        j->tokens[id].end = *p; j->tokens[id].next = j->count; return id;
    }
    int id = token_new(j, JT_PRIMITIVE, start); if (id < 0) return -1;
    while (*p < j->len) {
        c = j->src[*p];
        if (c == ',' || c == ']' || c == '}' || c == ' ' || c == '\n' || c == '\r' || c == '\t') break;
        (*p)++;
    }
    if (*p == start || !valid_json_primitive(j->src+start,*p-start)) { snprintf(j->error,sizeof(j->error),"primitivo JSON inválido"); return -1; }
    j->tokens[id].end = *p; j->tokens[id].next = j->count; return id;
}
static int json_parse(Json *j) {
    size_t p = 0;
    int root = parse_json_value(j, &p, 0);
    if (root < 0) return -1;
    skip_ws(j, &p);
    if (p != j->len) { snprintf(j->error, sizeof(j->error), "dados extras após JSON"); return -1; }
    return root;
}
static int utf8_emit(char *out, uint32_t cp) {
    if (cp <= 0x7f) { out[0] = (char)cp; return 1; }
    if (cp <= 0x7ff) { out[0] = (char)(0xc0 | (cp >> 6)); out[1] = (char)(0x80 | (cp & 0x3f)); return 2; }
    if (cp <= 0xffff) { out[0] = (char)(0xe0 | (cp >> 12)); out[1] = (char)(0x80 | ((cp >> 6) & 0x3f)); out[2] = (char)(0x80 | (cp & 0x3f)); return 3; }
    out[0] = (char)(0xf0 | (cp >> 18)); out[1] = (char)(0x80 | ((cp >> 12) & 0x3f));
    out[2] = (char)(0x80 | ((cp >> 6) & 0x3f)); out[3] = (char)(0x80 | (cp & 0x3f)); return 4;
}
static char *json_string(Json *j, int id) {
    if (id < 0 || (size_t)id >= j->count || j->tokens[id].type != JT_STRING) return NULL;
    const char *s = j->src + j->tokens[id].start + 1;
    size_t n = j->tokens[id].end - j->tokens[id].start - 2;
    /* JSON unescaping never expands the UTF-8 byte length beyond the raw escaped bytes. */
    if (n == SIZE_MAX) return NULL;
    char *out = (char *)malloc(n + 1); if (!out) return NULL;
    size_t r = 0, w = 0;
    while (r < n) {
        unsigned char c = (unsigned char)s[r++];
        if (c != '\\') { out[w++] = (char)c; continue; }
        if (r >= n) break;
        char e = s[r++];
        switch (e) {
            case '"': out[w++] = '"'; break; case '\\': out[w++] = '\\'; break; case '/': out[w++] = '/'; break;
            case 'b': out[w++] = '\b'; break; case 'f': out[w++] = '\f'; break; case 'n': out[w++] = '\n'; break;
            case 'r': out[w++] = '\r'; break; case 't': out[w++] = '\t'; break;
            case 'u': {
                if (r + 4 > n) { free(out); return NULL; }
                uint32_t cp = 0;
                for (int k = 0; k < 4; k++) {
                    char h = s[r++]; cp <<= 4;
                    if (h >= '0' && h <= '9') cp |= (uint32_t)(h - '0');
                    else if (h >= 'a' && h <= 'f') cp |= (uint32_t)(h - 'a' + 10);
                    else if (h >= 'A' && h <= 'F') cp |= (uint32_t)(h - 'A' + 10);
                    else { free(out); return NULL; }
                }
                if (cp == 0) { free(out); return NULL; }
                if (cp >= 0xd800 && cp <= 0xdbff) {
                    if (r + 6 > n || s[r] != '\\' || s[r+1] != 'u') { free(out); return NULL; }
                    r += 2; uint32_t low = 0;
                    for (int k = 0; k < 4; k++) {
                        char h = s[r++]; low <<= 4;
                        if (h >= '0' && h <= '9') low |= (uint32_t)(h - '0');
                        else if (h >= 'a' && h <= 'f') low |= (uint32_t)(h - 'a' + 10);
                        else if (h >= 'A' && h <= 'F') low |= (uint32_t)(h - 'A' + 10);
                        else { free(out); return NULL; }
                    }
                    if (low < 0xdc00 || low > 0xdfff) { free(out); return NULL; }
                    cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
                } else if (cp >= 0xdc00 && cp <= 0xdfff) {
                    free(out); return NULL;
                }
                w += (size_t)utf8_emit(out + w, cp); break;
            }
            default: free(out); return NULL;
        }
    }
    out[w] = '\0'; return out;
}
static int token_eq(Json *j, int id, const char *text) {
    if (id < 0 || (size_t)id >= j->count || j->tokens[id].type != JT_STRING) return 0;
    const JToken *token = &j->tokens[id];
    const char *raw = j->src + token->start + 1;
    size_t raw_length = token->end - token->start - 2;
    size_t text_length = strlen(text);
    /* JSON property names are overwhelmingly plain ASCII; compare those
       directly and keep the decoder only for escaped keys. */
    if (raw_length == text_length && !memchr(raw, '\\', raw_length))
        return memcmp(raw, text, raw_length) == 0;
    char *decoded = json_string(j, id);
    if (!decoded) return 0;
    int same = strcmp(decoded, text) == 0;
    free(decoded);
    return same;
}
static int object_get(Json *j, int object, const char *key) {
    if (object < 0 || (size_t)object >= j->count || j->tokens[object].type != JT_OBJECT) return -1;
    size_t i = (size_t)object + 1, end = j->tokens[object].next;
    while (i < end) {
        int k = (int)i, v = k + 1;
        if (token_eq(j, k, key)) return v;
        if ((size_t)v >= j->count) break;
        i = j->tokens[v].next;
    }
    return -1;
}
static int array_len(Json *j, int array) {
    if (array < 0 || (size_t)array >= j->count || j->tokens[array].type != JT_ARRAY) return -1;
    int n = 0; size_t i = (size_t)array + 1, end = j->tokens[array].next;
    while (i < end && i < j->count) { n++; i = j->tokens[i].next; }
    return n;
}
static int array_get(Json *j, int array, int index) {
    if (index < 0 || array < 0 || (size_t)array >= j->count ||
        j->tokens[array].type != JT_ARRAY) return -1;
    size_t cursor = (size_t)array + 1;
    size_t end = j->tokens[array].next;
    for (int i = 0; i < index; i++) {
        if (cursor >= end || cursor >= j->count ||
            j->tokens[cursor].next <= cursor || j->tokens[cursor].next > end) return -1;
        cursor = j->tokens[cursor].next;
    }
    if (cursor >= end || cursor >= j->count) return -1;
    return (int)cursor;
}
static int token_is(Json *j, int id, const char *s) {
    if (id < 0 || (size_t)id >= j->count) return 0;
    JToken *t = &j->tokens[id];
    size_t n = strlen(s);
    return t->type == JT_PRIMITIVE && t->end - t->start == n && memcmp(j->src + t->start, s, n) == 0;
}
static double token_number(Json *j, int id) {
    if (id < 0 || (size_t)id >= j->count) return 0;
    return strtod(j->src + j->tokens[id].start, NULL);
}
static int token_nonnegative_integer(Json *j, int id, int maximum, int *out) {
    if (!out || maximum < 0 || id < 0 || (size_t)id >= j->count) return 0;
    const JToken *token = &j->tokens[id];
    if (token->type != JT_PRIMITIVE || token->end <= token->start) return 0;
    size_t cursor = token->start;
    int negative = 0;
    if (j->src[cursor] == '-') { negative = 1; cursor++; }
    if (cursor >= token->end) return 0;
    /* JSON integers only: reject true/false/null, fractions and exponents. */
    if (token->end - cursor > 1 && j->src[cursor] == '0') return 0;
    int value = 0;
    for (; cursor < token->end; cursor++) {
        unsigned char ch = (unsigned char)j->src[cursor];
        if (ch < '0' || ch > '9') return 0;
        int digit = (int)(ch - '0');
        if (value > maximum / 10 ||
            (value == maximum / 10 && digit > maximum % 10)) return 0;
        value = value * 10 + digit;
    }
    /* Python treats JSON -0 as the integer zero. */
    if (negative && value != 0) return 0;
    *out = value;
    return 1;
}
static char *token_text(Json *j, int id) {
    if (id < 0 || (size_t)id >= j->count) return NULL;
    if (j->tokens[id].type == JT_STRING) return json_string(j, id);
    return NULL;
}
/* Decode common plain ASCII JSON strings into caller-owned storage. The rare
   escaped/long case uses the full decoder, then immediately releases it. */
static int token_text_buffer(Json *j, int id, char *buffer, size_t capacity) {
    if (!buffer || capacity == 0 || id < 0 || (size_t)id >= j->count ||
        j->tokens[id].type != JT_STRING) return 0;
    const JToken *token = &j->tokens[id];
    if (token->end < token->start + 2) return 0;
    const char *raw = j->src + token->start + 1;
    size_t length = token->end - token->start - 2;
    int plain_ascii = length < capacity;
    if (plain_ascii) {
        for (size_t i = 0; i < length; i++) {
            unsigned char ch = (unsigned char)raw[i];
            if (ch == '\\' || ch >= 0x80 || ch == 0) {
                plain_ascii = 0;
                break;
            }
        }
    }
    if (plain_ascii) {
        if (length) memcpy(buffer, raw, length);
        buffer[length] = '\0';
        return 1;
    }
    char *decoded = json_string(j, id);
    if (!decoded) return 0;
    size_t decoded_length = strlen(decoded);
    int fits = decoded_length < capacity;
    if (fits) memcpy(buffer, decoded, decoded_length + 1);
    free(decoded);
    return fits;
}

static void vm_error(VM *vm, const char *message) {
    if (!vm->error[0]) snprintf(vm->error, sizeof(vm->error), "%s", message);
}
static int vm_tick(VM *vm) {
    vm->steps++;
    if (vm->steps > vm->max_steps) { vm_error(vm, "limite de instruções excedido"); return 0; }
    return 1;
}
static int value_matches(const char *type, Value v) {
    if (!type || !*type || strcmp(type, "null") == 0) return 1;
    if (strcmp(type, "numero") == 0) return v.type == V_NUMBER;
    if (strcmp(type, "texto") == 0) return v.type == V_STRING;
    if (strcmp(type, "logico") == 0) return v.type == V_BOOL;
    if (strcmp(type, "lista") == 0) return v.type == V_ARRAY;
    if (strncmp(type, "lista<", 6) == 0) {
        size_t n = strlen(type);
        if (v.type != V_ARRAY || !v.array || n < 8 || type[n - 1] != '>') return 0;
        char element_type[128];
        size_t element_len = n - 7;
        if (!element_len || element_len >= sizeof(element_type)) return 0;
        memcpy(element_type, type + 6, element_len);
        element_type[element_len] = '\0';
        if (v.array->element_type && strcmp(v.array->element_type, element_type) != 0) return 0;
        for (size_t i = 0; i < v.array->len; i++) {
            if (!value_matches(element_type, v.array->items[i])) return 0;
        }
        return 1;
    }
    if (strcmp(type, "vazio") == 0) return v.type == V_NULL;
    return v.type == V_STRUCT && v.object && v.object->name && strcmp(v.object->name, type) == 0;
}
static int env_find(Env *env, const char *name) {
    for (size_t i = 0; i < env->len; i++) if (strcmp(env->names[i], name) == 0) return (int)i;
    return -1;
}
static int env_reserve(Env *env) {
    if (env->len < env->cap) return 1;
    if (env->cap > SIZE_MAX / 2) return 0;
    size_t cap = env->cap ? env->cap * 2 : 16;
    if (cap > SIZE_MAX / sizeof(Value) || cap > SIZE_MAX / sizeof(char *)) return 0;

    /* Commit each successful realloc immediately. If a later allocation fails,
       env_destroy still sees valid pointers for every array. */
    char **names = (char **)realloc(env->names, cap * sizeof(char *));
    if (!names) return 0;
    env->names = names;

    Value *values = (Value *)realloc(env->values, cap * sizeof(Value));
    if (!values) return 0;
    env->values = values;

    char **types = (char **)realloc(env->types, cap * sizeof(char *));
    if (!types) return 0;
    env->types = types;

    char **elements = (char **)realloc(env->element_types, cap * sizeof(char *));
    if (!elements) return 0;
    env->element_types = elements;
    env->cap = cap;
    return 1;
}
static int env_define(Env *env, const char *name, Value value, const char *type, const char *element) {
    if (env_find(env, name) >= 0 || !env_reserve(env)) return 0;
    char *name_copy = copy_string(name);
    char *type_copy = type ? copy_string(type) : NULL;
    char *element_copy = element ? copy_string(element) : NULL;
    if (!name_copy || (type && !type_copy) || (element && !element_copy)) {
        free(name_copy);
        free(type_copy);
        free(element_copy);
        return 0;
    }
    size_t i = env->len++;
    env->names[i] = name_copy;
    env->values[i] = value;
    env->types[i] = type_copy;
    env->element_types[i] = element_copy;
    return 1;
}
static void env_destroy(Env *env) {
    if (!env) return;
    for (size_t i=0;i<env->len;i++) { free(env->names[i]); free(env->types[i]); free(env->element_types[i]); }
    free(env->names); free(env->values); free(env->types); free(env->element_types);
    memset(env,0,sizeof(*env));
}
static int array_validate_type(Array *a, const char *type) {
    if (!type || !*type || strcmp(type, "null") == 0) return 1;
    for (size_t i = 0; i < a->len; i++) if (!value_matches(type, a->items[i])) return 0;
    return 1;
}
static int env_store(Env *env, const char *name, Value value, VM *vm) {
    int i = env_find(env, name);
    if (i >= 0) {
        if (env->types[i] && !value_matches(env->types[i], value)) { vm_error(vm, "tipo incompatível na atribuição"); return 0; }
        if (env->element_types[i] && value.type == V_ARRAY && !array_validate_type(value.array, env->element_types[i])) {
            vm_error(vm, "array contém elemento de tipo incompatível"); return 0;
        }
        env->values[i] = value; return 1;
    }
    vm_error(vm, "variável não declarada para STORE"); return 0;
}
static int env_store_chain(Env *local, Env *globals, const char *name, Value value, VM *vm) {
    if (env_find(local, name) >= 0) return env_store(local, name, value, vm);
    if (local != globals && env_find(globals, name) >= 0) return env_store(globals, name, value, vm);
    vm_error(vm, "variável não definida"); return 0;
}
static int env_load(Env *local, Env *globals, const char *name, Value *out) {
    int i = env_find(local, name);
    if (i >= 0) { *out = local->values[i]; return 1; }
    if (local != globals && (i = env_find(globals, name)) >= 0) { *out = globals->values[i]; return 1; }
    return 0;
}
static int stack_push(Value **stack, size_t *len, size_t *cap, Value value) {
    if (*len == *cap) {
        if (*cap > SIZE_MAX / 2 / sizeof(Value)) return 0;
        size_t nc = *cap ? *cap * 2 : 32;
        size_t added = (nc - *cap) * sizeof(Value);
        if (added > SIZE_MAX - gp_stack_capacity_bytes) return 0;
        unsigned int previous_category = gp_current_alloc_category;
        gp_current_alloc_category = GP_ALLOC_STACK;
        Value *p = (Value *)realloc(*stack, nc * sizeof(Value));
        gp_current_alloc_category = previous_category;
        if (!p) return 0;
        gp_stack_capacity_bytes += added;
        if (gp_stack_capacity_bytes > gp_stack_peak_bytes) gp_stack_peak_bytes = gp_stack_capacity_bytes;
        *stack = p; *cap = nc;
    }
    (*stack)[(*len)++] = value; return 1;
}
static void stack_release(Value *stack, size_t cap) {
    size_t bytes = cap * sizeof(Value);
    gp_stack_capacity_bytes = gp_stack_capacity_bytes >= bytes ? gp_stack_capacity_bytes - bytes : 0;
    free(stack);
}
static int stack_pop(Value *stack, size_t *len, Value *out) {
    if (!*len) return 0; *out = stack[--(*len)]; return 1;
}
static int vm_pop(VM *vm, Value *stack, size_t *len, Value *out) {
    if (!stack_pop(stack, len, out)) { vm_error(vm, "pilha de execução vazia"); return 0; }
    return 1;
}
static int truthy(Value v) {
    if (v.type == V_BOOL) return v.boolean;
    if (v.type == V_NUMBER) return v.number != 0;
    if (v.type == V_NULL) return 0;
    return 1;
}
static void print_value(Value v) {
    switch (v.type) {
        case V_NULL: printf("nulo"); break;
        case V_NUMBER: printf("%g", v.number); break;
        case V_STRING: printf("%s", v.string ? v.string : ""); break;
        case V_BOOL: printf("%s", v.boolean ? "verdadeiro" : "falso"); break;
        case V_ARRAY:
            putchar('[');
            for (size_t i = 0; i < v.array->len; i++) { if (i) printf(", "); print_value(v.array->items[i]); }
            putchar(']'); break;
        case V_STRUCT:
            printf("%s{", v.object->name);
            for (size_t i = 0; i < v.object->len; i++) { if (i) printf(", "); printf("%s=", v.object->names[i]); print_value(v.object->values[i]); }
            putchar('}'); break;
    }
}
static int binary_op(VM *vm, const char *op, Value a, Value b, Value *out) {
    if (strcmp(op, "ADD") == 0 && a.type == V_STRING && b.type == V_STRING) {
        size_t n = strlen(a.string) + strlen(b.string) + 1;
        char *s = (char *)malloc(n); if (!s) { vm_error(vm, "memória insuficiente"); return 0; }
        snprintf(s, n, "%s%s", a.string, b.string); *out = string_value(vm, s); return vm->error[0] == '\0';
    }
    if (strcmp(op, "EQ") == 0 || strcmp(op, "NE") == 0) {
        int eq = 0;
        if (a.type == b.type) {
            if (a.type == V_NUMBER) eq = a.number == b.number;
            else if (a.type == V_STRING) eq = strcmp(a.string, b.string) == 0;
            else if (a.type == V_BOOL) eq = a.boolean == b.boolean;
            else if (a.type == V_NULL) eq = 1;
            else eq = &a == &b;
        }
        *out = bool_value(strcmp(op, "EQ") == 0 ? eq : !eq); return 1;
    }
    if (a.type == V_NUMBER && b.type == V_NUMBER) {
        double x = a.number, y = b.number;
        if (strcmp(op, "ADD") == 0) *out = number_value(x + y);
        else if (strcmp(op, "SUB") == 0) *out = number_value(x - y);
        else if (strcmp(op, "MUL") == 0) *out = number_value(x * y);
        else if (strcmp(op, "DIV") == 0) { if (y == 0) { vm_error(vm, "divisão por zero"); return 0; } *out = number_value(x / y); }
        else if (strcmp(op, "MOD") == 0) { if (y == 0) { vm_error(vm, "módulo por zero"); return 0; } *out = number_value(fmod(x, y)); }
        else if (strcmp(op, "GT") == 0) *out = bool_value(x > y);
        else if (strcmp(op, "LT") == 0) *out = bool_value(x < y);
        else if (strcmp(op, "GE") == 0) *out = bool_value(x >= y);
        else if (strcmp(op, "LE") == 0) *out = bool_value(x <= y);
        else { vm_error(vm, "operador numérico desconhecido"); return 0; }
        return 1;
    }
    if ((strcmp(op, "AND") == 0 || strcmp(op, "OR") == 0)) {
        *out = bool_value(strcmp(op, "AND") == 0 ? (truthy(a) && truthy(b)) : (truthy(a) || truthy(b))); return 1;
    }
    if ((strcmp(op, "GT") == 0 || strcmp(op, "LT") == 0 || strcmp(op, "GE") == 0 || strcmp(op, "LE") == 0) &&
        a.type == V_STRING && b.type == V_STRING) {
        int cmp = strcmp(a.string, b.string);
        if (strcmp(op, "GT") == 0) *out = bool_value(cmp > 0);
        else if (strcmp(op, "LT") == 0) *out = bool_value(cmp < 0);
        else if (strcmp(op, "GE") == 0) *out = bool_value(cmp >= 0);
        else *out = bool_value(cmp <= 0);
        return 1;
    }
    vm_error(vm, "tipos incompatíveis em operação binária"); return 0;
}
static int call_builtin(VM *vm, const char *name, Value *args, int count, Value *out) {
    if (strcmp(name, "entrada_fonte") == 0 && count == 0) {
        if (!vm->host_source) {
            vm_error(vm, "entrada_fonte indisponível: o host não forneceu uma fonte");
            return 0;
        }
        *out = string_value(vm, copy_string(vm->host_source));
        return !vm->error[0];
    }
    if (strcmp(name, "tamanho") == 0 && count == 1) {
        if (args[0].type == V_STRING) { size_t chars=utf8_length(args[0].string); if(chars==SIZE_MAX){vm_error(vm,"texto contém UTF-8 inválido");return 0;} *out=number_value((double)chars); }
        else if (args[0].type == V_ARRAY) *out = number_value((double)args[0].array->len);
        else { vm_error(vm, "tamanho exige texto ou lista"); return 0; }
        return 1;
    }
    if (strcmp(name, "unir_textos") == 0 && count == 1 && args[0].type == V_ARRAY) {
        Array *a = args[0].array;
        size_t total = 0;
        for (size_t i = 0; i < a->len; i++) {
            Value part = a->items[i];
            if (part.type != V_STRING || !part.string) {
                vm_error(vm, "unir_textos() exige que todos os itens sejam texto");
                return 0;
            }
            size_t length = strlen(part.string);
            if (length > GP_MAX_TEXT_JOIN_BYTES - total) {
                vm_error(vm, "unir_textos() excede o limite de 64 MiB");
                return 0;
            }
            total += length;
        }
        if (total == SIZE_MAX) {
            vm_error(vm, "unir_textos() excede o limite de memória");
            return 0;
        }
        char *joined = (char *)malloc(total + 1);
        if (!joined) {
            vm_error(vm, "memória insuficiente em unir_textos()");
            return 0;
        }
        size_t offset = 0;
        for (size_t i = 0; i < a->len; i++) {
            size_t length = strlen(a->items[i].string);
            if (length) memcpy(joined + offset, a->items[i].string, length);
            offset += length;
        }
        joined[total] = '\0';
        *out = string_value(vm, joined);
        return !vm->error[0];
    }
    if (strcmp(name, "adicionar") == 0 && count == 2 && args[0].type == V_ARRAY) {
        Array *a = args[0].array;
        if (a->element_type && !value_matches(a->element_type, args[1])) { vm_error(vm, "tipo incompatível ao adicionar no array"); return 0; }
        if (a->len == a->cap) {
            /* Most internal GP lists start with one child; grow from one slot to avoid wasting seven Values per list. */
            size_t nc = a->cap ? a->cap * 2 : 1;
            Value *p = (Value *)realloc(a->items, nc * sizeof(Value)); if (!p) { vm_error(vm, "memória insuficiente"); return 0; }
            a->items = p; a->cap = nc;
        }
        a->items[a->len++] = args[1]; *out = args[0]; return 1;
    }
    if (strcmp(name, "remover") == 0 && count == 2 && args[0].type == V_ARRAY && args[1].type == V_NUMBER) {
        Array *a = args[0].array; int index = (int)args[1].number;
        if (args[1].number != index || index < 0 || (size_t)index >= a->len) { vm_error(vm, "índice inválido em remover"); return 0; }
        *out = a->items[index];
        for (size_t i = (size_t)index; i + 1 < a->len; i++) a->items[i] = a->items[i + 1];
        a->len--; return 1;
    }
    vm_error(vm, "função nativa desconhecida ou argumentos inválidos"); return 0;
}

static int execute_code(VM *vm, int code, Env *local, int functions, int depth, Value *result);
static int call_function(VM *vm, const char *name, Value *args, int count, int functions, int depth, Value *out) {
    int fn = object_get(&vm->json, functions, name);
    if (fn < 0) return call_builtin(vm, name, args, count, out);
    if (depth >= GP_MAX_CALLS) { vm_error(vm, "profundidade máxima de chamadas excedida"); return 0; }
    int params = object_get(&vm->json, fn, "parameters");
    int param_count = array_len(&vm->json, params);
    if (param_count != count) { vm_error(vm, "quantidade incorreta de argumentos da função"); return 0; }
    Env frame; memset(&frame, 0, sizeof(frame));
    for (int i = 0; i < count; i++) {
        int pair = array_get(&vm->json, params, i);
        char *type = token_text(&vm->json, array_get(&vm->json, pair, 0));
        char *pname = token_text(&vm->json, array_get(&vm->json, pair, 1));
        if (!type || !pname || !value_matches(type, args[i])) {
            free(type); free(pname);
            vm_error(vm, "tipo incompatível em parâmetro da função"); env_destroy(&frame); return 0;
        }
        const char *element = NULL;
        if (!strncmp(type, "lista<", 6)) {
            size_t type_len = strlen(type);
            size_t element_len = type_len >= 7 ? type_len - 7 : 0;
            if (!element_len || type[type_len - 1] != '>' || element_len >= 128) {
                free(type); free(pname);
                vm_error(vm, "tipo de lista inválido em parâmetro da função"); env_destroy(&frame); return 0;
            }
            char element_buffer[128];
            memcpy(element_buffer, type + 6, element_len);
            element_buffer[element_len] = '\0';
            element = copy_string(element_buffer);
            if (!element) { free(type); free(pname); vm_error(vm, "memória insuficiente"); env_destroy(&frame); return 0; }
            if (args[i].array->element_type && strcmp(args[i].array->element_type, element) != 0) {
                free((void *)element); free(type); free(pname);
                vm_error(vm, "lista tipada incompatível em parâmetro da função"); env_destroy(&frame); return 0;
            }
            if (!args[i].array->element_type) args[i].array->element_type = copy_string(element);
            if (!args[i].array->element_type) { free((void *)element); free(type); free(pname); vm_error(vm, "memória insuficiente"); env_destroy(&frame); return 0; }
        }
        int defined = env_define(&frame, pname, args[i], type, element);
        free((void *)element);
        free(type);
        free(pname);
        if (!defined) { vm_error(vm, "parâmetro duplicado ou memória insuficiente"); env_destroy(&frame); return 0; }
    }
    int code_token = object_get(&vm->json, fn, "code");
    int ok = execute_code(vm, code_token, &frame, functions, depth + 1, out);
    int rt = object_get(&vm->json, fn, "return_type");
    if (ok && rt >= 0 && !token_is(&vm->json, rt, "null")) {
        char *type = token_text(&vm->json, rt);
        if (type && !value_matches(type, *out)) { vm_error(vm, "tipo de retorno incompatível"); ok = 0; }
        free(type);
    }
    env_destroy(&frame);
    return ok;
}
static int execute_code(VM *vm, int code, Env *local, int functions, int depth, Value *result) {
    if (code < 0 || vm->json.tokens[code].type != JT_ARRAY) { vm_error(vm, "bloco de bytecode inválido"); return 0; }
    int count = array_len(&vm->json, code);
    if (count < 0) { vm_error(vm, "bloco de bytecode inválido"); return 0; }
    int inline_instruction_tokens[128];
    int *instruction_tokens = inline_instruction_tokens;
    int owns_instruction_tokens = 0;
    if (count > (int)(sizeof(inline_instruction_tokens) / sizeof(inline_instruction_tokens[0]))) {
        if ((size_t)count > SIZE_MAX / sizeof(*instruction_tokens)) {
            vm_error(vm, "bloco de bytecode excede o limite de indexação"); return 0;
        }
        instruction_tokens = (int *)malloc((size_t)count * sizeof(*instruction_tokens));
        if (!instruction_tokens) { vm_error(vm, "memória insuficiente ao indexar bytecode"); return 0; }
        owns_instruction_tokens = 1;
    }
    size_t instruction_cursor = (size_t)code + 1;
    size_t instruction_end = vm->json.tokens[code].next;
    for (int i = 0; i < count; i++) {
        if (instruction_cursor >= instruction_end || instruction_cursor >= vm->json.count ||
            vm->json.tokens[instruction_cursor].next <= instruction_cursor ||
            vm->json.tokens[instruction_cursor].next > instruction_end) {
            if (owns_instruction_tokens) free(instruction_tokens);
            vm_error(vm, "índice de instruções inválido"); return 0;
        }
        instruction_tokens[i] = (int)instruction_cursor;
        instruction_cursor = vm->json.tokens[instruction_cursor].next;
    }
    if (instruction_cursor != instruction_end) {
        if (owns_instruction_tokens) free(instruction_tokens);
        vm_error(vm, "índice de instruções inconsistente"); return 0;
    }

    Value *stack = NULL; size_t sp = 0, cap = 0;
    VMRoot root = { local, &stack, &sp, vm->roots };
    vm->roots = &root;
    for (int ip = 0; ip < count && !vm->error[0]; ) {
        gp_gc_maybe_collect(vm);
        if (!vm_tick(vm)) break;
        int ins = instruction_tokens[ip++];
        int op_token = object_get(&vm->json, ins, "op");
        char op_buffer[32];
        const char *op = token_text_buffer(&vm->json, op_token, op_buffer, sizeof(op_buffer))
            ? op_buffer : NULL;
        int av = object_get(&vm->json, ins, "args");
        int argc = array_len(&vm->json, av);
        int a0 = argc > 0 ? array_get(&vm->json, av, 0) : -1;
        int a1 = argc > 1 ? array_get(&vm->json, av, 1) : -1;
        int a2 = argc > 2 ? array_get(&vm->json, av, 2) : -1;
        Value x, y, z;
        if (!op) { vm_error(vm, "opcode sem nome"); break; }
        if (strcmp(op, "CONST") == 0) {
            if (token_is(&vm->json, a0, "null")) z = null_value();
            else if (token_is(&vm->json, a0, "true")) z = bool_value(1);
            else if (token_is(&vm->json, a0, "false")) z = bool_value(0);
            else if (a0 >= 0 && vm->json.tokens[a0].type == JT_STRING) z = string_value(vm, token_text(&vm->json, a0));
            else z = number_value(token_number(&vm->json, a0));
            if (!stack_push(&stack, &sp, &cap, z)) {
                snprintf(vm->error, sizeof(vm->error),
                    "memória insuficiente na pilha (sp=%zu cap=%zu heap=%.2f MiB gerenciado=%.2f MiB buffers=%.2f MiB)",
                    sp, cap, (double)gp_heap_bytes / (1024.0 * 1024.0),
                    (double)vm->gc_bytes / (1024.0 * 1024.0),
                    (double)gp_stack_capacity_bytes / (1024.0 * 1024.0));
            }
        } else if (strcmp(op, "LOAD") == 0) {
            char *name = token_text(&vm->json, a0);
            if (!name || !env_load(local, &vm->globals, name, &z)) vm_error(vm, "variável não definida");
            free(name);
            if (!vm->error[0] && !stack_push(&stack, &sp, &cap, z)) {
                snprintf(vm->error, sizeof(vm->error),
                    "memória insuficiente na pilha (sp=%zu cap=%zu heap=%.2f MiB gerenciado=%.2f MiB buffers=%.2f MiB)",
                    sp, cap, (double)gp_heap_bytes / (1024.0 * 1024.0),
                    (double)vm->gc_bytes / (1024.0 * 1024.0),
                    (double)gp_stack_capacity_bytes / (1024.0 * 1024.0));
            }
        } else if (strcmp(op, "DECLARE") == 0) {
            char *name = token_text(&vm->json, a0);
            char *type = a1 >= 0 && !token_is(&vm->json, a1, "null") ? token_text(&vm->json, a1) : NULL;
            char *element = a2 >= 0 && !token_is(&vm->json, a2, "null") ? token_text(&vm->json, a2) : NULL;
            if (!name || !vm_pop(vm, stack, &sp, &z)) {
                free(name); free(type); free(element); break;
            }
            if (type && !value_matches(type, z)) {
                free(name); free(type); free(element);
                vm_error(vm, "tipo incompatível na declaração"); break;
            }
            if (z.type == V_ARRAY && element) {
                if (!z.array->element_type || strcmp(z.array->element_type, element) != 0) {
                    free(z.array->element_type);
                    z.array->element_type = copy_string(element);
                }
                if (!z.array->element_type || !array_validate_type(z.array, element)) {
                    free(name); free(type); free(element);
                    vm_error(vm, "elemento inválido no array tipado"); break;
                }
            }
            int declared = env_define(local, name, z, type, element);
            free(name); free(type); free(element);
            if (!declared) vm_error(vm, "identificador duplicado ou memória insuficiente");
        } else if (strcmp(op, "STORE") == 0) {
            char *name = token_text(&vm->json, a0);
            int stored = name && vm_pop(vm, stack, &sp, &z) && env_store_chain(local, &vm->globals, name, z, vm);
            free(name);
            if (!stored) break;
        } else if (strcmp(op, "POP") == 0) {
            if (!vm_pop(vm, stack, &sp, &z)) break;
        } else if (strcmp(op, "BUILD_ARRAY") == 0) {
            int n = (int)token_number(&vm->json, a0);
            if (n < 0 || (size_t)n > sp) { vm_error(vm, "pilha insuficiente para array"); break; }
            Array *arr = (Array *)gp_gc_alloc(vm, sizeof(Array), GP_GC_ARRAY);
            if (!arr) { vm_error(vm, "memória insuficiente"); break; }
            arr->len = arr->cap = (size_t)n;
            arr->items = n ? (Value *)malloc((size_t)n * sizeof(Value)) : NULL;
            if (n && !arr->items) { vm_error(vm, "memória insuficiente"); break; }
            for (int i = n - 1; i >= 0; i--) arr->items[i] = stack[--sp];
            z = null_value(); z.type = V_ARRAY; z.array = arr;
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "MAKE_TYPED_ARRAY") == 0) {
            char *element = token_text(&vm->json, a0);
            if (!vm_pop(vm, stack, &sp, &z) || z.type != V_ARRAY || !element) {
                free(element); vm_error(vm, "MAKE_TYPED_ARRAY exige array e tipo"); break;
            }
            // Match Python GPTypedArray(values, element_type): create a new
            // array container instead of changing the element type of an
            // aliased source array (for example adicionar(lista, item)).
            Array *source = z.array;
            Array *typed = (Array *)gp_gc_alloc(vm, sizeof(Array), GP_GC_ARRAY);
            if (!typed) { free(element); vm_error(vm, "memória insuficiente"); break; }
            typed->len = source->len;
            typed->cap = source->len;
            typed->items = source->len ? (Value *)malloc(source->len * sizeof(Value)) : NULL;
            typed->element_type = copy_string(element);
            if ((source->len && !typed->items) || !typed->element_type) {
                free(element);
                vm_error(vm, "memória insuficiente ao copiar array tipado"); break;
            }
            if (source->len) memcpy(typed->items, source->items, source->len * sizeof(Value));
            z.array = typed;
            int elements_match = array_validate_type(typed, typed->element_type);
            free(element);
            element = NULL;
            if (!elements_match) { vm_error(vm, "tipo de elemento inválido no array"); break; }
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "GET_INDEX") == 0) {
            if (!vm_pop(vm, stack, &sp, &y) || !vm_pop(vm, stack, &sp, &x)) break;
            if (y.type != V_NUMBER || floor(y.number) != y.number || y.number < 0) { vm_error(vm, "índice deve ser inteiro não negativo"); break; }
            size_t index = (size_t)y.number;
            if (x.type == V_ARRAY && index < x.array->len) {
                z = x.array->items[index];
            } else if (x.type == V_STRING) {
                if (!string_index_value(vm, x.string, index, &z)) {
                    vm_error(vm, "índice fora dos limites ou texto UTF-8 inválido");
                    break;
                }
            } else {
                vm_error(vm, "índice fora dos limites ou alvo inválido");
                break;
            }
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "SET_INDEX") == 0) {
            if (!vm_pop(vm, stack, &sp, &z) || !vm_pop(vm, stack, &sp, &y) || !vm_pop(vm, stack, &sp, &x)) break;
            if (x.type != V_ARRAY || y.type != V_NUMBER || floor(y.number) != y.number || y.number < 0 || (size_t)y.number >= x.array->len) { vm_error(vm, "atribuição por índice inválida"); break; }
            size_t index = (size_t)y.number;
            if (x.array->element_type && !value_matches(x.array->element_type, z)) { vm_error(vm, "tipo incompatível no array"); break; }
            x.array->items[index] = z;
        } else if (strcmp(op, "BUILD_STRUCT") == 0) {
            char *name = token_text(&vm->json, a0);
            int schema = a1, n = array_len(&vm->json, schema);
            if (!name || n < 0 || (size_t)n > sp) { free(name); vm_error(vm, "schema de estrutura inválido"); break; }
            Struct *obj = (Struct *)gp_gc_alloc(vm, sizeof(Struct), GP_GC_STRUCT);
            if (!obj) { free(name); vm_error(vm, "memória insuficiente"); break; }
            obj->name = copy_string(name);
            free(name);
            name = NULL;
            obj->len = obj->cap = (size_t)n;
            obj->names = n ? (char **)calloc((size_t)n, sizeof(char *)) : NULL;
            obj->types = n ? (char **)calloc((size_t)n, sizeof(char *)) : NULL;
            obj->values = n ? (Value *)calloc((size_t)n, sizeof(Value)) : NULL;
            if (n && (!obj->names || !obj->types || !obj->values)) { vm_error(vm, "memória insuficiente"); break; }
            for (int i = n - 1; i >= 0; i--) {
                int pair = array_get(&vm->json, schema, i);
                obj->names[i] = token_text(&vm->json, array_get(&vm->json, pair, 0));
                obj->types[i] = token_text(&vm->json, array_get(&vm->json, pair, 1));
                obj->values[i] = stack[--sp];
                if (!obj->names[i] || !value_matches(obj->types[i], obj->values[i])) { vm_error(vm, "tipo de campo de estrutura inválido"); break; }
            }
            if (vm->error[0]) break;
            z = null_value(); z.type = V_STRUCT; z.object = obj;
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "GET_FIELD") == 0 || strcmp(op, "SET_FIELD") == 0) {
            char *field = token_text(&vm->json, a0);
            if (strcmp(op, "GET_FIELD") == 0) {
                if (!field || !vm_pop(vm, stack, &sp, &x) || x.type != V_STRUCT) {
                    free(field); vm_error(vm, "acesso de campo inválido"); break;
                }
                int found = 0;
                for (size_t i = 0; i < x.object->len; i++) if (strcmp(x.object->names[i], field) == 0) { z = x.object->values[i]; found = 1; break; }
                free(field);
                if (!found || !stack_push(&stack, &sp, &cap, z)) vm_error(vm, "campo inexistente");
            } else {
                if (!field || !vm_pop(vm, stack, &sp, &z) || !vm_pop(vm, stack, &sp, &x) || x.type != V_STRUCT) {
                    free(field); vm_error(vm, "atribuição de campo inválida"); break;
                }
                int found = 0;
                for (size_t i = 0; i < x.object->len; i++) if (strcmp(x.object->names[i], field) == 0) {
                    if (!value_matches(x.object->types[i], z)) { vm_error(vm, "tipo incompatível no campo"); break; }
                    x.object->values[i] = z; found = 1; break;
                }
                free(field);
                if (!found && !vm->error[0]) vm_error(vm, "campo inexistente");
            }
        } else if (strcmp(op, "NEG") == 0 || strcmp(op, "NOT") == 0) {
            if (!vm_pop(vm, stack, &sp, &x)) break;
            if (strcmp(op, "NEG") == 0 && x.type == V_NUMBER) z = number_value(-x.number);
            else if (strcmp(op, "NOT") == 0) z = bool_value(!truthy(x));
            else { vm_error(vm, "operador unário exige tipo compatível"); break; }
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (!strcmp(op, "ADD") || !strcmp(op, "SUB") || !strcmp(op, "MUL") ||
                   !strcmp(op, "DIV") || !strcmp(op, "MOD") || !strcmp(op, "EQ") ||
                   !strcmp(op, "NE") || !strcmp(op, "GT") || !strcmp(op, "LT") ||
                   !strcmp(op, "GE") || !strcmp(op, "LE") || !strcmp(op, "AND") || !strcmp(op, "OR")) {
            if (!vm_pop(vm, stack, &sp, &y) || !vm_pop(vm, stack, &sp, &x) || !binary_op(vm, op, x, y, &z)) break;
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "PRINT") == 0) {
            int n = (int)token_number(&vm->json, a0);
            if (n < 0 || (size_t)n > sp) { vm_error(vm, "argumentos insuficientes para mostrar"); break; }
            size_t start = sp - (size_t)n;
            for (int i = 0; i < n; i++) { if (i) putchar(' '); print_value(stack[start + (size_t)i]); }
            puts(""); sp = start;
        } else if (strcmp(op, "JUMP") == 0) {
            int target = (int)token_number(&vm->json, a0);
            if (target < 0 || target > count) { vm_error(vm, "destino de salto inválido"); break; } ip = target;
        } else if (strcmp(op, "JUMP_IF_FALSE") == 0) {
            if (!vm_pop(vm, stack, &sp, &x)) break;
            if (!truthy(x)) {
                int target = (int)token_number(&vm->json, a0);
                if (target < 0 || target > count) { vm_error(vm, "destino de salto inválido"); break; } ip = target;
            }
        } else if (strcmp(op, "CALL") == 0) {
            char *name = token_text(&vm->json, a0);
            int n = (int)token_number(&vm->json, a1);
            if (!name || n < 0 || (size_t)n > sp) { free(name); vm_error(vm, "chamada GP inválida"); break; }
            Value *callargs = n ? (Value *)malloc((size_t)n * sizeof(Value)) : NULL;
            if (n && !callargs) { free(name); vm_error(vm, "memória insuficiente"); break; }
            size_t start = sp - (size_t)n;
            for (int i = 0; i < n; i++) callargs[i] = stack[start + (size_t)i];
            sp = start;
            int called = call_function(vm, name, callargs, n, functions, depth, &z);
            free(callargs);
            free(name);
            if (!called) break;
            if (!stack_push(&stack, &sp, &cap, z)) vm_error(vm, "memória insuficiente");
        } else if (strcmp(op, "RETURN") == 0) {
            *result = sp ? stack[--sp] : null_value();
            gp_gc_remove_root(vm, &root);
            stack_release(stack, cap);
            if (owns_instruction_tokens) free(instruction_tokens);
            return 1;
        } else {
            snprintf(vm->error, sizeof(vm->error), "opcode desconhecido: %s", op); break;
        }
    }
    gp_gc_remove_root(vm, &root);
    stack_release(stack, cap);
    if (owns_instruction_tokens) free(instruction_tokens);
    *result = null_value();
    return vm->error[0] == '\0';
}

static uint32_t read_u32be(const unsigned char *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
static uint16_t read_u16be(const unsigned char *p) { return (uint16_t)(((uint16_t)p[0] << 8) | p[1]); }

static int valid_opcode(const char *op) {
    static const char *ops[]={"CONST","LOAD","DECLARE","STORE","POP","BUILD_ARRAY","MAKE_TYPED_ARRAY","BUILD_STRUCT","GET_FIELD","SET_FIELD","GET_INDEX","SET_INDEX","NEG","NOT","ADD","SUB","MUL","DIV","MOD","EQ","NE","GT","LT","GE","LE","AND","OR","PRINT","JUMP","JUMP_IF_FALSE","CALL","RETURN"};
    for(size_t i=0;i<sizeof(ops)/sizeof(ops[0]);i++)if(!strcmp(op,ops[i]))return 1;return 0;
}
static int token_nonempty_string(Json *j, int id) {
    char *text = token_text(j, id);
    int valid = text != NULL && text[0] != '\0';
    free(text);
    return valid;
}
static int token_finite_json_number(Json *j, int id) {
    if (id < 0 || (size_t)id >= j->count || j->tokens[id].type != JT_PRIMITIVE) return 0;
    if (token_is(j, id, "true") || token_is(j, id, "false") || token_is(j, id, "null")) return 0;
    const JToken *token = &j->tokens[id];
    char *end = NULL;
    double value = strtod(j->src + token->start, &end);
    return end == j->src + token->end && end != j->src + token->start && isfinite(value);
}
static int compare_string_pointers(const void *left, const void *right) {
    const char *a = *(char * const *)left;
    const char *b = *(char * const *)right;
    return strcmp(a, b);
}
static int validate_json_tree_unique_keys(Json *j, int id) {
    if (id < 0 || (size_t)id >= j->count) return 0;
    const JToken *container = &j->tokens[id];
    if (container->type == JT_STRING) {
        char *decoded = token_text(j, id);
        if (!decoded) return 0;
        free(decoded);
        return 1;
    }
    if (container->type == JT_ARRAY) {
        size_t cursor = (size_t)id + 1, end = container->next;
        while (cursor < end) {
            if (cursor >= j->count || j->tokens[cursor].next <= cursor ||
                !validate_json_tree_unique_keys(j, (int)cursor)) return 0;
            cursor = j->tokens[cursor].next;
        }
        return cursor == end;
    }
    if (container->type != JT_OBJECT) return 1;

    size_t cursor = (size_t)id + 1, end = container->next, count = 0;
    while (cursor < end) {
        if (cursor >= j->count || j->tokens[cursor].type != JT_STRING) return 0;
        size_t value = cursor + 1;
        if (value >= end || j->tokens[value].next <= value ||
            j->tokens[value].next > end) return 0;
        count++;
        cursor = j->tokens[value].next;
    }
    if (cursor != end) return 0;
    char **keys = count ? (char **)calloc(count, sizeof(char *)) : NULL;
    if (count && !keys) return 0;
    cursor = (size_t)id + 1;
    int valid = 1;
    for (size_t i = 0; i < count; i++) {
        size_t value = cursor + 1;
        keys[i] = token_text(j, (int)cursor);
        if (!keys[i]) { valid = 0; break; }
        cursor = j->tokens[value].next;
    }
    if (valid && count > 1) {
        qsort(keys, count, sizeof(char *), compare_string_pointers);
        for (size_t i = 1; i < count; i++) {
            if (strcmp(keys[i - 1], keys[i]) == 0) { valid = 0; break; }
        }
    }
    for (size_t i = 0; i < count; i++) free(keys ? keys[i] : NULL);
    free(keys);
    if (!valid) return 0;

    cursor = (size_t)id + 1;
    while (cursor < end) {
        size_t value = cursor + 1;
        if (!validate_json_tree_unique_keys(j, (int)value)) return 0;
        cursor = j->tokens[value].next;
    }
    return cursor == end;
}
static int validate_unique_names(Json *j, int array, int name_position, int pair_values) {
    int count = array_len(j, array);
    if (count < 0) return 0;
    char **names = count ? (char **)calloc((size_t)count, sizeof(char *)) : NULL;
    if (count && !names) return 0;
    int valid = 1;
    for (int i = 0; i < count; i++) {
        int item = array_get(j, array, i);
        int token = pair_values ? array_get(j, item, name_position) : item;
        names[i] = token_text(j, token);
        if (!names[i] || !names[i][0]) { valid = 0; break; }
    }
    if (valid && count > 1) {
        qsort(names, (size_t)count, sizeof(char *), compare_string_pointers);
        for (int i = 1; i < count; i++) {
            if (strcmp(names[i - 1], names[i]) == 0) { valid = 0; break; }
        }
    }
    for (int i = 0; i < count; i++) free(names ? names[i] : NULL);
    free(names);
    return valid;
}
static int validate_struct_schema(Json *j, int schema) {
    int count = array_len(j, schema);
    if (count < 0) return 0;
    for (int i = 0; i < count; i++) {
        int field = array_get(j, schema, i);
        if (array_len(j, field) != 2) return 0;
        if (!token_nonempty_string(j, array_get(j, field, 0)) ||
            !token_nonempty_string(j, array_get(j, field, 1))) return 0;
    }
    return validate_unique_names(j, schema, 0, 1);
}
static int validate_function_parameters(Json *j, int parameters) {
    int count = array_len(j, parameters);
    if (count < 0) return 0;
    for (int i = 0; i < count; i++) {
        int parameter = array_get(j, parameters, i);
        if (array_len(j, parameter) != 2) return 0;
        if (!token_nonempty_string(j, array_get(j, parameter, 0)) ||
            !token_nonempty_string(j, array_get(j, parameter, 1))) return 0;
    }
    return validate_unique_names(j, parameters, 1, 1);
}
static int json_object_member_count(Json *j, int object);

static int validate_code_schema(Json *j,int code) {
    if(code<0||(size_t)code>=j->count||j->tokens[code].type!=JT_ARRAY)return 0;
    int n=array_len(j,code);
    size_t instruction_cursor=(size_t)code+1, instruction_end=j->tokens[code].next;
    for(int i=0;i<n;i++){
        if(instruction_cursor>=instruction_end||instruction_cursor>=j->count||
           j->tokens[instruction_cursor].next<=instruction_cursor||
           j->tokens[instruction_cursor].next>instruction_end)return 0;
        int ins=(int)instruction_cursor;
        instruction_cursor=j->tokens[instruction_cursor].next;
        if (j->tokens[ins].type != JT_OBJECT || json_object_member_count(j, ins) != 2)
            return 0;
        int opid=object_get(j,ins,"op"),args=object_get(j,ins,"args");
        char op_buffer[32];
        const char *op = token_text_buffer(j, opid, op_buffer, sizeof(op_buffer))
            ? op_buffer : NULL;
        int argc=array_len(j,args);
        if(!op||argc<0||!valid_opcode(op))return 0;
        int valid=1;
        if(!strcmp(op,"CONST"))valid=argc==1;
        else if(!strcmp(op,"LOAD")||!strcmp(op,"STORE")||!strcmp(op,"GET_FIELD")||!strcmp(op,"SET_FIELD")||!strcmp(op,"MAKE_TYPED_ARRAY")||!strcmp(op,"PRINT")||!strcmp(op,"JUMP")||!strcmp(op,"JUMP_IF_FALSE")||!strcmp(op,"BUILD_ARRAY"))valid=argc==1;
        else if(!strcmp(op,"DECLARE"))valid=argc==3;
        else if(!strcmp(op,"BUILD_STRUCT"))valid=argc==2&&token_nonempty_string(j,array_get(j,args,0))&&validate_struct_schema(j,array_get(j,args,1));
        else if(!strcmp(op,"CALL"))valid=argc==2;else valid=argc==0;

        if(valid&&!strcmp(op,"CONST")){
            int value=array_get(j,args,0);
            if(value<0 || (size_t)value>=j->count) valid=0;
            else if(j->tokens[value].type==JT_STRING) valid=1;
            else if(j->tokens[value].type==JT_PRIMITIVE)
                valid=token_is(j,value,"true")||token_is(j,value,"false")||token_is(j,value,"null")||token_finite_json_number(j,value);
            else valid=0;
        }
        if(valid&&(!strcmp(op,"LOAD")||!strcmp(op,"STORE")||!strcmp(op,"GET_FIELD")||!strcmp(op,"SET_FIELD")||!strcmp(op,"MAKE_TYPED_ARRAY")))
            valid=token_nonempty_string(j,array_get(j,args,0));
        if(valid&&!strcmp(op,"DECLARE")){
            int name=array_get(j,args,0),type=array_get(j,args,1),element=array_get(j,args,2);
            valid=token_nonempty_string(j,name)&&token_nonempty_string(j,type);
            if(valid&&token_eq(j,type,"lista")) valid=token_nonempty_string(j,element);
            else if(valid) valid=token_is(j,element,"null");
        }
        if(valid&&(!strcmp(op,"JUMP")||!strcmp(op,"JUMP_IF_FALSE")||!strcmp(op,"PRINT")||!strcmp(op,"BUILD_ARRAY"))){
            int operand=0, k=array_get(j,args,0);
            valid=token_nonnegative_integer(j,k,n,&operand);
        }
        if(valid&&!strcmp(op,"CALL")){
            int argument_count=0, k=array_get(j,args,1);
            valid=token_nonempty_string(j,array_get(j,args,0))&&token_nonnegative_integer(j,k,n,&argument_count);
        }
        if(!valid)return 0;
    }
    return instruction_cursor==instruction_end;
}
static int validate_ir_schema(Json *j,int root) {
    if(root<0||(size_t)root>=j->count||j->tokens[root].type!=JT_OBJECT)return 0;
    int payload_version=object_get(j,root,"bytecode_version");
    if(!token_is(j,payload_version,"2"))return 0;
    int language_version=object_get(j,root,"language_version");
    if(!token_nonempty_string(j,language_version))return 0;
    int program=object_get(j,root,"program");
    if(program<0||j->tokens[program].type!=JT_OBJECT||!token_eq(j,object_get(j,program,"format"),"GP-IR"))return 0;
    int program_fields=json_object_member_count(j,program);
    if(program_fields!=4&&program_fields!=5)return 0;
    int ir_version=object_get(j,program,"ir_version");
    if((program_fields==5 && ir_version<0) ||
       (program_fields==4 && ir_version>=0) ||
       (ir_version>=0 && !token_is(j,ir_version,"1")))return 0;
    int program_version=object_get(j,program,"version");
    char *lang=token_text(j,language_version),*prog=token_text(j,program_version);
    int versions_match=lang&&prog&&strcmp(lang,prog)==0;
    free(lang);free(prog);
    if(!versions_match)return 0;
    int main_code=object_get(j,program,"main"),functions=object_get(j,program,"functions");
    if(!validate_code_schema(j,main_code)||functions<0||j->tokens[functions].type!=JT_OBJECT)return 0;
    size_t i=(size_t)functions+1,end=j->tokens[functions].next;
    while(i<end){
        if(i>=j->count)return 0;
        int key=(int)i,fn=key+1;
        if(fn<0||(size_t)fn>=j->count||j->tokens[key].type!=JT_STRING||!token_nonempty_string(j,key)||
           j->tokens[fn].type!=JT_OBJECT||json_object_member_count(j,fn)!=3)return 0;
        int params=object_get(j,fn,"parameters"),code=object_get(j,fn,"code");
        int return_type=object_get(j,fn,"return_type");
        if(!validate_function_parameters(j,params)||!validate_code_schema(j,code))return 0;
        if(!token_is(j,return_type,"null")&&!token_nonempty_string(j,return_type))return 0;
        i=j->tokens[fn].next;
    }
    return 1;
}

static int load_bytecode(VM *vm, const char *path, int *root) {
    FILE *f = fopen(path, "rb");
    if (!f) { snprintf(vm->error, sizeof(vm->error), "não foi possível abrir bytecode: %s", strerror(errno)); return 0; }
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); vm_error(vm, "falha no tamanho do arquivo"); return 0; }
    long file_size = ftell(f);
    if (file_size < 14 || file_size > (long)(GP_MAX_PAYLOAD * 2u)) { fclose(f); vm_error(vm, "tamanho de bytecode inválido"); return 0; }
    rewind(f);
    unsigned char *file = (unsigned char *)malloc((size_t)file_size);
    if (!file) { fclose(f); vm_error(vm, "memória insuficiente"); return 0; }
    if (fread(file, 1, (size_t)file_size, f) != (size_t)file_size) { free(file); fclose(f); vm_error(vm, "falha ao ler bytecode"); return 0; }
    fclose(f);
    if (memcmp(file, "GGPC", 4) != 0 || read_u16be(file + 4) != 2) { free(file); vm_error(vm, "assinatura/versão GP bytecode não suportada (exigido v2)"); return 0; }
    uint32_t raw_size = read_u32be(file + 6), expected_crc = read_u32be(file + 10);
    if (!raw_size || raw_size > GP_MAX_PAYLOAD) { free(file); vm_error(vm, "tamanho descomprimido inválido"); return 0; }
    unsigned char *raw = (unsigned char *)malloc((size_t)raw_size + 1);
    if (!raw) { free(file); vm_error(vm, "memória insuficiente"); return 0; }
    z_stream stream;
    memset(&stream, 0, sizeof(stream));
    stream.next_in = file + 14;
    stream.avail_in = (uInt)((size_t)file_size - 14);
    stream.next_out = raw;
    stream.avail_out = (uInt)raw_size;
    int init_result = inflateInit(&stream);
    if (init_result != Z_OK) {
        free(file); free(raw); vm_error(vm, "não foi possível inicializar zlib"); return 0;
    }
    int zr = inflate(&stream, Z_FINISH);
    int exact_stream = zr == Z_STREAM_END &&
        stream.total_out == (uLong)raw_size &&
        stream.avail_in == 0;
    inflateEnd(&stream);
    free(file);
    if (!exact_stream) { free(raw); vm_error(vm, "payload zlib inválido, truncado ou com dados extras"); return 0; }
    raw[raw_size] = '\0';
    uint32_t actual_crc = (uint32_t)crc32(0L, raw, raw_size);
    if (actual_crc != expected_crc) { free(raw); vm_error(vm, "checksum GP inválido"); return 0; }
    if (!utf8_validate(raw,raw_size)) { free(raw); vm_error(vm,"payload JSON não é UTF-8 válido"); return 0; }
    vm->json.src = (const char *)raw; vm->json.len = raw_size;
    *root = json_parse(&vm->json);
    if (*root < 0) { snprintf(vm->error, sizeof(vm->error), "JSON inválido: %s", vm->json.error); return 0; }
    if (!validate_json_tree_unique_keys(&vm->json, *root)) { vm_error(vm, "chaves JSON duplicadas ou estrutura JSON inválida"); return 0; }
    if (!token_eq(&vm->json, object_get(&vm->json, *root, "magic"), "GABRIEL-GP-BYTECODE")) { vm_error(vm, "assinatura interna GP inválida"); return 0; }
    if (!token_is(&vm->json, object_get(&vm->json, *root, "bytecode_version"), "2")) { vm_error(vm, "versão interna do bytecode inválida"); return 0; }
    if (!validate_ir_schema(&vm->json,*root)) { vm_error(vm,"estrutura IR inválida ou opcode/operandos não suportados"); return 0; }
    return 1;
}
static int load_host_source_stdin(VM *vm) {
    size_t capacity = 4096;
    size_t used = 0;
    char *data = (char *)malloc(capacity + 1);
    if (!data) {
        vm_error(vm, "memória insuficiente para entrada_fonte de stdin");
        return 0;
    }
    for (;;) {
        if (used == capacity) {
            if (capacity >= GP_MAX_HOST_SOURCE_BYTES) {
                unsigned char extra = 0;
                ssize_t count;
                do { count = read(STDIN_FILENO, &extra, 1); }
                while (count < 0 && errno == EINTR);
                if (count > 0) {
                    free(data);
                    vm_error(vm, "entrada_fonte excede o limite de 16 MiB");
                    return 0;
                }
                if (count < 0) {
                    int saved_errno = errno;
                    free(data);
                    snprintf(vm->error, sizeof(vm->error),
                             "falha ao ler entrada_fonte de stdin: %s", strerror(saved_errno));
                    return 0;
                }
                break;
            }
            size_t next_capacity = capacity * 2;
            if (next_capacity > GP_MAX_HOST_SOURCE_BYTES || next_capacity < capacity)
                next_capacity = GP_MAX_HOST_SOURCE_BYTES;
            char *grown = (char *)realloc(data, next_capacity + 1);
            if (!grown) {
                free(data);
                vm_error(vm, "memória insuficiente para entrada_fonte de stdin");
                return 0;
            }
            data = grown;
            capacity = next_capacity;
        }
        ssize_t count = read(STDIN_FILENO, data + used, capacity - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) {
            int saved_errno = errno;
            free(data);
            snprintf(vm->error, sizeof(vm->error),
                     "falha ao ler entrada_fonte de stdin: %s", strerror(saved_errno));
            return 0;
        }
        if (count == 0) break;
        used += (size_t)count;
    }
    if (memchr(data, '\0', used) ||
        !utf8_validate((const unsigned char *)data, used)) {
        free(data);
        vm_error(vm, "entrada_fonte precisa conter UTF-8 válido sem NUL");
        return 0;
    }
    data[used] = '\0';
    vm->host_source = data;
    return 1;
}

static int load_host_source(VM *vm, const char *path) {
    if (strcmp(path, "-") == 0) return load_host_source_stdin(vm);
    FILE *f = fopen(path, "rb");
    if (!f) {
        snprintf(vm->error, sizeof(vm->error), "não foi possível abrir entrada_fonte: %s", strerror(errno));
        return 0;
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        vm_error(vm, "falha ao determinar tamanho de entrada_fonte");
        return 0;
    }
    long file_size = ftell(f);
    if (file_size < 0 || (unsigned long long)file_size > GP_MAX_HOST_SOURCE_BYTES) {
        fclose(f);
        vm_error(vm, "entrada_fonte excede o limite de 16 MiB");
        return 0;
    }
    rewind(f);
    size_t length = (size_t)file_size;
    char *data = (char *)malloc(length + 1);
    if (!data) {
        fclose(f);
        vm_error(vm, "memória insuficiente para entrada_fonte");
        return 0;
    }
    if (length && fread(data, 1, length, f) != length) {
        free(data);
        fclose(f);
        vm_error(vm, "falha ao ler entrada_fonte");
        return 0;
    }
    fclose(f);
    if (memchr(data, '\0', length) || !utf8_validate((const unsigned char *)data, length)) {
        free(data);
        vm_error(vm, "entrada_fonte precisa conter UTF-8 válido sem NUL");
        return 0;
    }
    data[length] = '\0';
    vm->host_source = data;
    return 1;
}

static int json_object_member_count(Json *j, int object) {
    if (object < 0 || (size_t)object >= j->count || j->tokens[object].type != JT_OBJECT) return -1;
    int count = 0;
    size_t cursor = (size_t)object + 1, end = j->tokens[object].next;
    while (cursor < end) {
        size_t value = cursor + 1;
        if (cursor >= j->count || value >= end || j->tokens[value].next <= value ||
            j->tokens[value].next > end) return -1;
        count++;
        cursor = j->tokens[value].next;
    }
    return cursor == end ? count : -1;
}

static int read_json_stdin(char **data, size_t *length, char *error, size_t error_size) {
    size_t capacity = 4096;
    size_t used = 0;
    char *buffer = (char *)malloc(capacity + 1);
    if (!buffer) {
        snprintf(error, error_size, "memória insuficiente para GP-IR de stdin");
        return 0;
    }
    for (;;) {
        if (used == capacity) {
            if (capacity >= GP_MAX_PAYLOAD) {
                unsigned char extra = 0;
                ssize_t count;
                do { count = read(STDIN_FILENO, &extra, 1); } while (count < 0 && errno == EINTR);
                if (count > 0) {
                    free(buffer);
                    snprintf(error, error_size, "GP-IR vazio ou acima de 64 MiB");
                    return 0;
                }
                if (count < 0) {
                    int saved_errno = errno;
                    free(buffer);
                    snprintf(error, error_size, "falha ao ler GP-IR de stdin: %s", strerror(saved_errno));
                    return 0;
                }
                break;
            }
            size_t next_capacity = capacity * 2;
            if (next_capacity > GP_MAX_PAYLOAD || next_capacity < capacity)
                next_capacity = GP_MAX_PAYLOAD;
            char *grown = (char *)realloc(buffer, next_capacity + 1);
            if (!grown) {
                free(buffer);
                snprintf(error, error_size, "memória insuficiente para GP-IR de stdin");
                return 0;
            }
            buffer = grown;
            capacity = next_capacity;
        }
        ssize_t count = read(STDIN_FILENO, buffer + used, capacity - used);
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) {
            int saved_errno = errno;
            free(buffer);
            snprintf(error, error_size, "falha ao ler GP-IR de stdin: %s", strerror(saved_errno));
            return 0;
        }
        if (count == 0) break;
        used += (size_t)count;
    }
    if (used == 0) {
        free(buffer);
        snprintf(error, error_size, "GP-IR vazio ou acima de 64 MiB");
        return 0;
    }
    if (memchr(buffer, '\0', used) || !utf8_validate((const unsigned char *)buffer, used)) {
        free(buffer);
        snprintf(error, error_size, "GP-IR deve ser UTF-8 válido e não conter NUL");
        return 0;
    }
    buffer[used] = '\0';
    *data = buffer;
    *length = used;
    return 1;
}

static int read_json_file(const char *path, char **data, size_t *length, char *error, size_t error_size) {
    if (strcmp(path, "-") == 0)
        return read_json_stdin(data, length, error, error_size);
    FILE *file = fopen(path, "rb");
    if (!file) {
        snprintf(error, error_size, "não foi possível abrir GP-IR: %s", strerror(errno));
        return 0;
    }
    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        snprintf(error, error_size, "falha ao determinar tamanho do GP-IR");
        return 0;
    }
    long size = ftell(file);
    if (size <= 0 || (unsigned long)size > GP_MAX_PAYLOAD) {
        fclose(file);
        snprintf(error, error_size, "GP-IR vazio ou acima de 64 MiB");
        return 0;
    }
    rewind(file);
    char *buffer = (char *)malloc((size_t)size + 1);
    if (!buffer) {
        fclose(file);
        snprintf(error, error_size, "memória insuficiente para GP-IR");
        return 0;
    }
    if (fread(buffer, 1, (size_t)size, file) != (size_t)size) {
        free(buffer);
        fclose(file);
        snprintf(error, error_size, "falha ao ler GP-IR");
        return 0;
    }
    fclose(file);
    if (memchr(buffer, '\0', (size_t)size) || !utf8_validate((const unsigned char *)buffer, (size_t)size)) {
        free(buffer);
        snprintf(error, error_size, "GP-IR deve ser UTF-8 válido e não conter NUL");
        return 0;
    }
    buffer[size] = '\0';
    *data = buffer;
    *length = (size_t)size;
    return 1;
}

static int append_bytes(char *target, size_t capacity, size_t *offset, const char *source, size_t length) {
    if (!target || !offset || (!source && length) || *offset > capacity || length > capacity - *offset) return 0;
    if (length) memcpy(target + *offset, source, length);
    *offset += length;
    return 1;
}

static int write_binary_atomic(const char *path, const unsigned char *data, size_t length, char *error, size_t error_size) {
    static const char suffix[] = ".tmp.XXXXXX";
    size_t path_length = strlen(path);
    if (path_length > SIZE_MAX - sizeof(suffix)) {
        snprintf(error, error_size, "caminho de saída muito longo");
        return 0;
    }
    char *temporary = (char *)malloc(path_length + sizeof(suffix));
    if (!temporary) {
        snprintf(error, error_size, "memória insuficiente para caminho temporário");
        return 0;
    }
    memcpy(temporary, path, path_length);
    memcpy(temporary + path_length, suffix, sizeof(suffix));

    /* mkstemp uses O_CREAT|O_EXCL and mode 0600: never follow or truncate a
       pre-existing predictable temporary path supplied by another process. */
    int fd = mkstemp(temporary);
    if (fd < 0) {
        snprintf(error, error_size, "não foi possível criar bytecode temporário: %s", strerror(errno));
        free(temporary);
        return 0;
    }

    int ok = 1;
    size_t offset = 0;
    while (offset < length) {
        ssize_t written = write(fd, data + offset, length - offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) {
            snprintf(error, error_size, "falha ao gravar bytecode temporário: %s",
                     written < 0 ? strerror(errno) : "escrita sem progresso");
            ok = 0;
            break;
        }
        offset += (size_t)written;
    }
    if (ok && fsync(fd) != 0) {
        snprintf(error, error_size, "falha ao sincronizar bytecode temporário: %s", strerror(errno));
        ok = 0;
    }
    if (close(fd) != 0) {
        if (ok) snprintf(error, error_size, "falha ao fechar bytecode temporário: %s", strerror(errno));
        ok = 0;
    }
    if (ok && rename(temporary, path) != 0) {
        snprintf(error, error_size, "não foi possível publicar bytecode: %s", strerror(errno));
        ok = 0;
    }
    if (!ok) unlink(temporary);
    free(temporary);
    return ok;
}

/* Native GGPC v2 encoder. Input is canonical GP-IR v1 emitted by the GP frontend. */
static int encode_ir_file(const char *input_path, const char *output_path) {
    char error[512] = {0};
    char *source = NULL;
    size_t source_length = 0;
    Json input;
    memset(&input, 0, sizeof(input));
    if (!read_json_file(input_path, &source, &source_length, error, sizeof(error))) {
        fprintf(stderr, "GP Native Encoder: %s\n", error);
        return 1;
    }
    input.src = source;
    input.len = source_length;
    int root = json_parse(&input);
    if (root < 0 || !validate_json_tree_unique_keys(&input, root) ||
        root < 0 || input.tokens[root].type != JT_OBJECT ||
        json_object_member_count(&input, root) != 5 ||
        !token_eq(&input, object_get(&input, root, "format"), "GP-IR") ||
        !token_is(&input, object_get(&input, root, "ir_version"), "1")) {
        snprintf(error, sizeof(error), "GP-IR v1 inválido, com chaves duplicadas ou campos inesperados");
        goto fail_input;
    }

    int version = object_get(&input, root, "version");
    int main_code = object_get(&input, root, "main");
    int functions = object_get(&input, root, "functions");
    if (version < 0 || (size_t)version >= input.count || input.tokens[version].type != JT_STRING ||
        !token_nonempty_string(&input, version) ||
        main_code < 0 || (size_t)main_code >= input.count || input.tokens[main_code].type != JT_ARRAY ||
        functions < 0 || (size_t)functions >= input.count || input.tokens[functions].type != JT_OBJECT) {
        snprintf(error, sizeof(error), "campos version/main/functions inválidos no GP-IR");
        goto fail_input;
    }

    const JToken *version_token = &input.tokens[version];
    const JToken *main_token = &input.tokens[main_code];
    const JToken *functions_token = &input.tokens[functions];
    size_t version_length = version_token->end - version_token->start;
    size_t main_length = main_token->end - main_token->start;
    size_t functions_length = functions_token->end - functions_token->start;
    char *normalized_functions = (char *)malloc(functions_length + 1);
    if (!normalized_functions) {
        snprintf(error, sizeof(error), "memória insuficiente para normalizar funções GP-IR");
        goto fail_input;
    }
    size_t normalized_length = 0;
    int normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, "{", 1);
    size_t function_cursor = (size_t)functions + 1;
    size_t function_end = functions_token->next;
    int first_function = 1;
    while (normalized_ok && function_cursor < function_end) {
        int function_key = (int)function_cursor;
        int function_value = function_key + 1;
        int parameters = object_get(&input, function_value, "parameters");
        int return_type = object_get(&input, function_value, "return_type");
        int code = object_get(&input, function_value, "code");
        if (function_value < 0 || (size_t)function_value >= input.count ||
            input.tokens[function_value].type != JT_OBJECT ||
            json_object_member_count(&input, function_value) != 3 ||
            parameters < 0 || return_type < 0 || code < 0) {
            normalized_ok = 0;
            break;
        }
        const JToken *key_token = &input.tokens[function_key];
        const JToken *parameters_token = &input.tokens[parameters];
        const JToken *return_token = &input.tokens[return_type];
        const JToken *code_token = &input.tokens[code];
        if (!first_function)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, ",", 1);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length,
                source + key_token->start, key_token->end - key_token->start);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, ":{\"parameters\":", 15);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length,
                source + parameters_token->start, parameters_token->end - parameters_token->start);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, ",\"return_type\":", 15);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length,
                source + return_token->start, return_token->end - return_token->start);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, ",\"code\":", 8);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length,
                source + code_token->start, code_token->end - code_token->start);
        if (normalized_ok)
            normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, "}", 1);
        first_function = 0;
        function_cursor = input.tokens[function_value].next;
    }
    if (normalized_ok)
        normalized_ok = append_bytes(normalized_functions, functions_length, &normalized_length, "}", 1);
    if (!normalized_ok) {
        free(normalized_functions);
        snprintf(error, sizeof(error), "estrutura de funções GP-IR inválida");
        goto fail_input;
    }
    functions_length = normalized_length;
    static const char prefix[] = "{\"magic\":\"GABRIEL-GP-BYTECODE\",\"bytecode_version\":2,\"language_version\":";
    static const char middle[] = ",\"program\":{\"format\":\"GP-IR\",\"ir_version\":1,\"version\":";
    static const char main_prefix[] = ",\"main\":";
    static const char functions_prefix[] = ",\"functions\":";
    static const char suffix[] = "}}";
    size_t raw_length = sizeof(prefix)-1 + version_length + sizeof(middle)-1 +
        version_length + sizeof(main_prefix)-1 + main_length +
        sizeof(functions_prefix)-1 + functions_length + sizeof(suffix)-1;
    if (raw_length == 0 || raw_length > GP_MAX_PAYLOAD) {
        free(normalized_functions);
        snprintf(error, sizeof(error), "payload GGPC excede 64 MiB");
        goto fail_input;
    }
    char *raw = (char *)malloc(raw_length + 1);
    if (!raw) {
        free(normalized_functions);
        snprintf(error, sizeof(error), "memória insuficiente para payload GGPC");
        goto fail_input;
    }
    size_t offset = 0;
    int assembled =
        append_bytes(raw, raw_length, &offset, prefix, sizeof(prefix)-1) &&
        append_bytes(raw, raw_length, &offset, source + version_token->start, version_length) &&
        append_bytes(raw, raw_length, &offset, middle, sizeof(middle)-1) &&
        append_bytes(raw, raw_length, &offset, source + version_token->start, version_length) &&
        append_bytes(raw, raw_length, &offset, main_prefix, sizeof(main_prefix)-1) &&
        append_bytes(raw, raw_length, &offset, source + main_token->start, main_length) &&
        append_bytes(raw, raw_length, &offset, functions_prefix, sizeof(functions_prefix)-1) &&
        append_bytes(raw, raw_length, &offset, normalized_functions, functions_length) &&
        append_bytes(raw, raw_length, &offset, suffix, sizeof(suffix)-1);
    if (!assembled || offset != raw_length) {
        free(raw);
        snprintf(error, sizeof(error), "falha ao materializar envelope GGPC v2");
        goto fail_input;
    }
    raw[raw_length] = '\0';
    free(normalized_functions);

    Json payload;
    memset(&payload, 0, sizeof(payload));
    payload.src = raw;
    payload.len = raw_length;
    int payload_root = json_parse(&payload);
    int valid = payload_root >= 0 &&
        validate_json_tree_unique_keys(&payload, payload_root) &&
        validate_ir_schema(&payload, payload_root);
    free(input.tokens);
    free(source);
    if (!valid) {
        snprintf(error, sizeof(error), "GP-IR rejeitado pelo validador nativo: %s", payload.error);
        free(payload.tokens);
        free(raw);
        fprintf(stderr, "GP Native Encoder: %s\n", error);
        return 1;
    }

    uLong compressed_capacity = compressBound((uLong)raw_length);
    if (compressed_capacity > (uLong)GP_MAX_PAYLOAD * 2u) {
        free(payload.tokens);
        free(raw);
        fprintf(stderr, "GP Native Encoder: limite do payload comprimido excedido\n");
        return 1;
    }
    unsigned char *compressed = (unsigned char *)malloc((size_t)compressed_capacity);
    if (!compressed) {
        free(payload.tokens);
        free(raw);
        fprintf(stderr, "GP Native Encoder: memória insuficiente para compressão\n");
        return 1;
    }
    uLongf compressed_length = compressed_capacity;
    int zresult = compress2(compressed, &compressed_length, (const Bytef *)raw,
                            (uLong)raw_length, Z_BEST_COMPRESSION);
    if (zresult != Z_OK || compressed_length > (uLong)GP_MAX_PAYLOAD * 2u - 14u) {
        free(compressed);
        free(payload.tokens);
        free(raw);
        fprintf(stderr, "GP Native Encoder: compressão GGPC falhou (zlib=%d)\n", zresult);
        return 1;
    }
    size_t output_length = 14u + (size_t)compressed_length;
    unsigned char *output = (unsigned char *)malloc(output_length);
    if (!output) {
        free(compressed);
        free(payload.tokens);
        free(raw);
        fprintf(stderr, "GP Native Encoder: memória insuficiente para arquivo GGPC\n");
        return 1;
    }
    memcpy(output, "GGPC", 4);
    output[4] = 0;
    output[5] = 2;
    uint32_t raw_size = (uint32_t)raw_length;
    uint32_t checksum = (uint32_t)crc32(0L, (const Bytef *)raw, (uInt)raw_length);
    output[6] = (unsigned char)(raw_size >> 24);
    output[7] = (unsigned char)(raw_size >> 16);
    output[8] = (unsigned char)(raw_size >> 8);
    output[9] = (unsigned char)raw_size;
    output[10] = (unsigned char)(checksum >> 24);
    output[11] = (unsigned char)(checksum >> 16);
    output[12] = (unsigned char)(checksum >> 8);
    output[13] = (unsigned char)checksum;
    memcpy(output + 14, compressed, (size_t)compressed_length);

    int written = write_binary_atomic(output_path, output, output_length, error, sizeof(error));
    if (written) {
        printf("GGPC v2 nativo: %zu bytes; GP-IR validado; CRC32=%08" PRIx32 "\n",
               output_length, checksum);
    } else {
        fprintf(stderr, "GP Native Encoder: %s\n", error);
    }
    free(output);
    free(compressed);
    free(payload.tokens);
    free(raw);
    return written ? 0 : 1;

fail_input:
    free(input.tokens);
    free(source);
    fprintf(stderr, "GP Native Encoder: %s\n", error);
    return 1;
}

static void usage(const char *program) {
    fprintf(stderr, "Uso: %s arquivo.gbc [--max-steps N] [--gc-threshold BYTES] [--source-input <arquivo.txt|->]\n", program);
    fprintf(stderr, "     %s --encode-ir <entrada.gp-ir.json|-> saida.gbc\n", program);
}
int main(int argc, char **argv) {
    if (argc == 4 && strcmp(argv[1], "--encode-ir") == 0)
        return encode_ir_file(argv[2], argv[3]);
    if (argc < 2) { usage(argv[0]); return 2; }
    VM vm;
    memset(&vm, 0, sizeof(vm));
    vm.max_steps = GP_DEFAULT_STEPS;
    vm.gc_min_threshold = 1024u * 1024u;
    vm.gc_threshold = vm.gc_min_threshold;
    const char *source_input_path = NULL;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--max-steps") == 0 && i + 1 < argc) {
            char *end = NULL;
            unsigned long long n = strtoull(argv[++i], &end, 10);
            if (!end || *end || n == 0) { usage(argv[0]); return 2; }
            vm.max_steps = (uint64_t)n;
        } else if (strcmp(argv[i], "--gc-threshold") == 0 && i + 1 < argc) {
            char *end = NULL;
            unsigned long long n = strtoull(argv[++i], &end, 10);
            if (!end || *end || n < 1024 || n > GP_MAX_HEAP_BYTES / 2) { usage(argv[0]); return 2; }
            vm.gc_min_threshold = (size_t)n;
            vm.gc_threshold = (size_t)n;
        } else if (strcmp(argv[i], "--source-input") == 0 && i + 1 < argc) {
            if (source_input_path) { usage(argv[0]); return 2; }
            source_input_path = argv[++i];
        } else {
            usage(argv[0]);
            return 2;
        }
    }
    if (source_input_path && !load_host_source(&vm, source_input_path)) {
        fprintf(stderr, "GP Native VM: %s\n", vm.error);
        free(vm.host_source);
        gp_gc_cleanup(&vm);
        free(vm.json.tokens);
        free((void *)vm.json.src);
        gp_memory_cleanup();
        return 1;
    }
    int root = -1;
    if (!load_bytecode(&vm, argv[1], &root)) {
        fprintf(stderr, "GP Native VM: %s\n", vm.error);
        free(vm.host_source);
        gp_gc_cleanup(&vm);
        free(vm.json.tokens);
        free((void *)vm.json.src);
        gp_memory_cleanup();
        return 1;
    }
    int program = object_get(&vm.json, root, "program");
    int main_code = object_get(&vm.json, program, "main");
    int functions = object_get(&vm.json, program, "functions");
    Value result = null_value();
    int ok = execute_code(&vm, main_code, &vm.globals, functions, 0, &result);
    if (!ok) fprintf(stderr, "GP Native VM: %s\n", vm.error);
    else fprintf(stderr, "[GP Native VM: %" PRIu64 " instruções]\n", vm.steps);
    fprintf(stderr, "[GP GC: %zu ciclos, %zu objetos liberados, %.2f MiB recuperados]\n",
            vm.gc_collections, vm.gc_freed_objects,
            (double)vm.gc_reclaimed_bytes / (1024.0 * 1024.0));
    fprintf(stderr, "[GP GC: %zu objetos gerenciados alocados]\n", vm.gc_allocated_objects);
    fprintf(stderr, "[GP memória: pico %.2f MiB / limite 256 MiB (contabilizado pelo alocador)]\n",
            (double)gp_heap_peak / (1024.0 * 1024.0));
    fprintf(stderr, "[GP pilha: pico agregado %.2f MiB em buffers de operandos]\n",
            (double)gp_stack_peak_bytes / (1024.0 * 1024.0));
    {
        size_t counts[4] = {0}, payloads[4] = {0};
        for (GPGCHeader *h = vm.gc_objects; h; h = h->next) {
            if (h->kind <= GP_GC_STRUCT) {
                counts[h->kind]++;
                payloads[h->kind] += h->size;
            }
        }
        fprintf(stderr, "[GP GC tipos: strings=%zu/%zuB arrays=%zu/%zuB structs=%zu/%zuB]\n",
                counts[GP_GC_STRING], payloads[GP_GC_STRING],
                counts[GP_GC_ARRAY], payloads[GP_GC_ARRAY],
                counts[GP_GC_STRUCT], payloads[GP_GC_STRUCT]);
    }
    gp_heap_report(stderr);
    gp_write_memory_report(getenv("GPVM_MEMORY_REPORT"), ok, &vm);
    env_destroy(&vm.globals);
    free(vm.host_source);
    gp_gc_cleanup(&vm);
    free(vm.json.tokens);
    free((void *)vm.json.src);
    gp_memory_cleanup();
    return ok ? 0 : 1;
}
