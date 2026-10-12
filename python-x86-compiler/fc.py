#!/usr/bin/env python3
"""
FC: a compiler for a small C-like language that outputs real x86-64 assembly.

    source.fc  ->  [lexer]  ->  tokens  ->  [parser]  ->  AST  ->  [optimizer]  ->  AST
               ->  [code generator]  ->  x86-64 assembly (.s)  ->  [gcc/as + ld]  ->  native executable

The output runs directly on the CPU with no interpreter or virtual machine. It follows the System V AMD64
calling convention, so compiled functions can call C library functions (printf, putchar, malloc…).

Usage:
    python fc.py program.fc            # compile to ./program
    python fc.py program.fc -o out     # choose the output name
    python fc.py program.fc -S         # only emit assembly (program.s)
    python fc.py program.fc --run      # compile and run
"""
import argparse
import os
import re
import subprocess
import sys


class CompileError(Exception):
    def __init__(self, msg, line):
        super().__init__(f"line {line}: {msg}")


# ======================================================================== LEXER
TOKEN_RE = re.compile(r"""
    (?P<ws>[ \t\r]+) | (?P<nl>\n) | (?P<comment>//[^\n]*|/\*.*?\*/) |
    (?P<num>0x[0-9a-fA-F]+|\d+) | (?P<char>'(?:\\.|[^\\'])') | (?P<str>"(?:\\.|[^\\"])*") |
    (?P<id>[A-Za-z_]\w*) |
    (?P<op><<=|>>=|==|!=|<=|>=|&&|\|\||<<|>>|\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|->|[-+*/%<>=!&|^~(){}\[\];,?:])
""", re.VERBOSE | re.DOTALL)
KEYWORDS = {"fn", "var", "if", "else", "while", "for", "return", "break", "continue", "extern", "global"}
ESCAPES = {"n": "\n", "t": "\t", "0": "\0", "\\": "\\", "'": "'", '"': '"', "r": "\r"}


def unescape(s):
    return re.sub(r"\\(.)", lambda m: ESCAPES.get(m.group(1), m.group(1)), s)


def lex(src):
    tokens, line, pos = [], 1, 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise CompileError(f"unexpected character {src[pos]!r}", line)
        kind, text = m.lastgroup, m.group()
        if kind == "nl":
            line += 1
        elif kind == "comment":
            line += text.count("\n")
        elif kind == "num":
            tokens.append(("num", int(text, 0), line))
        elif kind == "char":
            tokens.append(("num", ord(unescape(text[1:-1])), line))
        elif kind == "str":
            tokens.append(("str", unescape(text[1:-1]), line))
        elif kind == "id":
            tokens.append(("kw" if text in KEYWORDS else "id", text, line))
        elif kind == "op":
            tokens.append(("op", text, line))
        pos = m.end()
    tokens.append(("eof", None, line))
    return tokens


# ======================================================================== AST
# Nodes are plain tuples: (kind, line, ...fields). Simple to pattern-match and print.
class Parser:
    PRECEDENCE = [  # lowest to highest
        ["||"], ["&&"], ["|"], ["^"], ["&"], ["==", "!="], ["<", "<=", ">", ">="], ["<<", ">>"], ["+", "-"], ["*", "/", "%"],
    ]

    def __init__(self, tokens):
        self.t, self.i = tokens, 0

    def peek(self, k=0):
        return self.t[min(self.i + k, len(self.t) - 1)]

    def line(self):
        return self.peek()[2]

    def at(self, kind, val=None):
        tk = self.peek()
        return tk[0] == kind and (val is None or tk[1] == val)

    def eat(self, kind, val=None):
        if self.at(kind, val):
            tk = self.t[self.i]
            self.i += 1
            return tk
        return None

    def expect(self, kind, val=None):
        tk = self.eat(kind, val)
        if not tk:
            got = self.peek()
            raise CompileError(f"expected {val or kind} but found {got[1]!r}", got[2])
        return tk

    # ---------------------------------------------------------------- top level
    def program(self):
        funcs, globals_, externs = [], [], []
        while not self.at("eof"):
            if self.eat("kw", "extern"):
                externs.append(self.expect("id")[1])
                self.expect("op", ";")
            elif self.eat("kw", "global"):
                name = self.expect("id")[1]
                size = None
                if self.eat("op", "["):
                    size = self.expect("num")[1]
                    self.expect("op", "]")
                init = 0
                if self.eat("op", "="):
                    neg = bool(self.eat("op", "-"))
                    init = self.expect("num")[1] * (-1 if neg else 1)
                self.expect("op", ";")
                globals_.append((name, size, init))
            else:
                funcs.append(self.function())
        return ("program", 1, funcs, globals_, externs)

    def function(self):
        line = self.line()
        self.expect("kw", "fn")
        name = self.expect("id")[1]
        self.expect("op", "(")
        params = []
        if not self.at("op", ")"):
            while True:
                params.append(self.expect("id")[1])
                if not self.eat("op", ","):
                    break
        self.expect("op", ")")
        if len(params) > 6:
            raise CompileError("functions can have at most 6 parameters", line)
        return ("func", line, name, params, self.block())

    # ---------------------------------------------------------------- statements
    def block(self):
        line = self.line()
        self.expect("op", "{")
        body = []
        while not self.eat("op", "}"):
            if self.at("eof"):
                raise CompileError("missing '}'", line)
            body.append(self.statement())
        return ("block", line, body)

    def statement(self):
        line = self.line()
        if self.at("op", "{"):
            return self.block()
        if self.eat("kw", "var"):
            decls = []
            while True:
                name = self.expect("id")[1]
                if self.eat("op", "["):
                    size = self.expect("num")[1]
                    self.expect("op", "]")
                    decls.append(("arraydecl", line, name, size))
                else:
                    init = self.expr() if self.eat("op", "=") else ("num", line, 0)
                    decls.append(("vardecl", line, name, init))
                if not self.eat("op", ","):
                    break
            self.expect("op", ";")
            return ("decls", line, decls) if len(decls) > 1 else decls[0]  # no new scope
        if self.eat("kw", "if"):
            self.expect("op", "(")
            cond = self.expr()
            self.expect("op", ")")
            then = self.statement()
            other = self.statement() if self.eat("kw", "else") else None
            return ("if", line, cond, then, other)
        if self.eat("kw", "while"):
            self.expect("op", "(")
            cond = self.expr()
            self.expect("op", ")")
            return ("while", line, cond, self.statement(), None)
        if self.eat("kw", "for"):
            self.expect("op", "(")
            init = None if self.at("op", ";") else self.simple_statement()
            self.expect("op", ";")
            cond = ("num", line, 1) if self.at("op", ";") else self.expr()
            self.expect("op", ";")
            step = None if self.at("op", ")") else self.expr()
            self.expect("op", ")")
            body = self.statement()
            loop = ("while", line, cond, body, step)
            return ("block", line, [init, loop] if init else [loop])  # for gets its own scope
        if self.eat("kw", "return"):
            value = ("num", line, 0) if self.at("op", ";") else self.expr()
            self.expect("op", ";")
            return ("return", line, value)
        if self.eat("kw", "break"):
            self.expect("op", ";")
            return ("break", line)
        if self.eat("kw", "continue"):
            self.expect("op", ";")
            return ("continue", line)
        st = self.simple_statement()
        self.expect("op", ";")
        return st

    def simple_statement(self):
        line = self.line()
        if self.eat("kw", "var"):
            name = self.expect("id")[1]
            init = self.expr() if self.eat("op", "=") else ("num", line, 0)
            return ("vardecl", line, name, init)
        return ("exprstmt", line, self.expr())

    # ---------------------------------------------------------------- expressions
    def expr(self):
        return self.assignment()

    def assignment(self):
        left = self.ternary()
        line = self.line()
        for op in ("=", "+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "^="):
            if self.eat("op", op):
                if left[0] not in ("var", "index", "deref"):
                    raise CompileError("can only assign to variables, array elements or *pointers", line)
                right = self.assignment()
                if op != "=":
                    right = ("bin", line, op[:-1], left, right)
                return ("assign", line, left, right)
        return left

    def ternary(self):
        cond = self.binary(0)
        if self.eat("op", "?"):
            line = self.line()
            a = self.expr()
            self.expect("op", ":")
            b = self.ternary()
            return ("cond", line, cond, a, b)
        return cond

    def binary(self, level):
        if level == len(self.PRECEDENCE):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek()[0] == "op" and self.peek()[1] in self.PRECEDENCE[level]:
            op, line = self.peek()[1], self.line()
            self.i += 1
            right = self.binary(level + 1)
            if op in ("&&", "||"):
                left = ("logic", line, op, left, right)
            else:
                left = ("bin", line, op, left, right)
        return left

    def unary(self):
        line = self.line()
        for op in ("-", "!", "~"):
            if self.eat("op", op):
                return ("unary", line, op, self.unary())
        if self.eat("op", "&"):
            target = self.unary()
            if target[0] not in ("var", "index", "deref"):
                raise CompileError("can only take the address of a variable or element", line)
            return ("addr", line, target)
        if self.eat("op", "*"):
            return ("deref", line, self.unary())
        for op in ("++", "--"):
            if self.eat("op", op):
                target = self.unary()
                if target[0] not in ("var", "index", "deref"):
                    raise CompileError(f"can only increment/decrement a variable, not {target[0]}", line)
                return ("assign", line, target, ("bin", line, op[0], target, ("num", line, 1)))
        return self.postfix()

    def postfix(self):
        e = self.primary()
        while True:
            line = self.line()
            if self.eat("op", "["):
                idx = self.expr()
                self.expect("op", "]")
                e = ("index", line, e, idx)
            elif self.at("op", "++") or self.at("op", "--"):
                if e[0] not in ("var", "index", "deref"):
                    raise CompileError("can only increment/decrement a variable", line)
                op = self.eat("op")[1]
                e = ("postinc", line, e, 1 if op == "++" else -1)
            else:
                return e

    def primary(self):
        tk = self.peek()
        line = tk[2]
        if self.eat("num"):
            return ("num", line, tk[1])
        if self.eat("str"):
            return ("str", line, tk[1])
        if self.eat("op", "("):
            e = self.expr()
            self.expect("op", ")")
            return e
        if self.eat("id"):
            if self.eat("op", "("):
                args = []
                if not self.at("op", ")"):
                    while True:
                        args.append(self.expr())
                        if not self.eat("op", ","):
                            break
                self.expect("op", ")")
                if len(args) > 6:
                    raise CompileError("at most 6 arguments are supported", line)
                return ("call", line, tk[1], args)
            return ("var", line, tk[1])
        raise CompileError(f"unexpected {tk[1]!r}", line)


# ======================================================================== OPTIMIZER
def wrap64(v):
    """Behave like a 64-bit CPU register: overflow wraps around (two's complement)."""
    v &= (1 << 64) - 1
    return v - (1 << 64) if v >= 1 << 63 else v


def fold(node):
    """Constant folding + strength reduction: (2+3)*x -> 5*x, x*8 -> x<<3, if(0){...} -> nothing."""
    if not isinstance(node, tuple):
        return node
    if isinstance(node, tuple) and node and isinstance(node[0], str):
        node = tuple(fold(c) if isinstance(c, tuple) else [fold(x) for x in c] if isinstance(c, list) else c for c in node)
    kind = node[0]
    if kind == "bin":
        _, line, op, a, b = node
        if a[0] == "num" and b[0] == "num":
            x, y = a[2], b[2]
            if op in "/%" and y == 0:
                raise CompileError("division by zero in a constant expression", line)
            if op in ("<<", ">>") and not 0 <= y < 64:
                return node  # leave out-of-range shifts to the CPU, exactly like C compilers do
            if op in ("/", "%"):
                q = abs(x) // abs(y) * (1 if (x < 0) == (y < 0) else -1)  # C truncates toward zero
                val = q if op == "/" else x - q * y
            else:
                ops = {"+": lambda: x + y, "-": lambda: x - y, "*": lambda: x * y, "<<": lambda: x << y,
                       ">>": lambda: x >> y, "&": lambda: x & y, "|": lambda: x | y, "^": lambda: x ^ y,
                       "==": lambda: int(x == y), "!=": lambda: int(x != y), "<": lambda: int(x < y),
                       "<=": lambda: int(x <= y), ">": lambda: int(x > y), ">=": lambda: int(x >= y)}
                val = ops[op]()  # lazy: only compute the operator we need
            return ("num", line, wrap64(val))
        if op == "*" and b[0] == "num" and b[2] > 0 and b[2] & (b[2] - 1) == 0:
            return ("bin", line, "<<", a, ("num", line, b[2].bit_length() - 1))
        if op in "+-" and b[0] == "num" and b[2] == 0:
            return a
    if kind == "unary" and node[3][0] == "num":
        _, line, op, (_, _, v) = node
        return ("num", line, wrap64({"-": -v, "!": int(not v), "~": ~v}[op]))
    if kind == "if" and node[2][0] == "num":
        return node[3] if node[2][2] else (node[4] or ("block", node[1], []))
    return node


# ======================================================================== CODE GENERATOR
ARG_REGS = ["%rdi", "%rsi", "%rdx", "%rcx", "%r8", "%r9"]
LIBC = {"printf", "putchar", "puts", "malloc", "free", "exit", "rand", "srand", "time", "getchar", "abs"}


class CodeGen:
    """
    Stack-machine style: every expression leaves its value in %rax. Binary operators push the
    left side, evaluate the right side, then pop. Locals live at negative offsets from %rbp.
    """

    def __init__(self):
        self.out = []
        self.strings = {}
        self.label_n = 0
        self.globals = {}
        self.functions = {}

    def emit(self, s):
        self.out.append(s)

    def label(self, hint):
        self.label_n += 1
        return f".L{hint}{self.label_n}"

    # ------------------------------------------------------------ program / function
    def program(self, prog):
        _, _, funcs, globals_, externs = prog
        self.externs = set(externs) | LIBC
        for f in funcs:
            if f[2] in self.functions:
                raise CompileError(f"function {f[2]!r} defined twice", f[1])
            self.functions[f[2]] = len(f[3])
        if "main" not in self.functions:
            raise CompileError("no main() function", 1)

        self.emit("    .text")
        for f in funcs:
            self.function(f, globals_)

        if globals_:
            self.emit("    .data")
            for name, size, init in globals_:
                self.emit(f"    .globl G_{name}\nG_{name}:")
                self.emit(f"    .zero {size * 8}" if size else f"    .quad {init}")
        self.emit("    .section .rodata")
        for text, lab in self.strings.items():
            data = ", ".join(str(b) for b in text.encode("utf-8") + b"\0")
            self.emit(f"{lab}:\n    .byte {data}")
        self.emit('    .section .note.GNU-stack,"",@progbits')
        return "\n".join(self.out) + "\n"

    def function(self, f, globals_):
        _, line, name, params, body = f
        self.global_names = {g[0]: g[1] is not None for g in globals_}  # name -> is_array
        self.scopes = [{}]
        self.frame = 0
        self.loops = []
        self.depth = 0  # bytes pushed on the stack inside expressions (for call alignment)
        self.ret_label = self.label("ret")

        sym = "main" if name == "main" else f"F_{name}"
        self.emit(f"    .globl {sym}\n{sym}:")
        self.emit("    push %rbp\n    mov %rsp, %rbp")
        frame_idx = len(self.out)
        self.emit("    PLACEHOLDER")
        for i, p in enumerate(params):
            off = self.declare(p, 8, False, line)
            self.emit(f"    mov {ARG_REGS[i]}, {off}(%rbp)")
        self.stmt(body)
        self.emit("    mov $0, %rax")
        self.emit(f"{self.ret_label}:\n    leave\n    ret")
        size = (self.frame + 15) // 16 * 16
        self.out[frame_idx] = f"    sub ${size}, %rsp" if size else "    # no locals"

    def declare(self, name, nbytes, is_array, line):
        if name in self.scopes[-1]:
            raise CompileError(f"{name!r} already declared in this scope", line)
        self.frame += nbytes
        self.scopes[-1][name] = (-self.frame, is_array)
        return -self.frame

    def lookup(self, name, line):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if name in self.global_names:
            return ("global", self.global_names[name])
        raise CompileError(f"undefined variable {name!r}", line)

    # ------------------------------------------------------------ statements
    def stmt(self, s):
        if s is None:
            return
        kind, line = s[0], s[1]
        if kind == "block":
            self.scopes.append({})
            for st in s[2]:
                self.stmt(st)
            self.scopes.pop()
        elif kind == "decls":
            for st in s[2]:
                self.stmt(st)
        elif kind == "vardecl":
            self.expr(s[3])  # evaluate first, so "var x = x + 1" sees the outer x
            off = self.declare(s[2], 8, False, line)
            self.emit(f"    mov %rax, {off}(%rbp)")
        elif kind == "arraydecl":
            if s[3] <= 0:
                raise CompileError("array size must be positive", line)
            # zero-initialise the array, then remember where element 0 lives
            off = self.declare(s[2], s[3] * 8, True, line)
            self.emit(f"    lea {off}(%rbp), %rdi\n    mov ${s[3]}, %rcx\n    xor %eax, %eax\n    rep stosq")
        elif kind == "exprstmt":
            self.expr(s[2])
        elif kind == "return":
            self.expr(s[2])
            self.emit(f"    jmp {self.ret_label}")
        elif kind == "if":
            else_l, end_l = self.label("else"), self.label("endif")
            self.expr(s[2])
            self.emit(f"    test %rax, %rax\n    jz {else_l}")
            self.stmt(s[3])
            self.emit(f"    jmp {end_l}\n{else_l}:")
            self.stmt(s[4])
            self.emit(f"{end_l}:")
        elif kind == "while":
            top, cont, end = self.label("loop"), self.label("cont"), self.label("endloop")
            self.loops.append((cont, end))
            self.emit(f"{top}:")
            self.expr(s[2])
            self.emit(f"    test %rax, %rax\n    jz {end}")
            self.stmt(s[3])
            self.emit(f"{cont}:")
            if s[4] is not None:
                self.expr(s[4])
            self.emit(f"    jmp {top}\n{end}:")
            self.loops.pop()
        elif kind in ("break", "continue"):
            if not self.loops:
                raise CompileError(f"{kind} outside a loop", line)
            self.emit(f"    jmp {self.loops[-1][1 if kind == 'break' else 0]}")
        else:
            raise CompileError(f"unknown statement {kind}", line)

    # ------------------------------------------------------------ expressions
    def push(self):
        self.emit("    push %rax")
        self.depth += 8

    def pop(self, reg):
        self.emit(f"    pop {reg}")
        self.depth -= 8

    def address(self, e):
        """Put the address of an lvalue in %rax."""
        kind, line = e[0], e[1]
        if kind == "var":
            info = self.lookup(e[2], line)
            if info[0] == "global":
                self.emit(f"    lea G_{e[2]}(%rip), %rax")
            else:
                self.emit(f"    lea {info[0]}(%rbp), %rax")
        elif kind == "index":
            self.expr(e[2])          # base pointer (arrays evaluate to their address)
            self.push()
            self.expr(e[3])
            self.pop("%rcx")
            self.emit("    lea (%rcx,%rax,8), %rax")
        elif kind == "deref":
            self.expr(e[2])
        else:
            raise CompileError("not an lvalue", line)

    def expr(self, e):
        kind, line = e[0], e[1]
        if kind == "num":
            v = e[2]
            self.emit(f"    mov ${v}, %rax" if -2**31 <= v < 2**31 else f"    movabs ${v}, %rax")
        elif kind == "str":
            lab = self.strings.setdefault(e[2], f".Lstr{len(self.strings)}")
            self.emit(f"    lea {lab}(%rip), %rax")
        elif kind == "var":
            info = self.lookup(e[2], line)
            if info[0] == "global":
                self.emit(f"    {'lea' if info[1] else 'mov'} G_{e[2]}(%rip), %rax")
            elif info[1]:  # arrays decay to a pointer to their first element
                self.emit(f"    lea {info[0]}(%rbp), %rax")
            else:
                self.emit(f"    mov {info[0]}(%rbp), %rax")
        elif kind in ("index", "deref"):
            self.address(e)
            self.emit("    mov (%rax), %rax")
        elif kind == "addr":
            target = e[2]
            if target[0] == "var" and self.lookup(target[2], line)[1] is True:
                self.expr(target)  # &array is just the array's address
            else:
                self.address(target)
        elif kind == "assign":
            self.address(e[2])
            self.push()
            self.expr(e[3])
            self.pop("%rcx")
            self.emit("    mov %rax, (%rcx)")
        elif kind == "postinc":
            self.address(e[2])
            self.emit(f"    mov (%rax), %rcx\n    {'incq' if e[3] > 0 else 'decq'} (%rax)\n    mov %rcx, %rax")
        elif kind == "unary":
            self.expr(e[3])
            self.emit({"-": "    neg %rax", "~": "    not %rax",
                       "!": "    test %rax, %rax\n    sete %al\n    movzx %al, %rax"}[e[2]])
        elif kind == "logic":  # short-circuit && and ||
            end = self.label("logic")
            self.expr(e[3])
            self.emit("    test %rax, %rax\n    setne %al\n    movzx %al, %rax")
            self.emit(f"    {'jz' if e[2] == '&&' else 'jnz'} {end}")
            self.expr(e[4])
            self.emit(f"    test %rax, %rax\n    setne %al\n    movzx %al, %rax\n{end}:")
        elif kind == "cond":
            other, end = self.label("cond"), self.label("endcond")
            self.expr(e[2])
            self.emit(f"    test %rax, %rax\n    jz {other}")
            self.expr(e[3])
            self.emit(f"    jmp {end}\n{other}:")
            self.expr(e[4])
            self.emit(f"{end}:")
        elif kind == "bin":
            self.binop(e)
        elif kind == "call":
            self.call(e)
        else:
            raise CompileError(f"unknown expression {kind}", line)

    def binop(self, e):
        _, line, op, a, b = e
        # small optimisation: constants on the right don't need the stack
        if b[0] == "num" and -2**31 <= b[2] < 2**31 and op in ("+", "-", "&", "|", "^", "<<", ">>"):
            self.expr(a)
            ins = {"+": "add", "-": "sub", "&": "and", "|": "or", "^": "xor", "<<": "shl", ">>": "sar"}[op]
            self.emit(f"    {ins} ${b[2]}, %rax")
            return
        self.expr(a)
        self.push()
        self.expr(b)
        self.emit("    mov %rax, %rcx")
        self.pop("%rax")
        if op in ("+", "-", "&", "|", "^"):
            self.emit(f"    {dict(zip('+-&|^', ['add', 'sub', 'and', 'or', 'xor']))[op]} %rcx, %rax")
        elif op == "*":
            self.emit("    imul %rcx, %rax")
        elif op in ("/", "%"):
            self.emit("    cqo\n    idiv %rcx")
            if op == "%":
                self.emit("    mov %rdx, %rax")
        elif op in ("<<", ">>"):
            self.emit(f"    {'shl' if op == '<<' else 'sar'} %cl, %rax")
        else:
            cc = {"==": "e", "!=": "ne", "<": "l", "<=": "le", ">": "g", ">=": "ge"}[op]
            self.emit(f"    cmp %rcx, %rax\n    set{cc} %al\n    movzx %al, %rax")

    def call(self, e):
        _, line, name, args = e
        if name not in self.functions and name not in self.externs and name not in ("print", "prints"):
            raise CompileError(f"undefined function {name!r}", line)
        if name in self.functions and self.functions[name] != len(args):
            raise CompileError(f"{name}() takes {self.functions[name]} arguments, got {len(args)}", line)

        if name in ("print", "prints"):  # built-ins compile to printf calls
            if len(args) != 1:
                raise CompileError(f"{name}() takes 1 argument", line)
            fmt = "%ld\n" if name == "print" else "%s"
            args = [("str", line, fmt), args[0]]
            name = "printf"

        for a in args:
            self.expr(a)
            self.push()
        for i in reversed(range(len(args))):
            self.pop(ARG_REGS[i])
        # The ABI requires %rsp to be 16-byte aligned at every call.
        pad = self.depth % 16
        if pad:
            self.emit(f"    sub ${pad}, %rsp")
        if name in self.functions:
            self.emit(f"    call F_{name}")
        else:
            self.emit("    xor %eax, %eax")  # variadic functions (printf) read %al = number of vector args
            self.emit(f"    call {name}@PLT")
        if pad:
            self.emit(f"    add ${pad}, %rsp")


# ======================================================================== DRIVER
def compile_source(src):
    ast = Parser(lex(src)).program()
    ast = fold(ast)
    return CodeGen().program(ast)


def main():
    ap = argparse.ArgumentParser(description="FC compiler: C-like language to x86-64")
    ap.add_argument("source")
    ap.add_argument("-o", "--output")
    ap.add_argument("-S", action="store_true", help="only write assembly")
    ap.add_argument("--run", action="store_true", help="run the program after compiling")
    a = ap.parse_args()

    base = os.path.splitext(a.source)[0]
    try:
        with open(a.source, encoding="utf-8") as f:
            asm = compile_source(f.read())
    except CompileError as err:
        print(f"{a.source}: error: {err}", file=sys.stderr)
        sys.exit(1)

    asm_path = base + ".s"
    with open(asm_path, "w") as f:
        f.write(asm)
    if a.S:
        print(f"Wrote {asm_path}")
        return
    exe = a.output or base
    result = subprocess.run(["gcc", "-o", exe, asm_path])
    if result.returncode != 0:
        sys.exit("assembler/linker failed (this is a compiler bug, please report it)")
    os.remove(asm_path)
    if a.run:
        sys.exit(subprocess.run([os.path.abspath(exe)]).returncode)


if __name__ == "__main__":
    main()
