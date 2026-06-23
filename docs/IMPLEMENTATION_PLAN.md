# Plan de implementación — Fichajes Global Meats

Roadmap por fases para construir la app con Claude Code. Cada fase cierra con su
checklist (`compliance_check.py` + tests). Los REQ-XX remiten a la matriz de la skill
`legal-compliance`. 🟢 = obligación legal vigente · 🟡 = objetivo reforma 2026.

## Cómo ejecutar cada fase con Claude Code

Prompt tipo para arrancar una fase:

> "Vamos con la Fase N del plan de fichajes. Lee `CLAUDE.md` y las skills implicadas,
> implementa las tareas de la fase y deja los tests en verde. Antes de cerrar, corre
> `compliance_check.py`."

Claude Code debe abrir las skills que correspondan (no asumir de memoria) y referenciar
el REQ en cada commit.

---

## Fase 0 — Cimientos y cumplimiento de base

**Objetivo**: esqueleto del proyecto + andamiaje de cumplimiento operativo.

- Estructura de carpetas (`fastapi-supabase`).
- `core/config.py` con verificación de **región UE** (REQ-23 🟡).
- `core/security.py`: PIN bcrypt, JWT con `role`/`worker_id` (REQ-05 🟢, 21 🟡).
- **Alta de empleados** (`onboarding-empleados`): generación de `employee_code` sin
  colisiones (UNIQUE en BD + reintento transaccional), PIN inicial aleatorio mostrado una
  vez, `pin_temporary`. Endpoint de admin + cambio de PIN obligatorio en primer login.
- `core/time.py`: utilidades UTC y sellado (REQ-15 🟡).
- Conexión Supabase async; primera migración vacía + RLS habilitado por defecto.
- Integrar `compliance_check.py` en CI.

**Aceptación**: app levanta; login PIN funciona; deploy falla si la región no es UE.

---

## Fase 1 — Registro diario inmutable (núcleo legal vigente)

**Objetivo**: cumplir el mínimo VIGENTE del art. 34.9 con garantías de inmutabilidad.

- Tabla `time_record` append-only (`fichaje-domain`).
- Servicio `audit/chain.py`: timestamp servidor + hash encadenado (REQ-15 🟡).
- Trigger + revoke UPDATE/DELETE (REQ-02 🟢, `audit-trail`).
- Endpoint `POST /fichaje/event` (check_in/check_out) (REQ-01 🟢).
- Reconstrucción de jornada vía máquina de estados (`fichaje-domain`).
- RLS: empleado solo ve lo suyo (REQ-05/24).

**Aceptación**: REQ-01, REQ-02 verdes. UPDATE/DELETE rechazado. Cadena de hash verificable.

---

## Fase 2 — Pausas, desplazamientos y tiempo efectivo

**Objetivo**: distinguir tiempo efectivo del bruto (evita la presunción legal).

- Eventos `break_*` y `travel_*` (REQ-07 🟢, REQ-09 🟢).
- Cálculo de tiempo efectivo (`domain/hours.py`).
- `time_policy` configurable: pausas computables, periodo de cómputo (REQ-13 🟢).
- Modalidades presencial/teletrabajo/móvil (REQ-06 🟢).

**Aceptación**: REQ-06,07,09,13 verdes; pausas no computables no restan; traslado en
puesta a disposición no computa pero queda registrado.

---

## Fase 3 — Horas extra y cómputo flexible

**Objetivo**: art. 35.5 ET + flexibilidad supra-diaria.

- Agregador de horas por periodo (REQ-12 🟢).
- Totalización y resumen de horas extra, flag abono/descanso (REQ-08 🟢).
- Clasificación ordinarias/extra/complementarias (REQ-26 🟡).
- Endpoint `GET /reports/overtime`.

**Aceptación**: REQ-08,12 verdes; exceso diario no es extra si el periodo cuadra;
resumen exportable.

---

## Fase 4 — Correcciones y auditoría

**Objetivo**: editar sin romper la inmutabilidad + detección de manipulación.

- `record_correction` con `reason` obligatorio, autor, referencia al original (REQ-16 🟡).
- Verificador periódico de cadena de hash.
- `audit_alert`: intentos de mutación, cadena rota, accesos anómalos, fallos de login
  (REQ-25 🟡).

**Aceptación**: REQ-16 verde; corrección deja rastro; alertas se generan.

---

## Fase 5 — Acceso, exportación y conservación

**Objetivo**: disponibilidad inmediata + retención.

- Portal del trabajador (sus registros 24/7) (REQ-18 🟡).
- Export PDF/CSV verificable: id, detalle, correcciones, totales (REQ-04 🟢, 19 🟡).
- Acceso de Inspección solo lectura/remoto (REQ-17 🟡); cumple ya el "a disposición"
  vigente (REQ-04 🟢).
- Roles RLT/inspección (REQ-24 🟡).
- Job de retención que NO borra < 4 años y loguea borrados posteriores (REQ-03 🟢).

**Aceptación**: REQ-03,04 verdes; export operativo; retención respeta los 4 años.

---

## Fase 6 — RGPD avanzado y robustez

**Objetivo**: cerrar los objetivos de reforma y el endurecimiento de privacidad.

- Geolocalización puntual con consentimiento y cifrado (REQ-20 🟡).
- Cifrado en reposo de columnas sensibles; verificación de residencia UE (REQ-23 🟡).
- Funcionamiento offline + sync sin pérdida (REQ-22 🟡).
- DPIA y registro de actividades de tratamiento (REQ-10 🟢).
- Excepciones de ámbito: alta dirección, ETT→usuaria, subcontrata (REQ-11 🟢).
- Módulo de desconexión digital (REQ-26 🟡).

**Aceptación**: REQ-10,11 verdes; geo solo puntual; offline sincroniza; DPIA documentada.

---

## Estado de cumplimiento objetivo al cerrar el plan

- **100% de los REQ 🟢 (vigentes)**: obligatorio antes de producción.
- **REQ 🟡 (reforma)**: implementados como objetivo de diseño. Revisar contra el texto
  definitivo cuando se publique en BOE (a 22/06/2026 sigue pendiente).

> Recordatorio: esto es soporte técnico, no asesoramiento jurídico. Validar con
> laboralista antes de producción.
