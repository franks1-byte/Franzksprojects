import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * FranzLang: a small dynamically-typed programming language.
 *
 * Pipeline:  source text -> Lexer (tokens) -> Parser (AST) -> Interpreter (tree-walking evaluator)
 *
 * Supports: numbers, strings, booleans, nil, variables (let), arithmetic, comparison,
 * logic (and/or/not), if/else, while, functions with recursion and closures,
 * lists with indexing, and built-ins: print, len, push, str, clock.
 *
 * Run a file:  java FranzLang examples/fib.fz
 * Start REPL:  java FranzLang
 */
public class FranzLang {

    // ============================================================ LEXER
    enum T {
        NUMBER, STRING, IDENT,
        LET, FN, IF, ELSE, WHILE, RETURN, TRUE, FALSE, NIL, AND, OR, NOT,
        PLUS, MINUS, STAR, SLASH, PERCENT, EQ, EQEQ, NEQ, LT, LTE, GT, GTE,
        LPAREN, RPAREN, LBRACE, RBRACE, LBRACKET, RBRACKET, COMMA, SEMI, EOF
    }

    record Token(T type, String text, Object value, int line) {}

    static final Map<String, T> KEYWORDS = Map.ofEntries(
            Map.entry("let", T.LET), Map.entry("fn", T.FN), Map.entry("if", T.IF),
            Map.entry("else", T.ELSE), Map.entry("while", T.WHILE), Map.entry("return", T.RETURN),
            Map.entry("true", T.TRUE), Map.entry("false", T.FALSE), Map.entry("nil", T.NIL),
            Map.entry("and", T.AND), Map.entry("or", T.OR), Map.entry("not", T.NOT));

    static class Lexer {
        private final String src;
        private int pos = 0, line = 1;
        private final List<Token> tokens = new ArrayList<>();

        Lexer(String src) { this.src = src; }

        List<Token> lex() {
            while (pos < src.length()) {
                char c = src.charAt(pos);
                if (c == '\n') { line++; pos++; }
                else if (Character.isWhitespace(c)) pos++;
                else if (c == '#') { while (pos < src.length() && src.charAt(pos) != '\n') pos++; }
                else if (Character.isDigit(c)) number();
                else if (c == '"') string();
                else if (Character.isLetter(c) || c == '_') identifier();
                else symbol(c);
            }
            tokens.add(new Token(T.EOF, "", null, line));
            return tokens;
        }

        private void number() {
            int start = pos;
            while (pos < src.length() && (Character.isDigit(src.charAt(pos)) || src.charAt(pos) == '.')) pos++;
            String text = src.substring(start, pos);
            tokens.add(new Token(T.NUMBER, text, Double.parseDouble(text), line));
        }

        private void string() {
            pos++; // opening quote
            StringBuilder sb = new StringBuilder();
            while (pos < src.length() && src.charAt(pos) != '"') {
                char c = src.charAt(pos++);
                if (c == '\\' && pos < src.length()) {
                    char e = src.charAt(pos++);
                    sb.append(switch (e) { case 'n' -> '\n'; case 't' -> '\t'; default -> e; });
                } else {
                    if (c == '\n') line++;
                    sb.append(c);
                }
            }
            if (pos >= src.length()) throw new LangError("Unterminated string", line);
            pos++; // closing quote
            tokens.add(new Token(T.STRING, sb.toString(), sb.toString(), line));
        }

        private void identifier() {
            int start = pos;
            while (pos < src.length() && (Character.isLetterOrDigit(src.charAt(pos)) || src.charAt(pos) == '_')) pos++;
            String text = src.substring(start, pos);
            tokens.add(new Token(KEYWORDS.getOrDefault(text, T.IDENT), text, null, line));
        }

        private void symbol(char c) {
            String two = pos + 1 < src.length() ? src.substring(pos, pos + 2) : "";
            T type = switch (two) {
                case "==" -> T.EQEQ; case "!=" -> T.NEQ; case "<=" -> T.LTE; case ">=" -> T.GTE;
                default -> null;
            };
            if (type != null) { tokens.add(new Token(type, two, null, line)); pos += 2; return; }
            type = switch (c) {
                case '+' -> T.PLUS; case '-' -> T.MINUS; case '*' -> T.STAR; case '/' -> T.SLASH;
                case '%' -> T.PERCENT; case '=' -> T.EQ; case '<' -> T.LT; case '>' -> T.GT;
                case '(' -> T.LPAREN; case ')' -> T.RPAREN; case '{' -> T.LBRACE; case '}' -> T.RBRACE;
                case '[' -> T.LBRACKET; case ']' -> T.RBRACKET; case ',' -> T.COMMA; case ';' -> T.SEMI;
                default -> throw new LangError("Unexpected character '" + c + "'", line);
            };
            tokens.add(new Token(type, String.valueOf(c), null, line));
            pos++;
        }
    }

    // ============================================================ AST
    sealed interface Node permits Expr, Stmt {}

    sealed interface Expr extends Node permits Literal, Var, Assign, Binary, Unary, Logical, Call, FnExpr, ListLit, Index, IndexAssign {}
    record Literal(Object value) implements Expr {}
    record Var(Token name) implements Expr {}
    record Assign(Token name, Expr value) implements Expr {}
    record Binary(Expr left, Token op, Expr right) implements Expr {}
    record Unary(Token op, Expr operand) implements Expr {}
    record Logical(Expr left, Token op, Expr right) implements Expr {}
    record Call(Expr callee, List<Expr> args, int line) implements Expr {}
    record FnExpr(List<Token> params, List<Stmt> body) implements Expr {}
    record ListLit(List<Expr> items) implements Expr {}
    record Index(Expr target, Expr index, int line) implements Expr {}
    record IndexAssign(Expr target, Expr index, Expr value, int line) implements Expr {}

    sealed interface Stmt extends Node permits ExprStmt, Let, Block, If, While, Return {}
    record ExprStmt(Expr expr) implements Stmt {}
    record Let(Token name, Expr init) implements Stmt {}
    record Block(List<Stmt> body) implements Stmt {}
    record If(Expr cond, Stmt then, Stmt otherwise) implements Stmt {}
    record While(Expr cond, Stmt body) implements Stmt {}
    record Return(Expr value) implements Stmt {}

    // ============================================================ PARSER (recursive descent)
    static class Parser {
        private final List<Token> tokens;
        private int pos = 0;

        Parser(List<Token> tokens) { this.tokens = tokens; }

        List<Stmt> parse() {
            List<Stmt> program = new ArrayList<>();
            while (!check(T.EOF)) program.add(statement());
            return program;
        }

        // ---- statements
        private Stmt statement() {
            if (match(T.LET)) {
                Token name = expect(T.IDENT, "variable name");
                Expr init = match(T.EQ) ? expression() : new Literal(null);
                optionalSemi();
                return new Let(name, init);
            }
            if (check(T.FN) && peek(1).type() == T.IDENT) { // fn name(...) {...}  ->  let name = fn(...) {...}
                advance();
                Token name = advance();
                return new Let(name, functionRest());
            }
            if (match(T.IF)) {
                Expr cond = expression();
                Stmt then = block();
                Stmt otherwise = null;
                if (match(T.ELSE)) otherwise = check(T.IF) ? statement() : block();
                return new If(cond, then, otherwise);
            }
            if (match(T.WHILE)) return new While(expression(), block());
            if (match(T.RETURN)) {
                Expr value = (check(T.RBRACE) || check(T.SEMI)) ? new Literal(null) : expression();
                optionalSemi();
                return new Return(value);
            }
            if (check(T.LBRACE)) return block();
            Expr e = expression();
            optionalSemi();
            return new ExprStmt(e);
        }

        private Block block() {
            expect(T.LBRACE, "'{'");
            List<Stmt> body = new ArrayList<>();
            while (!check(T.RBRACE) && !check(T.EOF)) body.add(statement());
            expect(T.RBRACE, "'}'");
            return new Block(body);
        }

        private FnExpr functionRest() {
            expect(T.LPAREN, "'('");
            List<Token> params = new ArrayList<>();
            if (!check(T.RPAREN)) do params.add(expect(T.IDENT, "parameter name")); while (match(T.COMMA));
            expect(T.RPAREN, "')'");
            return new FnExpr(params, block().body());
        }

        // ---- expressions, lowest precedence first
        private Expr expression() { return assignment(); }

        private Expr assignment() {
            Expr target = or();
            if (match(T.EQ)) {
                Expr value = assignment();
                if (target instanceof Var v) return new Assign(v.name(), value);
                if (target instanceof Index i) return new IndexAssign(i.target(), i.index(), value, i.line());
                throw new LangError("Invalid assignment target", previous().line());
            }
            return target;
        }

        private Expr or() {
            Expr e = and();
            while (match(T.OR)) e = new Logical(e, previous(), and());
            return e;
        }

        private Expr and() {
            Expr e = equality();
            while (match(T.AND)) e = new Logical(e, previous(), equality());
            return e;
        }

        private Expr equality() {
            Expr e = comparison();
            while (match(T.EQEQ, T.NEQ)) e = new Binary(e, previous(), comparison());
            return e;
        }

        private Expr comparison() {
            Expr e = term();
            while (match(T.LT, T.LTE, T.GT, T.GTE)) e = new Binary(e, previous(), term());
            return e;
        }

        private Expr term() {
            Expr e = factor();
            while (match(T.PLUS, T.MINUS)) e = new Binary(e, previous(), factor());
            return e;
        }

        private Expr factor() {
            Expr e = unary();
            while (match(T.STAR, T.SLASH, T.PERCENT)) e = new Binary(e, previous(), unary());
            return e;
        }

        private Expr unary() {
            if (match(T.MINUS, T.NOT)) return new Unary(previous(), unary());
            return postfix();
        }

        private Expr postfix() {
            Expr e = primary();
            while (true) {
                if (match(T.LPAREN)) {
                    int line = previous().line();
                    List<Expr> args = new ArrayList<>();
                    if (!check(T.RPAREN)) do args.add(expression()); while (match(T.COMMA));
                    expect(T.RPAREN, "')'");
                    e = new Call(e, args, line);
                } else if (match(T.LBRACKET)) {
                    int line = previous().line();
                    Expr index = expression();
                    expect(T.RBRACKET, "']'");
                    e = new Index(e, index, line);
                } else return e;
            }
        }

        private Expr primary() {
            if (match(T.NUMBER, T.STRING)) return new Literal(previous().value());
            if (match(T.TRUE)) return new Literal(true);
            if (match(T.FALSE)) return new Literal(false);
            if (match(T.NIL)) return new Literal(null);
            if (match(T.IDENT)) return new Var(previous());
            if (match(T.FN)) return functionRest();
            if (match(T.LPAREN)) { Expr e = expression(); expect(T.RPAREN, "')'"); return e; }
            if (match(T.LBRACKET)) {
                List<Expr> items = new ArrayList<>();
                if (!check(T.RBRACKET)) do items.add(expression()); while (match(T.COMMA));
                expect(T.RBRACKET, "']'");
                return new ListLit(items);
            }
            Token t = peek(0);
            throw new LangError("Unexpected '" + t.text() + "'", t.line());
        }

        // ---- helpers
        private Token peek(int ahead) { return tokens.get(Math.min(pos + ahead, tokens.size() - 1)); }
        private Token previous() { return tokens.get(pos - 1); }
        private Token advance() { return tokens.get(pos++); }
        private boolean check(T type) { return peek(0).type() == type; }
        private boolean match(T... types) {
            for (T t : types) if (check(t)) { pos++; return true; }
            return false;
        }
        private Token expect(T type, String what) {
            if (check(type)) return advance();
            throw new LangError("Expected " + what + " but found '" + peek(0).text() + "'", peek(0).line());
        }
        private void optionalSemi() { match(T.SEMI); }
    }

    // ============================================================ RUNTIME
    static class LangError extends RuntimeException {
        LangError(String msg, int line) { super("[line " + line + "] " + msg); }
    }

    /** Thrown to unwind the stack on `return` (not an error). */
    static class ReturnSignal extends RuntimeException {
        final Object value;
        ReturnSignal(Object value) { super(null, null, false, false); this.value = value; }
    }

    static class Env {
        final Map<String, Object> vars = new HashMap<>();
        final Env parent;
        Env(Env parent) { this.parent = parent; }

        Object get(Token name) {
            for (Env e = this; e != null; e = e.parent)
                if (e.vars.containsKey(name.text())) return e.vars.get(name.text());
            throw new LangError("Undefined variable '" + name.text() + "'", name.line());
        }

        void assign(Token name, Object value) {
            for (Env e = this; e != null; e = e.parent)
                if (e.vars.containsKey(name.text())) { e.vars.put(name.text(), value); return; }
            throw new LangError("Undefined variable '" + name.text() + "' (declare it with let)", name.line());
        }
    }

    interface Callable { Object call(Interpreter in, List<Object> args, int line); int arity(); }

    /** A user-defined function. It keeps the environment it was created in, which makes closures work. */
    record Function(FnExpr decl, Env closure) implements Callable {
        public int arity() { return decl.params().size(); }
        public Object call(Interpreter in, List<Object> args, int line) {
            Env local = new Env(closure);
            for (int i = 0; i < args.size(); i++) local.vars.put(decl.params().get(i).text(), args.get(i));
            try { in.execBlock(decl.body(), local); }
            catch (ReturnSignal r) { return r.value; }
            return null;
        }
        @Override public String toString() { return "<fn/" + arity() + ">"; }
    }

    record Builtin(String name, int arity, java.util.function.BiFunction<List<Object>, Integer, Object> fn) implements Callable {
        public Object call(Interpreter in, List<Object> args, int line) { return fn.apply(args, line); }
        @Override public String toString() { return "<builtin " + name + ">"; }
    }

    // ============================================================ INTERPRETER
    static class Interpreter {
        final Env globals = new Env(null);

        Interpreter() {
            def(new Builtin("print", -1, (a, l) -> {
                StringJoiner sj = new StringJoiner(" ");
                for (Object o : a) sj.add(stringify(o));
                System.out.println(sj);
                return null;
            }));
            def(new Builtin("len", 1, (a, l) -> {
                if (a.get(0) instanceof List<?> list) return (double) list.size();
                if (a.get(0) instanceof String s) return (double) s.length();
                throw new LangError("len() needs a list or string", l);
            }));
            def(new Builtin("push", 2, (a, l) -> {
                if (!(a.get(0) instanceof List<?>)) throw new LangError("push() needs a list", l);
                @SuppressWarnings("unchecked") List<Object> list = (List<Object>) a.get(0);
                list.add(a.get(1));
                return a.get(0);
            }));
            def(new Builtin("str", 1, (a, l) -> stringify(a.get(0))));
            def(new Builtin("clock", 0, (a, l) -> System.nanoTime() / 1e9));
        }

        private void def(Builtin b) { globals.vars.put(b.name(), b); }

        void run(List<Stmt> program) { execBlock(program, globals); }

        void execBlock(List<Stmt> body, Env env) { for (Stmt s : body) exec(s, env); }

        void exec(Stmt s, Env env) {
            switch (s) {
                case ExprStmt es -> eval(es.expr(), env);
                case Let let -> env.vars.put(let.name().text(), eval(let.init(), env));
                case Block b -> execBlock(b.body(), new Env(env));
                case If i -> {
                    if (truthy(eval(i.cond(), env))) exec(i.then(), env);
                    else if (i.otherwise() != null) exec(i.otherwise(), env);
                }
                case While w -> { while (truthy(eval(w.cond(), env))) exec(w.body(), env); }
                case Return r -> throw new ReturnSignal(eval(r.value(), env));
            }
        }

        Object eval(Expr e, Env env) {
            return switch (e) {
                case Literal l -> l.value();
                case Var v -> env.get(v.name());
                case Assign a -> { Object val = eval(a.value(), env); env.assign(a.name(), val); yield val; }
                case Unary u -> {
                    Object v = eval(u.operand(), env);
                    yield u.op().type() == T.NOT ? !truthy(v) : -num(v, u.op());
                }
                case Logical lg -> {
                    Object left = eval(lg.left(), env);
                    if (lg.op().type() == T.OR) yield truthy(left) ? left : eval(lg.right(), env);
                    yield !truthy(left) ? left : eval(lg.right(), env);
                }
                case Binary b -> binary(b, eval(b.left(), env), eval(b.right(), env));
                case FnExpr f -> new Function(f, env);
                case ListLit ll -> {
                    List<Object> list = new ArrayList<>();
                    for (Expr item : ll.items()) list.add(eval(item, env));
                    yield list;
                }
                case Index ix -> {
                    List<Object> list = asList(eval(ix.target(), env), ix.line());
                    yield list.get(checkIndex(list, eval(ix.index(), env), ix.line()));
                }
                case IndexAssign ia -> {
                    List<Object> list = asList(eval(ia.target(), env), ia.line());
                    int i = checkIndex(list, eval(ia.index(), env), ia.line());
                    Object val = eval(ia.value(), env);
                    list.set(i, val);
                    yield val;
                }
                case Call c -> call(c, env);
            };
        }

        private Object call(Call c, Env env) {
            Object callee = eval(c.callee(), env);
            if (!(callee instanceof Callable fn)) throw new LangError("Can only call functions", c.line());
            List<Object> args = new ArrayList<>();
            for (Expr a : c.args()) args.add(eval(a, env));
            if (fn.arity() >= 0 && args.size() != fn.arity())
                throw new LangError("Expected " + fn.arity() + " arguments but got " + args.size(), c.line());
            try { return fn.call(this, args, c.line()); }
            catch (StackOverflowError so) { throw new LangError("Stack overflow (too much recursion)", c.line()); }
        }

        private Object binary(Binary b, Object l, Object r) {
            Token op = b.op();
            return switch (op.type()) {
                case PLUS -> {
                    if (l instanceof Double x && r instanceof Double y) yield x + y;
                    if (l instanceof String || r instanceof String) yield stringify(l) + stringify(r);
                    throw new LangError("'+' needs two numbers or a string", op.line());
                }
                case MINUS -> num(l, op) - num(r, op);
                case STAR -> num(l, op) * num(r, op);
                case SLASH -> {
                    double d = num(r, op);
                    if (d == 0) throw new LangError("Division by zero", op.line());
                    yield num(l, op) / d;
                }
                case PERCENT -> num(l, op) % num(r, op);
                case LT -> num(l, op) < num(r, op);
                case LTE -> num(l, op) <= num(r, op);
                case GT -> num(l, op) > num(r, op);
                case GTE -> num(l, op) >= num(r, op);
                case EQEQ -> Objects.equals(l, r);
                case NEQ -> !Objects.equals(l, r);
                default -> throw new LangError("Unknown operator " + op.text(), op.line());
            };
        }

        // ---- helpers
        static boolean truthy(Object o) { return o != null && !Boolean.FALSE.equals(o); }

        static double num(Object o, Token op) {
            if (o instanceof Double d) return d;
            throw new LangError("Operator '" + op.text() + "' needs numbers, got " + stringify(o), op.line());
        }

        @SuppressWarnings("unchecked")
        static List<Object> asList(Object o, int line) {
            if (o instanceof List<?>) return (List<Object>) o;
            throw new LangError("Only lists can be indexed", line);
        }

        static int checkIndex(List<Object> list, Object idx, int line) {
            if (!(idx instanceof Double d) || d != Math.floor(d)) throw new LangError("Index must be a whole number", line);
            int i = d.intValue();
            if (i < 0) i += list.size(); // negative indexes count from the end
            if (i < 0 || i >= list.size()) throw new LangError("Index " + d.intValue() + " out of range (size " + list.size() + ")", line);
            return i;
        }

        static String stringify(Object o) {
            if (o == null) return "nil";
            if (o instanceof Double d) return d == Math.floor(d) && !d.isInfinite() ? String.valueOf(d.longValue()) : d.toString();
            if (o instanceof List<?> list) {
                StringJoiner sj = new StringJoiner(", ", "[", "]");
                for (Object item : list) sj.add(item instanceof String s ? "\"" + s + "\"" : stringify(item));
                return sj.toString();
            }
            return o.toString();
        }
    }

    // ============================================================ ENTRY POINT
    static void runSource(String src, Interpreter in) {
        in.run(new Parser(new Lexer(src).lex()).parse());
    }

    public static void main(String[] args) throws Exception {
        Interpreter in = new Interpreter();
        if (args.length > 0) {
            try { runSource(Files.readString(Path.of(args[0])), in); }
            catch (LangError e) { System.err.println("Error " + e.getMessage()); System.exit(1); }
            return;
        }
        System.out.println("FranzLang REPL. Type code, or 'exit' to quit.");
        Scanner sc = new Scanner(System.in);
        while (true) {
            System.out.print("fz> ");
            if (!sc.hasNextLine()) break;
            String line = sc.nextLine();
            if (line.trim().equals("exit")) break;
            try {
                List<Stmt> prog = new Parser(new Lexer(line).lex()).parse();
                // In the REPL, show the value of a bare expression.
                if (prog.size() == 1 && prog.get(0) instanceof ExprStmt es && !(es.expr() instanceof Call))
                    System.out.println(Interpreter.stringify(in.eval(es.expr(), in.globals)));
                else in.run(prog);
            } catch (LangError e) {
                System.out.println("Error " + e.getMessage());
            } catch (ReturnSignal r) {
                System.out.println("Error: 'return' outside a function");
            }
        }
    }
}
