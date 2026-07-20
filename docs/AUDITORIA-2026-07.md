# Auditoría integral y plan de remediación — gm_fichaje (2026-07-18)

## Estado de remediación (actualizado 2026-07-19)

Remediación ejecutada por Claude Fable 5. Suite completa en verde (**243 tests**), ruff y
`compliance_check.py` OK. Resumen por hallazgo:

| Estado | Hallazgos |
|---|---|
| ✅ **Arreglado (código + tests)** | SEC-01, BUG-01, SEC-05, TEST-01, BUG-02, BUG-03, BUG-06, SEC-03, SEC-06, SEC-07, SEC-08, BUG-04, SEC-09, SEC-10, SEC-12, BUG-07, BUG-08, BUG-09, CMP-06 |
| ✅ **Arreglado (documental)** | CMP-01, CMP-02, CMP-05 — RAT/DPIA actualizados |
| ✅ **Arreglado (código, más allá del informe original)** | BUG-05 (escaneos O(N) acotados, verificado sin cambio de resultados), **SEC-04(a) RLS ACTIVA en producción (2026-07-20)**: rol no-privilegiado + claims por sesión + políticas completas; suite verde en ambos modos + prueba de bloqueo cruzado a nivel de BD. RAT/DPIA reflejan la doble barrera (ver `docs/RLS.md`) |
| ⏸️ **Diferido — requiere decisión humana / riesgo** | OPS-01 monitorización del backup (operativo), CMP-03/CMP-04 (criterio laboralista/DPO), SEC-02 rate-limiting (se cubre en Fase 3 con Cloudflare), SEC-11 (`--forwarded-allow-ips`: no tocar sin los rangos reales del proxy, Fase 3) |

Los diferidos están registrados en `docs/DEFERRED.md`. Lo que sigue es el informe original.

---


> **Para Claude Fable 5.** Este documento es una lista de trabajo, no una verdad establecida.
> Cada hallazgo lo produjo una auditoría (código, seguridad, compliance) sobre el estado del
> repo el 2026-07-18. Antes de tocar nada:
>
> 1. **VERIFICA** que el hallazgo sigue siendo cierto leyendo el código en la ubicación
>    indicada. El código evoluciona; un hallazgo puede estar ya resuelto o haberse movido.
>    Si no lo puedes reproducir, márcalo como *no reproducible* y NO lo "arregles" a ciegas.
> 2. Consulta las **skills** implicadas (`audit-trail`, `rgpd-dataguard`, `fastapi-supabase`,
>    `legal-compliance`, `fichaje-domain`) ANTES de implementar — las Reglas de Oro de
>    `CLAUDE.md` mandan sobre cualquier sugerencia de aquí.
> 3. Trabaja **un hallazgo por commit**, con su(s) test(s), atado al REQ y al ID de aquí
>    (p. ej. `fix(security): supervisor no puede resetear PIN de admin [SEC-01][REQ-21]`).
> 4. **Tests siempre contra el Postgres local** (contenedor `fichajes-db-test`, puerto 55432),
>    NUNCA contra producción (ver `memory` del proyecto y `docs/BACKUP.md`).
> 5. Corre `ruff check .`, `pytest -q` y `compliance_check.py` en verde antes de cerrar cada uno.
> 6. Pide aprobación humana antes de cambios destructivos o que alteren el modelo de conexión
>    a la BD (SEC-04 toca el rol de Postgres: es de alto riesgo, no lo hagas sin OK explícito).
>
> **Cómo verificar cada fix (entorno):**
> ```bash
> docker start fichajes-db-test
> export DATABASE_URL="postgresql+asyncpg://fichajes:localdev@localhost:55432/fichajes" DB_REQUIRE_TLS=false
> .venv/bin/ruff check . && .venv/bin/pytest -q && .venv/bin/python .claude/skills/legal-compliance/scripts/compliance_check.py
> ```

## Índice de severidad

| ID | Sev | Título | REQ |
|----|-----|--------|-----|
| SEC-01 | 🔴 Crítico | Escalada supervisor→admin vía reset-pin | 21 |
| OPS-01 | 🔴 Crítico | Conservación 4 años depende del backup: monitorizarlo | 03 |
| BUG-01 | 🟠 Alto | Race condition: validación de estado fuera del lock | 01 |
| SEC-04 | 🟠 Alto | RLS inerte (app conecta como superusuario) | 24 |
| SEC-05 | 🟠 Alto | TRUNCATE esquiva la inmutabilidad | 02 |
| TEST-01 | 🟠 Alto | El fixture de tests convierte fallos en `skip` | — |
| CMP-01 | 🟠 Alto | RAT incompleto: faltan encargados (Railway/Cloudflare/R2) | 10/23 |
| CMP-02 | 🟠 Alto | `baja` es categoría especial (art. 9 RGPD); DPIA lo niega | 10 |
| BUG-02 | 🟡 Medio | Cómputo de periodos en fronteras UTC, no Madrid | 12 |
| BUG-03 | 🟡 Medio | Desconexión: compara UTC contra ventana local | 26 |
| SEC-02 | 🟡 Medio | Sin rate limiting por IP (fuerza bruta horizontal) | 21 |
| SEC-03 | 🟡 Medio | Enumeración de empleados por timing de bcrypt | 05 |
| SEC-06 | 🟡 Medio | JWT sin revocación (logout/reset/rol no expulsan) | 21 |
| SEC-07 | 🟡 Medio | Sin cabeceras de seguridad (CSP/HSTS/X-Frame/nosniff) | — |
| SEC-08 | 🟡 Medio | Derivación de clave Fernet sin KDF; clave compartida geo/docs | 20 |
| BUG-04 | 🟡 Medio | Autorización no revalida is_active/rol en cada request | — |
| BUG-05 | 🟡 Medio | Escaneos O(N) del histórico en cada fichaje | — |
| BUG-06 | 🟡 Medio | `/reports/overtime` no pasa relation_type | 26 |
| CMP-03 | 🟡 Medio | Art. 35.5: falta resumen entregable + flag abono/descanso | 08 |
| CMP-04 | 🟡 Medio | Sobre-retención: nada borra tras 4 años (art. 5.1.e) | 03 |
| CMP-05 | 🟡 Medio | Geo sobre consentimiento: base jurídica cuestionable | 20 |
| BUG-07 | 🟢 Bajo | Solape de ausencias es TOCTOU | — |
| BUG-08 | 🟢 Bajo | Cutoff de retención ignora bisiestos | 03 |
| SEC-09 | 🟢 Bajo | Sin CSRF token (solo SameSite=strict) | — |
| SEC-10 | 🟢 Bajo | Upload: content-type del cliente, filename en cabecera | 28 |
| SEC-11 | 🟢 Bajo | `--forwarded-allow-ips '*'` confía cualquier upstream | — |
| SEC-12 | 🟢 Bajo | TLS a BD no se verifica en el arranque (solo en deploy) | 23 |
| BUG-09 | 🟢 Bajo | `get_db` envuelve `get_session` sin necesidad | — |
| CMP-06 | 🟢 Bajo | `client_event_id` sin escapar en el payload sellado | 15 |

> Nota sobre el **repo público**: la primera auditoría lo marcó como alto. Es una decisión
> ya tomada por el propietario ("lo dejamos como está"). NO lo cambies; queda fuera de alcance.

---

## 🔴 CRÍTICO

### SEC-01 — Escalada de privilegios: un `supervisor` puede apoderarse de una cuenta `admin`
- **Dónde:** `app/api/admin.py:65` (`admin_reset_pin`) y `app/web/router.py:543` (`/admin/reset-pin`).
- **Qué pasa:** ambos exigen `require_role("admin","supervisor")`, resetean **cualquier**
  `worker_id` (incluidos admins) y devuelven el PIN nuevo **en claro** en la respuesta.
  Un supervisor resetea el PIN de un admin, lo lee, entra (cambia el PIN temporal en el
  primer login) y obtiene control total: política de tiempo, alta de empleados, verificación
  de cadena.
- **Verificar:** confirma los dos decoradores `require_role`/`require_web_role` y que no hay
  ninguna comprobación de la jerarquía de roles entre actor y objetivo antes del reset.
- **Fix propuesto:** impedir resetear una cuenta cuyo rol sea igual o superior al del actor
  (definir un orden `empleado < supervisor < admin`), o restringir `reset-pin` a `admin` a
  secas. Elige lo segundo si el flujo operativo lo permite (más simple y seguro). Registra el
  evento en el log de seguridad (`log_event("pin_reset", by=..., target=...)`).
- **Tests:** un `supervisor` recibe 403 al intentar resetear a un `admin` (y a otro
  `supervisor` si aplica la regla de jerarquía); un `admin` sí puede resetear a un `empleado`.
- **Criterio de aceptación:** ningún actor puede resetear el PIN de una cuenta de rol ≥ al suyo.

### OPS-01 — La conservación de 4 años depende de un backup que debe estar monitorizado
- **Dónde:** `app/jobs/retention.py` (nunca borra, solo marca `eligible`), `app/jobs/backup.py`
  (única copia real), `docs/DEFERRED.md` (Supabase Free sin backups gestionados + pausa ~7 días).
- **Qué pasa:** la conservación legal (Regla de Oro nº4, REQ-03) se sostiene sobre el cron a
  R2. Si ese cron deja de correr sin que nadie se entere, y la instancia Free se pausa/pierde,
  se pierden registros de obligada conservación (infracción grave LISOS).
- **Estado:** el backup y el restore se verificaron manualmente el 2026-07-18 (un run real +
  simulacro de restore con cadena de hashes íntegra). Lo que falta es **detección de fallo**.
- **Fix propuesto:** una alerta si un día NO aparece backup nuevo en R2 (p. ej. un pequeño job
  que liste `daily/` y avise si el objeto más reciente tiene > 26 h; o healthcheck externo del
  cron). Documentar la evidencia de que corre. NO es código de la app necesariamente; puede ser
  operativo. Alternativa de fondo: subir a Supabase Pro (elimina esta pieza).
- **Criterio de aceptación:** existe un mecanismo que avisa si el backup diario no se produce.

---

## 🟠 ALTO

### BUG-01 — Race condition: la validación de estado vive fuera del advisory lock
- **Dónde:** `app/api/fichaje.py:151` (lee `reconstruct_state` y valida `next_state` ANTES de
  `append_event`), `app/web/router.py:306`. El lock (`pg_advisory_xact_lock`) está dentro de
  `app/audit/chain.py:80`.
- **Qué pasa:** el lock serializa `seq`/`prev_hash` pero NO la validación de estado. Dos
  peticiones concurrentes del mismo trabajador (doble clic, dos pestañas, cola offline + online)
  leen ambas el mismo estado, ambas validan, y el lock las inserta en serie → p. ej. dos
  `check_in` seguidos. La cadena de hash queda íntegra (verify_chain verde) pero el histórico es
  semánticamente inválido. Peor: `reconstruct_state` (`app/domain/state_machine.py:71`) lanza
  `InvalidTransition` NO capturada en `today()`, `summary()`, `_estado_ctx()` y en `fichar_evento`
  → **500 permanente** en `/fichaje/today`, `/summary`, `/fichar`, `/fichar/estado` para ese
  trabajador, irreparable por la inmutabilidad (haría falta una corrección manual).
- **Verificar:** confirma que entre la lectura de estado y el insert no hay lock compartido; y
  que las vistas que llaman a `reconstruct_state` no capturan `InvalidTransition`.
- **Fix propuesto:** hacer atómico el check+act. Mover la reconstrucción+validación de estado
  DENTRO de la sección con lock de `append_event` (adquirir advisory lock → releer histórico →
  revalidar `next_state` → insertar), o exponer una variante de `append_event` que reciba un
  validador de estado y lo ejecute bajo el lock. Además, capturar `InvalidTransition` en las
  vistas de lectura y degradar con gracia (no 500).
- **Tests:** dos `append_event` concurrentes de `check_in` para el mismo worker → el segundo
  debe fallar con transición inválida, no crear un segundo check_in. Una vista de lectura sobre
  un histórico artificialmente incoherente no debe devolver 500.
- **Criterio de aceptación:** imposible insertar dos eventos que violen la máquina de estados,
  aun con concurrencia; las lecturas nunca caen a 500 por estado incoherente.

### SEC-04 — La RLS de Postgres es inerte (no hay defensa en profundidad)
- ⚠️ **Alto riesgo de implementación: NO tocar el rol de conexión sin aprobación humana explícita.**
- **Dónde:** `app/db/migrations/0001_init.sql:20` (`auth.uid()`/`auth.jwt()` son stubs que
  devuelven NULL), comentarios honestos en `0002_worker.sql`, `0003_time_record.sql:20`,
  `app/db/session.py:15` (conecta como superusuario, que bypassa RLS). Las políticas
  `*_self_select`/`*_oversight_select` de las 6 tablas con datos personales **no se evalúan nunca**.
- **Qué pasa:** el único control de acceso real es la capa de aplicación (que hoy está bien
  hecha: sin IDOR conocidos). Pero no hay backstop: cualquier endpoint futuro que olvide el
  check self-vs-oversight expone a toda la plantilla, y una SQLi hipotética tendría acceso total.
  Además la **DPIA/RAT afirman "RLS" como medida activa** → inexacto (ver CMP correlativo).
- **Verificar:** confirma con qué usuario conecta la app en prod (`\du` / rol del `DATABASE_URL`)
  y que no se inyectan claims por transacción (`SET LOCAL request.jwt.claims`).
- **Fix propuesto (dos caminos, elegir con el humano):**
  - **(a) Activar RLS de verdad:** crear un rol Postgres NO superusuario y NO `BYPASSRLS` para
    la app; inyectar los claims JWT por transacción (`SET LOCAL request.jwt.claims = ...`) en la
    dependencia de sesión; implementar `auth.uid()`/`auth.jwt()` para leer esos claims. Es el
    mayor salto de robustez y las políticas ya están escritas. Requiere pruebas exhaustivas de
    que ningún flujo legítimo se rompe (admin/oversight, jobs, backup).
  - **(b) Si no se activa ahora:** corregir `docs/compliance/DPIA.md` y `.../RAT.md` para
    describir el control como "capa de aplicación", no "RLS", y NO apoyarse en RLS en el modelo
    de amenazas. (Esto es CMP; hazlo YA aunque (a) se difiera, para no afirmar algo falso.)
- **Criterio de aceptación:** o las políticas RLS se aplican en runtime con un rol restringido,
  o los documentos de compliance dejan de presentar la RLS como salvaguarda activa.

### SEC-05 — `TRUNCATE` esquiva la garantía de inmutabilidad
- **Dónde:** `app/db/migrations/0003_time_record.sql:63` y `0006_corrections_audit.sql:44`: los
  triggers son `BEFORE UPDATE OR DELETE FOR EACH ROW`. `TRUNCATE` no dispara triggers de fila, y
  como la app es superusuario el `REVOKE` no la afecta. `app/jobs/restore.py:87` demuestra que
  `TRUNCATE ... CASCADE` funciona.
- **Qué pasa:** cualquier SQL con el rol de la app (o un job mal usado) puede vaciar
  `time_record`/`record_correction` saltándose REQ-02, sin el bloqueo esperado.
- **Verificar:** confirma que no existe trigger `BEFORE TRUNCATE`.
- **Fix propuesto:** nueva migración `00NN_truncate_guard.sql` con
  `CREATE TRIGGER ... BEFORE TRUNCATE ON time_record FOR EACH STATEMENT EXECUTE FUNCTION prevent_mutation();`
  (y en `record_correction`). Ojo: esto haría fallar `restore.run_restore(..., force=True)`, que
  usa TRUNCATE — el restore debe desactivar el trigger dentro de su transacción
  (`ALTER TABLE ... DISABLE TRIGGER`) o usar `DELETE` en su lugar. Contempla esa interacción.
- **Tests:** `TRUNCATE time_record` lanza excepción; el restore local con `--force` sigue
  funcionando (ajustar `restore.py` en consecuencia).
- **Criterio de aceptación:** no se puede vaciar el ledger por TRUNCATE por la vía normal de la app.

### TEST-01 — El fixture de tests convierte cualquier fallo en `skip`
- **Dónde:** `app/tests/conftest.py:37` (`except Exception: pytest.skip(...)`).
- **Qué pasa:** `prepared` es la base de casi toda la suite. El `except Exception` captura no
  solo caídas de conexión sino fallos de `migrate.run()`, drift de esquema o SQL roto. En CI el
  Postgres está garantizado, así que un fallo debería ser rojo; en su lugar **toda la suite se
  salta y CI queda verde**, ocultando regresiones (p. ej. un trigger de inmutabilidad roto).
- **Fix propuesto:** si `DATABASE_URL` apunta a una BD que debería estar disponible (CI), fallar
  duro; reservar `skip` para local sin BD, y acotar el `except` a errores de conexión
  (`OperationalError`, `ConnectionError`, `socket.gaierror`), nunca `Exception`. Considera un
  umbral mínimo de cobertura en CI.
- **Criterio de aceptación:** un fallo de migración o de esquema pone CI en ROJO, no en skip.

### CMP-01 — RAT incompleto: faltan encargados del tratamiento
- **Dónde:** `docs/compliance/registro-actividades-tratamiento.md:22,36` (solo lista "Supabase").
- **Qué pasa:** el sistema trata datos personales también en **Railway** (hosting/cómputo),
  **Cloudflare** (proxy: ve IPs y tráfico) y **Cloudflare R2** (volcados cifrados de TODA la BD).
  Art. 30.1.d exige listar todos los encargados; art. 28 exige DPA con cada uno.
- **Fix propuesto:** añadir Railway, Cloudflare y R2 al RAT con rol, ubicación UE y referencia a
  su DPA. Verificar/adjuntar los DPA (Supabase solicitado 2026-07-16; Railway y Cloudflare
  pendientes). Coordinar con la Fase 5 del go-live.
- **Criterio de aceptación:** el RAT refleja los cuatro encargados y el estado de sus DPA.

### CMP-02 — `baja` es categoría especial (art. 9 RGPD) y la DPIA lo niega
- **Dónde:** `app/db/migrations/0012_absence.sql:39` (`absence_type='baja'`), `app/db/models.py`;
  frente a `docs/compliance/DPIA.md` y `.../RAT.md` que afirman "no se tratan datos de salud".
- **Qué pasa:** el hecho de una baja médica (incapacidad temporal) es dato de salud (art. 9.1),
  aun sin diagnóstico. Requiere base del art. 9.2.b (obligaciones laborales/seguridad social),
  hoy no citada, y agrava la valoración de riesgo de la DPIA.
- **Fix propuesto:** reconocer en DPIA/RAT que `baja` es categoría especial, citar art. 9.2.b y
  reevaluar el riesgo/medidas. Documental, sin código.
- **Criterio de aceptación:** DPIA/RAT tratan `baja` como art. 9 con su base jurídica.

---

## 🟡 MEDIO

### BUG-02 — El cómputo de periodos usa fronteras UTC, no Europe/Madrid
- **Dónde:** `app/domain/hours.py:128` (`period_window`), `:161` (`annual_window`);
  `app/api/fichaje.py:277` (`today`), `:320` (`summary`). Existe `to_madrid` en
  `app/core/time.py:30` pero solo se usa para presentación.
- **Qué pasa:** día/semana/mes/año se cortan a medianoche UTC (01:00–02:00 en Madrid). El
  trabajo cercano a medianoche se atribuye al periodo equivocado, distorsionando la totalización
  diaria y **la mensual de horas extra (REQ-12, legalmente exigible art. 35.5)**, y "hoy" cambia
  a las 02:00 locales.
- **Fix propuesto:** calcular las fronteras de periodo en Europe/Madrid y convertirlas a UTC para
  filtrar. Mantener el sellado en UTC (no tocar `chain.py`). Consulta skill `fichaje-domain`.
- **Tests:** un evento a las 23:30 de Madrid el último día del mes cuenta en ese mes, no en el
  siguiente; "hoy" cambia a medianoche de Madrid.

### BUG-03 — Desconexión: compara hora UTC contra una ventana introducida en local
- **Dónde:** `app/domain/desconexion.py:34` compara `dt.astimezone(UTC).time()` contra
  `desconexion_start/end`, que el admin teclea como horario local (`app/web/router.py:508`).
- **Qué pasa:** desfase de 1–2 h → las alertas `off_hours` (REQ-26) saltan en la franja errónea.
- **Fix propuesto:** convertir `dt` a Madrid antes de comparar, o forzar/documentar que la ventana
  se almacene en UTC. Elige una y sé consistente con BUG-02.

### SEC-02 — Sin rate limiting por IP: fuerza bruta horizontal
- **Dónde:** `app/api/auth.py:46` (lockout solo por cuenta), sin middleware de rate limiting.
- **Qué pasa:** PIN de 6 dígitos (10^6) + códigos derivables del nombre. Un origen puede rociar
  un PIN candidato contra toda la plantilla; el lockout por cuenta no frena el ataque horizontal.
- **Fix propuesto:** parte se mitiga con **rate limiting de Cloudflare en `/login`** (Fase 3) —
  documentarlo como control. Opcionalmente, límite por IP en la app (`slowapi`) + backoff. Coordina
  con la Fase 3; no dupliques si Cloudflare lo cubre suficientemente.

### SEC-03 — Enumeración de empleados por timing de bcrypt
- **Dónde:** `app/api/auth.py:56` (si el worker no existe/inactivo, retorna ANTES de `verify_pin`).
- **Qué pasa:** un código válido ejecuta bcrypt (lento); uno inválido retorna rápido → la latencia
  distingue códigos válidos. Segundo oráculo: cuenta bloqueada devuelve 429 vs 401.
- **Fix propuesto:** ejecutar siempre un `verify_pin` contra un hash bcrypt dummy fijo cuando el
  worker no existe (trabajo constante). Valorar unificar 401/429 (con cuidado: el 429 es útil al
  usuario legítimo; quizá basta el constant-work).
- **Tests:** difícil testear timing de forma estable; al menos verifica que existe la rama de
  trabajo constante (se llama a `verify_pin` también en el camino "no existe").

### SEC-06 — JWT sin revocación
- **Dónde:** `app/core/security.py:65` (sin `jti`/versión), `app/web/session.py:65` (logout solo
  borra cookie), `app/api/deps.py` (sin lista de revocación).
- **Qué pasa:** logout, reset de PIN (SEC-01), bloqueo por fuerza bruta y cambio de rol NO
  expulsan sesiones vivas (ventana de hasta 30 min).
- **Fix propuesto:** `token_version` en `worker`, incluido en el claim y validado en
  `decode_token`; incrementarlo en reset-pin, lockout y cambio de rol. Migración + lógica.
- **Tests:** tras reset-pin/cambio de rol, un token previo deja de validar.

### SEC-07 — Sin cabeceras de seguridad
- **Dónde:** `app/main.py` (sin middleware de cabeceras).
- **Qué pasa:** faltan CSP, HSTS, X-Frame-Options/frame-ancestors (clickjacking en `/login`,
  `/fichar`), X-Content-Type-Options: nosniff.
- **Fix propuesto:** middleware que las añada globalmente. HSTS lo puede poner Cloudflare (Fase 3),
  pero CSP y X-Frame-Options conviene ponerlas en la app. CSP con cuidado por Alpine/htmx inline
  (probablemente `script-src 'self' 'unsafe-inline'` inicialmente; endurecer luego).
- **Tests:** las respuestas HTML llevan las cabeceras esperadas.

### SEC-08 — Derivación de clave Fernet sin KDF; misma clave para geo y justificantes
- **Dónde:** `app/core/crypto.py:28` (`sha256(passphrase)` sin sal), `app/jobs/backup.py:70`
  (idem para `BACKUP_ENCRYPTION_KEY`). La misma `geo_encryption_key` cifra geo Y justificantes
  médicos (`crypto.py:49`, usado en `absences.py` y `web/router.py`).
- **Qué pasa:** si la passphrase configurada tiene poca entropía, es fuerza-bruteable offline
  desde un ciphertext (volcado de BD/backup). Compromiso de una clave expone geo + datos médicos.
- **Fix propuesto:** exigir/generar claves Fernet de 32 bytes aleatorios reales (documentar en el
  runbook que NO deben ser passphrases memorizables) o derivar con scrypt/Argon2 + sal fija
  documentada. Separar la clave de documentos de la de geo. Cuidado con la **migración de datos ya
  cifrados**: cambiar la derivación invalida lo existente — si hay datos reales, hace falta
  recifrado; en prod aún no hay datos reales (reset pre-golive pendiente), así que es el momento.
- **Criterio de aceptación:** claves de alta entropía y separación geo/documentos.

### BUG-04 — La autorización por request no revalida is_active/rol/estado del PIN
- **Dónde:** `app/api/auth.py:59` (solo comprueba `is_active` en login), `app/api/deps.py:23` y
  `app/web/session.py:69` (solo decodifican el JWT).
- **Qué pasa:** un trabajador desactivado (baja/cese) o con rol cambiado conserva acceso hasta que
  expira el token. Relacionado con SEC-06 (misma solución de fondo).
- **Fix propuesto:** en operaciones sensibles, recargar el `Worker` y verificar `is_active`; o TTL
  corto + `token_version` (unificar con SEC-06).

### BUG-05 — Escaneos O(N) del histórico completo en cada fichaje
- **Dónde:** `app/api/fichaje.py:87` (`_alert_if_annual_cap` carga TODOS los `time_record`),
  `annual_status` reconstruye todas las jornadas, `_ordered_event_types:124` carga todos los
  `event_type`. Varios por evento.
- **Qué pasa:** con ledger append-only y 4 años de retención, N crece sin cota; cada fichaje hace
  varios full-scans. Escala mal con plantilla grande fichando varias veces al día.
- **Fix propuesto:** acotar por ventana (año natural para el anual; última jornada abierta para el
  estado) y/o cachear último `seq`/estado. No cambia semántica, solo rendimiento.

### BUG-06 — `/reports/overtime` no pasa `relation_type`
- **Dónde:** `app/api/reports.py:66` llama `classify_overtime(records, policy, reference)` sin
  `relation_type`; `export.py:92` y `web/router.py:973` sí lo pasan.
- **Qué pasa:** el exceso de un trabajador a tiempo parcial se etiqueta `extra` en vez de
  `complementarias` (REQ-26), inconsistente con el export. `OvertimeReport` tampoco expone
  `complementarias`.
- **Fix propuesto:** pasar `worker.relation_type` y añadir el campo al schema/respuesta.
- **Tests:** un reporte de overtime de un trabajador `tiempo_parcial` clasifica como complementarias.

### CMP-03 — Art. 35.5: totalización presente, pero falta resumen entregable y flag abono/descanso
- **Dónde:** la totalización existe (`domain/hours.py::classify_overtime`, `api/reports.py`,
  export). Pero `compensacion` está hardcodeado a `"pending"` (`schemas/report.py:26`) y no
  aparece en el export; ver `docs/DEFERRED.md`.
- **Qué pasa:** el núcleo del 35.5 se cumple (hay disponibilidad vía portal/export); los matices
  (abono vs descanso, entrega formal de copia del resumen, tope 80 h/año art. 35.2) son mejoras.
- **Fix propuesto:** resolver el flag abono/descanso e incluirlo en el export; valorar un artefacto
  de "resumen entregado". Requiere decisión de negocio (ver DEFERRED) — no lo cierres sin criterio.

### CMP-04 — Sobre-retención: nada borra tras los 4 años (art. 5.1.e RGPD)
- **Dónde:** `app/jobs/retention.py` marca `eligible` pero el borrado físico está fuera de alcance
  y el trigger de inmutabilidad lo impediría igualmente.
- **Qué pasa:** los datos se conservan indefinidamente > 4 años. La ley obliga a conservar 4 años;
  el RGPD obliga a no conservar de más. Hoy solo se cumple la primera mitad. Riesgo AEPD menor.
- **Fix propuesto:** decisión de política (con DPO/laboralista) sobre borrado post-4-años vs
  derecho de supresión, y su interacción con la inmutabilidad (¿borrado físico controlado con
  registro en `retention_log`?, ¿anonimización?). Decisión pendiente, no implementar a ciegas.

### CMP-05 — Base jurídica de la geolocalización = consentimiento (cuestionable en relación laboral)
- **Dónde:** DPIA/RAT y `config` tratan geo sobre consentimiento (art. 6.1.a). Minimización
  técnica excelente (solo si `geo_consent AND modalidad='movil'`, cifrada, puntual).
- **Qué pasa:** AEPD/EDPB consideran que el consentimiento del trabajador rara vez es libre
  (desequilibrio de poder). Defendible aquí por ser genuinamente opcional y puntual, pero conviene
  revisar con el DPO si la base idónea es 6.1.b/f con juicio de proporcionalidad.
- **Fix propuesto:** revisión documental con DPO; ajustar DPIA/RAT si procede. Nuance, no bloqueante.

---

## 🟢 BAJO

- **BUG-07** — Solape de ausencias TOCTOU (`app/api/absences.py:107`, `web/router.py:762`): lectura-
  comprobación-inserción sin lock/constraint de exclusión. Flujo admin, poca concurrencia. Fix:
  constraint de exclusión Postgres (`EXCLUDE USING gist`) o lock.
- **BUG-08** — Cutoff de retención usa `365*4` días (`app/jobs/retention.py:34`), ignora bisiestos;
  marca `eligible` ~1 día antes. Inocuo (no borra). Fix: `relativedelta(years=4)` o equivalente.
- **SEC-09** — Sin token CSRF en los POST web; única defensa `SameSite=strict` (`web/session.py:41`).
  Mitiga el CSRF clásico pero no subdominios same-site comprometidos ni login-CSRF. Fix: double-submit
  token o validación de `Origin`/`Referer`.
- **SEC-10** — Upload de justificantes: `content_type` declarado por el cliente sin verificar magic
  bytes; `filename` reflejado en `Content-Disposition` (`absences.py:190,244`, `web/router.py:832`).
  Riesgo acotado (attachment, cifrado en reposo, 5 MB). Fix: validar bytes mágicos y sanear filename
  (RFC 6266 `filename*`).
- **SEC-11** — `railway.json` arranca uvicorn con `--forwarded-allow-ips '*'`. Con
  `trust_cf_connecting_ip=False` la IP de logs sale de XFF → falsificable si la instancia es
  alcanzable sin pasar por el proxy. Impacto: envenenamiento de logs. Fix: fijar los rangos del
  proxy de Railway/Cloudflare (coordinar con Fase 3, donde se activa `trust_cf_connecting_ip`).
- **SEC-12** — `db_uses_tls()` existe (`config.py:98`) pero nada lo invoca en el arranque (el
  `lifespan` solo llama a `assert_eu_region` + `assert_secure_secrets`). El TLS a BD solo se verifica
  en el deploy (`scripts/check_region.py`). Fix: añadir un assert de TLS al lifespan.
- **BUG-09** — `app/api/deps.py:18` (`get_db`) envuelve `get_session` con `async for`; en desconexión
  del cliente el async-gen interno puede cerrarse solo en GC (no determinista). Fix: usar `get_session`
  directo o `async with SessionLocal() as s: yield s` inline.
- **CMP-06** — `client_event_id` (del cliente en offline) se concatena sin escapar en el payload
  sellado (`app/audit/chain.py:44`). Un valor con `|` es teóricamente inyectable en el payload
  canónico. Riesgo muy bajo (el hash se recomputa consistente). Fix: normalizar/escapar o excluirlo
  del payload sellado.

---

## Lo que está BIEN — NO romper al arreglar lo anterior

Verificado en código, no solo afirmado:
- **Inmutabilidad real**: trigger `prevent_mutation()` BEFORE UPDATE/DELETE (afecta incluso al
  superusuario) + `REVOKE`, sobre `time_record` y `record_correction`, con `UNIQUE(worker_id,seq)` y
  `UNIQUE(hash)`. (SEC-05 solo añade la cobertura de TRUNCATE; no toques lo existente.)
- **Sellado encadenado**: SHA-256 `prev_hash→hash` por trabajador con `pg_advisory_xact_lock` por
  transacción; verificador puro + endpoint + cron. (BUG-01 amplía el lock a la validación de estado;
  no debilites el sellado.)
- **Backup/restore**: `COPY` nativo en streaming, cifrado antes de salir del proceso, SHA-256 por
  tabla + verificación de tamaño remoto, toposort de FKs, restore en una transacción con recolocación
  de secuencias, residencia UE forzada. (SEC-05 obliga a ajustar el TRUNCATE del restore.)
- **Onboarding**: unicidad del código por constraint + reintento sobre `IntegrityError` (no chequeo
  Python). Correcto frente a concurrencia.
- **Capas limpias**: dominio puro con `Protocol`; API y web SSR reutilizan las mismas funciones de
  dominio/servicio sin duplicar lógica.
- **Auth**: bcrypt, PIN nunca logueado, generación con `secrets` + blocklist de PINs triviales,
  respuesta uniforme en credenciales inválidas, JWT con algoritmo fijado (sin confusión alg).
- **Control horizontal (IDOR)**: patrón self-vs-`OVERSIGHT_ROLES` consistente en export, reports,
  absences, corrections, portal, justificante. Sin IDOR conocido.
- **Guardas de arranque**: `assert_secure_secrets` (no arranca con defaults en prod), `assert_eu_region`.
- **Logging de seguridad**: JSON a stdout con minimización de PII (sin PIN/nombres/geo/contenido).
- **Bypass de PIN temporal**: `/fichaje/event` y `/sync` rechazan `pin_temporary` con 403.

---

## Orden recomendado

1. **Bloque críticos de código** (SEC-01, BUG-01, SEC-05, TEST-01) con sus tests — antes del go-live.
2. **CMP-01, CMP-02** y la parte documental de SEC-04(b) — completar RAT/DPIA (Fase 5), pero corregir
   la afirmación sobre RLS cuanto antes.
3. **OPS-01** — monitorización del backup.
4. **SEC-04(a)** — activar RLS de verdad (alto riesgo; solo con OK humano y pruebas exhaustivas).
5. **BUG-02/03** (zona horaria en cómputo) y **SEC-02/06/07/08**, muchos coordinados con la Fase 3
   (Cloudflare: rate limiting, HSTS, IP real).
6. Resto de medios y bajos como deuda priorizada.

> Recuerda: los pendientes de negocio/laboralista (CMP-03/04/05, y los de `docs/DEFERRED.md`:
> festivos, tope anual vs ausencias, `travel_computes`) NO se resuelven en código sin criterio
> jurídico. Escala la consulta, no inventes la regla.
