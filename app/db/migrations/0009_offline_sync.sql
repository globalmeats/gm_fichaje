-- 0009_offline_sync: sincronización de fichajes capturados offline (REQ-22).
-- REQ-22: el cliente puede encolar fichajes sin red y sincronizarlos después SIN pérdida ni
--         duplicado. client_event_id es la CLAVE DE IDEMPOTENCIA generada por el cliente: un
--         mismo evento reenviado (reintento) trae el mismo id y no se duplica.
--         occurred_at conserva la hora REAL del fichaje (la del cliente); created_at es la
--         hora de recepción del servidor. Separación limpia: el ledger sigue sellando con la
--         hora real, y el servidor deja constancia de cuándo lo recibió.
-- El índice UNIQUE es PARCIAL (WHERE client_event_id IS NOT NULL) para no afectar a las
-- inserciones online (que dejan la columna a NULL) ni exigir un id en cada fila histórica.
-- time_record es append-only: ADD COLUMN / CREATE INDEX son DDL y no disparan el trigger
-- anti-mutación (BEFORE UPDATE/DELETE por fila). Las filas previas quedan con NULL -> el
-- payload del hash las incluye condicionalmente, así verify_chain sigue validándolas.
-- Idempotente.

ALTER TABLE time_record
    ADD COLUMN IF NOT EXISTS client_event_id text;

CREATE UNIQUE INDEX IF NOT EXISTS time_record_client_event_id_key
    ON time_record (client_event_id)
    WHERE client_event_id IS NOT NULL;
