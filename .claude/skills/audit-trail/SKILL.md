---
name: audit-trail
description: >
  Inmutabilidad, sellado temporal y trazabilidad de los registros de fichaje de Global
  Meats. USA ESTA SKILL siempre que implementes o modifiques cómo se escriben, sellan,
  versionan o auditan los registros: tablas append-only, hash encadenado, prevención de
  UPDATE/DELETE, correcciones versionadas con motivo y autor, y alertas de manipulación.
  Consúltala antes de tocar cualquier escritura sobre time_record o de diseñar el
  mecanismo de correcciones. Cubre REQ-02, 15, 16, 25.
---

# Audit Trail & Inmutabilidad

El registro de jornada debe ser **fiable, inmodificable y no manipulable a posteriori**
(exigencia VIGENTE del art. 34.9 ET, reforzada por la reforma 2026). Esta skill define
cómo lo garantizamos técnicamente.

## Principio rector

**Append-only.** Un `time_record` se inserta una vez y jamás se actualiza ni borra.
Toda "edición" es un registro nuevo. La verdad histórica es inmutable.

## 1. Bloqueo de mutación (REQ-02)

A nivel de Postgres/Supabase:
- Revocar `UPDATE` y `DELETE` sobre `time_record` para todos los roles de aplicación.
- Trigger defensivo que lanza excepción ante cualquier `UPDATE`/`DELETE`:

```sql
CREATE OR REPLACE FUNCTION prevent_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'time_record es append-only: % no permitido', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER no_update_time_record
  BEFORE UPDATE OR DELETE ON time_record
  FOR EACH ROW EXECUTE FUNCTION prevent_mutation();
```

## 2. Sellado temporal + hash encadenado (REQ-15)

Cada registro se sella con la hora del **servidor** (UTC) y un hash que encadena con el
registro anterior del mismo trabajador, formando una cadena verificable estilo ledger.

```
hash_i = sha256( worker_id || occurred_at || event_type || payload || prev_hash )
```

- `prev_hash` = hash del último `time_record` de ese `worker_id` (o un génesis fijo).
- Alterar cualquier registro rompe la cadena de todos los posteriores → detectable.
- Implementar el cálculo en un único punto (servicio de escritura), nunca en el cliente.
- El timestamp lo pone el servidor; el cliente no puede dictarlo (salvo offline, donde
  se guarda la hora real del fichaje y se valida una ventana de tolerancia al sync).

Verificación: un job periódico recomputa la cadena por trabajador y alerta si rompe.

## 3. Correcciones versionadas (REQ-16)

Nunca se corrige el original. Se inserta en `record_correction`:
- `original_record_id` (referencia inmutable al registro corregido),
- `corrected_value` (el dato correcto),
- `reason` — **obligatorio** (la reforma exige campo de justificación),
- `author_id` (quién corrige), `created_at`.

Al exportar/consultar, mostrar el original **y** sus correcciones, nunca solo el valor
corregido. Esto preserva el rastro completo exigido.

## 4. Alertas de auditoría (REQ-25)

Tabla `audit_alert` alimentada por:
- Intentos de `UPDATE`/`DELETE` capturados por el trigger.
- Cadena de hash rota detectada por el verificador.
- Lecturas masivas o accesos fuera de patrón (p.ej. un rol `empleado` intentando leer
  registros de terceros — debería bloquearlo RLS, pero también se alerta).
- N intentos de login fallidos por trabajador.

Cada alerta: `tipo`, `worker_id`/`actor_id`, `detalle`, `detected_at`, `severity`.

## 5. Qué NO hacer

- ❌ `UPDATE time_record SET ...` — jamás.
- ❌ Borrar registros para "limpiar" datos.
- ❌ Calcular hash/timestamp en el frontend.
- ❌ Aceptar `occurred_at` arbitrario del cliente sin validación.
- ❌ Exponer el valor corregido ocultando el original.

## Interacción con otras skills

- El modelo de las tablas vive en `fichaje-domain`.
- Permisos de lectura por rol y RLS en `rgpd-dataguard`.
- Mapeo legal en `legal-compliance` (REQ-02 es VIGENTE; 15/16/25 son objetivo reforma).
