# FranzLang: a programming language written in Java

A complete small programming language built from scratch: **lexer → parser → abstract syntax tree → tree-walking interpreter**, all in one Java file with no libraries.

```js
fn makeCounter() {
  let count = 0
  return fn() { count = count + 1  return count }
}
let c = makeCounter()
c() c()
print("count is", c())   # count is 3
```

## Run it
```bash
javac -d out src/FranzLang.java
java -cp out FranzLang examples/showcase.fz   # run a program
java -cp out FranzLang                        # interactive REPL
```

## Language features
| Feature | Example |
|---|---|
| Variables | `let x = 10`  ·  `x = x + 1` |
| Numbers, strings, booleans, nil | `3.14`, `"hi\n"`, `true`, `nil` |
| Arithmetic & comparison | `+ - * / %`, `== != < <= > >=` |
| Logic (short-circuit) | `and`, `or`, `not` |
| Control flow | `if … { } else if … { } else { }`, `while … { }` |
| Functions & recursion | `fn fib(n) { … }` |
| Closures & lambdas | `fn(x) { return x * x }` |
| Lists | `[1, 2, 3]`, `list[0]`, `list[-1]`, `list[i] = v` |
| Built-ins | `print`, `len`, `push`, `str`, `clock` |
| Comments | `# like this` |

## How it works
1. **Lexer**: turns source text into tokens (`LET`, `IDENT x`, `EQ`, `NUMBER 10`…).
2. **Parser**: a *recursive descent* parser with one method per precedence level (`or → and → equality → comparison → term → factor → unary → postfix → primary`) builds an AST from Java `record`s.
3. **Interpreter**: walks the tree using Java 21 *pattern-matching switch* over a `sealed` interface. Scopes are a chain of `Env` objects; functions capture their `Env`, which is what makes closures work. `return` unwinds the stack with a lightweight exception.
4. **Errors**: friendly messages with line numbers (undefined variables, wrong argument count, division by zero, index out of range, infinite recursion).

Requires **Java 21+**.
