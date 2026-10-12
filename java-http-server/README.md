# MiniServer: an HTTP server from raw sockets (Java)

A working HTTP/1.1 web server built on `java.net.ServerSocket`, with **no frameworks and no built-in HTTP library**. It serves a to-do web app and a JSON REST API.

## Run it
```bash
javac -d out src/MiniServer.java
java -cp out MiniServer 8080 public
```
Open **http://localhost:8080**.

## What's implemented
| Feature | How |
|---|---|
| **Request parsing** | Reads the request line, headers, query string (`?done=true`), URL decoding, and the body via `Content-Length` |
| **Thread pool** | Each connection is handled by an `ExecutorService` worker, so many clients are served at once |
| **Keep-alive** | One TCP connection carries many requests, with a 5-second idle timeout |
| **Router** | Method + path patterns with parameters: `PATCH /api/todos/{id}` |
| **Static files** | MIME types, `index.html` for folders, `HEAD` support |
| **Security** | Path-traversal guard (`/../../etc/passwd` → 404) and a 1 MB body limit (413) |
| **Errors** | JSON errors for 400, 404, 405, 413, and 500, with the right status codes |
| **Logging** | Thread name, method, path, status, and time in ms for every request |

## REST API
| Method | Path | Does |
|---|---|---|
| GET | `/api/todos` | List all (`?done=true` / `?done=false` to filter) |
| GET | `/api/todos/{id}` | One to-do |
| POST | `/api/todos` | Create: `{"title": "..."}` → **201** + `Location` header |
| PATCH | `/api/todos/{id}` | Update `title` and/or `done` |
| DELETE | `/api/todos/{id}` | Delete → **204** |
| GET | `/api/stats` | Requests served, uptime, thread count |

```bash
curl -X POST -d '{"title":"Learn sockets"}' localhost:8080/api/todos
curl -X PATCH -d '{"done":true}' localhost:8080/api/todos/4
```

## Tested
- Every endpoint, including error cases and `"quotes"` / Unicode in titles
- `/../../etc/passwd` traversal is blocked
- Keep-alive: three requests over one connection
- **200 concurrent requests → 200 × `200 OK`**
