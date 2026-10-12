import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * MiniServer: an HTTP/1.1 web server built from raw TCP sockets (no frameworks, no com.sun.net.httpserver).
 *
 * Features: thread pool, keep-alive connections, request parsing (request line, headers, query string,
 * Content-Length body), a tiny router with path parameters (/api/todos/{id}), static file serving with
 * MIME types and path-traversal protection, a JSON REST API, and access logging with timing.
 *
 * Run:  java MiniServer [port] [publicDir]     then open http://localhost:8080
 */
public class MiniServer {

    // ============================================================ HTTP model
    record Request(String method, String path, Map<String, String> query, Map<String, String> headers,
                   String body, Map<String, String> params) {
        String header(String name) { return headers.getOrDefault(name.toLowerCase(), ""); }
        Request withParams(Map<String, String> p) { return new Request(method, path, query, headers, body, p); }
    }

    record Response(int status, String contentType, byte[] body, Map<String, String> headers) {
        static Response text(int status, String text) {
            return new Response(status, "text/plain; charset=utf-8", text.getBytes(StandardCharsets.UTF_8), new LinkedHashMap<>());
        }
        static Response json(int status, String json) {
            return new Response(status, "application/json; charset=utf-8", json.getBytes(StandardCharsets.UTF_8), new LinkedHashMap<>());
        }
    }

    interface Handler { Response handle(Request req) throws Exception; }

    static class HttpException extends RuntimeException {
        final int status;
        HttpException(int status, String msg) { super(msg); this.status = status; }
    }

    static final Map<Integer, String> REASONS = Map.of(
            200, "OK", 201, "Created", 204, "No Content", 400, "Bad Request", 404, "Not Found",
            405, "Method Not Allowed", 413, "Payload Too Large", 500, "Internal Server Error");

    static final Map<String, String> MIME = Map.of(
            "html", "text/html; charset=utf-8", "css", "text/css; charset=utf-8",
            "js", "text/javascript; charset=utf-8", "json", "application/json",
            "png", "image/png", "jpg", "image/jpeg", "svg", "image/svg+xml", "ico", "image/x-icon",
            "txt", "text/plain; charset=utf-8");

    static final int MAX_BODY = 1_000_000;
    static final int KEEP_ALIVE_TIMEOUT_MS = 5000;

    // ============================================================ Router
    static class Router {
        private record Route(String method, String[] parts, Handler handler) {}
        private final List<Route> routes = new ArrayList<>();

        Router on(String method, String pattern, Handler h) {
            routes.add(new Route(method, split(pattern), h));
            return this;
        }

        /** Returns the handler for this request, or throws 404/405. Fills in {param} values. */
        Response dispatch(Request req) throws Exception {
            String[] parts = split(req.path());
            boolean pathMatched = false;
            for (Route r : routes) {
                Map<String, String> params = match(r.parts(), parts);
                if (params == null) continue;
                pathMatched = true;
                if (r.method().equals(req.method())) return r.handler().handle(req.withParams(params));
            }
            if (pathMatched) throw new HttpException(405, "Method " + req.method() + " not allowed here");
            return null; // let static files try
        }

        private static Map<String, String> match(String[] pattern, String[] parts) {
            if (pattern.length != parts.length) return null;
            Map<String, String> params = new HashMap<>();
            for (int i = 0; i < pattern.length; i++) {
                if (pattern[i].startsWith("{") && pattern[i].endsWith("}"))
                    params.put(pattern[i].substring(1, pattern[i].length() - 1), parts[i]);
                else if (!pattern[i].equals(parts[i])) return null;
            }
            return params;
        }

        private static String[] split(String path) {
            return Arrays.stream(path.split("/")).filter(s -> !s.isEmpty()).toArray(String[]::new);
        }
    }

    // ============================================================ Server
    private final int port;
    private final Path publicDir;
    private final Router router = new Router();
    private final ExecutorService pool = Executors.newFixedThreadPool(Math.max(4, Runtime.getRuntime().availableProcessors() * 2));
    private final AtomicInteger requestCount = new AtomicInteger();
    private final Instant started = Instant.now();
    private volatile boolean running = true;
    private ServerSocket serverSocket;

    MiniServer(int port, Path publicDir) {
        this.port = port;
        this.publicDir = publicDir.toAbsolutePath().normalize();
    }

    Router router() { return router; }

    void start() throws IOException {
        serverSocket = new ServerSocket();
        serverSocket.setReuseAddress(true);
        serverSocket.bind(new InetSocketAddress(port));
        System.out.printf("MiniServer running on http://localhost:%d  (serving %s)%n", port, publicDir);
        while (running) {
            try {
                Socket client = serverSocket.accept();
                pool.submit(() -> handleConnection(client));
            } catch (SocketException e) {
                if (running) throw e;
            }
        }
    }

    void stop() throws IOException {
        running = false;
        serverSocket.close();
        pool.shutdownNow();
    }

    /** One TCP connection may carry many requests (HTTP keep-alive). */
    private void handleConnection(Socket socket) {
        try (socket) {
            socket.setSoTimeout(KEEP_ALIVE_TIMEOUT_MS);
            InputStream in = new BufferedInputStream(socket.getInputStream());
            OutputStream out = new BufferedOutputStream(socket.getOutputStream());
            boolean keepAlive = true;
            while (keepAlive) {
                long t0 = System.nanoTime();
                Request req;
                Response res;
                try {
                    req = parseRequest(in);
                    if (req == null) return; // client closed the connection
                } catch (SocketTimeoutException e) {
                    return; // idle keep-alive connection timed out
                } catch (HttpException e) {
                    write(out, errorResponse(e.status, e.getMessage()), false, false);
                    return;
                }

                try {
                    res = router.dispatch(req);
                    if (res == null) res = serveStatic(req);
                } catch (HttpException e) {
                    res = errorResponse(e.status, e.getMessage());
                } catch (Exception e) {
                    e.printStackTrace();
                    res = errorResponse(500, "Something went wrong");
                }

                keepAlive = !req.header("connection").equalsIgnoreCase("close");
                write(out, res, keepAlive, req.method().equals("HEAD"));
                requestCount.incrementAndGet();
                System.out.printf("%s %-6s %-28s %d  %.1fms%n", Thread.currentThread().getName().replace("pool-1-", ""),
                        req.method(), req.path(), res.status(), (System.nanoTime() - t0) / 1e6);
            }
        } catch (IOException ignored) {
            // client disconnected mid-request; nothing to do
        }
    }

    // ============================================================ Parsing
    private static String readLine(InputStream in) throws IOException {
        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        int b;
        while ((b = in.read()) != -1) {
            if (b == '\n') break;
            if (b != '\r') buf.write(b);
            if (buf.size() > 8192) throw new HttpException(400, "Header line too long");
        }
        if (b == -1 && buf.size() == 0) return null;
        return buf.toString(StandardCharsets.ISO_8859_1);
    }

    static Request parseRequest(InputStream in) throws IOException {
        String requestLine = readLine(in);
        if (requestLine == null) return null;
        while (requestLine.isEmpty()) { // tolerate stray blank lines between keep-alive requests
            requestLine = readLine(in);
            if (requestLine == null) return null;
        }
        String[] parts = requestLine.split(" ");
        if (parts.length != 3 || !parts[2].startsWith("HTTP/")) throw new HttpException(400, "Malformed request line");

        String method = parts[0].toUpperCase();
        String target = parts[1];
        int q = target.indexOf('?');
        String path = urlDecode(q >= 0 ? target.substring(0, q) : target);
        Map<String, String> query = q >= 0 ? parseQuery(target.substring(q + 1)) : Map.of();

        Map<String, String> headers = new HashMap<>();
        String line;
        while ((line = readLine(in)) != null && !line.isEmpty()) {
            int colon = line.indexOf(':');
            if (colon <= 0) throw new HttpException(400, "Malformed header");
            headers.put(line.substring(0, colon).trim().toLowerCase(), line.substring(colon + 1).trim());
        }

        String body = "";
        String lenHeader = headers.get("content-length");
        if (lenHeader != null) {
            int len;
            try { len = Integer.parseInt(lenHeader); } catch (NumberFormatException e) { throw new HttpException(400, "Bad Content-Length"); }
            if (len > MAX_BODY) throw new HttpException(413, "Body too large");
            body = new String(in.readNBytes(len), StandardCharsets.UTF_8);
        }
        return new Request(method, path, query, headers, body, Map.of());
    }

    static Map<String, String> parseQuery(String qs) {
        Map<String, String> map = new LinkedHashMap<>();
        for (String pair : qs.split("&")) {
            if (pair.isEmpty()) continue;
            int eq = pair.indexOf('=');
            map.put(urlDecode(eq >= 0 ? pair.substring(0, eq) : pair), eq >= 0 ? urlDecode(pair.substring(eq + 1)) : "");
        }
        return map;
    }

    static String urlDecode(String s) {
        try { return URLDecoder.decode(s, StandardCharsets.UTF_8); }
        catch (IllegalArgumentException e) { throw new HttpException(400, "Bad URL encoding"); }
    }

    // ============================================================ Writing
    private void write(OutputStream out, Response res, boolean keepAlive, boolean headOnly) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append("HTTP/1.1 ").append(res.status()).append(' ').append(REASONS.getOrDefault(res.status(), "")).append("\r\n");
        sb.append("Server: MiniServer/1.0\r\n");
        sb.append("Content-Type: ").append(res.contentType()).append("\r\n");
        sb.append("Content-Length: ").append(res.body().length).append("\r\n");
        sb.append("Connection: ").append(keepAlive ? "keep-alive" : "close").append("\r\n");
        res.headers().forEach((k, v) -> sb.append(k).append(": ").append(v).append("\r\n"));
        sb.append("\r\n");
        out.write(sb.toString().getBytes(StandardCharsets.ISO_8859_1));
        if (!headOnly) out.write(res.body());
        out.flush();
    }

    static Response errorResponse(int status, String message) {
        return Response.json(status, "{\"error\":" + Json.quote(message) + ",\"status\":" + status + "}");
    }

    // ============================================================ Static files
    private Response serveStatic(Request req) throws IOException {
        if (!req.method().equals("GET") && !req.method().equals("HEAD")) throw new HttpException(405, "Static files are read-only");
        String rel = req.path().equals("/") ? "index.html" : req.path().substring(1);
        Path file = publicDir.resolve(rel).normalize();
        // Path traversal guard: "/../../etc/passwd" must not escape the public folder.
        if (!file.startsWith(publicDir)) throw new HttpException(404, "Not found");
        if (Files.isDirectory(file)) file = file.resolve("index.html");
        if (!Files.isRegularFile(file)) throw new HttpException(404, "No such page: " + req.path());

        String name = file.getFileName().toString();
        String ext = name.contains(".") ? name.substring(name.lastIndexOf('.') + 1).toLowerCase() : "";
        Response res = new Response(200, MIME.getOrDefault(ext, "application/octet-stream"), Files.readAllBytes(file), new LinkedHashMap<>());
        res.headers().put("Cache-Control", "no-cache");
        return res;
    }

    // ============================================================ Tiny JSON helpers
    static final class Json {
        static String quote(String s) {
            StringBuilder sb = new StringBuilder("\"");
            for (char c : s.toCharArray()) {
                switch (c) {
                    case '"' -> sb.append("\\\"");
                    case '\\' -> sb.append("\\\\");
                    case '\n' -> sb.append("\\n");
                    case '\r' -> sb.append("\\r");
                    case '\t' -> sb.append("\\t");
                    default -> { if (c < 0x20) sb.append(String.format("\\u%04x", (int) c)); else sb.append(c); }
                }
            }
            return sb.append('"').toString();
        }

        /** Reads one string field from a flat JSON object, e.g. {"title":"Buy milk"}. Enough for this API. */
        static Optional<String> stringField(String json, String field) {
            int key = json.indexOf("\"" + field + "\"");
            if (key < 0) return Optional.empty();
            int colon = json.indexOf(':', key);
            int start = json.indexOf('"', colon + 1);
            if (colon < 0 || start < 0) return Optional.empty();
            StringBuilder sb = new StringBuilder();
            for (int i = start + 1; i < json.length(); i++) {
                char c = json.charAt(i);
                if (c == '\\' && i + 1 < json.length()) {
                    char n = json.charAt(++i);
                    switch (n) {
                        case 'n' -> sb.append('\n');
                        case 't' -> sb.append('\t');
                        case 'u' -> { if (i + 4 < json.length()) { sb.append((char) Integer.parseInt(json.substring(i + 1, i + 5), 16)); i += 4; } }
                        default -> sb.append(n);
                    }
                } else if (c == '"') return Optional.of(sb.toString());
                else sb.append(c);
            }
            return Optional.empty();
        }

        static Optional<Boolean> boolField(String json, String field) {
            int key = json.indexOf("\"" + field + "\"");
            if (key < 0) return Optional.empty();
            String rest = json.substring(json.indexOf(':', key) + 1).trim();
            if (rest.startsWith("true")) return Optional.of(true);
            if (rest.startsWith("false")) return Optional.of(false);
            return Optional.empty();
        }
    }

    // ============================================================ Demo app: a to-do REST API
    record Todo(int id, String title, boolean done) {
        String toJson() { return "{\"id\":" + id + ",\"title\":" + Json.quote(title) + ",\"done\":" + done + "}"; }
    }

    static void installTodoApi(MiniServer server) {
        Map<Integer, Todo> todos = new ConcurrentSkipListMap<>();
        AtomicInteger nextId = new AtomicInteger(1);
        for (String t : new String[]{"Finish OOP assignment", "Push projects to GitHub", "Learn how HTTP works"}) {
            int id = nextId.getAndIncrement();
            todos.put(id, new Todo(id, t, id == 2));
        }

        java.util.function.Function<Request, Todo> find = req -> {
            int id;
            try { id = Integer.parseInt(req.params().get("id")); } catch (NumberFormatException e) { throw new HttpException(400, "id must be a number"); }
            Todo t = todos.get(id);
            if (t == null) throw new HttpException(404, "No todo with id " + id);
            return t;
        };

        server.router()
            .on("GET", "/api/todos", req -> {
                String filter = req.query().getOrDefault("done", "");
                StringJoiner sj = new StringJoiner(",", "[", "]");
                for (Todo t : todos.values())
                    if (filter.isEmpty() || String.valueOf(t.done()).equals(filter)) sj.add(t.toJson());
                return Response.json(200, sj.toString());
            })
            .on("GET", "/api/todos/{id}", req -> Response.json(200, find.apply(req).toJson()))
            .on("POST", "/api/todos", req -> {
                String title = Json.stringField(req.body(), "title").map(String::trim)
                        .filter(s -> !s.isEmpty()).orElseThrow(() -> new HttpException(400, "JSON body needs a non-empty \"title\""));
                int id = nextId.getAndIncrement();
                Todo t = new Todo(id, title, false);
                todos.put(id, t);
                Response res = Response.json(201, t.toJson());
                res.headers().put("Location", "/api/todos/" + id);
                return res;
            })
            .on("PATCH", "/api/todos/{id}", req -> {
                Todo old = find.apply(req);
                Todo t = new Todo(old.id(), Json.stringField(req.body(), "title").orElse(old.title()),
                        Json.boolField(req.body(), "done").orElse(old.done()));
                todos.put(t.id(), t);
                return Response.json(200, t.toJson());
            })
            .on("DELETE", "/api/todos/{id}", req -> {
                todos.remove(find.apply(req).id());
                return new Response(204, "text/plain", new byte[0], new LinkedHashMap<>());
            })
            .on("GET", "/api/stats", req -> Response.json(200, String.format(
                    "{\"requests\":%d,\"uptimeSeconds\":%d,\"todos\":%d,\"threads\":%d}",
                    server.requestCount.get(), java.time.Duration.between(server.started, Instant.now()).getSeconds(),
                    todos.size(), Thread.activeCount())));
    }

    public static void main(String[] args) throws IOException {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 8080;
        Path dir = Path.of(args.length > 1 ? args[1] : "public");
        MiniServer server = new MiniServer(port, dir);
        installTodoApi(server);
        Runtime.getRuntime().addShutdownHook(new Thread(() -> { try { server.stop(); } catch (IOException ignored) {} }));
        server.start();
    }
}
