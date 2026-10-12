# FC: a compiler from scratch to x86-64 machine code

A compiler for a small C-like language, written in Python. It produces **real x86-64 assembly**, which becomes a **native executable** that runs directly on the CPU: no interpreter, no virtual machine.

```
source.fc → lexer → parser → AST → optimizer → code generator → x86-64 assembly → gcc/as/ld → native program
```

```c
fn fib(n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}
fn main() {
    prints("fib(30) = "); print(fib(30));     // fib(30) = 832040
    return 0;
}
```
It compiles to:
```asm
F_fib:
    push %rbp
    mov %rsp, %rbp
    sub $16, %rsp
    mov %rdi, -8(%rbp)
    ...
    call F_fib
```

## Run it (Linux, WSL, or macOS with gcc)
```bash
python fc.py examples/showcase.fc --run     # compile + run
python fc.py examples/showcase.fc -S        # just look at the assembly
python test_fc.py                           # full test suite
```
On Windows, use **WSL** (`wsl --install`), since the output targets Linux x86-64.

## The language
| Feature | Example |
|---|---|
| 64-bit integer variables | `var x = 5, y = 9;` |
| Functions + recursion (up to 6 params) | `fn gcd(a, b) { return b == 0 ? a : gcd(b, a % b); }` |
| Arrays (zero-initialized) | `var a[100]; a[i] = i * i;` |
| Pointers | `&x`, `*p = 3`, arrays passed to functions as pointers |
| Globals | `global counter = 0; global table[16];` |
| Control flow | `if/else`, `while`, `for`, `break`, `continue`, `?:` |
| All C operators | `+ - * / % & \| ^ << >> == != < <= > >= && \|\| ! ~ ++ --` and `+= -= *= /= %= <<= >>= &= \|= ^=` |
| Strings and chars | `prints("hi\n")`, `'A'` |
| Call C's standard library | `printf("%ld\n", x)`, `putchar(65)`, `malloc(80)` |

## How it works
| Stage | Details |
|---|---|
| **Lexer** | One regular expression splits the source into tokens and tracks line numbers for errors |
| **Parser** | Recursive descent with 10 precedence levels, producing an abstract syntax tree |
| **Optimizer** | Constant folding with exact 64-bit wraparound (`(2+3)*x` → `5*x`), strength reduction (`x*8` → `x<<3`), and dead-branch removal (`if (0) {…}` disappears) |
| **Code generator** | Each expression leaves its result in `%rax`; temporaries go on the stack; locals live at offsets from `%rbp` |
| **Calling convention** | Full **System V AMD64 ABI**: arguments in `rdi, rsi, rdx, rcx, r8, r9`, the stack aligned to 16 bytes at every call, and `%al = 0` for variadic C functions like `printf`, so FC code can call C libraries |

## Tested three ways
1. **19 programs** compiled to native code and run: recursion to depth 100,000, 6-argument calls, pointers, globals, 64-bit overflow, and sorting 1,000 numbers.
2. **11 error cases**, each giving a clear message with a line number and never crashing the compiler.
3. **Differential fuzzing against gcc**: thousands of random expressions are compiled by FC *and* by gcc, run, and compared. **16,000 out of 16,000 matched exactly**, including edge cases like `-9223372036854775808`, division of negatives, and shifts. The fuzzer found and helped fix two real optimizer bugs during development.
