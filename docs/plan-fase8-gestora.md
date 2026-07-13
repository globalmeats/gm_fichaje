# Fase 8 — Requisitos de la gestora: horario flexible por trabajador, descanso de comida, tope anual y ausencias

> Plan de implementación listo para ejecutar con Claude Code. Sigue el flujo del proyecto
> (ver `CLAUDE.md` §5 y `MEMORY`): explora → implementa por bloques → pasa el *verification
> gauntlet* → **para y deja que el usuario haga commit/push** (NUNCA auto-commit).
>
> Origen: 5 requisitos aclarados por la gestora. Evaluados contra el sistema actual:
> 1. Fichaje entrada/salida → **ya cubierto**. Horario flexible → **parcial**.
> 2. Descanso de comida → **parcial** (las pausas ya se descuentan).
> 3. Tiempo parcial → **ya cubierto** (`relation_type='tiempo_parcial'` → complementarias).
> 4. Días de vacaciones → **nuevo**.
> 5. Tope anual 1760 h/convenio → **nuevo**.

## Decisiones confirmadas con el usuario
- **(a) La jornada pactada/flexible es POR TRABAJADOR**, no global. Hoy `time_policy` es un
  singleton global (`id=1`). Se añaden columnas por trabajador con *fallback* a la política
  global, sin romper lo existente.
- **(b) Las ausencias cubren VACACIONES + BAJAS + PERMISOS** (no solo vacaciones). Los permisos
  retribuidos (art. 37.3 ET / convenio) llevan **subtipo** (cita médica propia, acompañamiento a
  familiar, mudanza, fallecimiento, ingreso hospitalario, deber inexcusable, matrimonio…) y pueden
  ser **de día completo o por horas** (una cita médica son unas horas, no un día).
- **(c) Justificantes: SE ADJUNTAN documentos** (justificante de **asistencia** de cualquier tipo),
  almacenados **cifrados** en la BD. **Solo el admin/gestora** da de alta ausencias y sube
  justificantes (no hay autoservicio del trabajador; el trabajador solo consulta lo suyo).
- **Regla operativa**: si hay vacaciones/permiso justificado, **NO se ficha** ese tiempo y queda
  justificado; el sistema no debe tratar ese hueco como ausencia anómala ni como fichaje faltante.

## ⚠️ Notas de cumplimiento (leer antes de implementar) — consultar skills `legal-compliance` y `rgpd-dataguard`
- **Justificante de ASISTENCIA ≠ parte/informe médico.** Lo que se sube es el justificante de
  **asistencia** (acredita que se acudió a la cita), que **no contiene diagnóstico**. En la UI y la
  documentación hay que **instruir explícitamente**: *subir solo justificantes de asistencia,
  NUNCA partes, informes o documentos con diagnóstico/causa clínica* (minimización, art. 5.1.c).
- **Aun así, trátalo con cuidado** (acudir a un centro médico es información sensible por
  asociación): el documento se guarda **cifrado en reposo** (reutilizar Fernet de
  `app/core/crypto.py`), **acceso restringido** por rol (self: el trabajador ve su justificante;
  oversight: admin/supervisor/inspección), **límite de tamaño y tipos** (PDF/JPG/PNG), y
  **retención** definida. Documentarlo en `docs/compliance/DPIA.md` y en el registro de actividades.
- **Baja (incapacidad temporal)**: el tipo `baja` se registra con tipo + fechas; el parte de baja/
  alta lo gestiona la Seguridad Social/mutua. En la app, **solo fechas + estado**, sin diagnóstico.
- **Tope de 1760 h**: límite del convenio (vinculante hoy). Se computa sobre horas EFECTIVAS
  trabajadas del año natural. La interpretación de si las vacaciones/permisos descuentan del
  tope se deja a confirmación legal (ver DEFERRED); por defecto el tope se mide sobre lo
  realmente trabajado y las ausencias se llevan en su propio cómputo.
- **Inmutabilidad**: NO se toca `time_record` ni su sellado. Las tablas nuevas (`absence`,
  `absence_document`) y las columnas de `worker`/`time_policy` son **config/HR mutable** (como
  `worker` y `time_policy`), sin trigger anti-mutación ni hash chain.

---

## Bloque 1 — Jornada por trabajador + horario flexible + tope anual (REQ-12 ext., REQ-27, REQ-29)

Objetivo: que cada trabajador tenga su jornada pactada y su tope anual, marcar quién tiene
horario flexible (clave para la subvención), computar las horas trabajadas del año y alertar
al acercarse/superar el tope.

### 1.1 Esquema (migración `0011_worker_schedule.sql`, idempotente)
`ALTER TABLE worker ADD COLUMN IF NOT EXISTS ...`:
- `weekly_hours numeric NULL` — jornada semanal pactada (p.ej. 40). NULL → usa el default global.
- `annual_hours_cap numeric NULL` — tope anual del trabajador. NULL → usa el default global del
  convenio. Para tiempo parcial se fija aquí el prorrateo.
- `flexible_schedule boolean NOT NULL DEFAULT false` — marca de horario flexible (subvención).

`ALTER TABLE time_policy ADD COLUMN IF NOT EXISTS ...` (defaults globales del convenio):
- `annual_hours_cap numeric NOT NULL DEFAULT 1760`.
- `annual_vacation_days numeric NOT NULL DEFAULT 22` (laborables; se usa en el Bloque 2).

`ALTER TABLE audit_alert` → ampliar el CHECK de `alert_type` para añadir `'annual_cap'`
(mismo patrón que 0010 con `off_hours`).

### 1.2 ORM espejo (`app/db/models.py`)
- Añadir las 3 columnas a `Worker` y las 2 a `TimePolicy` (mantener el espejo manual).
- Añadir `'annual_cap'` a `ALERT_TYPES` y al `CheckConstraint` de `AuditAlert`.

### 1.3 Dominio — resolución de jornada (`app/domain/schedule.py`, nuevo, lógica pura)
```python
def effective_annual_cap(worker, policy) -> float        # worker.annual_hours_cap or policy.annual_hours_cap
def effective_weekly_hours(worker, policy) -> float | None
def effective_vacation_days(worker, policy) -> float      # worker.annual_vacation_days or policy.annual_vacation_days
```
(Se usa un `_Worker`/`_Policy` Protocol con duck typing, como en `hours.py`.)

### 1.4 Dominio — cómputo anual (extender `app/domain/hours.py`)
Reutiliza `reconstruct_journeys` + `journey_effective`. Añadir:
```python
def annual_window(now: datetime) -> tuple[datetime, datetime]   # [1 ene, 1 ene+1) en UTC
def annual_worked(records, policy, now) -> timedelta            # Σ efectivo de jornadas cerradas del año
def annual_status(records, worker, policy, now) -> dict         # {worked, cap, remaining, ratio, exceeded}
```
`annual_status` devuelve minutos/horas trabajados del año, el cap efectivo (vía `schedule`),
el restante y un flag `exceeded`/umbral (p.ej. ≥90 %).

### 1.5 Alerta de tope (`app/api/fichaje.py` o helper en `app/audit/alerts.py`)
Tras registrar un evento (en `create_event` y `sync_event`), si `annual_status(...).exceeded`
(o cruza el umbral) y aún no hay una alerta `annual_cap` reciente para ese trabajador/año,
emitir `record_alert(db, "annual_cap", ..., severity="warning")`. No bloquea el fichaje
(igual filosofía que `off_hours`).

### 1.6 Descanso de comida (#2) — mejora ligera, sin tocar sellado
Lo esencial ya existe (`break_start`/`break_end`, `is_pause_computable`, `journey_effective`
descuenta las pausas computables). Para “contabilizar la comida” de forma explícita:
- Exponer el total de pausa del periodo en el resumen/export como línea propia (`pausa_min`),
  para que la gestora lo vea separado del efectivo (presentación, sin schema nuevo).
- El flag computable **por evento** (distinguir comida de otras pausas a nivel de cada pausa)
  toca el sellado de `time_record` → **se deja en DEFERRED** (la doc lo modela por-pausa y el
  código ya deja la “costura” en `hours.is_pause_computable`).

### 1.7 Tiempo parcial + tope (#3)
Ya cubierto (`classify_overtime` etiqueta complementarias). Solo asegurar que el cap anual de un
`tiempo_parcial` se fija en `worker.annual_hours_cap` (prorrateado) y que `annual_status` lo usa.

### 1.8 Tests Bloque 1
- `app/tests/test_schedule.py` (puro): fallbacks de `effective_*` (worker override vs global).
- `app/tests/test_annual.py` (puro): `annual_window` (límites de año), `annual_worked` suma solo
  jornadas cerradas dentro del año, `annual_status` (restante, exceeded, umbral).
- `app/tests/test_annual_cap_alert.py` (BD): fichar por encima del cap genera `audit_alert`
  `annual_cap`; por debajo no.

---

## Bloque 2 — Ausencias: vacaciones + bajas + permisos, con subtipo, por horas y justificante (REQ-28)

### 2.1 Esquema — ausencias (migración `0012_absence.sql`, idempotente)
```sql
CREATE TABLE IF NOT EXISTS absence (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id uuid NOT NULL,                       -- (no FK estricta: mismo estilo que el resto)
    absence_type text NOT NULL
        CHECK (absence_type IN ('vacaciones','baja','permiso')),
    -- Subtipo del permiso retribuido (art. 37.3 ET / convenio). Solo relevante si type='permiso'.
    -- Validado en la app contra PERMISO_SUBTYPES (sin CHECK en BD: el catálogo varía por convenio).
    subtype text NULL,
    start_date date NOT NULL,
    end_date   date NOT NULL CHECK (end_date >= start_date),
    -- Ausencia por horas (p.ej. cita médica): NULL/NULL = día(s) completo(s). Si van informados,
    -- start_date debe = end_date (ausencia de unas horas dentro de un mismo día).
    start_time time NULL,
    end_time   time NULL,
    status text NOT NULL DEFAULT 'aprobada'
        CHECK (status IN ('pendiente','aprobada','rechazada','cancelada')),
    -- Justificación: 'justified' lo marca el admin al verificar el justificante adjunto.
    justified boolean NOT NULL DEFAULT false,
    verified_by uuid NULL,
    note text NULL,                                -- nota administrativa; NUNCA dato clínico (RGPD)
    created_by uuid NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS absence_worker_idx ON absence (worker_id);
```
Tabla **mutable** (como `worker`): se puede cancelar/editar. Sin trigger anti-mutación.

### 2.1bis Esquema — justificante adjunto (migración `0013_absence_document.sql`, idempotente)
```sql
CREATE TABLE IF NOT EXISTS absence_document (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    absence_id uuid NOT NULL,                      -- relación 1:N (permite varios justificantes)
    filename text NOT NULL,
    content_type text NOT NULL
        CHECK (content_type IN ('application/pdf','image/jpeg','image/png')),
    byte_size integer NOT NULL CHECK (byte_size > 0 AND byte_size <= 5242880),  -- ≤5 MB
    content_encrypted bytea NOT NULL,              -- justificante CIFRADO (Fernet) en reposo
    uploaded_by uuid NULL,
    uploaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS absence_document_absence_idx ON absence_document (absence_id);
```
El documento se almacena **cifrado** (no en claro) y permanece en la BD de la UE; queda cubierto
por el backup de la BD. **Solo justificantes de asistencia**; ver notas RGPD.

### 2.2 ORM espejo (`app/db/models.py`)
- `class Absence(Base)` y `class AbsenceDocument(Base)` con sus CHECKs.
- Constantes: `ABSENCE_TYPES = ('vacaciones','baja','permiso')`,
  `ABSENCE_STATUSES = ('pendiente','aprobada','rechazada','cancelada')`,
  `PERMISO_SUBTYPES` (cita_medica, acompanamiento_familiar, mudanza, fallecimiento,
  ingreso_hospitalario, deber_inexcusable, matrimonio, lactancia, otro),
  `JUSTIFICANTE_CONTENT_TYPES` (pdf/jpeg/png), `MAX_JUSTIFICANTE_BYTES = 5 * 1024 * 1024`.

### 2.3 Cifrado de documentos (`app/core/crypto.py`, extender)
Reutilizar el Fernet ya existente. Añadir `encrypt_blob(data: bytes) -> bytes` /
`decrypt_blob(token: bytes) -> bytes` con la misma clave derivada de `settings.geo_encryption_key`
(o un `doc_encryption_key` dedicado si se prefiere separar claves — decisión menor, documentarla).

### 2.4 Dominio (`app/domain/absences.py`, nuevo, lógica pura)
```python
def leave_days(start, end, *, working_only=True) -> int      # nº de días; working_only ⇒ L–V
def absence_hours(absence) -> float | None                   # horas si start_time/end_time; None si día completo
def vacation_days_taken(absences, year) -> int               # Σ días de 'vacaciones' aprobadas del año
def vacation_balance(entitled, taken) -> dict                # {entitled, taken, remaining}
def overlaps(start, end, start_time, end_time, existing) -> bool   # solapa con ausencias activas
def covers(absence, day) -> bool                             # si una ausencia activa cubre un día (justificación)
```
Notas:
- `leave_days` cuenta L–V (no descuenta festivos nacionales/autonómicos) → **DEFERRED** (calendario).
- Las ausencias por horas (`start_time/end_time`) **no** consumen día de vacaciones; cuentan como
  horas justificadas del permiso.
- `covers` se usa para la regla operativa: un día/tramo cubierto por una ausencia activa
  (`aprobada`) es tiempo **justificado** → no es fichaje faltante ni ausencia anómala.

### 2.5 Esquemas (`app/schemas/absence.py`, nuevo)
- `AbsenceCreate` (worker_id, absence_type, subtype?, start_date, end_date, start_time?, end_time?,
  note?, status?) con validaciones: `end_date >= start_date`; si `absence_type='permiso'` exigir
  `subtype` ∈ `PERMISO_SUBTYPES`; si hay horas, `start_date == end_date` y `end_time > start_time`.
- `AbsenceResponse` (from_attributes, incluye `justified`, `has_document`).
- `AbsenceDocumentResponse` (id, filename, content_type, byte_size, uploaded_at) — **sin** el binario.
- `VacationBalanceResponse` (entitled, taken, remaining, year).

### 2.6 API JSON (`app/api/absences.py`, nuevo router; montar en `app/main.py`)
Alta y gestión **solo admin/gestora** (rol oversight de escritura: admin/supervisor); el trabajador
solo consulta lo suyo.
- `POST /absences` — crear (admin/supervisor). Valida solapamiento (`overlaps`).
- `GET /absences` — listar; `worker_id` opcional. Self vs oversight (patrón de `load_report`:
  empleado solo lo suyo; oversight cualquiera).
- `POST /absences/{id}/cancel` — marcar `cancelada` (admin/supervisor).
- `POST /absences/{id}/justificante` — subir documento (multipart, `UploadFile`): valida tipo y
  tamaño, cifra con `encrypt_blob`, guarda en `absence_document`; marca `absence.justified=true` y
  `verified_by` (admin/supervisor).
- `GET /absences/{id}/justificante/{doc_id}` — descargar: descifra y devuelve con su `content_type`.
  Acceso self (el trabajador descarga **su** justificante) + oversight.
- `GET /me/absences` y `GET /me/vacation-balance` — del propio trabajador (autodisponibilidad, REQ-18).
- Reutilizar `OVERSIGHT_ROLES`; añadir un `ABSENCE_WRITE_ROLES = {'admin','supervisor'}`.

### 2.7 Tests Bloque 2
- `app/tests/test_absences.py` (puro): `leave_days` (working_only sí/no, un día, cruce de finde),
  `absence_hours`, `vacation_days_taken`, `vacation_balance`, `overlaps` (días y por horas), `covers`.
- `app/tests/test_api_absences.py` (BD): crear vacaciones/permiso con subtipo; permiso por horas;
  empleado no ve ni crea ajenas (403); oversight sí; cancelar; balance correcto; solapamiento (422);
  subir justificante (tipo/tamaño válidos e inválidos), `justified` pasa a true, descarga self +
  oversight, y que el binario **no** aparece en los listados JSON.

---

## Bloque 3 — Informes y UI (export anual + vacaciones, panel admin, portal trabajador) + docs

### 3.1 Export / informe (`app/schemas/export.py`, `app/domain/export.py`, `app/api/export.py`)
Extender `ExportReport` con:
- `flexible_schedule: bool`
- `annual_worked_min: int`, `annual_cap_min: int`, `annual_remaining_min: int`
- `pausa_min: int` (total de pausas del periodo — descanso comida visible)
- `vacation_days_entitled/taken/remaining: int`
- `absences: list[AbsenceRow]` (tipo, **subtipo**, fechas, **horas si aplica**, estado,
  **justified**) del periodo. **NO** incluir el binario del justificante en el informe; como mucho
  un indicador “justificante: sí/no”.
En `load_report`: cargar `worker` (ya se hace), calcular `annual_status` (Bloque 1), balance de
vacaciones y ausencias del rango, y pasarlos a `build_report`. Reflejarlo en `to_csv` y `to_pdf`
(nuevas filas/líneas; mantener UTC + Madrid como ya se hace). Añadir asserts en `test_export.py`.

### 3.2 Resumen propio (`app/api/fichaje.py::summary`)
Añadir al `SummaryResponse` el estado anual y el balance de vacaciones del propio trabajador
(autodisponibilidad, REQ-18). Actualizar `app/schemas/fichaje.py`.

### 3.3 Alta/edición de trabajador (`app/api/admin.py`, `app/schemas/worker.py`, web)
- `WorkerCreate`: añadir `weekly_hours?`, `annual_hours_cap?`, `annual_vacation_days?`,
  `flexible_schedule` (default false). Pasarlos en `create_employee` (`app/services/onboarding.py`).
- Nuevo `WorkerUpdate` + endpoint `PATCH /admin/workers/{id}` para editar la jornada de un
  trabajador existente (no hay edición hoy, solo alta + reset-pin).
- Web: campos nuevos en `admin/alta.html`; nueva página `admin/trabajador.html` (editar jornada)
  con ruta `GET/POST /admin/trabajador/{id}`.

### 3.4 Política global (`app/schemas/policy.py`, `app/api/admin.py`, `admin/politica.html`)
Añadir `annual_hours_cap` y `annual_vacation_days` a `TimePolicyResponse`/`TimePolicyUpdate`,
al `PUT /admin/time-policy`, y al formulario `admin/politica.html`. Actualizar el reset del
singleton en `app/tests/conftest.py` (la línea `UPDATE time_policy SET ...`) para incluir los
nuevos campos con sus defaults (1760 / 22).

### 3.5 UI web (`app/web/router.py` + plantillas)
- **Ausencias** (solo admin/gestora escriben): `GET /admin/ausencias` (lista + alta + cancelar +
  subir/descargar justificante), POST handlers. Plantilla `admin/ausencias.html`. El formulario de
  alta incluye tipo, subtipo (visible si `permiso`), rango de fechas, **horas opcionales** y, tras
  crear, un `input type=file` para subir el justificante (multipart). Handlers FINOS reutilizando
  el dominio/servicio del Bloque 2. **Aviso visible en el formulario de subida**: “sube solo el
  justificante de asistencia; nunca informes o partes con diagnóstico”.
- **Portal trabajador**: balance de vacaciones + próximas/actuales ausencias en `/mis-registros`
  (o nueva `/mis-ausencias` + plantilla), con enlace para descargar **su** justificante. Mostrar
  también el estado anual (horas/tope/restante).
- **Horas anuales**: ampliar `GET /admin/horas` (y `admin/horas.html`) con la sección anual
  (trabajado/tope/restante) además del periodo actual.
- **Nav**: añadir enlaces en `admin/panel.html` y `base.html` (Ausencias, editar trabajador).
- Recordar: horas en hora local de Madrid en presentación (filtro `madrid` ya existente). Las
  descargas web autentican por cookie (patrón `/descargar/...`), no por Bearer.

### 3.6 Tests UI
- `app/tests/test_web_ausencias.py`: alta de vacaciones y de un permiso por horas desde admin;
  subir un justificante y descargarlo; el portal del trabajador muestra su balance y descarga su
  justificante; cancelar refleja el cambio.
- Ampliar `test_web_portal.py` (balance visible) y `test_export.py` (campos anuales/vacaciones/
  ausencias; el binario del justificante NO aparece en el export).

### 3.7 Documentación y cumplimiento
- `.claude/skills/legal-compliance/SKILL.md`: añadir filas a la matriz:
  - **REQ-27** Tope anual de jornada (convenio 1760 h) — 🟢 VIGENTE — cómputo anual + alerta.
  - **REQ-28** Registro de ausencias (vacaciones/bajas/permisos + justificante) — 🟡 — tabla +
    balance + documento cifrado; baja y justificante tratados con minimización (art. 9/5.1.c).
  - **REQ-29** Jornada flexible por trabajador (subvención) — 🟢 — jornada pactada por trabajador
    + cómputo > diario + informe.
- `scripts/compliance_check.py`: añadir REQ-27/28/29 al dict `REQUISITOS` con patrones que SÍ
  aparecerán (`annual.?cap|tope.?anual`, `1760`, `convenio`; `vacacion|absence|ausencia`,
  `balance|justificante`; `flexible|flexibilidad`, `jornada`). Mantener el gate en verde.
- `docs/compliance/DPIA.md` + `registro-actividades-tratamiento.md`: añadir el tratamiento de
  **ausencias y justificantes**. Puntos a dejar por escrito: (1) solo se suben justificantes de
  **asistencia**, nunca diagnósticos; (2) el documento se almacena **cifrado** en la UE con acceso
  restringido por rol; (3) la `baja` se registra solo con fechas/estado (sin datos clínicos);
  (4) base jurídica (obligación legal/contrato) y **retención** del justificante; (5) que “asistir
  a un centro médico” puede ser información sensible por asociación → acceso mínimo necesario.
- `docs/DEFERRED.md`: añadir
  - calendario laboral (festivos nacionales/autonómicos) para `leave_days`/cómputo anual;
  - si vacaciones/permisos descuentan del tope de 1760 (confirmación legal del convenio);
  - si las ausencias justificadas computan como tiempo trabajado para la jornada (convenio);
  - flag computable de pausa **por evento** (comida vs otras pausas) — toca sellado;
  - devengo/prorrateo de vacaciones por antigüedad y carryover de saldo entre años;
  - catálogo de subtipos de permiso configurable por convenio (hoy constante en código);
  - antivirus/escaneo de los justificantes subidos y política de retención/borrado del documento.
- `docs/IMPLEMENTATION_PLAN.md`: registrar esta Fase 8 con sus criterios de aceptación.

---

## Mapa de ficheros

| Fichero | Acción |
|---|---|
| `app/db/migrations/0011_worker_schedule.sql` | NUEVO: worker (weekly_hours, annual_hours_cap, flexible_schedule) + time_policy (annual_hours_cap=1760, annual_vacation_days=22) + audit_alert `annual_cap` |
| `app/db/migrations/0012_absence.sql` | NUEVO: tabla `absence` (subtype, horas, justified, verified_by) + índice |
| `app/db/migrations/0013_absence_document.sql` | NUEVO: tabla `absence_document` (justificante cifrado) + índice |
| `app/db/models.py` | espejo: cols Worker/TimePolicy, `Absence`, `AbsenceDocument`, `ALERT_TYPES`+`annual_cap`, `ABSENCE_TYPES/STATUSES/PERMISO_SUBTYPES/JUSTIFICANTE_CONTENT_TYPES` |
| `app/core/crypto.py` | `encrypt_blob`/`decrypt_blob` (cifrado del justificante) |
| `app/domain/schedule.py` | NUEVO: resolución jornada por trabajador (fallback global) |
| `app/domain/hours.py` | `annual_window`, `annual_worked`, `annual_status` |
| `app/domain/absences.py` | NUEVO: `leave_days`, `absence_hours`, `vacation_days_taken`, `vacation_balance`, `overlaps`, `covers` |
| `app/schemas/absence.py` | NUEVO: AbsenceCreate/Response, AbsenceDocumentResponse, VacationBalanceResponse |
| `app/schemas/worker.py` | WorkerCreate +campos jornada; WorkerUpdate |
| `app/schemas/policy.py` | +annual_hours_cap, +annual_vacation_days |
| `app/schemas/export.py` | +anual, +pausa_min, +vacaciones, +absences (con subtipo/horas/justified) |
| `app/schemas/fichaje.py` | SummaryResponse +anual +balance |
| `app/services/onboarding.py` | `create_employee` acepta campos de jornada |
| `app/api/absences.py` | NUEVO router (CRUD ausencias + subir/descargar justificante; montar en `app/main.py`) |
| `app/api/admin.py` | alta con jornada, `PATCH /admin/workers/{id}`, policy anual |
| `app/api/export.py` | `load_report` calcula anual+vacaciones+ausencias |
| `app/api/fichaje.py` | alerta `annual_cap`; summary anual+balance |
| `app/main.py` | `include_router(absences.router)` |
| `app/web/router.py` | rutas ausencias (+ subir/descargar justificante), edición trabajador, anual en /admin/horas, portal balance |
| `app/web/templates/...` | `admin/ausencias.html`, `admin/trabajador.html`, ampliar `admin/{alta,politica,horas,panel}.html`, `mis_registros.html`/`mis_ausencias.html`, `base.html` |
| `app/tests/test_schedule.py` `test_annual.py` `test_absences.py` | NUEVOS (puros) |
| `app/tests/test_annual_cap_alert.py` `test_api_absences.py` `test_web_ausencias.py` | NUEVOS (BD) |
| `app/tests/test_export.py` `test_web_portal.py` `conftest.py` | AMPLIAR |
| `.claude/skills/legal-compliance/SKILL.md` + `scripts/compliance_check.py` | REQ-27/28/29 |
| `docs/compliance/DPIA.md` + `registro-actividades-tratamiento.md` | tratamiento ausencias + baja (art.9) |
| `docs/DEFERRED.md`, `docs/IMPLEMENTATION_PLAN.md` | entradas nuevas |

## Verification gauntlet (antes de declarar la fase hecha)
1. `source .venv/bin/activate`.
2. `python -m app.db.migrate` (aplica 0011, 0012 y 0013 en local + Supabase).
3. `ruff check .` limpio (línea ≤100, orden de imports I001).
4. `pytest -q` verde (los tests de BD pegan a Supabase remoto, ~2-3 min).
5. `python .claude/skills/legal-compliance/scripts/compliance_check.py` → exit 0, sin VIGENTE en FALTA.
6. **Recrear admin** tras la suite (el `TRUNCATE` borra workers): con `SessionLocal` →
   `create_employee(db,'Jaime','Aznar',role='admin')` → code `JaAz`, `pin_hash=hash_pin('194608')`,
   `pin_temporary=False`, `await db.commit()`.
7. **Parar y proponer mensaje de commit**; el usuario hace commit/push.

## Fuera de alcance
- No se toca `time_record` ni su sellado/hash chain.
- No se implementa flujo de aprobación de ausencias multi-paso (se crean ya `aprobada`; existe
  `pendiente`/`rechazada` en el modelo para un futuro flujo).
- No se implementa calendario de festivos ni devengo/prorrateo de vacaciones (DEFERRED).
- No se añade flag de pausa computable por-evento (DEFERRED; toca sellado).
- No se cambia la lógica de región (REQ-23) ni la guarda de secretos (B1).
