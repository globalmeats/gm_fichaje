-- 0003_time_record: registro de jornada append-only (núcleo legal vigente, art. 34.9).
-- REQ-01: registro de eventos de jornada (check_in/out y -reservados- pausas/desplaz.).
-- REQ-02: inmutabilidad. La garantía EFECTIVA es el trigger prevent_mutation() (se ejecuta
--         también para el superusuario) + REVOKE UPDATE/DELETE. La app conecta como
--         postgres (superusuario) -> RLS se bypassa; el control de acceso real lo hace la
--         capa de aplicación. La RLS queda como defensa en profundidad.
-- REQ-15: sellado temporal. occurred_at lo pone el servidor (UTC); prev_hash/hash encadenan
--         la cadena por trabajador (el cálculo vive en app/audit/chain.py).
-- REQ-24: RLS habilitado + políticas por rol (defensa en profundidad).
-- NOTA: el "RLS automático" de Supabase solo aplica a tablas creadas por el Table Editor;
--       esta tabla se crea por SQL, así que el ENABLE explícito es necesario (idempotente).
-- Idempotente.

CREATE TABLE IF NOT EXISTS time_record (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_id            uuid NOT NULL REFERENCES worker(id),
    -- Secuencia monotónica por trabajador (1, 2, 3, ...). Ordena la cadena de hash.
    seq                  bigint NOT NULL,
    event_type           text NOT NULL,
    -- Hora del servidor en UTC. El cliente NO la dicta.
    occurred_at          timestamptz NOT NULL,
    modalidad            text NOT NULL DEFAULT 'presencial',
    source               text NOT NULL DEFAULT 'web',
    -- Geolocalización puntual opcional (cifrada en Fase 6); nullable.
    geo                  text,
    -- Puesta a disposición (desplazamientos) -> cómputo en Fase 2.
    puesta_a_disposicion boolean NOT NULL DEFAULT false,
    -- Sellado encadenado (REQ-15). prev_hash del primer registro = 'GENESIS'.
    prev_hash            text NOT NULL,
    hash                 text NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT time_record_event_type_check
        CHECK (event_type IN (
            'check_in','check_out','break_start','break_end','travel_start','travel_end'
        )),
    CONSTRAINT time_record_modalidad_check
        CHECK (modalidad IN ('presencial','teletrabajo','movil')),
    CONSTRAINT time_record_source_check
        CHECK (source IN ('web','kiosk','mobile','offline_sync'))
);

-- Monotonía de la secuencia por trabajador (evita huecos/duplicados en la cadena).
CREATE UNIQUE INDEX IF NOT EXISTS time_record_worker_seq_key ON time_record (worker_id, seq);
-- Unicidad del hash (un hash repetido delataría manipulación o colisión).
CREATE UNIQUE INDEX IF NOT EXISTS time_record_hash_key ON time_record (hash);
-- Consultas de jornada por trabajador y fecha.
CREATE INDEX IF NOT EXISTS time_record_worker_occurred_idx
    ON time_record (worker_id, occurred_at);

-- ---- Inmutabilidad (REQ-02) ----
-- Revoca mutaciones para los roles de aplicación. El superusuario las ignora, por eso
-- el trigger de abajo es la garantía real.
REVOKE UPDATE, DELETE ON time_record FROM PUBLIC;

CREATE OR REPLACE FUNCTION prevent_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'time_record es append-only: % no permitido', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_mutate_time_record ON time_record;
CREATE TRIGGER no_mutate_time_record
  BEFORE UPDATE OR DELETE ON time_record
  FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

-- ---- Row Level Security (REQ-24, defensa en profundidad) ----
ALTER TABLE time_record ENABLE ROW LEVEL SECURITY;

-- Empleado: solo sus propios registros.
DROP POLICY IF EXISTS time_record_self_select ON time_record;
CREATE POLICY time_record_self_select ON time_record FOR SELECT
    USING ( auth.uid() = worker_id );

-- Roles de supervisión/oversight: lectura global.
DROP POLICY IF EXISTS time_record_oversight_select ON time_record;
CREATE POLICY time_record_oversight_select ON time_record FOR SELECT
    USING ( (auth.jwt() ->> 'role') IN ('supervisor','admin','rlt','inspeccion') );

-- Alta: el propio trabajador inserta sus eventos (vía servicio de cadena).
DROP POLICY IF EXISTS time_record_self_insert ON time_record;
CREATE POLICY time_record_self_insert ON time_record FOR INSERT
    WITH CHECK ( auth.uid() = worker_id );
