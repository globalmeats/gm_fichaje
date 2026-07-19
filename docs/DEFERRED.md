# Decisiones diferidas y deuda técnica conocida

Registro vivo de decisiones aplazadas. **Consultar al planificar cada nueva fase** para
reconsiderar los pendientes en el momento oportuno (ver `CLAUDE.md`). Una entrada por ítem.

- **Validación legal de "puesta a disposición" / `travel_computes` (Fase 2)** — la spec resta el
  tiempo de desplazamiento que no computa; confirmar con abogado laboralista contra el ET.
- **Compensación de horas extra, abono vs descanso (Fase 3)** — hoy marcado "pending"; el registro
  inmutable/sellado de esa decisión queda diferido a una fase posterior.
- ~~**REQ-26 horas complementarias (Fase 3)** — diferido hasta modelar `relation_type` (contratos a
  tiempo parcial) en el trabajador.~~ **RESUELTO (Fase 6)**: `worker.relation_type` incluye
  `tiempo_parcial` y `app/domain/hours.py::classify_overtime` etiqueta el exceso como
  `complementarias` (no extra) para ese tipo de relación; expuesto en el export (`complementarias_min`).
- ~~**Cifrado del campo `geo` al corregirlo (Fase 4)** — confirmar que corregir `geo` no salta el
  cifrado; revisar en Fase 6 cuando entre la geolocalización real.~~ **RESUELTO (Fase 6)**:
  `app/api/corrections.py` cifra el `corrected_value` con `encrypt_geo` antes de sellarlo y
  almacenarlo cuando `field == 'geo'`; el export lo descifra para mostrarlo.
- **FK `retention_log.worker_id` (Fase 5)** — al implementar el borrado físico de `time_record`,
  asegurar que el FK no bloquea el borrado ni deja el log huérfano (probablemente
  `ON DELETE SET NULL`); además es un punto RGPD (derecho de supresión vs deber de conservación
  4 años).
- **Calendario laboral de festivos (Fase 8)** — `leave_days`/cómputo anual cuentan L–V sin
  descontar festivos nacionales/autonómicos; falta un calendario laboral configurable.
- **¿Vacaciones/permisos descuentan del tope anual de 1760 h? (Fase 8)** — hoy el tope se mide
  solo sobre tiempo efectivo trabajado; confirmar con el convenio si las ausencias reducen el tope.
- **¿Las ausencias justificadas computan como tiempo trabajado? (Fase 8)** — operativamente el
  tiempo justificado no exige fichaje (no es anómalo), pero no se suma como trabajado; confirmar
  con convenio.
- **Flag de pausa computable por evento (Fase 8)** — distinguir comida vs otras pausas a nivel de
  evento; toca el sellado de `time_record`, por eso se difiere (hoy es política global).
- **Devengo/prorrateo de vacaciones por antigüedad y carryover entre años (Fase 8)** — hoy el
  balance es derecho anual fijo (`annual_vacation_days`) menos lo disfrutado del año en curso.
- **Catálogo de subtipos de permiso configurable por convenio (Fase 8)** — hoy `PERMISO_SUBTYPES`
  es constante en código; debería poder editarse como config del convenio.
- **Antivirus/escaneo y política de retención/borrado del justificante (Fase 8)** — los
  justificantes subidos no se escanean ni tienen política de borrado documentada.
- **SEC-04(a): activar la RLS en runtime (auditoría 2026-07)** — las políticas RLS están
  escritas pero no se evalúan (la app conecta como superusuario, que las omite, y `auth.uid()`
  es un stub que devuelve NULL). RAT/DPIA ya NO presentan la RLS como salvaguarda activa
  (SEC-04(b) hecho). Alto riesgo de implementación → **requiere OK humano y sesión dedicada con
  pruebas exhaustivas**. Pasos concretos que faltan:
  1. **Rol de BD sin privilegios**: crear en Supabase un rol de aplicación NO superusuario y sin
     `BYPASSRLS`, con los `GRANT` mínimos (SELECT/INSERT donde toque) sobre las tablas con datos
     personales. Apuntar el `DATABASE_URL` de la app a ese rol (guardar el de superusuario solo
     para migraciones/seed/jobs administrativos).
  2. **`auth.uid()` / `auth.jwt()` reales**: reimplementarlas para leer del contexto de la
     transacción, p. ej. `current_setting('request.jwt.claims', true)::json->>'worker_id'` y
     `->>'role'` (hoy son stubs en `0001_init.sql`). Nueva migración.
  3. **Inyección de claims por transacción**: en la dependencia de sesión (`app/api/deps.py::get_db`
     y `app/web/session.py`), tras abrir la transacción ejecutar
     `SET LOCAL request.jwt.claims = '{"worker_id": "...", "role": "..."}'` con los datos del JWT
     ya verificado. Sin esto las políticas ven NULL y bloquean todo.
  4. **Revisar cobertura de políticas**: que cada patrón de acceso legítimo esté permitido —
     lectura propia del trabajador, lectura global de roles de supervisión (supervisor/admin/rlt/
     inspeccion), inserción de fichajes propios, y **escrituras administrativas** (alta de
     empleados, correcciones, ausencias, política). Cuidado con `append_event` (advisory lock),
     el onboarding y el portal.
  5. **Jobs y backup**: `retention`, `backup` y `restore` conectan hoy como superusuario y usan
     `session_replication_role='replica'` (SEC-05). Decidir si siguen con un rol privilegiado
     (fuera de RLS, correcto para tareas de sistema) o se adaptan. Migraciones y `seed_admin`
     igual: rol privilegiado.
  6. **Pruebas**: recorrer cada rol contra cada endpoint (incl. que un empleado NO ve ajenos ni
     por RLS ni por app), los dos jobs, y el ciclo backup→restore, antes de dar por buena la
     activación. Objetivo: misma funcionalidad, con la RLS como segunda muralla real.
- **OPS-01: monitorización del backup diario (auditoría 2026-07)** — la conservación de 4 años
  depende del cron a R2; falta una alerta si un día no aparece backup nuevo (o el objeto más
  reciente supera ~26 h). Operativo, no código de la app. Alternativa: subir a Supabase Pro.
- **BUG-05: escaneos O(N) del histórico por fichaje (auditoría 2026-07)** — `_alert_if_annual_cap`
  y `annual_status` cargan todos los `time_record`. Optimización pendiente (acotar por ventana),
  omitida ahora para no arriesgar el cómputo en jornadas que cruzan la frontera de año.
- **SEC-11: `--forwarded-allow-ips '*'` en railway.json (auditoría 2026-07)** — confía XFF de
  cualquier upstream (envenenamiento de logs). No se fija a rangos concretos porque el proxy de
  Railway no expone IP estable; se revisa en la Fase 3 (Cloudflare) junto con `TRUST_CF_CONNECTING_IP`.
- **CMP-03: art. 35.5, resumen entregable + flag abono/descanso (auditoría 2026-07)** — la
  totalización existe; falta resolver `compensacion` (hoy "pending") e incluirlo en el export, y
  valorar un artefacto de "resumen entregado". Requiere criterio de negocio/convenio.
- **CMP-04: borrado tras los 4 años vs derecho de supresión (auditoría 2026-07)** — hoy nada
  borra tras la retención (tensión con art. 5.1.e). Decisión de política con DPO/laboralista,
  y su interacción con la inmutabilidad (borrado físico controlado vs anonimización).
- ~~**Rediseño de UI "Documento de origen"**~~ **IMPLEMENTADO (2026-07-19)**: sistema de diseño
  en `app/web/static/app.css` + fuentes self-hosted, `base.html` enlaza el CSS. Sin cambios de
  comportamiento (243 tests verde). Detalle en `docs/UI-REDISENO.md`. Pendiente opcional: pulir
  pantalla por pantalla los formularios admin más densos.
- ~~**UI responsive en todos los dispositivos**~~ **IMPLEMENTADO (2026-07-19)**: contenedor
  `.table-scroll` (overflow contenido con affordance) envolviendo todas las tablas densas,
  breakpoints móvil/tablet/escritorio, cabecera que envuelve en móvil, filas de formulario que
  apilan, botón de fichar a ancho completo, y guarda `overflow-x:hidden`. Verificado a 500px y
  1100px con capturas (Chrome headless clampa el viewport a 500 mín.; a 500 `bodyScrollWidth`=
  viewport, sin overflow). 243 tests verde, sin tocar comportamiento. Ver `docs/UI-RESPONSIVE.md`.
- **Supabase plan Free: backup propio obligatorio (go-live, 15/07/2026)** — el proyecto de
  producción arranca en plan Free (sin backups gestionados). Mitigación comprometida para la
  Fase 2 del go-live: `pg_dump` programado (cron en Railway), cifrado, con destino en
  almacenamiento UE; documentar destino y retención en el RAT. La conservación de 4 años
  (regla de oro nº 4) no está garantizada sin esto. Reconsiderar upgrade a Pro cuando haya
  presupuesto: elimina esta pieza y añade backups diarios gestionados.
- **Reset de esquema antes del go-live (go-live, 15/07/2026)** — durante la preparación
  corrió una suite de pytest contra el proyecto Supabase de producción (antes de fijar la
  regla "tests solo contra Postgres local"). Como los triggers de inmutabilidad impiden
  limpiar residuos por la vía normal, el último paso antes de meter datos reales es: drop
  del esquema + `python -m app.db.migrate` desde cero + recrear el admin (`scripts.seed_admin`).
  Los tests van SIEMPRE contra el Postgres local de test (puerto 55432), nunca contra prod.
- **Supabase plan Free: keep-alive anti-pausa (go-live, 15/07/2026)** — Free pausa proyectos
  tras ~7 días "sin actividad" y la conexión directa por pooler (asyncpg) puede no contar
  como actividad. Mitigación: keep-alive periódico en la Fase 2 y vigilancia del estado del
  proyecto. La Data API queda desactivada a propósito (minimización: la app no usa
  supabase-js; solo Postgres directo).
