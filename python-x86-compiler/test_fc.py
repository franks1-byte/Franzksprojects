"""
Test suite for the FC compiler.

1. Program tests: compile real programs, run the native executables, compare the output.
2. Error tests: bad programs must fail with a helpful message (and never crash the compiler).
3. Differential fuzzing: generate hundreds of random expressions, compile them with FC *and* with
   gcc (as C), run both, and demand identical results. This catches subtle code-generation and
   optimizer bugs that hand-written tests miss.

Run:  python test_fc.py
"""
import os
import random
import subprocess
import sys
import tempfile

from fc import CompileError, compile_source

TMP = tempfile.mkdtemp(prefix="fc_test_")


def build_and_run(src, name="prog"):
    asm = compile_source(src)
    s_path, exe = os.path.join(TMP, name + ".s"), os.path.join(TMP, name)
    with open(s_path, "w") as f:
        f.write(asm)
    subprocess.run(["gcc", "-o", exe, s_path], check=True)
    r = subprocess.run([exe], capture_output=True, text=True, timeout=20)
    return r.stdout, r.returncode


PROGRAMS = [
    ("return code", "fn main() { return 42; }", "", 42),
    ("arithmetic + precedence", "fn main() { print(2 + 3 * 4 - 10 / 2); print((2 + 3) * 4); print(-7 / 2); print(-7 % 3); }", "9\n20\n-3\n-1\n", 0),
    ("recursion", "fn f(n) { return n <= 1 ? 1 : n * f(n - 1); } fn main() { print(f(20)); }", "2432902008176640000\n", 0),
    ("six parameters", "fn s(a,b,c,d,e,f) { return a+2*b+3*c+4*d+5*e+6*f; } fn main() { print(s(1,2,3,4,5,6)); }", "91\n", 0),
    ("nested calls keep the stack aligned", "fn id(x) { return x; } fn main() { print(id(id(1) + id(id(2) + id(3)))); printf(\"%ld %ld\\n\", id(7), id(8)); }", "6\n7 8\n", 0),
    ("while / break / continue",
     "fn main() { var s = 0; var i = 0; while (1) { i++; if (i > 10) break; if (i % 2) continue; s += i; } print(s); }", "30\n", 0),
    ("for with scopes", "fn main() { var x = 1; for (var x = 0; x < 3; x++) { var y = x * 10; print(y); } print(x); }", "0\n10\n20\n1\n", 0),
    ("short-circuit && ||",
     "global hits = 0; fn t() { hits++; return 1; } fn main() { var a = 0 && t(); var b = 1 || t(); var c = 1 && t(); print(a + b + c); print(hits); }", "2\n1\n", 0),
    ("arrays + pointers", "fn main() { var a[5]; var p = a; for (var i = 0; i < 5; i++) a[i] = i * i; *(p + 16) = 100; print(a[1] + a[4]); print(p[2]); }", "17\n100\n", 0),  # pointer math is in bytes; p[i] scales by 8
    ("arrays start zeroed", "fn main() { var a[100]; var s = 0; for (var i = 0; i < 100; i++) s += a[i]; print(s); }", "0\n", 0),
    ("pass pointer to local", "fn inc(p) { *p = *p + 1; } fn main() { var x = 41; inc(&x); print(x); }", "42\n", 0),
    ("globals + global arrays", "global g = -5; global arr[4]; fn main() { arr[3] = 9; g += arr[3]; print(g); }", "4\n", 0),
    ("post/pre increment", "fn main() { var i = 5; var a = i++; var b = ++i; print(a); print(b); print(i--); print(i); }", "5\n7\n7\n6\n", 0),
    ("compound assignment", "fn main() { var x = 3; x += 4; x *= 5; x -= 1; x /= 2; x %= 10; x <<= 3; x |= 1; x ^= 3; x &= 30; x >>= 1; print(x); }", "13\n", 0),
    ("strings + putchar", 'fn main() { prints("hi "); putchar(70); putchar(67); putchar(10); }', "hi FC\n", 0),
    ("char literals", "fn main() { print('A' + 1); print('\\n'); }", "66\n10\n", 0),
    ("64-bit overflow wraps", "fn main() { var x = 9223372036854775807; x = x + 1; print(x); print(9223372036854775807 + 1); }", "-9223372036854775808\n-9223372036854775808\n", 0),
    ("deep recursion", "fn d(n) { if (n == 0) return 0; return 1 + d(n - 1); } fn main() { print(d(100000)); }", "100000\n", 0),
    ("bubble sort 1000 elements",
     "fn main() { var a[1000]; var seed = 12345; for (var i = 0; i < 1000; i++) { seed = (seed * 1103515245 + 12345) % 2147483648; a[i] = seed % 10000; }"
     " for (var i = 0; i < 1000; i++) for (var j = 0; j < 999 - i; j++) if (a[j] > a[j+1]) { var t = a[j]; a[j] = a[j+1]; a[j+1] = t; }"
     " var ok = 1; for (var i = 1; i < 1000; i++) if (a[i-1] > a[i]) ok = 0; print(ok); }", "1\n", 0),
]

ERRORS = [
    ("undefined variable", "fn main() { return y; }", "undefined variable 'y'"),
    ("undefined function", "fn main() { return nope(1); }", "undefined function 'nope'"),
    ("wrong argument count", "fn f(a) { return a; } fn main() { return f(1, 2); }", "takes 1 arguments, got 2"),
    ("redeclared variable", "fn main() { var a = 1; var a = 2; }", "already declared"),
    ("break outside loop", "fn main() { break; }", "break outside a loop"),
    ("missing semicolon", "fn main() { var a = 1 return a; }", "expected ;"),
    ("assign to non-lvalue", "fn main() { 3 = 4; }", "can only assign"),
    ("no main", "fn helper() { return 1; }", "no main()"),
    ("constant division by zero", "fn main() { return 1 / 0; }", "division by zero"),
    ("bad character", "fn main() { return 1 @ 2; }", "unexpected character"),
    ("increment a constant", "fn main() { return --13; }", "can only increment"),
]


def run_programs():
    ok = True
    for i, (label, src, expected, code) in enumerate(PROGRAMS):
        try:
            out, rc = build_and_run(src, f"p{i}")
            good = out == expected and rc == code
        except Exception as e:
            out, rc, good = f"{type(e).__name__}: {e}", None, False
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label}" + ("" if good else f"\n        got {out!r} (exit {rc}), expected {expected!r} (exit {code})"))
    return ok


def run_errors():
    ok = True
    for label, src, needle in ERRORS:
        try:
            compile_source(src)
            msg, good = "compiled without error!", False
        except CompileError as e:
            msg = str(e)
            good = needle in msg
        except Exception as e:  # any other exception is a compiler crash
            msg, good = f"CRASH {type(e).__name__}: {e}", False
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {label:28s} -> {msg}")
    return ok


# ---------------------------------------------------------------- differential fuzzing
def random_expr(rng, depth, leaves):
    """Returns the same random expression twice: (FC syntax, C syntax).
    In C, comparisons, ! and && / || produce a 32-bit int, so the C side casts them back to long;
    in FC every value is 64-bit."""
    if depth == 0 or rng.random() < 0.2:
        leaf = rng.choice(leaves)()
        c_leaf = leaf if not leaf.lstrip("-").isdigit() else leaf + "L"
        return leaf, c_leaf
    r = rng.random()
    a, ca = random_expr(rng, depth - 1, leaves)
    b, cb = random_expr(rng, depth - 1, leaves)
    if r < 0.12:
        op = rng.choice(['-', '!', '~'])
        c = f"((long)(! {ca}))" if op == "!" else f"({op} {ca})"   # spaces stop "- -13" lexing as "--"
        return f"({op} {a})", c
    if r < 0.2:
        x, cx = random_expr(rng, depth - 1, leaves)
        return f"({a} ? {b} : {x})", f"({ca} ? {cb} : {cx})"
    op = rng.choice(["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "==", "!=", "<", "<=", ">", ">=", "&&", "||"])
    if op in ("/", "%"):
        b, cb = f"((({b}) & 255) + 1)", f"((({cb}) & 255L) + 1L)"   # never divide by zero (or -1, which can trap)
    if op in ("<<", ">>"):
        b, cb = f"(({b}) & 31)", f"(({cb}) & 31L)"                   # shifts of 64+ bits are undefined in C
    c = f"((long)({ca} {op} {cb}))" if op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||") else f"({ca} {op} {cb})"
    return f"({a} {op} {b})", c


def fuzz(n=400, seed=2026):
    rng = random.Random(seed)
    values = [rng.choice([0, 1, -1, 7, -13, 255, 1000003, -987654321, 2**62, -(2**63)]) for _ in range(3)]
    runtime_leaves = [lambda v=v: v for v in ("a", "b", "c")] + [lambda: str(rng.randint(-50, 50))]
    const_leaves = [lambda: str(rng.choice([0, 1, -1, 3, 17, -100, 65535, 2**40]))]
    pairs = [random_expr(rng, 4, runtime_leaves) for _ in range(n // 2)] + \
            [random_expr(rng, 4, const_leaves) for _ in range(n // 2)]   # constant ones exercise the optimizer
    exprs = [p[0] for p in pairs]
    c_exprs = [p[1].replace("-9223372036854775808L", "(-9223372036854775807L - 1L)") for p in pairs]

    fc_lines = "\n".join(f"    print({e});" for e in exprs)
    fc_src = f"fn run(a, b, c) {{\n{fc_lines}\n    return 0;\n}}\nfn main() {{ return run({values[0]}, {values[1]}, {values[2]}); }}\n"
    fc_src = fc_src.replace("-9223372036854775808", "(-9223372036854775807 - 1)")

    c_lines = "\n".join(f'    printf("%ld\\n", (long)({e}));' for e in c_exprs)
    vals = [str(v) + "L" if v != -(2**63) else "(-9223372036854775807L - 1)" for v in values]
    c_src = (f"#include <stdio.h>\n__attribute__((noinline)) int run(long a, long b, long c) {{\n{c_lines}\n    return 0;\n}}\n"
             f"int main(void) {{ return run({vals[0]}, {vals[1]}, {vals[2]}); }}\n")

    fc_out, _ = build_and_run(fc_src, "fuzz_fc")
    c_path, c_exe = os.path.join(TMP, "fuzz.c"), os.path.join(TMP, "fuzz_c")
    with open(c_path, "w") as f:
        f.write(c_src)
    subprocess.run(["gcc", "-O0", "-fwrapv", "-w", "-o", c_exe, c_path], check=True)  # -fwrapv: overflow wraps like FC
    c_out = subprocess.run([c_exe], capture_output=True, text=True).stdout

    mismatches = [(e, x, y) for e, x, y in zip(exprs, fc_out.splitlines(), c_out.splitlines()) if x != y]
    for e, x, y in mismatches[:5]:
        print(f"        MISMATCH {e}\n          FC={x}  gcc={y}")
    good = not mismatches and len(fc_out.splitlines()) == len(exprs)
    print(f"  {'PASS' if good else 'FAIL'}  {len(exprs)} random expressions (a={values[0]}, b={values[1]}, c={values[2]}): "
          f"{len(exprs) - len(mismatches)}/{len(exprs)} identical to gcc")
    return good


if __name__ == "__main__":
    print("Programs (compiled to native x86-64 and executed):")
    p = run_programs()
    print("\nCompile errors:")
    e = run_errors()
    print("\nDifferential fuzzing vs gcc:")
    f = all(fuzz(seed=s) for s in (1, 2, 3, 4, 5))
    print("\nALL TESTS PASSED" if p and e and f else "\nSOME TESTS FAILED")
    sys.exit(0 if p and e and f else 1)
