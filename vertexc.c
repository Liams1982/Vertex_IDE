/* ============================================================
   vertexc.c - Vertex Compiler with file/line tracking
   ============================================================ */

#define _POSIX_C_SOURCE 200809L

/* ================== Includes ================== */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdarg.h>
#include <stdint.h>

/* ================== Token Types ================== */

typedef enum {
    TOK_EOF = 0,
    TOK_ENTER, TOK_EXIT, TOK_RUN, TOK_STOP,
    TOK_IMPORT, TOK_CONST, TOK_TYPE, TOK_VAR,
    TOK_FUNC, TOK_PROC,
    TOK_CLASS, TOK_RECORD, TOK_EXTENDS,
    TOK_PRIVATE, TOK_PUBLIC,
    TOK_VIRTUAL, TOK_OVERRIDE,
    TOK_IF, TOK_THEN, TOK_ELSE,
    TOK_FOR, TOK_TO, TOK_DOWNTO, TOK_DO,
    TOK_WHILE, TOK_REPEAT, TOK_UNTIL,
    TOK_WITH,
    TOK_ATTEMPT, TOK_RECOVER,
    TOK_BREAK, TOK_CONTINUE,
    TOK_NEW, TOK_DISPOSE,
    TOK_ASM,
    TOK_ABSOLUTE,
    TOK_PRINT,
    TOK_INPUT,
    TOK_SIZEOF, TOK_OFFSETOF,
    TOK_ARRAY, TOK_OF, TOK_END,
    TOK_CONSTRUCTOR, TOK_DESTRUCTOR,

    /* Operators */
    TOK_ASSIGN,
    TOK_PLUS, TOK_MINUS, TOK_STAR, TOK_SLASH,
    TOK_DIV, TOK_MOD, TOK_SHL, TOK_SHR,
    TOK_AND, TOK_OR, TOK_XOR, TOK_NOT,
    TOK_EQ, TOK_NEQ, TOK_LT, TOK_GT, TOK_LE, TOK_GE,
    TOK_AT, TOK_CARET,
    TOK_LPAREN, TOK_RPAREN,
    TOK_LBRACKET, TOK_RBRACKET,
    TOK_DOT, TOK_DOTDOT,
    TOK_COLON, TOK_SEMICOLON, TOK_EQUALS, TOK_COMMA,

    TOK_TRUE, TOK_FALSE,
    TOK_IDENT, TOK_NUMBER, TOK_REAL, TOK_STRING, TOK_CHAR
} TokenType;

/* ================== AST Node Types ================== */

typedef enum {
    NODE_PROGRAM,
    NODE_IMPORT,
    NODE_CONST_DECL,
    NODE_TYPE_DECL,
    NODE_VAR_DECL,
    NODE_FUNC_DECL,
    NODE_PROC_DECL,
    NODE_CLASS_DECL,
    NODE_RECORD_DECL,
    NODE_ARRAY_TYPE,
    NODE_POINTER_TYPE,
    NODE_SIMPLE_TYPE,
    NODE_PROC_TYPE,
    NODE_FUNC_TYPE,
    NODE_MAIN_BODY,
    NODE_BLOCK,
    NODE_ASSIGN,
    NODE_PRINT,
    NODE_INPUT,
    NODE_IF,
    NODE_FOR,
    NODE_WHILE,
    NODE_REPEAT,
    NODE_WITH,
    NODE_ATTEMPT,
    NODE_BREAK,
    NODE_CONTINUE,
    NODE_RETURN,
    NODE_NEW,
    NODE_DISPOSE,
    NODE_ASM,
    NODE_BINOP,
    NODE_UNOP,
    NODE_NUMBER,
    NODE_REAL,
    NODE_STRING,
    NODE_VAR,
    NODE_ARRAY_INDEX,
    NODE_RECORD_FIELD,
    NODE_POINTER_DEREF,
    NODE_ADDRESS_OF,
    NODE_CALL,
    NODE_SIZEOF,
    NODE_OFFSETOF,
    NODE_ABSOLUTE,
    NODE_EMPTY,
    NODE_EXPR_STMT,
    NODE_IDENT
} NodeType;

/* ================== Lexer/Token Structures ================== */

typedef struct {
    const char *src;
    int pos;
    int line;           /* combined source line number */
    int orig_line;      /* original source line number (tracked via #line) */
    char *filename;     /* owned copy of current source file name */
    int filename_owned; /* 1 if filename must be freed */
} Lexer;

typedef struct {
    TokenType type;
    char *value;
    int line;           /* original source line number */
    char *filename;     /* original source file name */
} Token;

typedef struct {
    Lexer *lex;
    Token *current;
} Parser;

/* ================== AST Node ================== */

typedef struct ASTNode {
    NodeType type;
    struct ASTNode *next;
    int line;
    char *filename;
    union {
        struct { char *path; } import;
        struct { char *name; struct ASTNode *type_expr; struct ASTNode *value; } decl;
        struct { char *name; struct ASTNode *params; struct ASTNode *return_type; struct ASTNode *body; int is_method; char *class_name; } func;
        struct { char *name; struct ASTNode *extends; struct ASTNode *fields; struct ASTNode *methods; } class;
        struct { char *name; struct ASTNode *fields; } record;
        struct { struct ASTNode *low; struct ASTNode *high; struct ASTNode *base; } array_type;
        struct { struct ASTNode *base; } pointer_type;
        struct { char *name; } simple_type;
        struct { struct ASTNode *params; struct ASTNode *return_type; } proc_type;
        struct { struct ASTNode *stmt_list; } block;
        struct { struct ASTNode *lvalue; struct ASTNode *expr; } assign;
        struct { struct ASTNode *expr; } print;
        struct { struct ASTNode *var; } input_var;
        struct { struct ASTNode *cond; struct ASTNode *then_stmt; struct ASTNode *else_stmt; } if_stmt;
        struct { char *var; struct ASTNode *start; struct ASTNode *end; int downto; struct ASTNode *body; } for_stmt;
        struct { struct ASTNode *cond; struct ASTNode *body; } while_stmt;
        struct { struct ASTNode *body; struct ASTNode *cond; } repeat_stmt;
        struct { struct ASTNode *expr; struct ASTNode *body; } with_stmt;
        struct { struct ASTNode *body; char *err_var; struct ASTNode *recover; } attempt;
        struct { struct ASTNode *var; char *class_name; struct ASTNode *args; } new_stmt;
        struct { struct ASTNode *ptr; } dispose;
        struct { char *code; } asm;
        struct { struct ASTNode *left; struct ASTNode *right; int op; } binop;
        struct { struct ASTNode *operand; int op; } unop;
        struct { char *value; } number;
        struct { char *value; } string;
        struct { char *name; } var;
        struct { struct ASTNode *array_expr; struct ASTNode *index_expr; } array_index;
        struct { struct ASTNode *record_expr; char *field; } record_field;
        struct { struct ASTNode *ptr_expr; } pointer_deref;
        struct { struct ASTNode *expr; } address_of;
        struct { struct ASTNode *func; struct ASTNode *args; } call;
        struct { struct ASTNode *type_expr; char *type_name; char *field_name; } size_offset;
        struct { struct ASTNode *addr_expr; } absolute;
        struct { struct ASTNode *expr; } return_stmt;
        struct { struct ASTNode *expr; } expr_stmt;
    } data;
} ASTNode;

/* ================== Global State ================== */

static int error_count = 0;

/* ================== Helpers ================== */

static ASTNode *new_node(NodeType type, int line, const char *filename) {
    ASTNode *n = calloc(1, sizeof(ASTNode));
    n->type = type;
    n->line = line;
    n->filename = filename ? strdup(filename) : NULL;
    return n;
}

static char *my_strndup(const char *s, size_t n) {
    size_t len = strnlen(s, n);
    char *d = malloc(len + 1);
    if (!d) return NULL;
    memcpy(d, s, len);
    d[len] = '\0';
    return d;
}


/* Escape \ and " for use inside #line "..." directives */
static char *escape_for_line_directive(const char *path) {
    if (!path) path = "";
    size_t n = 0;
    for (const char *s = path; *s; s++)
        n += (*s == '\\' || *s == '"') ? 2 : 1;
    char *out = malloc(n + 1);
    if (!out) return NULL;
    char *d = out;
    for (const char *s = path; *s; s++) {
        if (*s == '\\' || *s == '"') *d++ = '\\';
        *d++ = *s;
    }
    *d = '\0';
    return out;
}

/* ================== Lexer ================== */

static void skip_whitespace_and_comments(Lexer *lex) {
    while (lex->src[lex->pos]) {
        char c = lex->src[lex->pos];
        if (isspace((unsigned char)c)) {
            if (c == '\n') {
                lex->line++;
                lex->orig_line++;
            }
            lex->pos++;
        } else if (c == '{') {
            lex->pos++;
            while (lex->src[lex->pos] && lex->src[lex->pos] != '}') {
                if (lex->src[lex->pos] == '\n') {
                    lex->line++;
                    lex->orig_line++;
                }
                lex->pos++;
            }
            if (lex->src[lex->pos] == '}') lex->pos++;
        } else if (c == '/' && lex->src[lex->pos+1] == '/') {
            lex->pos += 2;
            while (lex->src[lex->pos] && lex->src[lex->pos] != '\n') lex->pos++;
        } else {
            break;
        }
    }
}

static char *read_ident(Lexer *lex) {
    int start = lex->pos;
    while (isalnum((unsigned char)lex->src[lex->pos]) || lex->src[lex->pos] == '_')
        lex->pos++;
    return my_strndup(lex->src + start, (size_t)(lex->pos - start));
}

static char *read_number(Lexer *lex) {
    int start = lex->pos;
    while (isdigit((unsigned char)lex->src[lex->pos])) lex->pos++;
    if (lex->src[lex->pos] == '.' && isdigit((unsigned char)lex->src[lex->pos+1])) {
        lex->pos++;
        while (isdigit((unsigned char)lex->src[lex->pos])) lex->pos++;
        return my_strndup(lex->src + start, (size_t)(lex->pos - start));
    }
    return my_strndup(lex->src + start, (size_t)(lex->pos - start));
}

static char *read_string_with_escapes(Lexer *lex) {
    lex->pos++;
    char *result = NULL;
    size_t len = 0;
    while (lex->src[lex->pos] && lex->src[lex->pos] != '"') {
        char c = lex->src[lex->pos];
        if (c == '\\') {
            lex->pos++;
            if (lex->src[lex->pos] == '"') {
                result = realloc(result, len + 2);
                result[len++] = '"';
                result[len] = '\0';
                lex->pos++;
            } else if (lex->src[lex->pos] == '\\') {
                result = realloc(result, len + 2);
                result[len++] = '\\';
                result[len] = '\0';
                lex->pos++;
            } else if (lex->src[lex->pos] == 'n') {
                result = realloc(result, len + 2);
                result[len++] = '\n';
                result[len] = '\0';
                lex->pos++;
            } else if (lex->src[lex->pos] == 't') {
                result = realloc(result, len + 2);
                result[len++] = '\t';
                result[len] = '\0';
                lex->pos++;
            } else {
                result = realloc(result, len + 3);
                result[len++] = '\\';
                result[len++] = lex->src[lex->pos];
                result[len] = '\0';
                lex->pos++;
            }
        } else {
            result = realloc(result, len + 2);
            result[len++] = c;
            result[len] = '\0';
            lex->pos++;
        }
    }
    if (lex->src[lex->pos] == '"') lex->pos++;
    if (!result) {
        result = malloc(1);
        result[0] = '\0';
    }
    return result;
}

static Token *make_token(TokenType type, char *value, int line, const char *filename) {
    Token *t = malloc(sizeof(Token));
    t->type = type;
    t->value = value;
    t->line = line;
    t->filename = filename ? strdup(filename) : NULL;
    return t;
}

/* Handle #line directive: update lexer's file and line */
static void handle_line_directive(Lexer *lex) {
    /* format: #line <number> "filename" */
    lex->pos++; /* skip '#' */
    while (isspace((unsigned char)lex->src[lex->pos])) lex->pos++;
    if (strncmp(lex->src + lex->pos, "line", 4) != 0) {
        /* Not a line directive — leave '#' for the unexpected-char path */
        lex->pos--;
        return;
    }
    lex->pos += 4;
    while (isspace((unsigned char)lex->src[lex->pos])) lex->pos++;
    int num = 0;
    while (isdigit((unsigned char)lex->src[lex->pos])) {
        num = num * 10 + (lex->src[lex->pos] - '0');
        lex->pos++;
    }
    while (isspace((unsigned char)lex->src[lex->pos])) lex->pos++;
    if (lex->src[lex->pos] == '"') {
        lex->pos++;
        int start = lex->pos;
        while (lex->src[lex->pos] && lex->src[lex->pos] != '"') lex->pos++;
        int len = lex->pos - start;
        /* Unescape \ and \" inside the directive string */
        {
            char *raw = my_strndup(lex->src + start, len);
            size_t cap = (size_t)len + 1;
            char *fname = malloc(cap);
            size_t di = 0;
            for (size_t si = 0; raw && raw[si]; si++) {
                if (raw[si] == '\\' && raw[si + 1]) {
                    si++;
                    fname[di++] = raw[si];
                } else {
                    fname[di++] = raw[si];
                }
            }
            if (fname) fname[di] = '\0';
            free(raw);
            if (lex->src[lex->pos] == '"') lex->pos++;
        if (lex->filename_owned && lex->filename)
            free(lex->filename);
        lex->filename = fname;
        lex->filename_owned = 1;
        /* #line N → next source line is N (do not pre-decrement) */
        lex->orig_line = num;
    }
    while (lex->src[lex->pos] && lex->src[lex->pos] != '\n') lex->pos++;
    if (lex->src[lex->pos] == '\n') {
        lex->pos++;
        lex->line++;
        /* do NOT do lex->orig_line++ here */
    }
}
}

static Token *get_token(Lexer *lex) {
    /* handle BOM */
    if (lex->pos == 0) {
        const unsigned char *s = (const unsigned char *)lex->src;
        if (s[0] == 0xEF && s[1] == 0xBB && s[2] == 0xBF) lex->pos += 3;
        else if (s[0] == 0xFF && s[1] == 0xFE) {
            fprintf(stderr, "Error: Source file is UTF-16 LE.\n");
            exit(1);
        }
        else if (s[0] == 0xFE && s[1] == 0xFF) {
            fprintf(stderr, "Error: Source file is UTF-16 BE.\n");
            exit(1);
        }
        else if ((s[0] == 0xFF && s[1] == 0xFE && s[2] == 0x00 && s[3] == 0x00) ||
                 (s[0] == 0x00 && s[1] == 0x00 && s[2] == 0xFE && s[3] == 0xFF)) {
            fprintf(stderr, "Error: Source file is UTF-32.\n");
            exit(1);
        }
    }

    skip_whitespace_and_comments(lex);
    if (!lex->src[lex->pos]) return make_token(TOK_EOF, NULL, lex->orig_line, lex->filename);

    char c = lex->src[lex->pos];
    int orig_line = lex->orig_line;
    const char *filename = lex->filename;

    /* Check for line directive */
    if (c == '#' && strncmp(lex->src + lex->pos, "#line", 5) == 0) {
        handle_line_directive(lex);
        return get_token(lex);
    }

    switch (c) {
        case '+': lex->pos++; return make_token(TOK_PLUS, NULL, orig_line, filename);
        case '-': lex->pos++; return make_token(TOK_MINUS, NULL, orig_line, filename);
        case '*': lex->pos++; return make_token(TOK_STAR, NULL, orig_line, filename);
        case '/': lex->pos++; return make_token(TOK_SLASH, NULL, orig_line, filename);
        case '(': lex->pos++; return make_token(TOK_LPAREN, NULL, orig_line, filename);
        case ')': lex->pos++; return make_token(TOK_RPAREN, NULL, orig_line, filename);
        case '[': lex->pos++; return make_token(TOK_LBRACKET, NULL, orig_line, filename);
        case ']': lex->pos++; return make_token(TOK_RBRACKET, NULL, orig_line, filename);
        case ':': lex->pos++; return make_token(TOK_COLON, NULL, orig_line, filename);
        case ';': lex->pos++; return make_token(TOK_SEMICOLON, NULL, orig_line, filename);
        case ',': lex->pos++; return make_token(TOK_COMMA, NULL, orig_line, filename);
        case '=': lex->pos++; return make_token(TOK_EQUALS, NULL, orig_line, filename);
        case '@': lex->pos++; return make_token(TOK_AT, NULL, orig_line, filename);
        case '^': lex->pos++; return make_token(TOK_CARET, NULL, orig_line, filename);
        case '"': {
            char *s = read_string_with_escapes(lex);
            return make_token(TOK_STRING, s, orig_line, filename);
        }
        case '<':
            if (lex->src[lex->pos+1] == '-') { lex->pos += 2; return make_token(TOK_ASSIGN, NULL, orig_line, filename); }
            else if (lex->src[lex->pos+1] == '>') { lex->pos += 2; return make_token(TOK_NEQ, NULL, orig_line, filename); }
            else if (lex->src[lex->pos+1] == '=') { lex->pos += 2; return make_token(TOK_LE, NULL, orig_line, filename); }
            else { lex->pos++; return make_token(TOK_LT, NULL, orig_line, filename); }
        case '>':
            if (lex->src[lex->pos+1] == '=') { lex->pos += 2; return make_token(TOK_GE, NULL, orig_line, filename); }
            else { lex->pos++; return make_token(TOK_GT, NULL, orig_line, filename); }
        case '.':
            if (lex->src[lex->pos+1] == '.') { lex->pos += 2; return make_token(TOK_DOTDOT, NULL, orig_line, filename); }
            else { lex->pos++; return make_token(TOK_DOT, NULL, orig_line, filename); }
        default:
            if (isalpha((unsigned char)c) || c == '_') {
                char *ident = read_ident(lex);
#define KW(w,t) if (strcmp(ident, w)==0) { free(ident); return make_token(t, NULL, orig_line, filename); }
                KW("Enter", TOK_ENTER) KW("Exit", TOK_EXIT) KW("Run", TOK_RUN) KW("Stop", TOK_STOP)
                KW("Import", TOK_IMPORT) KW("Const", TOK_CONST) KW("Type", TOK_TYPE) KW("Var", TOK_VAR)
                KW("Func", TOK_FUNC) KW("Proc", TOK_PROC) KW("Class", TOK_CLASS) KW("Record", TOK_RECORD)
                KW("Extends", TOK_EXTENDS) KW("Private", TOK_PRIVATE) KW("Public", TOK_PUBLIC)
                KW("Virtual", TOK_VIRTUAL) KW("Override", TOK_OVERRIDE)
                KW("If", TOK_IF) KW("Then", TOK_THEN) KW("Else", TOK_ELSE)
                KW("For", TOK_FOR) KW("To", TOK_TO) KW("Downto", TOK_DOWNTO) KW("Do", TOK_DO)
                KW("While", TOK_WHILE) KW("Repeat", TOK_REPEAT) KW("Until", TOK_UNTIL)
                KW("With", TOK_WITH) KW("Attempt", TOK_ATTEMPT) KW("Recover", TOK_RECOVER)
                KW("Break", TOK_BREAK) KW("Continue", TOK_CONTINUE)
                KW("New", TOK_NEW) KW("Dispose", TOK_DISPOSE)
                KW("Asm", TOK_ASM) KW("Absolute", TOK_ABSOLUTE)
                KW("Print", TOK_PRINT)
                KW("Input", TOK_INPUT)
                KW("SizeOf", TOK_SIZEOF) KW("OffsetOf", TOK_OFFSETOF)
                KW("Array", TOK_ARRAY) KW("Of", TOK_OF) KW("End", TOK_END)
                KW("And", TOK_AND) KW("Or", TOK_OR) KW("Xor", TOK_XOR) KW("Not", TOK_NOT)
                KW("Div", TOK_DIV) KW("Mod", TOK_MOD) KW("Shl", TOK_SHL) KW("Shr", TOK_SHR)
                KW("Constructor", TOK_CONSTRUCTOR) KW("Destructor", TOK_DESTRUCTOR)
                KW("True", TOK_TRUE) KW("False", TOK_FALSE)
#undef KW
                return make_token(TOK_IDENT, ident, orig_line, filename);
            } else if (isdigit((unsigned char)c)) {
                char *num = read_number(lex);
                Token *t = make_token(strchr(num, '.') ? TOK_REAL : TOK_NUMBER, num, orig_line, filename);
                return t;
            } else {
                fprintf(stderr, "Unexpected character '%c' (0x%02X) at line %d in %s\n",
                        (c >= 32 && c < 127) ? c : '?', (unsigned char)c, orig_line, filename ? filename : "<unknown>");
                exit(1);
            }
    }
}

static void free_token(Token *tok) {
    if (!tok) return;
    free(tok->value);
    tok->value = NULL;
    free(tok->filename);
    tok->filename = NULL;
    free(tok);
}

/* ================== Diagnostics ================== */

static const char *token_name(TokenType t) {
    switch (t) {
        case TOK_EOF: return "end of file";
        case TOK_ENTER: return "Enter"; case TOK_EXIT: return "Exit";
        case TOK_RUN: return "Run"; case TOK_STOP: return "Stop";
        case TOK_IMPORT: return "Import"; case TOK_CONST: return "Const";
        case TOK_TYPE: return "Type"; case TOK_VAR: return "Var";
        case TOK_FUNC: return "Func"; case TOK_PROC: return "Proc";
        case TOK_CLASS: return "Class"; case TOK_RECORD: return "Record";
        case TOK_EXTENDS: return "Extends";
        case TOK_PRIVATE: return "Private"; case TOK_PUBLIC: return "Public";
        case TOK_IF: return "If"; case TOK_THEN: return "Then"; case TOK_ELSE: return "Else";
        case TOK_FOR: return "For"; case TOK_TO: return "To"; case TOK_DOWNTO: return "Downto";
        case TOK_DO: return "Do"; case TOK_WHILE: return "While";
        case TOK_REPEAT: return "Repeat"; case TOK_UNTIL: return "Until";
        case TOK_WITH: return "With"; case TOK_ATTEMPT: return "Attempt";
        case TOK_RECOVER: return "Recover";
        case TOK_BREAK: return "Break"; case TOK_CONTINUE: return "Continue";
        case TOK_NEW: return "New"; case TOK_DISPOSE: return "Dispose";
        case TOK_PRINT: return "Print"; case TOK_INPUT: return "Input";
        case TOK_SIZEOF: return "SizeOf"; case TOK_ARRAY: return "Array";
        case TOK_OF: return "Of"; case TOK_END: return "End";
        case TOK_AND: return "And"; case TOK_OR: return "Or"; case TOK_NOT: return "Not";
        case TOK_TRUE: return "True"; case TOK_FALSE: return "False";
        case TOK_ASSIGN: return "'<-'"; case TOK_EQUALS: return "'='";
        case TOK_EQ: return "'='"; case TOK_NEQ: return "'<>'";
        case TOK_LT: return "'<'"; case TOK_GT: return "'>'";
        case TOK_LE: return "'<='"; case TOK_GE: return "'>='";
        case TOK_PLUS: return "'+'"; case TOK_MINUS: return "'-'";
        case TOK_STAR: return "'*'"; case TOK_SLASH: return "'/'";
        case TOK_LPAREN: return "'('"; case TOK_RPAREN: return "')'";
        case TOK_LBRACKET: return "'['"; case TOK_RBRACKET: return "']'";
        case TOK_DOT: return "'.'"; case TOK_DOTDOT: return "'..'";
        case TOK_COLON: return "':'"; case TOK_SEMICOLON: return "';'";
        case TOK_COMMA: return "','"; case TOK_AT: return "'@'";
        case TOK_CARET: return "'^'";
        case TOK_IDENT: return "identifier";
        case TOK_NUMBER: return "number"; case TOK_REAL: return "real number";
        case TOK_STRING: return "string"; case TOK_CHAR: return "character";
        case TOK_CONSTRUCTOR: return "Constructor";
        case TOK_DESTRUCTOR: return "Destructor";
        default: return "token";
    }
}

/* ================== Error Handling ================== */

static void parse_error(Parser *p, const char *fmt, ...) {
    error_count++;
    if (error_count > 40) {
        fprintf(stderr, "Too many errors; stopping.\n");
        exit(1);
    }
    if (p->current) {
        fprintf(stderr, "Error in %s at line %d: ",
                p->current->filename ? p->current->filename : "<unknown>",
                p->current->line);
        va_list ap;
        va_start(ap, fmt);
        vfprintf(stderr, fmt, ap);
        va_end(ap);
        if (p->current->type == TOK_IDENT && p->current->value)
            fprintf(stderr, " (found identifier '%s')", p->current->value);
        else if (p->current->type == TOK_STRING && p->current->value)
            fprintf(stderr, " (found string \"%s\")", p->current->value);
        else if (p->current->type == TOK_NUMBER && p->current->value)
            fprintf(stderr, " (found number %s)", p->current->value);
        else
            fprintf(stderr, " (found %s)", token_name(p->current->type));
        fprintf(stderr, "\n");
    } else {
        fprintf(stderr, "Error: ");
        va_list ap;
        va_start(ap, fmt);
        vfprintf(stderr, fmt, ap);
        va_end(ap);
        fprintf(stderr, "\n");
    }
}

/* ================== Parser ================== */

static void advance(Parser *p) {
    free_token(p->current);
    p->current = get_token(p->lex);
}

static void expect(Parser *p, TokenType type, const char *msg) {
    if (p->current->type != type) {
        parse_error(p, "expected %s", msg);
        while (p->current->type != TOK_EOF &&
               p->current->type != TOK_SEMICOLON &&
               p->current->type != TOK_RUN &&
               p->current->type != TOK_STOP &&
               p->current->type != TOK_END) {
            advance(p);
        }
        if (p->current->type == TOK_SEMICOLON ||
            p->current->type == TOK_RUN ||
            p->current->type == TOK_STOP ||
            p->current->type == TOK_END) {
            advance(p);
        }
    } else {
        advance(p);
    }
}

static int match(Parser *p, TokenType type) {
    if (p->current->type == type) {
        advance(p);
        return 1;
    }
    return 0;
}

static void expect_stmt_end(Parser *p) {
    if (p->current->type == TOK_ELSE)
        return;
    expect(p, TOK_SEMICOLON, "';'");
}

/* Forward declarations */
static ASTNode *parse_block(Parser *p);
static ASTNode *parse_statement(Parser *p);
static ASTNode *parse_expression(Parser *p);
static ASTNode *parse_type(Parser *p);
static ASTNode *parse_primary(Parser *p);
static ASTNode *parse_binop(Parser *p, int min_prec);
static ASTNode *parse_class_body(Parser *p, char *class_name);

/* ---------- parse_class_body ---------- */
static ASTNode *parse_class_body(Parser *p, char *class_name) {
    ASTNode *fields = NULL, *methods = NULL, *tail_f = NULL, *tail_m = NULL;

    while (p->current->type != TOK_END) {
        if (p->current->type == TOK_PRIVATE || p->current->type == TOK_PUBLIC ||
            p->current->type == TOK_VIRTUAL || p->current->type == TOK_OVERRIDE) {
            advance(p);
            continue;
        }
        if (p->current->type == TOK_IDENT &&
            (strcmp(p->current->value, "Published") == 0 ||
             strcmp(p->current->value, "published") == 0 ||
             strcmp(p->current->value, "Protected") == 0 ||
             strcmp(p->current->value, "protected") == 0 ||
             strcmp(p->current->value, "strict") == 0)) {
            advance(p);
            continue;
        }

        /* Property Name: Type [read X] [write Y]; → store as field */
        if (p->current->type == TOK_IDENT &&
            (strcmp(p->current->value, "Property") == 0 ||
             strcmp(p->current->value, "property") == 0)) {
            advance(p);
            if (p->current->type != TOK_IDENT) {
                parse_error(p, "expected property name after Property");
                continue;
            }
            char *name = strdup(p->current->value);
            advance(p);
            expect(p, TOK_COLON, "':'");
            ASTNode *type = parse_type(p);
            while (p->current->type != TOK_SEMICOLON &&
                   p->current->type != TOK_EOF &&
                   p->current->type != TOK_END) {
                advance(p);
            }
            expect(p, TOK_SEMICOLON, "';'");
            ASTNode *field = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
            field->data.decl.name = name;
            field->data.decl.type_expr = type;
            if (!fields) fields = field;
            else tail_f->next = field;
            tail_f = field;
            continue;
        }

        if (p->current->type == TOK_IDENT) {
            char *name = strdup(p->current->value);
            advance(p);
            if (p->current->type == TOK_COLON) {
                advance(p);
                ASTNode *type = parse_type(p);
                if (p->current->type == TOK_EQUALS) {
                    advance(p);
                    parse_expression(p);
                }
                expect(p, TOK_SEMICOLON, "';'");
                while (p->current->type == TOK_SEMICOLON) advance(p);

                ASTNode *field = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                field->data.decl.name = name;
                field->data.decl.type_expr = type;

                if (!fields) fields = field;
                else tail_f->next = field;
                tail_f = field;
            } else {
                parse_error(p, "unexpected '%s' in class '%s' (expected field 'name: Type;' or method)", name, class_name);
                free(name);
                advance(p);
                continue;
            }
        }
        else if (p->current->type == TOK_FUNC || p->current->type == TOK_PROC ||
                 p->current->type == TOK_CONSTRUCTOR || p->current->type == TOK_DESTRUCTOR) {

            int is_func = (p->current->type == TOK_FUNC);
            int is_ctor = (p->current->type == TOK_CONSTRUCTOR);
            int is_dtor = (p->current->type == TOK_DESTRUCTOR);
            advance(p);

            while (p->current->type == TOK_VIRTUAL || p->current->type == TOK_OVERRIDE)
                advance(p);

            char *name = NULL;
            if (p->current->type == TOK_IDENT) {
                name = strdup(p->current->value);
                advance(p);
            } else if (is_ctor) {
                name = strdup("Create");
            } else if (is_dtor) {
                name = strdup("Destroy");
            } else {
                parse_error(p, "expected method name in class '%s'", class_name);
                break;
            }

            ASTNode *params = NULL, *param_tail = NULL;
            if (p->current->type == TOK_LPAREN) {
                advance(p);
                while (p->current->type != TOK_RPAREN) {
                    int is_ref = 0;
                    if (match(p, TOK_VAR)) is_ref = 1;
                    if (p->current->type != TOK_IDENT) {
                        parse_error(p, "expected parameter name");
                        break;
                    }
                    char *pname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *ptype = parse_type(p);
                    ASTNode *param = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    param->data.decl.name = pname;
                    param->data.decl.type_expr = ptype;
                    param->data.decl.value = (ASTNode*)(intptr_t)is_ref;
                    if (!params) params = param;
                    else param_tail->next = param;
                    param_tail = param;
                    if (p->current->type == TOK_SEMICOLON) advance(p);
                    else break;
                }
                expect(p, TOK_RPAREN, "')'");
            }

            ASTNode *ret_type = NULL;
            if (is_func) {
                expect(p, TOK_COLON, "':'");
                ret_type = parse_type(p);
            }
            while (p->current->type == TOK_VIRTUAL || p->current->type == TOK_OVERRIDE)
                advance(p);
            expect(p, TOK_SEMICOLON, "';'");
            while (p->current->type == TOK_VIRTUAL || p->current->type == TOK_OVERRIDE ||
                   p->current->type == TOK_SEMICOLON) {
                advance(p);
            }

            ASTNode *method = new_node(is_func ? NODE_FUNC_DECL : NODE_PROC_DECL, p->current->line, p->current->filename);
            if (is_ctor) {
                method->data.func.name = strdup("Constructor");
                free(name);
                name = NULL;
            } else if (is_dtor) {
                method->data.func.name = strdup("Destructor");
                free(name);
                name = NULL;
            } else {
                method->data.func.name = name;
                name = NULL;
            }
            method->data.func.params = params;
            method->data.func.return_type = ret_type;
            method->data.func.body = NULL;
            method->data.func.is_method = 1;
            method->data.func.class_name = strdup(class_name);

            if (!methods) methods = method;
            else tail_m->next = method;
            tail_m = method;
        }
        else {
            parse_error(p, "unexpected token in class body of '%s' (found %s)", class_name, token_name(p->current->type));
            advance(p);
        }
    }

    expect(p, TOK_END, "End");

    ASTNode *class_node = new_node(NODE_CLASS_DECL, p->current->line, p->current->filename);
    class_node->data.class.name = strdup(class_name);
    class_node->data.class.fields = fields;
    class_node->data.class.methods = methods;
    class_node->data.class.extends = NULL;
    return class_node;
}

/* ---------- parse_type ---------- */
static ASTNode *parse_type(Parser *p) {
    ASTNode *type = NULL;
    switch (p->current->type) {
        case TOK_ARRAY: {
            advance(p);
            expect(p, TOK_LBRACKET, "'['");
            ASTNode *low = parse_expression(p);
            expect(p, TOK_DOTDOT, "'..'");
            ASTNode *high = parse_expression(p);
            expect(p, TOK_RBRACKET, "']'");
            if (match(p, TOK_OF)) { }
            ASTNode *base = parse_type(p);
            type = new_node(NODE_ARRAY_TYPE, p->current->line, p->current->filename);
            type->data.array_type.low = low;
            type->data.array_type.high = high;
            type->data.array_type.base = base;
            break;
        }
        case TOK_CARET: {
            advance(p);
            ASTNode *base = parse_type(p);
            type = new_node(NODE_POINTER_TYPE, p->current->line, p->current->filename);
            type->data.pointer_type.base = base;
            break;
        }
        case TOK_RECORD: {
            advance(p);
            ASTNode *fields = NULL, *tail = NULL;
            while (p->current->type != TOK_END) {
                char *fname = strdup(p->current->value);
                advance(p);
                expect(p, TOK_COLON, "':'");
                ASTNode *ftype = parse_type(p);
                expect(p, TOK_SEMICOLON, "';'");
                ASTNode *field = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                field->data.decl.name = fname;
                field->data.decl.type_expr = ftype;
                if (!fields) fields = field;
                else tail->next = field;
                tail = field;
            }
            expect(p, TOK_END, "End");
            type = new_node(NODE_RECORD_DECL, p->current->line, p->current->filename);
            type->data.record.fields = fields;
            break;
        }
        case TOK_CLASS: {
            advance(p);
            char *name = strdup("AnonymousClass");
            if (p->current->type == TOK_IDENT) {
                free(name);
                name = strdup(p->current->value);
                advance(p);
            }
            if (match(p, TOK_EXTENDS)) {
                expect(p, TOK_IDENT, "identifier");
            } else if (p->current->type == TOK_LPAREN) {
                advance(p);
                while (p->current->type != TOK_RPAREN && p->current->type != TOK_EOF) {
                    if (p->current->type == TOK_IDENT) advance(p);
                    else break;
                    if (p->current->type == TOK_COMMA) advance(p);
                    else break;
                }
                expect(p, TOK_RPAREN, "')'");
            }
            type = parse_class_body(p, name);
            free(name);
            break;
        }
        case TOK_IDENT: {
            char *name = strdup(p->current->value);
            advance(p);
            type = new_node(NODE_SIMPLE_TYPE, p->current->line, p->current->filename);
            type->data.simple_type.name = name;
            break;
        }
        case TOK_PROC:
        case TOK_FUNC: {
            int is_func = (p->current->type == TOK_FUNC);
            advance(p);
            ASTNode *params = NULL, *param_tail = NULL;
            if (p->current->type == TOK_LPAREN) {
                advance(p);
                while (p->current->type != TOK_RPAREN) {
                    int is_ref = 0;
                    if (match(p, TOK_VAR)) is_ref = 1;
                    if (p->current->type != TOK_IDENT) {
                        parse_error(p, "expected parameter name in procedure/function type");
                        break;
                    }
                    char *pname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *ptype = parse_type(p);
                    ASTNode *param = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    param->data.decl.name = pname;
                    param->data.decl.type_expr = ptype;
                    param->data.decl.value = (ASTNode*)(intptr_t)is_ref;
                    if (!params) params = param;
                    else param_tail->next = param;
                    param_tail = param;
                    if (p->current->type == TOK_SEMICOLON) advance(p);
                    else break;
                }
                expect(p, TOK_RPAREN, "')'");
            }
            ASTNode *ret = NULL;
            if (is_func) {
                expect(p, TOK_COLON, "':' after function type parameters");
                ret = parse_type(p);
            }
            type = new_node(is_func ? NODE_FUNC_TYPE : NODE_PROC_TYPE, p->current->line, p->current->filename);
            type->data.proc_type.params = params;
            type->data.proc_type.return_type = ret;
            break;
        }
        default:
            parse_error(p, "expected a type");
            type = new_node(NODE_SIMPLE_TYPE, p->current->line, p->current->filename);
            type->data.simple_type.name = strdup("int");
    }
    return type;
}

/* ---------- parse_expression ---------- */
static int binop_prec(TokenType op) {
    switch (op) {
        case TOK_OR: return 1;
        case TOK_AND: case TOK_XOR: return 2;
        case TOK_EQ: case TOK_EQUALS: case TOK_NEQ:
        case TOK_LT: case TOK_GT: case TOK_LE: case TOK_GE: return 3;
        case TOK_SHL: case TOK_SHR: return 4;
        case TOK_PLUS: case TOK_MINUS: return 5;
        case TOK_STAR: case TOK_SLASH: case TOK_DIV: case TOK_MOD: return 6;
        default: return 0;
    }
}

static ASTNode *parse_primary(Parser *p) {
    ASTNode *node = NULL;
    switch (p->current->type) {
        case TOK_NUMBER: {
            node = new_node(NODE_NUMBER, p->current->line, p->current->filename);
            node->data.number.value = strdup(p->current->value);
            advance(p);
            break;
        }
        case TOK_REAL: {
            node = new_node(NODE_REAL, p->current->line, p->current->filename);
            node->data.number.value = strdup(p->current->value);
            advance(p);
            break;
        }
        case TOK_STRING: {
            node = new_node(NODE_STRING, p->current->line, p->current->filename);
            node->data.string.value = strdup(p->current->value);
            advance(p);
            break;
        }
        case TOK_TRUE: {
            node = new_node(NODE_NUMBER, p->current->line, p->current->filename);
            node->data.number.value = strdup("true");
            advance(p);
            break;
        }
        case TOK_FALSE: {
            node = new_node(NODE_NUMBER, p->current->line, p->current->filename);
            node->data.number.value = strdup("false");
            advance(p);
            break;
        }
        case TOK_IDENT: {
            node = new_node(NODE_VAR, p->current->line, p->current->filename);
            node->data.var.name = strdup(p->current->value);
            advance(p);
            while (1) {
                if (p->current->type == TOK_LBRACKET) {
                    advance(p);
                    ASTNode *idx = parse_expression(p);
                    expect(p, TOK_RBRACKET, "']'");
                    ASTNode *arr = new_node(NODE_ARRAY_INDEX, p->current->line, p->current->filename);
                    arr->data.array_index.array_expr = node;
                    arr->data.array_index.index_expr = idx;
                    node = arr;
                } else if (p->current->type == TOK_DOT) {
                    advance(p);
                    char *field = strdup(p->current->value);
                    advance(p);
                    ASTNode *rec = new_node(NODE_RECORD_FIELD, p->current->line, p->current->filename);
                    rec->data.record_field.record_expr = node;
                    rec->data.record_field.field = field;
                    node = rec;
                } else if (p->current->type == TOK_CARET) {
                    advance(p);
                    ASTNode *deref = new_node(NODE_POINTER_DEREF, p->current->line, p->current->filename);
                    deref->data.pointer_deref.ptr_expr = node;
                    node = deref;
                } else if (p->current->type == TOK_LPAREN) {
                    advance(p);
                    ASTNode *args = NULL, *arg_tail = NULL;
                    while (p->current->type != TOK_RPAREN) {
                        ASTNode *a = parse_expression(p);
                        if (!args) args = a;
                        else arg_tail->next = a;
                        arg_tail = a;
                        if (p->current->type == TOK_COMMA) advance(p);
                        else break;
                    }
                    expect(p, TOK_RPAREN, "')'");
                    ASTNode *call = new_node(NODE_CALL, p->current->line, p->current->filename);
                    call->data.call.func = node;
                    call->data.call.args = args;
                    node = call;
                } else {
                    break;
                }
            }
            break;
        }
        case TOK_AT: {
            advance(p);
            ASTNode *operand = parse_primary(p);
            ASTNode *addr = new_node(NODE_UNOP, p->current->line, p->current->filename);
            addr->data.unop.op = TOK_AT;
            addr->data.unop.operand = operand;
            node = addr;
            break;
        }
        case TOK_NOT: {
            advance(p);
            ASTNode *operand = parse_primary(p);
            ASTNode *un = new_node(NODE_UNOP, p->current->line, p->current->filename);
            un->data.unop.op = TOK_NOT;
            un->data.unop.operand = operand;
            node = un;
            break;
        }
        case TOK_MINUS: {
            advance(p);
            ASTNode *operand = parse_primary(p);
            ASTNode *un = new_node(NODE_UNOP, p->current->line, p->current->filename);
            un->data.unop.op = TOK_MINUS;
            un->data.unop.operand = operand;
            node = un;
            break;
        }
        case TOK_NEW: {
            advance(p);
            expect(p, TOK_LPAREN, "'('");
            char *class_name = strdup(p->current->value);
            advance(p);
            ASTNode *args = NULL, *arg_tail = NULL;
            while (p->current->type != TOK_RPAREN) {
                if (p->current->type == TOK_COMMA) advance(p);
                ASTNode *a = parse_expression(p);
                if (!args) args = a;
                else arg_tail->next = a;
                arg_tail = a;
                if (p->current->type == TOK_COMMA) advance(p);
                else break;
            }
            expect(p, TOK_RPAREN, "')'");
            ASTNode *new_expr = new_node(NODE_NEW, p->current->line, p->current->filename);
            new_expr->data.new_stmt.class_name = class_name;
            new_expr->data.new_stmt.args = args;
            node = new_expr;
            break;
        }
        case TOK_SIZEOF: {
            advance(p);
            expect(p, TOK_LPAREN, "'('");
            ASTNode *te = NULL;
            char *tname = NULL;
            if (p->current->type == TOK_IDENT) {
                tname = strdup(p->current->value);
                advance(p);
            } else {
                te = parse_type(p);
            }
            expect(p, TOK_RPAREN, "')'");
            node = new_node(NODE_SIZEOF, p->current->line, p->current->filename);
            node->data.size_offset.type_expr = te;
            node->data.size_offset.type_name = tname;
            node->data.size_offset.field_name = NULL;
            break;
        }
        case TOK_LPAREN: {
            advance(p);
            node = parse_expression(p);
            expect(p, TOK_RPAREN, "')'");
            break;
        }
        default:
            parse_error(p, "unexpected token in expression");
            node = new_node(NODE_NUMBER, p->current->line, p->current->filename);
            node->data.number.value = strdup("0");
    }
    return node;
}

static ASTNode *parse_binop(Parser *p, int min_prec) {
    ASTNode *left = parse_primary(p);
    while (1) {
        TokenType op = p->current->type;
        int prec = binop_prec(op);
        if (prec < min_prec) break;
        advance(p);
        ASTNode *right = parse_binop(p, prec + 1);
        ASTNode *bin = new_node(NODE_BINOP, p->current->line, p->current->filename);
        bin->data.binop.left = left;
        bin->data.binop.right = right;
        bin->data.binop.op = op;
        left = bin;
    }
    return left;
}

static ASTNode *parse_expression(Parser *p) {
    return parse_binop(p, 1);
}

/* ---------- parse_statement ---------- */
static ASTNode *parse_statement(Parser *p) {
    ASTNode *stmt = NULL;
    switch (p->current->type) {
        case TOK_BREAK:
            advance(p);
            expect_stmt_end(p);
            stmt = new_node(NODE_BREAK, p->current->line, p->current->filename);
            break;

        case TOK_CONTINUE:
            advance(p);
            expect_stmt_end(p);
            stmt = new_node(NODE_CONTINUE, p->current->line, p->current->filename);
            break;

        case TOK_RUN: {
            advance(p);
            stmt = parse_block(p);
            match(p, TOK_SEMICOLON);
            break;
        }

        case TOK_IF: {
            advance(p);
            ASTNode *cond = parse_expression(p);
            expect(p, TOK_THEN, "Then");
            ASTNode *then_stmt = parse_statement(p);
            ASTNode *else_stmt = NULL;
            if (match(p, TOK_ELSE)) {
                else_stmt = parse_statement(p);
            }
            stmt = new_node(NODE_IF, p->current->line, p->current->filename);
            stmt->data.if_stmt.cond = cond;
            stmt->data.if_stmt.then_stmt = then_stmt;
            stmt->data.if_stmt.else_stmt = else_stmt;
            break;
        }

        case TOK_FOR: {
            advance(p);
            char *var = strdup(p->current->value);
            advance(p);
            expect(p, TOK_ASSIGN, "'<-'");
            ASTNode *start = parse_expression(p);
            int downto = 0;
            if (match(p, TOK_TO)) downto = 0;
            else if (match(p, TOK_DOWNTO)) downto = 1;
            else {
                parse_error(p, "expected To or Downto");
                break;
            }
            ASTNode *end = parse_expression(p);
            expect(p, TOK_DO, "Do");
            ASTNode *body = parse_statement(p);
            match(p, TOK_SEMICOLON);
            stmt = new_node(NODE_FOR, p->current->line, p->current->filename);
            stmt->data.for_stmt.var = var;
            stmt->data.for_stmt.start = start;
            stmt->data.for_stmt.end = end;
            stmt->data.for_stmt.downto = downto;
            stmt->data.for_stmt.body = body;
            break;
        }

        case TOK_WHILE: {
            advance(p);
            ASTNode *cond = parse_expression(p);
            expect(p, TOK_DO, "Do");
            ASTNode *body = parse_statement(p);
            match(p, TOK_SEMICOLON);
            stmt = new_node(NODE_WHILE, p->current->line, p->current->filename);
            stmt->data.while_stmt.cond = cond;
            stmt->data.while_stmt.body = body;
            break;
        }

        case TOK_REPEAT: {
            advance(p);
            ASTNode *body_head = NULL, *body_tail = NULL;
            while (p->current->type != TOK_UNTIL) {
                ASTNode *s = parse_statement(p);
                if (!body_head) body_head = s;
                else body_tail->next = s;
                body_tail = s;
            }
            expect(p, TOK_UNTIL, "Until");
            ASTNode *cond = parse_expression(p);
            expect(p, TOK_SEMICOLON, "';'");
            stmt = new_node(NODE_REPEAT, p->current->line, p->current->filename);
            stmt->data.repeat_stmt.body = body_head;
            stmt->data.repeat_stmt.cond = cond;
            break;
        }

        case TOK_WITH: {
            advance(p);
            ASTNode *expr = parse_expression(p);
            expect(p, TOK_DO, "Do");
            ASTNode *body = parse_statement(p);
            expect_stmt_end(p);
            stmt = new_node(NODE_WITH, p->current->line, p->current->filename);
            stmt->data.with_stmt.expr = expr;
            stmt->data.with_stmt.body = body;
            break;
        }

        case TOK_ATTEMPT: {
            advance(p);
            ASTNode *body_head = NULL, *body_tail = NULL;
            while (p->current->type != TOK_RECOVER && p->current->type != TOK_STOP) {
                ASTNode *s = parse_statement(p);
                if (!body_head) body_head = s;
                else body_tail->next = s;
                body_tail = s;
            }
            char *err_var = NULL;
            ASTNode *recover_body = NULL;
            if (match(p, TOK_RECOVER)) {
                if (match(p, TOK_WITH)) {
                    err_var = strdup(p->current->value);
                    advance(p);
                }
                recover_body = parse_block(p);
            }
            expect(p, TOK_STOP, "Stop");
            expect(p, TOK_SEMICOLON, "';'");
            stmt = new_node(NODE_ATTEMPT, p->current->line, p->current->filename);
            stmt->data.attempt.body = body_head;
            stmt->data.attempt.err_var = err_var;
            stmt->data.attempt.recover = recover_body;
            break;
        }

        case TOK_PRINT: {
            advance(p);
            expect(p, TOK_LPAREN, "'('");
            ASTNode *args = NULL, *arg_tail = NULL;
            while (p->current->type != TOK_RPAREN) {
                ASTNode *expr = parse_expression(p);
                if (!args) args = expr;
                else arg_tail->next = expr;
                arg_tail = expr;
                if (p->current->type == TOK_COMMA) advance(p);
                else break;
            }
            expect(p, TOK_RPAREN, "')'");
            expect_stmt_end(p);
            stmt = new_node(NODE_PRINT, p->current->line, p->current->filename);
            stmt->data.print.expr = args;
            break;
        }

        case TOK_INPUT: {
            advance(p);
            expect(p, TOK_LPAREN, "'('");
            ASTNode *var = parse_expression(p);
            if (var->type != NODE_VAR && var->type != NODE_ARRAY_INDEX &&
                var->type != NODE_RECORD_FIELD && var->type != NODE_POINTER_DEREF) {
                parse_error(p, "Input requires a variable");
                break;
            }
            expect(p, TOK_RPAREN, "')'");
            expect_stmt_end(p);
            stmt = new_node(NODE_INPUT, p->current->line, p->current->filename);
            stmt->data.input_var.var = var;
            break;
        }

        case TOK_ASM: {
            advance(p);
            char *code = strdup(p->current->value);
            advance(p);
            expect_stmt_end(p);
            stmt = new_node(NODE_ASM, p->current->line, p->current->filename);
            stmt->data.asm.code = code;
            break;
        }

        case TOK_DISPOSE: {
            advance(p);
            expect(p, TOK_LPAREN, "'('");
            ASTNode *expr = parse_expression(p);
            expect(p, TOK_RPAREN, "')'");
            expect_stmt_end(p);
            stmt = new_node(NODE_DISPOSE, p->current->line, p->current->filename);
            stmt->data.dispose.ptr = expr;
            break;
        }

        case TOK_IDENT: {
            ASTNode *expr = parse_expression(p);
            if (p->current->type == TOK_ASSIGN) {
                advance(p);
                ASTNode *rhs = parse_expression(p);
                expect_stmt_end(p);
                stmt = new_node(NODE_ASSIGN, p->current->line, p->current->filename);
                stmt->data.assign.lvalue = expr;
                stmt->data.assign.expr = rhs;
            } else {
                expect_stmt_end(p);
                stmt = new_node(NODE_EXPR_STMT, p->current->line, p->current->filename);
                stmt->data.expr_stmt.expr = expr;
            }
            break;
        }

        default: {
            parse_error(p, "unexpected token in statement");
            advance(p);
            stmt = new_node(NODE_EMPTY, p->current->line, p->current->filename);
        }
    }
    return stmt;
}

/* ---------- parse_block ---------- */
static ASTNode *parse_block(Parser *p) {
    ASTNode *head = NULL, *tail = NULL;
    while (p->current->type != TOK_STOP && p->current->type != TOK_EOF) {
        ASTNode *stmt = parse_statement(p);
        if (!head) head = stmt;
        else tail->next = stmt;
        tail = stmt;
    }
    expect(p, TOK_STOP, "Stop");
    ASTNode *block = new_node(NODE_BLOCK, p->current->line, p->current->filename);
    block->data.block.stmt_list = head;
    return block;
}

/* ---------- parse_program ---------- */
static ASTNode *parse_program(Parser *p) {
    ASTNode *head = NULL, *tail = NULL;

    while (p->current->type != TOK_ENTER && p->current->type != TOK_EOF) {
        ASTNode *decl = NULL;

        if (p->current->type == TOK_IMPORT) {
            advance(p);
            char *path = NULL;
            if (p->current->type == TOK_LT) {
                const char *src = p->lex->src;
                int pos = p->lex->pos;
                int start = pos;
                while (src[pos] && src[pos] != '>') pos++;
                if (src[pos] != '>') {
                    parse_error(p, "unmatched '<' in import");
                    break;
                }
                char *name = malloc(pos - start + 1);
                strncpy(name, src + start, pos - start);
                name[pos - start] = '\0';
                {
                    size_t plen = strlen(name) + 4; /* < + name + > + NUL */
                    path = malloc(plen);
                    if (path) snprintf(path, plen, "<%s>", name);
                }
                free(name);
                while (p->current->type != TOK_GT && p->current->type != TOK_EOF) advance(p);
                if (p->current->type == TOK_GT) advance(p);
                else {
                    parse_error(p, "expected '>' in import");
                    break;
                }
            } else if (p->current->type == TOK_STRING) {
                path = strdup(p->current->value);
                advance(p);
            } else {
                path = strdup(p->current->value);
                advance(p);
            }
            expect(p, TOK_SEMICOLON, "';'");
            decl = new_node(NODE_IMPORT, p->current->line, p->current->filename);
            decl->data.import.path = path;
        }
        else if (p->current->type == TOK_CONST) {
            advance(p);
            char *name = strdup(p->current->value);
            advance(p);
            expect(p, TOK_EQUALS, "'='");
            ASTNode *val = parse_expression(p);
            expect(p, TOK_SEMICOLON, "';'");
            decl = new_node(NODE_CONST_DECL, p->current->line, p->current->filename);
            decl->data.decl.name = name;
            decl->data.decl.value = val;
        }
        else if (p->current->type == TOK_TYPE) {
            advance(p);
            int any = 0;
            while (p->current->type == TOK_IDENT) {
                char *name = strdup(p->current->value);
                advance(p);
                expect(p, TOK_EQUALS, "'='");
                ASTNode *type = NULL;
                if (p->current->type == TOK_CLASS) {
                    advance(p);
                    if (match(p, TOK_EXTENDS)) {
                        expect(p, TOK_IDENT, "base class name");
                    } else if (p->current->type == TOK_LPAREN) {
                        advance(p);
                        while (p->current->type != TOK_RPAREN && p->current->type != TOK_EOF) {
                            if (p->current->type == TOK_IDENT)
                                advance(p);
                            else
                                break;
                            if (p->current->type == TOK_COMMA)
                                advance(p);
                            else
                                break;
                        }
                        expect(p, TOK_RPAREN, "')' after base class list");
                    }
                    type = parse_class_body(p, name);
                } else {
                    type = parse_type(p);
                }
                expect(p, TOK_SEMICOLON, "';'");
                ASTNode *tdecl = new_node(NODE_TYPE_DECL, p->current->line, p->current->filename);
                tdecl->data.decl.name = name;
                tdecl->data.decl.type_expr = type;
                if (!head) head = tdecl;
                else tail->next = tdecl;
                tail = tdecl;
                any = 1;
            }
            if (!any) {
                parse_error(p, "expected type name after Type");
            }
            continue;
        }
        else if (p->current->type == TOK_VAR) {
            advance(p);
            while (p->current->type == TOK_IDENT) {
                char *name = strdup(p->current->value);
                advance(p);
                expect(p, TOK_COLON, "':'");
                ASTNode *type = parse_type(p);
                ASTNode *abs_expr = NULL;
                if (match(p, TOK_ABSOLUTE)) {
                    abs_expr = parse_expression(p);
                }
                expect(p, TOK_SEMICOLON, "';'");
                ASTNode *vdecl = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                vdecl->data.decl.name = name;
                vdecl->data.decl.type_expr = type;
                vdecl->data.decl.value = abs_expr;
                if (!head) head = vdecl;
                else tail->next = vdecl;
                tail = vdecl;
            }
            continue;
        }
        else if (p->current->type == TOK_FUNC || p->current->type == TOK_PROC ||
                 p->current->type == TOK_CONSTRUCTOR || p->current->type == TOK_DESTRUCTOR) {
            int is_func = (p->current->type == TOK_FUNC);
            int is_ctor = (p->current->type == TOK_CONSTRUCTOR);
            int is_dtor = (p->current->type == TOK_DESTRUCTOR);
            advance(p);
            if (p->current->type != TOK_IDENT) {
                parse_error(p, "expected identifier after Func/Proc");
                continue;
            }
            char *first_name = strdup(p->current->value);
            advance(p);
            char *class_name = NULL, *func_name = NULL;
            int is_method = 0;
            if (p->current->type == TOK_DOT) {
                is_method = 1;
                class_name = first_name;
                advance(p);
                if (p->current->type != TOK_IDENT) {
                    parse_error(p, "expected method name after '.'");
                    continue;
                }
                func_name = strdup(p->current->value);
                advance(p);
            } else {
                func_name = first_name;
            }
            ASTNode *params = NULL, *param_tail = NULL;
            if (p->current->type == TOK_LPAREN) {
                advance(p);
                while (p->current->type != TOK_RPAREN) {
                    int is_ref = 0;
                    if (match(p, TOK_VAR)) is_ref = 1;
                    if (p->current->type != TOK_IDENT) {
                        parse_error(p, "expected parameter name");
                        break;
                    }
                    char *pname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *ptype = parse_type(p);
                    ASTNode *param = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    param->data.decl.name = pname;
                    param->data.decl.type_expr = ptype;
                    param->data.decl.value = (ASTNode*)(intptr_t)is_ref;
                    if (!params) params = param;
                    else param_tail->next = param;
                    param_tail = param;
                    if (p->current->type == TOK_SEMICOLON) advance(p);
                    else break;
                }
                expect(p, TOK_RPAREN, "')'");
            }
            ASTNode *ret_type = NULL;
            if (is_func) {
                expect(p, TOK_COLON, "':'");
                ret_type = parse_type(p);
            }
            match(p, TOK_SEMICOLON);
            ASTNode *locals = NULL, *local_tail = NULL;
            if (p->current->type == TOK_VAR) {
                advance(p);
                while (p->current->type == TOK_IDENT) {
                    char *vname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *vtype = parse_type(p);
                    expect(p, TOK_SEMICOLON, "';'");
                    ASTNode *v = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    v->data.decl.name = vname;
                    v->data.decl.type_expr = vtype;
                    if (!locals) locals = v;
                    else local_tail->next = v;
                    local_tail = v;
                }
            }
            expect(p, TOK_RUN, "Run");
            ASTNode *body = parse_block(p);
            match(p, TOK_SEMICOLON);
            if (locals) {
                ASTNode *last = locals;
                while (last->next) last = last->next;
                last->next = body->data.block.stmt_list;
                body->data.block.stmt_list = locals;
            }
            decl = new_node(is_func ? NODE_FUNC_DECL : NODE_PROC_DECL, p->current->line, p->current->filename);
            if (is_ctor) {
                decl->data.func.name = strdup("Constructor");
                free(func_name);
                func_name = NULL;
            } else if (is_dtor) {
                decl->data.func.name = strdup("Destructor");
                free(func_name);
                func_name = NULL;
            } else {
                decl->data.func.name = func_name;
                func_name = NULL;
            }
            decl->data.func.params = params;
            decl->data.func.return_type = ret_type;
            decl->data.func.body = body;
            decl->data.func.is_method = is_method;
            decl->data.func.class_name = class_name;
        }
        else {
            parse_error(p, "unexpected declaration");
            advance(p);
            continue;
        }

        if (decl) {
            if (!head) head = decl;
            else tail->next = decl;
            tail = decl;
        }
    }

    /* ---------- "Enter" ---------- */
    expect(p, TOK_ENTER, "Enter");
    if (p->current->type == TOK_IDENT) {
        advance(p);  /* program name is optional metadata; discard */
    } else {
        parse_error(p, "expected identifier after Enter");
    }
    expect(p, TOK_SEMICOLON, "';'");

    /* ---------- Declarations after Enter ---------- */
    while (p->current->type != TOK_RUN && p->current->type != TOK_EOF) {
        ASTNode *decl = NULL;

        if (p->current->type == TOK_IMPORT) {
            advance(p);
            char *path = NULL;
            if (p->current->type == TOK_LT) {
                const char *src = p->lex->src;
                int pos = p->lex->pos;
                int start = pos;
                while (src[pos] && src[pos] != '>') pos++;
                if (src[pos] != '>') {
                    parse_error(p, "unmatched '<' in import");
                    break;
                }
                char *name = malloc(pos - start + 1);
                strncpy(name, src + start, pos - start);
                name[pos - start] = '\0';
                {
                    size_t plen = strlen(name) + 4; /* < + name + > + NUL */
                    path = malloc(plen);
                    if (path) snprintf(path, plen, "<%s>", name);
                }
                free(name);
                while (p->current->type != TOK_GT && p->current->type != TOK_EOF) advance(p);
                if (p->current->type == TOK_GT) advance(p);
                else {
                    parse_error(p, "expected '>' in import");
                    break;
                }
            } else if (p->current->type == TOK_STRING) {
                path = strdup(p->current->value);
                advance(p);
            } else {
                path = strdup(p->current->value);
                advance(p);
            }
            expect(p, TOK_SEMICOLON, "';'");
            decl = new_node(NODE_IMPORT, p->current->line, p->current->filename);
            decl->data.import.path = path;
        }
        else if (p->current->type == TOK_CONST) {
            advance(p);
            char *name = strdup(p->current->value);
            advance(p);
            expect(p, TOK_EQUALS, "'='");
            ASTNode *val = parse_expression(p);
            expect(p, TOK_SEMICOLON, "';'");
            decl = new_node(NODE_CONST_DECL, p->current->line, p->current->filename);
            decl->data.decl.name = name;
            decl->data.decl.value = val;
        }
        else if (p->current->type == TOK_TYPE) {
            advance(p);
            int any = 0;
            while (p->current->type == TOK_IDENT) {
                char *name = strdup(p->current->value);
                advance(p);
                expect(p, TOK_EQUALS, "'='");
                ASTNode *type = NULL;
                if (p->current->type == TOK_CLASS) {
                    advance(p);
                    if (match(p, TOK_EXTENDS)) {
                        expect(p, TOK_IDENT, "base class name");
                    } else if (p->current->type == TOK_LPAREN) {
                        advance(p);
                        while (p->current->type != TOK_RPAREN && p->current->type != TOK_EOF) {
                            if (p->current->type == TOK_IDENT)
                                advance(p);
                            else
                                break;
                            if (p->current->type == TOK_COMMA)
                                advance(p);
                            else
                                break;
                        }
                        expect(p, TOK_RPAREN, "')' after base class list");
                    }
                    type = parse_class_body(p, name);
                } else {
                    type = parse_type(p);
                }
                expect(p, TOK_SEMICOLON, "';'");
                ASTNode *tdecl = new_node(NODE_TYPE_DECL, p->current->line, p->current->filename);
                tdecl->data.decl.name = name;
                tdecl->data.decl.type_expr = type;
                if (!head) head = tdecl;
                else tail->next = tdecl;
                tail = tdecl;
                any = 1;
            }
            if (!any) {
                parse_error(p, "expected type name after Type");
            }
            continue;
        }
        else if (p->current->type == TOK_VAR) {
            advance(p);
            ASTNode *var_head = NULL, *var_tail = NULL;
            while (p->current->type == TOK_IDENT) {
                char *name = strdup(p->current->value);
                advance(p);
                expect(p, TOK_COLON, "':'");
                ASTNode *type = parse_type(p);
                ASTNode *abs_expr = NULL;
                if (match(p, TOK_ABSOLUTE)) {
                    abs_expr = parse_expression(p);
                }
                expect(p, TOK_SEMICOLON, "';'");
                ASTNode *vdecl = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                vdecl->data.decl.name = name;
                vdecl->data.decl.type_expr = type;
                vdecl->data.decl.value = abs_expr;
                if (!var_head) var_head = vdecl;
                else var_tail->next = vdecl;
                var_tail = vdecl;
            }
            if (var_head) {
                if (!head) head = var_head;
                else tail->next = var_head;
                tail = var_tail;
            }
            continue;
        }
        else if (p->current->type == TOK_FUNC || p->current->type == TOK_PROC ||
                 p->current->type == TOK_CONSTRUCTOR || p->current->type == TOK_DESTRUCTOR) {

            int is_func = (p->current->type == TOK_FUNC);
            int is_ctor = (p->current->type == TOK_CONSTRUCTOR);
            int is_dtor = (p->current->type == TOK_DESTRUCTOR);
            advance(p);
            if (p->current->type != TOK_IDENT) {
                parse_error(p, "expected identifier after Func/Proc/Constructor");
                continue;
            }
            char *first_name = strdup(p->current->value);
            advance(p);
            char *class_name = NULL, *func_name = NULL;
            int is_method = 0;
            if (p->current->type == TOK_DOT) {
                is_method = 1;
                class_name = first_name;
                advance(p);
                if (p->current->type != TOK_IDENT) {
                    parse_error(p, "expected method name after '.'");
                    continue;
                }
                func_name = strdup(p->current->value);
                advance(p);
            } else {
                func_name = first_name;
            }
            ASTNode *params = NULL, *param_tail = NULL;
            if (p->current->type == TOK_LPAREN) {
                advance(p);
                while (p->current->type != TOK_RPAREN) {
                    int is_ref = 0;
                    if (match(p, TOK_VAR)) is_ref = 1;
                    if (p->current->type != TOK_IDENT) {
                        parse_error(p, "expected parameter name");
                        break;
                    }
                    char *pname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *ptype = parse_type(p);
                    ASTNode *param = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    param->data.decl.name = pname;
                    param->data.decl.type_expr = ptype;
                    param->data.decl.value = (ASTNode*)(intptr_t)is_ref;
                    if (!params) params = param;
                    else param_tail->next = param;
                    param_tail = param;
                    if (p->current->type == TOK_SEMICOLON) advance(p);
                    else break;
                }
                expect(p, TOK_RPAREN, "')'");
            }
            ASTNode *ret_type = NULL;
            if (is_func) {
                expect(p, TOK_COLON, "':'");
                ret_type = parse_type(p);
            }
            match(p, TOK_SEMICOLON);
            ASTNode *locals = NULL, *local_tail = NULL;
            if (p->current->type == TOK_VAR) {
                advance(p);
                while (p->current->type == TOK_IDENT) {
                    char *vname = strdup(p->current->value);
                    advance(p);
                    expect(p, TOK_COLON, "':'");
                    ASTNode *vtype = parse_type(p);
                    expect(p, TOK_SEMICOLON, "';'");
                    ASTNode *v = new_node(NODE_VAR_DECL, p->current->line, p->current->filename);
                    v->data.decl.name = vname;
                    v->data.decl.type_expr = vtype;
                    if (!locals) locals = v;
                    else local_tail->next = v;
                    local_tail = v;
                }
            }
            expect(p, TOK_RUN, "Run");
            ASTNode *body = parse_block(p);
            match(p, TOK_SEMICOLON);
            if (locals) {
                ASTNode *last = locals;
                while (last->next) last = last->next;
                last->next = body->data.block.stmt_list;
                body->data.block.stmt_list = locals;
            }
            decl = new_node(is_func ? NODE_FUNC_DECL : NODE_PROC_DECL, p->current->line, p->current->filename);
            if (is_ctor) {
                decl->data.func.name = strdup("Constructor");
                free(func_name);
                func_name = NULL;
            } else if (is_dtor) {
                decl->data.func.name = strdup("Destructor");
                free(func_name);
                func_name = NULL;
            } else {
                decl->data.func.name = func_name;
                func_name = NULL;
            }
            decl->data.func.params = params;
            decl->data.func.return_type = ret_type;
            decl->data.func.body = body;
            decl->data.func.is_method = is_method;
            decl->data.func.class_name = class_name;
        }
        else {
            break;
        }

        if (decl) {
            if (!head) head = decl;
            else tail->next = decl;
            tail = decl;
        }
    }

    /* ---------- Main Run block ---------- */
    expect(p, TOK_RUN, "Run");
    ASTNode *main_body = parse_block(p);

    expect(p, TOK_EXIT, "Exit");
    expect(p, TOK_DOT, "'.'");

    ASTNode *main_node = new_node(NODE_MAIN_BODY, p->current->line, p->current->filename);
    main_node->data.block.stmt_list = main_body->data.block.stmt_list;
    if (!head) head = main_node;
    else tail->next = main_node;
    tail = main_node;

    ASTNode *prog = new_node(NODE_PROGRAM, p->current->line, p->current->filename);
    prog->data.block.stmt_list = head;
    return prog;
}

/* ================== Emitter ================== */

static FILE *out;
static int indent_level = 0;
static int in_function = 0;
static char *current_function_name = NULL;
static int emitting_lvalue = 0;

static void emit_indent() {
    for (int i = 0; i < indent_level; i++) fputc(' ', out);
}

static void emit_line(const char *s) {
    emit_indent();
    fprintf(out, "%s\n", s);
}

static void emit_begin_block() {
    emit_line("{");
    indent_level += 2;
}

static void emit_end_block() {
    indent_level -= 2;
    emit_line("}");
}

static void emit_type(ASTNode *node) {
    if (!node) return;
    switch (node->type) {
        case NODE_SIMPLE_TYPE: {
            char *n = node->data.simple_type.name;
            if (strcmp(n, "Integer") == 0) fprintf(out, "int");
            else if (strcmp(n, "Real") == 0) fprintf(out, "double");
            else if (strcmp(n, "Boolean") == 0) fprintf(out, "bool");
            else if (strcmp(n, "String") == 0) fprintf(out, "std::string");
            else if (strcmp(n, "Char") == 0) fprintf(out, "char");
            else if (strcmp(n, "Byte") == 0) fprintf(out, "unsigned char");
            else if (strcmp(n, "HINST") == 0) fprintf(out, "HINSTANCE");
            else if (strcmp(n, "PChar") == 0) fprintf(out, "const char*");
            else fprintf(out, "%s", n);
            break;
        }
        case NODE_ARRAY_TYPE: {
            emit_type(node->data.array_type.base);
            fprintf(out, "[");
            if (node->data.array_type.high && node->data.array_type.high->type == NODE_NUMBER) {
                int high = atoi(node->data.array_type.high->data.number.value);
                int low = 0;
                if (node->data.array_type.low && node->data.array_type.low->type == NODE_NUMBER)
                    low = atoi(node->data.array_type.low->data.number.value);
                fprintf(out, "%d", high - low + 1);
            } else {
                fprintf(out, "/* size */");
            }
            fprintf(out, "]");
            break;
        }
        case NODE_POINTER_TYPE: {
            emit_type(node->data.pointer_type.base);
            fprintf(out, "*");
            break;
        }
        case NODE_PROC_TYPE:
        case NODE_FUNC_TYPE: {
            if (node->type == NODE_FUNC_TYPE && node->data.proc_type.return_type)
                emit_type(node->data.proc_type.return_type);
            else
                fprintf(out, "void");
            fprintf(out, " (*)(");
            ASTNode *p = node->data.proc_type.params;
            int first = 1;
            while (p) {
                if (!first) fprintf(out, ", ");
                int is_ref = (int)(intptr_t)p->data.decl.value;
                emit_type(p->data.decl.type_expr);
                if (is_ref) fprintf(out, "&");
                fprintf(out, " %s", p->data.decl.name);
                first = 0;
                p = p->next;
            }
            if (first) fprintf(out, "void");
            fprintf(out, ")");
            break;
        }
        case NODE_RECORD_DECL: {
            fprintf(out, "struct {\n");
            indent_level += 2;
            ASTNode *f = node->data.record.fields;
            while (f) {
                emit_indent();
                emit_type(f->data.decl.type_expr);
                fprintf(out, " %s;\n", f->data.decl.name);
                f = f->next;
            }
            indent_level -= 2;
            emit_indent();
            fprintf(out, "}");
            break;
        }
        default:
            fprintf(out, "/* unknown type */");
            break;
    }
}

static void emit_expr(ASTNode *node) {
    if (!node) return;
    switch (node->type) {
        case NODE_NUMBER: fprintf(out, "%s", node->data.number.value); break;
        case NODE_REAL: fprintf(out, "%s", node->data.number.value); break;
        case NODE_STRING: fprintf(out, "\"%s\"", node->data.string.value); break;
        case NODE_VAR: fprintf(out, "%s", node->data.var.name); break;
        case NODE_BINOP: {
            fputc('(', out);
            emit_expr(node->data.binop.left);
            int op = node->data.binop.op;
            switch (op) {
                case TOK_PLUS: fputc('+', out); break;
                case TOK_MINUS: fputc('-', out); break;
                case TOK_STAR: fputc('*', out); break;
                case TOK_SLASH: fputc('/', out); break;
                case TOK_DIV: fputc('/', out); break;
                case TOK_MOD: fputc('%', out); break;
                case TOK_SHL: fprintf(out, "<<"); break;
                case TOK_SHR: fprintf(out, ">>"); break;
                case TOK_AND: fputc('&', out); break;
                case TOK_OR: fputc('|', out); break;
                case TOK_XOR: fputc('^', out); break;
                case TOK_EQ: fprintf(out, "=="); break;
                case TOK_EQUALS: fprintf(out, "=="); break;
                case TOK_NEQ: fprintf(out, "!="); break;
                case TOK_LT: fputc('<', out); break;
                case TOK_GT: fputc('>', out); break;
                case TOK_LE: fprintf(out, "<="); break;
                case TOK_GE: fprintf(out, ">="); break;
                default: fprintf(out, "/* op */");
            }
            emit_expr(node->data.binop.right);
            fputc(')', out);
            break;
        }
        case NODE_UNOP: {
            int op = node->data.unop.op;
            if (op == TOK_AT) { fprintf(out, "&"); emit_expr(node->data.unop.operand); }
            else if (op == TOK_CARET) { fprintf(out, "(*"); emit_expr(node->data.unop.operand); fprintf(out, ")"); }
            else if (op == TOK_MINUS) { fputc('-', out); emit_expr(node->data.unop.operand); }
            else if (op == TOK_NOT) { fprintf(out, "!"); emit_expr(node->data.unop.operand); }
            else fprintf(out, "/* unop */");
            break;
        }
        case NODE_ARRAY_INDEX: {
            emit_expr(node->data.array_index.array_expr);
            fputc('[', out);
            emit_expr(node->data.array_index.index_expr);
            fputc(']', out);
            break;
        }
        case NODE_RECORD_FIELD: {
            emit_expr(node->data.record_field.record_expr);
            fprintf(out, ".%s", node->data.record_field.field);
            if (!emitting_lvalue &&
                node->data.record_field.field &&
                isupper((unsigned char)node->data.record_field.field[0]))
                fprintf(out, "()");
            break;
        }
        case NODE_POINTER_DEREF: {
            fprintf(out, "(*");
            emit_expr(node->data.pointer_deref.ptr_expr);
            fprintf(out, ")");
            break;
        }
        case NODE_CALL: {
            int saved = emitting_lvalue;
            emitting_lvalue = 1;
            emit_expr(node->data.call.func);
            emitting_lvalue = saved;
            fputc('(', out);
            ASTNode *arg = node->data.call.args;
            while (arg) {
                emit_expr(arg);
                arg = arg->next;
                if (arg) fprintf(out, ", ");
            }
            fputc(')', out);
            break;
        }
        case NODE_NEW: {
            fprintf(out, "new %s(", node->data.new_stmt.class_name);
            ASTNode *arg = node->data.new_stmt.args;
            while (arg) {
                emit_expr(arg);
                arg = arg->next;
                if (arg) fprintf(out, ", ");
            }
            fputc(')', out);
            break;
        }
        case NODE_SIZEOF: {
            fprintf(out, "sizeof(");
            if (node->data.size_offset.type_expr)
                emit_type(node->data.size_offset.type_expr);
            else if (node->data.size_offset.type_name)
                fprintf(out, "%s", node->data.size_offset.type_name);
            else
                fprintf(out, "/* type */");
            fprintf(out, ")");
            break;
        }
        default:
            fprintf(out, "/* expr */");
            break;
    }
}

static void emit_stmt(ASTNode *node) {
    if (!node) return;
    switch (node->type) {
        case NODE_BLOCK: {
            emit_begin_block();
            ASTNode *s = node->data.block.stmt_list;
            while (s) { emit_stmt(s); s = s->next; }
            emit_end_block();
            break;
        }
        case NODE_MAIN_BODY: {
            ASTNode *s = node->data.block.stmt_list;
            while (s) { emit_stmt(s); s = s->next; }
            break;
        }
        case NODE_ASSIGN: {
            emit_indent();
            {
                if (in_function && current_function_name &&
                    node->data.assign.lvalue->type == NODE_VAR &&
                    strcmp(node->data.assign.lvalue->data.var.name, current_function_name) == 0) {
                    fprintf(out, "_result = ");
                    emit_expr(node->data.assign.expr);
                    fprintf(out, ";\n");
                } else {
                    int saved = emitting_lvalue;
                    emitting_lvalue = 1;
                    emit_expr(node->data.assign.lvalue);
                    emitting_lvalue = saved;
                    fprintf(out, " = ");
                    emit_expr(node->data.assign.expr);
                    fprintf(out, ";\n");
                }
            }
            break;
        }
        case NODE_PRINT: {
            emit_indent();
            fprintf(out, "std::cout");
            ASTNode *arg = node->data.print.expr;
            while (arg) {
                fprintf(out, " << ");
                emit_expr(arg);
                arg = arg->next;
            }
            fprintf(out, " << std::endl;\n");
            break;
        }
        case NODE_INPUT: {
            emit_indent();
            fprintf(out, "std::getline(std::cin, ");
            emit_expr(node->data.input_var.var);
            fprintf(out, ");\n");
            break;
        }
        case NODE_IF: {
            emit_indent();
            fprintf(out, "if (");
            emit_expr(node->data.if_stmt.cond);
            fprintf(out, ") {\n");
            indent_level += 2;
            if (node->data.if_stmt.then_stmt) {
                if (node->data.if_stmt.then_stmt->type == NODE_BLOCK) {
                    ASTNode *s = node->data.if_stmt.then_stmt->data.block.stmt_list;
                    while (s) { emit_stmt(s); s = s->next; }
                } else {
                    emit_stmt(node->data.if_stmt.then_stmt);
                }
            }
            indent_level -= 2;
            emit_indent();
            fprintf(out, "}");
            if (node->data.if_stmt.else_stmt) {
                fprintf(out, " else {\n");
                indent_level += 2;
                if (node->data.if_stmt.else_stmt->type == NODE_BLOCK) {
                    ASTNode *s = node->data.if_stmt.else_stmt->data.block.stmt_list;
                    while (s) { emit_stmt(s); s = s->next; }
                } else if (node->data.if_stmt.else_stmt->type == NODE_IF) {
                    emit_stmt(node->data.if_stmt.else_stmt);
                } else {
                    emit_stmt(node->data.if_stmt.else_stmt);
                }
                indent_level -= 2;
                emit_indent();
                fprintf(out, "}");
            }
            fprintf(out, "\n");
            break;
        }
        case NODE_FOR: {
            emit_indent();
            fprintf(out, "for (%s = ", node->data.for_stmt.var);
            emit_expr(node->data.for_stmt.start);
            fprintf(out, "; ");
            if (node->data.for_stmt.downto) {
                fprintf(out, "%s >= ", node->data.for_stmt.var);
                emit_expr(node->data.for_stmt.end);
                fprintf(out, "; %s--", node->data.for_stmt.var);
            } else {
                fprintf(out, "%s <= ", node->data.for_stmt.var);
                emit_expr(node->data.for_stmt.end);
                fprintf(out, "; %s++", node->data.for_stmt.var);
            }
            fprintf(out, ") ");
            if (node->data.for_stmt.body->type != NODE_BLOCK) {
                fprintf(out, "\n");
                emit_stmt(node->data.for_stmt.body);
            } else {
                emit_stmt(node->data.for_stmt.body);
            }
            break;
        }
        case NODE_WHILE: {
            emit_indent();
            fprintf(out, "while (");
            emit_expr(node->data.while_stmt.cond);
            fprintf(out, ") ");
            if (node->data.while_stmt.body->type != NODE_BLOCK) {
                fprintf(out, "\n");
                emit_stmt(node->data.while_stmt.body);
            } else {
                emit_stmt(node->data.while_stmt.body);
            }
            break;
        }
        case NODE_REPEAT: {
            emit_line("do");
            emit_begin_block();
            ASTNode *s = node->data.repeat_stmt.body;
            while (s) { emit_stmt(s); s = s->next; }
            emit_end_block();
            emit_indent();
            fprintf(out, "while (!(");
            emit_expr(node->data.repeat_stmt.cond);
            fprintf(out, "));\n");
            break;
        }
        case NODE_WITH: {
            emit_line("{");
            indent_level += 2;
            emit_indent();
            fprintf(out, "auto& _w = ");
            emit_expr(node->data.with_stmt.expr);
            fprintf(out, ";\n");
            emit_stmt(node->data.with_stmt.body);
            indent_level -= 2;
            emit_line("}");
            break;
        }
        case NODE_ATTEMPT: {
            emit_line("try");
            emit_begin_block();
            ASTNode *s = node->data.attempt.body;
            while (s) { emit_stmt(s); s = s->next; }
            emit_end_block();
            if (node->data.attempt.recover) {
                emit_line("catch (const std::exception& e)");
                emit_begin_block();
                if (node->data.attempt.err_var) {
                    emit_indent();
                    fprintf(out, "std::string %s = e.what();\n", node->data.attempt.err_var);
                }
                emit_stmt(node->data.attempt.recover);
                emit_end_block();
            } else {
                emit_line("catch (...) { throw; }");
            }
            break;
        }
        case NODE_BREAK: emit_line("break;"); break;
        case NODE_CONTINUE: emit_line("continue;"); break;
        case NODE_DISPOSE: {
            emit_indent();
            fprintf(out, "delete ");
            emit_expr(node->data.dispose.ptr);
            fprintf(out, ";\n");
            break;
        }
        case NODE_ASM: {
            emit_indent();
            fprintf(out, "%s\n", node->data.asm.code);
            break;
        }
        case NODE_VAR_DECL: {
            emit_indent();
            {
                ASTNode *te = node->data.decl.type_expr;
                if (te && te->type == NODE_ARRAY_TYPE) {
                    int high = 0, low = 0;
                    if (te->data.array_type.high && te->data.array_type.high->type == NODE_NUMBER)
                        high = atoi(te->data.array_type.high->data.number.value);
                    if (te->data.array_type.low && te->data.array_type.low->type == NODE_NUMBER)
                        low = atoi(te->data.array_type.low->data.number.value);
                    emit_type(te->data.array_type.base);
                    fprintf(out, " %s[%d];\n", node->data.decl.name, high - low + 1);
                } else if (te && te->type == NODE_POINTER_TYPE) {
                    emit_type(te);
                    fprintf(out, " %s;\n", node->data.decl.name);
                } else if (te && (te->type == NODE_PROC_TYPE || te->type == NODE_FUNC_TYPE)) {
                    if (te->type == NODE_FUNC_TYPE && te->data.proc_type.return_type)
                        emit_type(te->data.proc_type.return_type);
                    else
                        fprintf(out, "void");
                    fprintf(out, " (*%s)(", node->data.decl.name);
                    ASTNode *pp = te->data.proc_type.params;
                    int first = 1;
                    while (pp) {
                        if (!first) fprintf(out, ", ");
                        emit_type(pp->data.decl.type_expr);
                        fprintf(out, " %s", pp->data.decl.name);
                        first = 0;
                        pp = pp->next;
                    }
                    if (first) fprintf(out, "void");
                    fprintf(out, ");\n");
                } else {
                    emit_type(te);
                    fprintf(out, " %s;\n", node->data.decl.name);
                }
            }
            break;
        }
        case NODE_EXPR_STMT: {
            emit_indent();
            emit_expr(node->data.expr_stmt.expr);
            fprintf(out, ";\n");
            break;
        }
        case NODE_EMPTY: break;
        default:
            emit_indent();
            fprintf(out, "/* unknown stmt */\n");
            break;
    }
}

static void emit_decl(ASTNode *node) {
    if (!node) return;
    switch (node->type) {
        case NODE_IMPORT: {
            char *path = node->data.import.path;
            if (path[0] == '<')
                fprintf(out, "#include %s\n", path);
            else
                fprintf(out, "#include \"%s\"\n", path);
            break;
        }

        case NODE_CONST_DECL: {
            if (node->data.decl.value && node->data.decl.value->type == NODE_STRING) {
                fprintf(out, "static const char* %s = ", node->data.decl.name);
                emit_expr(node->data.decl.value);
                fprintf(out, ";\n");
            } else {
                fprintf(out, "static constexpr int %s = ", node->data.decl.name);
                emit_expr(node->data.decl.value);
                fprintf(out, ";\n");
            }
            break;
        }

        case NODE_VAR_DECL: {
            ASTNode *te = node->data.decl.type_expr;
            if (te && te->type == NODE_ARRAY_TYPE) {
                emit_type(te->data.array_type.base);
                fprintf(out, " %s[", node->data.decl.name);
                fputc('(', out);
                if (te->data.array_type.high)
                    emit_expr(te->data.array_type.high);
                else
                    fprintf(out, "0");
                fprintf(out, ")-(");
                if (te->data.array_type.low)
                    emit_expr(te->data.array_type.low);
                else
                    fprintf(out, "0");
                fprintf(out, ")+1];\n");
            } else if (te && te->type == NODE_POINTER_TYPE) {
                emit_type(te);
                fprintf(out, " %s", node->data.decl.name);
                if (node->data.decl.value) {
                    fprintf(out, " = (");
                    emit_type(te);
                    fprintf(out, ")");
                    emit_expr(node->data.decl.value);
                }
                fprintf(out, ";\n");
            } else if (te && (te->type == NODE_PROC_TYPE || te->type == NODE_FUNC_TYPE)) {
                if (te->type == NODE_FUNC_TYPE && te->data.proc_type.return_type)
                    emit_type(te->data.proc_type.return_type);
                else
                    fprintf(out, "void");
                fprintf(out, " (*%s)(", node->data.decl.name);
                ASTNode *pp = te->data.proc_type.params;
                int first = 1;
                while (pp) {
                    if (!first) fprintf(out, ", ");
                    int is_ref = (int)(intptr_t)pp->data.decl.value;
                    emit_type(pp->data.decl.type_expr);
                    if (is_ref) fprintf(out, "&");
                    fprintf(out, " %s", pp->data.decl.name);
                    first = 0;
                    pp = pp->next;
                }
                if (first) fprintf(out, "void");
                fprintf(out, ")");
                if (node->data.decl.value) {
                    fprintf(out, " = ");
                    emit_expr(node->data.decl.value);
                }
                fprintf(out, ";\n");
            } else {
                emit_type(te);
                fprintf(out, " %s", node->data.decl.name);
                if (node->data.decl.value) {
                    fprintf(out, " = (");
                    emit_type(te);
                    fprintf(out, ")");
                    emit_expr(node->data.decl.value);
                }
                fprintf(out, ";\n");
            }
            break;
        }

        case NODE_TYPE_DECL: {
            ASTNode *te = node->data.decl.type_expr;
            if (te && te->type == NODE_RECORD_DECL) {
                fprintf(out, "typedef struct {\n");
                indent_level += 2;
                ASTNode *f = te->data.record.fields;
                while (f) {
                    emit_indent();
                    emit_type(f->data.decl.type_expr);
                    fprintf(out, " %s;\n", f->data.decl.name);
                    f = f->next;
                }
                indent_level -= 2;
                fprintf(out, "} %s;\n", node->data.decl.name);
            }
            else if (te && te->type == NODE_CLASS_DECL) {
                fprintf(out, "class %s {\n", te->data.class.name);
                indent_level += 2;
                emit_line("public:");
                ASTNode *f = te->data.class.fields;
                while (f) {
                    emit_indent();
                    if (f->type == NODE_VAR_DECL) {
                        emit_type(f->data.decl.type_expr);
                        fprintf(out, " %s;\n", f->data.decl.name);
                    }
                    f = f->next;
                }
                ASTNode *m = te->data.class.methods;
                while (m) {
                    if (m->type == NODE_FUNC_DECL || m->type == NODE_PROC_DECL) {
                        emit_indent();
                        int is_ctor = (strcmp(m->data.func.name, "Constructor") == 0);
                        int is_dtor = (strcmp(m->data.func.name, "Destructor") == 0);

                        if (is_ctor) {
                            fprintf(out, "%s(", te->data.class.name);
                        } else if (is_dtor) {
                            fprintf(out, "~%s(", te->data.class.name);
                        } else {
                            if (m->data.func.return_type) {
                                emit_type(m->data.func.return_type);
                                fprintf(out, " %s(", m->data.func.name);
                            } else {
                                fprintf(out, "void %s(", m->data.func.name);
                            }
                        }

                        ASTNode *p = m->data.func.params;
                        int first = 1;
                        while (p) {
                            if (!first) fprintf(out, ", ");
                            int is_ref = (int)(intptr_t)p->data.decl.value;
                            ASTNode *te2 = p->data.decl.type_expr;
                            if (te2 && te2->type == NODE_ARRAY_TYPE) {
                                emit_type(te2->data.array_type.base);
                                if (is_ref) fprintf(out, "*& %s", p->data.decl.name);
                                else fprintf(out, " %s[]", p->data.decl.name);
                            } else if (is_ref) {
                                emit_type(te2);
                                fprintf(out, "& %s", p->data.decl.name);
                            } else {
                                emit_type(te2);
                                fprintf(out, " %s", p->data.decl.name);
                            }
                            first = 0;
                            p = p->next;
                        }
                        fprintf(out, ");\n");
                    }
                    m = m->next;
                }
                indent_level -= 2;
                fprintf(out, "};\n");
            }
            else if (te && (te->type == NODE_PROC_TYPE || te->type == NODE_FUNC_TYPE)) {
                fprintf(out, "typedef ");
                if (te->type == NODE_FUNC_TYPE && te->data.proc_type.return_type)
                    emit_type(te->data.proc_type.return_type);
                else
                    fprintf(out, "void");
                fprintf(out, " (*%s)(", node->data.decl.name);
                ASTNode *pp = te->data.proc_type.params;
                int first = 1;
                while (pp) {
                    if (!first) fprintf(out, ", ");
                    int is_ref = (int)(intptr_t)pp->data.decl.value;
                    emit_type(pp->data.decl.type_expr);
                    if (is_ref) fprintf(out, "&");
                    fprintf(out, " %s", pp->data.decl.name);
                    first = 0;
                    pp = pp->next;
                }
                if (first) fprintf(out, "void");
                fprintf(out, ");\n");
            }
            else {
                fprintf(out, "typedef ");
                emit_type(te);
                fprintf(out, " %s;\n", node->data.decl.name);
            }
            break;
        }

        case NODE_FUNC_DECL:
        case NODE_PROC_DECL: {
            int is_ctor = (strcmp(node->data.func.name, "Constructor") == 0);
            int is_dtor = (strcmp(node->data.func.name, "Destructor") == 0);

            if (node->data.func.is_method) {
                if (is_ctor) {
                    fprintf(out, "%s::%s(", node->data.func.class_name, node->data.func.class_name);
                } else if (is_dtor) {
                    fprintf(out, "%s::~%s(", node->data.func.class_name, node->data.func.class_name);
                } else {
                    if (node->data.func.return_type) {
                        emit_type(node->data.func.return_type);
                        fprintf(out, " %s::%s(", node->data.func.class_name, node->data.func.name);
                    } else {
                        fprintf(out, "void %s::%s(", node->data.func.class_name, node->data.func.name);
                    }
                }
            } else {
                if (is_ctor || is_dtor) {
                    fprintf(stderr, "Error: Constructor/Destructor must be methods of a class.\n");
                    exit(1);
                }
                if (node->data.func.return_type) {
                    emit_type(node->data.func.return_type);
                    fprintf(out, " %s(", node->data.func.name);
                } else {
                    fprintf(out, "void %s(", node->data.func.name);
                }
            }

            ASTNode *p = node->data.func.params;
            int first = 1;
            while (p) {
                if (!first) fprintf(out, ", ");
                int is_ref = (int)(intptr_t)p->data.decl.value;
                ASTNode *te = p->data.decl.type_expr;
                if (te && te->type == NODE_ARRAY_TYPE) {
                    emit_type(te->data.array_type.base);
                    if (is_ref) fprintf(out, "*& %s", p->data.decl.name);
                    else fprintf(out, " %s[]", p->data.decl.name);
                } else if (is_ref) {
                    emit_type(te);
                    fprintf(out, "& %s", p->data.decl.name);
                } else {
                    emit_type(te);
                    fprintf(out, " %s", p->data.decl.name);
                }
                first = 0;
                p = p->next;
            }
            fprintf(out, ") ");
            if (node->data.func.body) {
                in_function = 1;
                current_function_name = node->data.func.name;
                if (node->type == NODE_FUNC_DECL && node->data.func.return_type) {
                    emit_line("{");
                    indent_level += 2;
                    emit_indent();
                    emit_type(node->data.func.return_type);
                    fprintf(out, " _result = ");
                    ASTNode *rt = node->data.func.return_type;
                    if (rt && rt->type == NODE_SIMPLE_TYPE &&
                        strcmp(rt->data.simple_type.name, "String") == 0)
                        fprintf(out, "\"\";\n");
                    else
                        fprintf(out, "0;\n");
                    if (node->data.func.body->type == NODE_BLOCK) {
                        ASTNode *s = node->data.func.body->data.block.stmt_list;
                        while (s) { emit_stmt(s); s = s->next; }
                    } else {
                        emit_stmt(node->data.func.body);
                    }
                    emit_indent();
                    fprintf(out, "return _result;\n");
                    indent_level -= 2;
                    emit_line("}");
                } else {
                    emit_stmt(node->data.func.body);
                }
                in_function = 0;
                current_function_name = NULL;
            } else {
                emit_line("{ /* body not parsed */ }");
            }
            break;
        }

        default:
            break;
    }
}

static void emit_cpp(ASTNode *ast, const char *filename) {
    out = fopen(filename, "w");
    if (!out) { fprintf(stderr, "Cannot open %s\n", filename); return; }
    indent_level = 0;

    fprintf(out, "// Generated by Vertex Compiler\n");
    fprintf(out, "// The Peak of Precision.\n\n");
    fprintf(out, "#include <iostream>\n#include <string>\n#include <cstdlib>\n");
    fprintf(out, "#include <cstring>\n#include <cmath>\n#include <cstddef>\n");
    fprintf(out, "#include <fstream>\n#include <vector>\n\n");

    ASTNode *node = ast;
    if (node && node->type == NODE_PROGRAM) {
        node = node->data.block.stmt_list;
    }

    ASTNode *cur = node;
    int has_windows = 0;
    while (cur) {
        if (cur->type == NODE_IMPORT && cur->data.import.path) {
            if (strstr(cur->data.import.path, "windows.h") != NULL) {
                has_windows = 1;
                break;
            }
        }
        cur = cur->next;
    }

    cur = node;
    while (cur) {
        if (cur->type == NODE_IMPORT) {
            emit_decl(cur);
        }
        cur = cur->next;
    }

    if (has_windows) {
        fprintf(out, "\n/* Vertex string bridge */\n");
        fprintf(out, "#ifdef _WIN32\n");
        fprintf(out, "inline BOOL Vtx_SetWindowText(HWND h, const std::string& s) "
                     "{ return ::SetWindowTextA(h, s.c_str()); }\n");
        fprintf(out, "inline BOOL Vtx_SetWindowText(HWND h, const char* s) "
                     "{ return ::SetWindowTextA(h, s); }\n");
        fprintf(out, "inline int Vtx_MessageBox(HWND h, const std::string& t, "
                     "const std::string& c, UINT u) "
                     "{ return ::MessageBoxA(h, t.c_str(), c.c_str(), u); }\n");
        fprintf(out, "inline int Vtx_MessageBox(HWND h, const char* t, "
                     "const char* c, UINT u) "
                     "{ return ::MessageBoxA(h, t, c, u); }\n");
        fprintf(out, "#define SetWindowTextA Vtx_SetWindowText\n");
        fprintf(out, "#define MessageBoxA Vtx_MessageBox\n");
        fprintf(out, "#endif\n\n");
    }

    cur = node;
    while (cur) {
        if (cur->type == NODE_CONST_DECL ||
            cur->type == NODE_TYPE_DECL || cur->type == NODE_VAR_DECL) {
            emit_decl(cur);
            fprintf(out, "\n");
        }
        cur = cur->next;
    }

    cur = node;
    while (cur) {
        if (cur->type == NODE_FUNC_DECL || cur->type == NODE_PROC_DECL) {
            emit_decl(cur);
            fprintf(out, "\n");
        }
        cur = cur->next;
    }

    fprintf(out, "int main() {\n");
    indent_level += 2;

    cur = node;
    while (cur) {
        if (cur->type == NODE_MAIN_BODY) {
            emit_stmt(cur);
            break;
        }
        cur = cur->next;
    }

    indent_level -= 2;
    fprintf(out, "  return 0;\n}\n");
    fclose(out);
    printf("Generated: %s\n", filename);
}

/* ================== Preprocessor ================== */

static int preprocess_depth = 0;

/* Append raw bytes to dynamic buffer */
static void pp_append(char **buf, size_t *len, const char *data, size_t n) {
    if (n == 0) return;
    char *nb = realloc(*buf, *len + n + 1);
    if (!nb) { fprintf(stderr, "Out of memory\n"); exit(1); }
    *buf = nb;
    memcpy(*buf + *len, data, n);
    *len += n;
    (*buf)[*len] = '\0';
}

static void pp_append_str(char **buf, size_t *len, const char *s) {
    pp_append(buf, len, s, strlen(s));
}

static void pp_append_char(char **buf, size_t *len, char c) {
    pp_append(buf, len, &c, 1);
}

static char *preprocess_file(const char *filename) {
    if (preprocess_depth > 32) {
        fprintf(stderr, "Error: import nesting too deep (possible circular Import of %s)\n", filename);
        exit(1);
    }
    preprocess_depth++;

    FILE *f = fopen(filename, "rb");
    if (!f) {
        fprintf(stderr, "Cannot open file: %s\n", filename);
        exit(1);
    }
    fseek(f, 0, SEEK_END);
    long flen = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *data = malloc((size_t)flen + 1);
    if (!data) { fclose(f); fprintf(stderr, "Out of memory\n"); exit(1); }
    size_t nread = fread(data, 1, (size_t)flen, f);
    data[nread] = '\0';
    fclose(f);

    char *result = NULL;
    size_t result_len = 0;

    /* Start of this file */
    {
        char *esc = escape_for_line_directive(filename);
        char dir[2048];
        snprintf(dir, sizeof(dir), "#line 1 \"%s\"\n", esc ? esc : filename);
        pp_append_str(&result, &result_len, dir);
        free(esc);
    }

    /* Track ORIGINAL line number in THIS file (not combined buffer) */
    int src_line = 1;
    const char *ptr = data;

    while (*ptr) {
        /* Block comment { ... } — copy as-is, count newlines for src_line */
        if (*ptr == '{') {
            pp_append_char(&result, &result_len, *ptr++);
            while (*ptr && *ptr != '}') {
                if (*ptr == '\n') src_line++;
                pp_append_char(&result, &result_len, *ptr++);
            }
            if (*ptr == '}')
                pp_append_char(&result, &result_len, *ptr++);
            continue;
        }

        /* Line comment // ... */
        if (*ptr == '/' && ptr[1] == '/') {
            while (*ptr && *ptr != '\n')
                pp_append_char(&result, &result_len, *ptr++);
            continue;
        }

        /* Newline in source → bump src_line */
        if (*ptr == '\n') {
            pp_append_char(&result, &result_len, *ptr++);
            src_line++;
            continue;
        }

        /* Import "file.vtx";  or  Import <header>; */
        if (strncmp(ptr, "Import", 6) == 0 &&
            (ptr[6] == ' ' || ptr[6] == '\t' || ptr[6] == '"' || ptr[6] == '<')) {
            const char *start = ptr;
            ptr += 6;
            while (*ptr == ' ' || *ptr == '\t') ptr++;

            if (*ptr == '"') {
                ptr++;
                const char *fname_start = ptr;
                while (*ptr && *ptr != '"' && *ptr != '\n') ptr++;
                if (*ptr == '"') {
                    char *fname = my_strndup(fname_start, (size_t)(ptr - fname_start));
                    ptr++; /* closing quote */
                    while (*ptr == ' ' || *ptr == '\t' || *ptr == ';') ptr++;

                    char *dot = strrchr(fname, '.');
                    if (dot && strcmp(dot, ".vtx") == 0) {
                        /* Expand imported .vtx (it brings its own #line markers) */
                        char *imported = preprocess_file(fname);
                        if (imported) {
                            pp_append_str(&result, &result_len, imported);
                            free(imported);
                        }
                        /* Consume the rest of the Import line (including its newline)
                           so parent line numbers stay in sync. */
                        while (*ptr && *ptr != '\n')
                            ptr++;
                        if (*ptr == '\n') {
                            ptr++;
                            src_line++;
                        }
                        /* Next content belongs to src_line */
                        {
                            char restore[1024];
                            {
                                char *esc = escape_for_line_directive(filename);
                                char restore[2048];
                                snprintf(restore, sizeof(restore),
                                         "#line %d \"%s\"\n", src_line, esc ? esc : filename);
                                pp_append_str(&result, &result_len, restore);
                                free(esc);
                            }
                        }
                        free(fname);
                        continue;
                    }
                    /* Quoted non-.vtx — keep as system-ish include line */
                    {
                        size_t line_len = (size_t)(ptr - start);
                        pp_append(&result, &result_len, start, line_len);
                    }
                    free(fname);
                    continue;
                }
                /* Malformed — fall through and copy one char */
                ptr = start;
            } else if (*ptr == '<') {
                while (*ptr && *ptr != '>' && *ptr != '\n') ptr++;
                if (*ptr == '>') ptr++;
                while (*ptr == ' ' || *ptr == '\t' || *ptr == ';') ptr++;
                {
                    size_t line_len = (size_t)(ptr - start);
                    pp_append(&result, &result_len, start, line_len);
                }
                continue;
            }
            /* Not a real Import form — copy 'I' and continue */
            ptr = start;
        }

        /* Ordinary character */
        pp_append_char(&result, &result_len, *ptr++);
    }

    free(data);
    if (!result) {
        result = malloc(1);
        result[0] = '\0';
    }
    preprocess_depth--;
    return result;
}


/* ================== Main ================== */

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Usage: vertexc <input.vtx>\n");
        fprintf(stderr, "vertexc 1.2 (file/line tracking + heap fix)\n");
        return 1;
    }

    char *preprocessed = preprocess_file(argv[1]);

    Lexer lex;
    lex.src = preprocessed;
    lex.pos = 0;
    lex.line = 1;
    lex.orig_line = 1;
    lex.filename = strdup(argv[1]);
    lex.filename_owned = 1;

    Parser p;
    p.lex = &lex;
    p.current = get_token(p.lex);

    ASTNode *ast = parse_program(&p);

    if (error_count > 0) {
        fprintf(stderr, "\n%d error(s) found. Compilation failed.\n", error_count);
        free(preprocessed);
        return 1;
    }

    if (!ast) {
        fprintf(stderr, "Parsing failed.\n");
        free(preprocessed);
        return 1;
    }

    emit_cpp(ast, "output.cpp");

    free(preprocessed);
    if (lex.filename_owned && lex.filename)
        free(lex.filename);
    return 0;
}