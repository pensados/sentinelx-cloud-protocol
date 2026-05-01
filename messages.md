# SentinelX Protocol — Specification

**Version:** 1.0.0
**Transport:** WebSocket Secure (WSS) over TLS 1.2+
**Encoding:** UTF-8 JSON, one message per WebSocket frame

## Connection lifecycle

```
core                                   hub
 │                                      │
 │  WSS /agent/connect?token=<JWT>      │
 │ ───────────────────────────────────▶ │
 │                                      │  verify enrollment JWT
 │                                      │  extract user_id, host_id
 │                                      │
 │  {"type":"hello",...}                │
 │ ───────────────────────────────────▶ │
 │                                      │  validate protocol_version
 │                                      │  register (user_id, host_id) → ws
 │                                      │
 │           {"type":"welcome",...}     │
 │ ◀─────────────────────────────────── │
 │                                      │
 │           {"type":"request",...}     │
 │ ◀─────────────────────────────────── │  (Claude llama una tool)
 │                                      │
 │  {"type":"response",...}             │
 │ ───────────────────────────────────▶ │  (resuelve el Future en el hub)
 │                                      │
 │  {"type":"ping"}                     │
 │ ───────────────────────────────────▶ │  (cada 30s)
 │           {"type":"pong"}            │
 │ ◀─────────────────────────────────── │
 │                                      │
```

## Authentication

El core se autentica con un **enrollment token** (JWT firmado por el hub durante el flow OAuth). Se manda como query param `?token=<JWT>` al abrir el WS.

Claims requeridas en el JWT:

- `iss`: `sentinelx-hub`
- `sub`: `user_id` (del Keycloak/Google del usuario)
- `host_id`: identificador único del host (generado en la instalación)
- `iat`, `exp`: estándar
- `scope`: `agent`

El hub rechaza la conexión con HTTP 401 si el token es inválido, expirado o tiene scope incorrecto.

## Message envelope

Todos los mensajes son objetos JSON con un campo `type` obligatorio:

```json
{ "type": "<message_type>", ...campos específicos... }
```

Tamaño máximo por frame: **1 MB**. Para payloads grandes (uploads), usar el flujo de chunks descrito en la sección "Large payloads".

## Message types

### `hello` (core → hub)

Primer mensaje después de abrir el WS. El hub no procesa requests hasta recibirlo.

```json
{
  "type": "hello",
  "protocol_version": "1.0.0",
  "agent_version": "0.3.2",
  "host": {
    "id": "host_abc123",
    "hostname": "pensa-orion",
    "os": "linux",
    "kernel": "6.8.0-45-generic",
    "arch": "x86_64"
  },
  "capabilities": ["exec", "edit", "service", "restart", "upload", "script"]
}
```

### `welcome` (hub → core)

Respuesta al `hello`. Si hay incompatibilidad, en vez de welcome se manda `error` y se cierra el WS.

```json
{
  "type": "welcome",
  "session_id": "sess_xyz789",
  "server_time": "2026-05-01T18:30:00Z",
  "heartbeat_interval_seconds": 30
}
```

### `request` (hub → core)

El hub le pide al core que ejecute una operación. Cada request tiene un `id` único que el core debe devolver en la response.

```json
{
  "type": "request",
  "id": "req_01JXYZ...",
  "op": "exec",
  "payload": { "command": "systemctl status nginx", "timeout": 30 },
  "deadline": "2026-05-01T18:30:30Z"
}
```

`op` válidos (mapean 1:1 a las tools del MCP):

- `ping`, `capabilities`, `help`, `state`
- `exec`, `script_run`
- `edit`, `edit_upload_init`, `edit_upload_file`, `edit_upload_complete`
- `restart`, `service`
- `upload_init`, `upload_chunk`, `upload_complete`, `upload_file`

### `response` (core → hub)

Respuesta a un `request`. **Obligatorio** devolver `id` igual al del request.

Caso éxito:

```json
{
  "type": "response",
  "id": "req_01JXYZ...",
  "ok": true,
  "result": { "stdout": "...", "stderr": "...", "exit_code": 0 }
}
```

Caso error:

```json
{
  "type": "response",
  "id": "req_01JXYZ...",
  "ok": false,
  "error": {
    "code": "command_not_allowed",
    "message": "command 'rm -rf /' rejected by policy",
    "details": { }
  }
}
```

Códigos de error estándar:

- `command_not_allowed` — bloqueado por capabilities
- `command_failed` — ejecución falló
- `timeout` — el core no terminó dentro de `deadline`
- `invalid_payload` — payload no matchea el schema esperado
- `unsupported_op` — el core no soporta esta operación
- `internal_error` — error inesperado en el core

### `ping` / `pong` (bidireccional)

Heartbeat para detectar conexiones muertas. Cualquiera de los dos lados puede iniciar.

```json
{ "type": "ping", "timestamp": "2026-05-01T18:30:00Z" }
{ "type": "pong", "timestamp": "2026-05-01T18:30:00Z" }
```

Si el hub no recibe ping/pong en 90s (3 intervalos), cierra el WS.

### `event` (core → hub)

Notificaciones asíncronas del core sin request previo. **No** generan response.

```json
{
  "type": "event",
  "kind": "service_state_changed",
  "data": { "service": "nginx", "state": "active" },
  "timestamp": "2026-05-01T18:30:00Z"
}
```

### `error` (hub → core)

Error fatal de protocolo. Se manda antes de cerrar el WS.

```json
{
  "type": "error",
  "code": "protocol_version_mismatch",
  "message": "agent uses protocol 0.x, hub requires >=1.0",
  "fatal": true
}
```

Códigos fatales:

- `protocol_version_mismatch`
- `auth_expired`
- `host_revoked`
- `duplicate_session` (otro WS se conectó con mismo host_id)
- `rate_limit_exceeded`

## Large payloads

Para archivos > 1 MB se usa flujo de upload por chunks. El cliente MCP (Claude) llama tools `upload_init`, `upload_chunk` (N veces), `upload_complete`. Cada llamada genera un request/response normal por el WS — el chunking es a nivel aplicación, no protocolo.

Tamaño recomendado de chunk: **256 KB**.

## Reconnection

El core debe implementar reconexión automática con **exponential backoff**:

- Intento 1: inmediato
- Intento 2: 1s
- Intento 3: 5s
- Intento 4+: 30s, 60s, 120s, 300s (max)

Al reconectar, el core manda `hello` de nuevo. Si el hub tenía requests en vuelo cuando se cayó la conexión, esos requests fallan con `agent_disconnected`.

## Idempotencia

Los `request.id` son únicos por sesión. El core **no debe** reusar IDs ni asumir que un mismo request va a llegar dos veces. Si el WS se reconecta, los requests viejos están perdidos — Claude los va a reintentar si corresponde.

## Versionado del protocolo

`protocol_version` en `hello` sigue SemVer. El hub:

- Acepta cualquier MINOR/PATCH dentro de la MAJOR actual
- Rechaza MAJOR distinta con `protocol_version_mismatch`

Cuando se introducen mensajes nuevos en una MINOR, el core viejo simplemente nunca los va a recibir/mandar — el hub debe degradarse limpiamente.
