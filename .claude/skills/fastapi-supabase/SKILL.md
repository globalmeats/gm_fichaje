---
name: fastapi-supabase
description: >
  Convenciones de implementación del stack del proyecto de fichajes de Global Meats:
  FastAPI (async, Pydantic v2), Supabase/PostgreSQL con RLS, auth por PIN bcrypt,
  migraciones, estructura de carpetas, despliegue en Railway (región UE) y gestión de
  versiones con mise. USA ESTA SKILL al crear endpoints, modelos, migraciones, o al
  configurar build/deploy. Garantiza que la implementación respeta los patrones de
  inmutabilidad (audit-trail) y RLS (rgpd-dataguard). Consúltala al escribir código nuevo.
---

# FastAPI + Supabase — Convenciones

Stack fijado: FastAPI · Pydantic v2 · SQLAlchemy 2.x async · Supabase (Postgres + RLS) ·
bcrypt · Railway (UE) · mise. No introducir dependencias nuevas sin justificarlo.

## Estructura de proyecto

```
app/
├── main.py                 # FastAPI app, middleware, routers
├── core/
│   ├── config.py           # settings (Pydantic Settings), región UE
│   ├── security.py         # bcrypt PIN, JWT, rate-limit
│   └── time.py             # utilidades UTC, sellado temporal
├── domain/                 # entidades y reglas (ver skill fichaje-domain)
│   ├── models.py
│   ├── state_machine.py
│   └── hours.py
├── audit/                  # hash encadenado, correcciones (ver skill audit-trail)
│   ├── chain.py
│   └── corrections.py
├── api/
│   ├── fichaje.py          # endpoints de fichaje
│   ├── export.py           # PDF/CSV (REQ-04,17,18,19)
│   └── admin.py
├── db/
│   ├── session.py          # async engine/session
│   └── migrations/         # SQL versionado (RLS, triggers, políticas)
└── tests/                  # cobertura por REQ (ver matriz-aceptacion.md)
```

## Reglas de implementación

1. **Escritura de fichajes** pasa SIEMPRE por `audit/chain.py` (sella + encadena hash).
   Ningún endpoint inserta en `time_record` directamente sin pasar por ese servicio.
2. **Timestamps en UTC**, generados por el servidor (`core/time.py`). Nunca confiar en
   la hora del cliente salvo el flujo offline controlado (REQ-22).
3. **RLS no es opcional**: cada migración que crea una tabla con datos personales activa
   RLS y define políticas (ver `rgpd-dataguard`). Test que verifique aislamiento.
4. **Sin UPDATE/DELETE sobre `time_record`**: revocar permisos + trigger (audit-trail).
5. **Async de punta a punta**: endpoints `async def`, sesión async, sin llamadas
   bloqueantes.
6. **Validación de transiciones** de jornada en `domain/state_machine.py`, no en el API.

## Auth (REQ-05, 21)

Los trabajadores **no tienen email**: login con **código de empleado + PIN de 6 dígitos**.
Ver detalle en la skill `rgpd-dataguard` (identificación inequívoca vs autenticación).

- Flujo: `POST /auth/login` recibe `employee_code` + `pin`. Resuelve el trabajador por
  código, verifica el PIN con bcrypt, emite JWT con `role` y `worker_id`.
- El **código de empleado** se puede recordar en el navegador (cookie no sensible, equipo
  de uso personal) para que la persona solo teclee el PIN. El **PIN jamás se recuerda**
  ni se loguea.
- **Rate-limit + bloqueo temporal por `employee_code`** tras N fallos → `audit_alert`
  (REQ-25). Imprescindible con PIN corto.
- Sesión autenticada de **caducidad corta**; sin "recordar sesión"; volver a pantalla
  neutra tras fichar.
- **Reset de PIN**: endpoint solo admin/supervisor (`POST /admin/workers/{id}/reset-pin`)
  que regenera el PIN; la acción se registra en el audit trail (sin PIN en claro).
- Sin biometría.

## Migraciones

- SQL versionado en `db/migrations/`. Cada migración es idempotente y revisable.
- Orden típico: tablas → RLS enable → políticas → triggers append-only → índices.
- Ver `references/rls-patterns.md` para plantillas de políticas y triggers.

## Despliegue (Railway) — REQ-23

- Región **UE** obligatoria. El script de deploy verifica la región y **falla** si no
  es UE (no desplegar datos personales fuera de la UE).
- Variables sensibles por entorno, nunca en el repo.
- **mise**: fijar versión de Python. Atención al fallo de build Python/mise ya visto en
  otro proyecto del usuario; replicar el fix conocido (alinear versión en `.mise.toml`
  y `pyproject.toml`, limpiar caché si el build de Python falla).

## Tests por requisito

- Cada REQ con criterio en `legal-compliance/references/matriz-aceptacion.md` tiene su
  test. Antes de cerrar una tarea, correr `compliance_check.py` y la suite.

## Detalle

- `references/rls-patterns.md` — Plantillas SQL de RLS, triggers y políticas por rol.
- `references/api-conventions.md` — Forma de los endpoints, errores, paginación, export.
