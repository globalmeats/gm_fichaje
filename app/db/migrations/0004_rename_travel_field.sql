-- 0004_rename_travel_field: renombra puesta_a_disposicion -> travel_computes.
-- REQ-09: desplazamientos. El nombre viejo usaba el término legal "puesta a disposición"
--         AL REVÉS: en el ET, el tiempo "a disposición" del empresario ES trabajo efectivo,
--         pero el campo marcaba el traslado que NO computa. Se renombra a un término neutro
--         y legible, INVIRTIENDO la polaridad:
--           travel_computes = true  -> ese desplazamiento SÍ computa (no se resta)
--           travel_computes = false -> NO computa (se resta del tiempo efectivo)
-- ALTER ... RENAME COLUMN / SET DEFAULT son DDL: no disparan el trigger anti-mutación
-- (BEFORE UPDATE/DELETE por fila). No hay eventos travel_* todavía, así que no hay valores
-- almacenados que invertir. El payload del hash no cambia de estructura -> verify_chain
-- sigue validando las cadenas previas.
-- Idempotente.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='time_record' AND column_name='puesta_a_disposicion') THEN
    ALTER TABLE time_record
      RENAME COLUMN puesta_a_disposicion TO travel_computes;
    -- Polaridad invertida: el default natural de "computa" es true.
    ALTER TABLE time_record ALTER COLUMN travel_computes SET DEFAULT true;
  END IF;
END $$;
