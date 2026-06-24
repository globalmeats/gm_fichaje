-- 0005_time_policy: política de cómputo de tiempo, configurable en runtime.
-- REQ-13: parámetros de convenio ajustables sin tocar código (editable vía endpoint admin).
-- REQ-12: computation_period define la ventana de cómputo (día/semana/mes) para horas extra.
-- A diferencia de time_record, esta tabla es CONFIG MUTABLE (no append-only): no lleva
-- trigger anti-mutación. Es un singleton (id smallint = 1) para no arrastrar multi-tenancy
-- que no necesitamos (una sola empresa).
-- Idempotente.

CREATE TABLE IF NOT EXISTS time_policy (
    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),          -- singleton global
    pause_computable_default  boolean NOT NULL DEFAULT true,   -- p.ej. comida = se descuenta
    computation_period        text NOT NULL DEFAULT 'monthly'
        CHECK (computation_period IN ('daily','weekly','monthly')),
    ordinary_hours_per_period numeric NOT NULL DEFAULT 160,
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO time_policy (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
