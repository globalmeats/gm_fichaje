# Plantillas RLS, triggers y políticas

## Activar RLS y políticas por rol (REQ-24)

```sql
ALTER TABLE time_record ENABLE ROW LEVEL SECURITY;

-- Empleado: solo sus filas
CREATE POLICY tr_empleado_select ON time_record FOR SELECT
  USING ( auth.uid() = worker_id );

-- Inserción: solo el propio trabajador (o kiosk autorizado) crea su fichaje
CREATE POLICY tr_empleado_insert ON time_record FOR INSERT
  WITH CHECK ( auth.uid() = worker_id );

-- Supervisión / Inspección / RLT / Admin: lectura global
CREATE POLICY tr_oversight_select ON time_record FOR SELECT
  USING ( (auth.jwt() ->> 'role') IN ('supervisor','inspeccion','rlt','admin') );
```

## Append-only: bloquear UPDATE/DELETE (REQ-02, audit-trail)

```sql
REVOKE UPDATE, DELETE ON time_record FROM PUBLIC, app_role;

CREATE OR REPLACE FUNCTION prevent_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'time_record es append-only: % no permitido', TG_OP;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER no_mutate_time_record
  BEFORE UPDATE OR DELETE ON time_record
  FOR EACH ROW EXECUTE FUNCTION prevent_mutation();
```

## Correcciones (REQ-16): tabla aparte, también con RLS

```sql
ALTER TABLE record_correction ENABLE ROW LEVEL SECURITY;
CREATE POLICY rc_supervisor_insert ON record_correction FOR INSERT
  WITH CHECK ( (auth.jwt() ->> 'role') IN ('supervisor','admin') );
-- reason NOT NULL se garantiza con constraint de columna
```

## Notas
- Probar cada política con un test de aislamiento (rol empleado ↔ otro worker → 0 filas).
- El JWT de Supabase debe incluir `role` y `worker_id` como claims fiables.
