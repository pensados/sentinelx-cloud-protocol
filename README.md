# sentinelx-cloud-protocol

Contrato compartido entre `sentinelx-cloud-core` (agente en el servidor del usuario) y `sentinelx-cloud-hub` (servicio en la nube de pensainfra).

Este repo es la **fuente de verdad** del protocolo WebSocket que conecta ambos componentes. No contiene lógica — solo specs, schemas y bindings tipados que ambas partes importan.

## Estructura

- `messages.md` — Especificación en prosa del protocolo (leer primero)
- `schemas/` — JSON Schemas de cada tipo de mensaje
- `python/` — Bindings de Python (modelos Pydantic) que tanto core como hub importan
- `CHANGELOG.md` — Versionado semántico del protocolo

## Versionado

El protocolo sigue [SemVer](https://semver.org/):

- **MAJOR**: cambios incompatibles (un core viejo no puede hablar con un hub nuevo)
- **MINOR**: campos opcionales nuevos, mensajes nuevos (compatibilidad hacia atrás)
- **PATCH**: aclaraciones en docs, fixes de schemas sin cambios funcionales

La versión actual está declarada en `python/sentinelx_protocol/__init__.py` como `PROTOCOL_VERSION`.

## Uso desde otro proyecto

```bash
pip install "git+https://github.com/pensados/sentinelx-cloud-protocol.git@v1.0.0"
```

```python
from sentinelx_protocol import PROTOCOL_VERSION
from sentinelx_protocol.messages import HelloMessage, RequestMessage, ResponseMessage
```

## Compatibilidad

El hub mantiene compatibilidad con todas las versiones MINOR de la MAJOR actual. Cuando un core se conecta con `protocol_version` distinto, el hub valida:

- Misma MAJOR → acepta
- MAJOR distinta → rechaza con `code: protocol_version_mismatch` y le dice al core que actualice

## Licencia

Apache-2.0 — ver [LICENSE](./LICENSE)
