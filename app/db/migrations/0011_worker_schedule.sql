-- 0011_worker_schedule: jornada flexible por trabajador y tope anual de jornada.
-- REQ-29: la jornada pactada y el horario flexible son POR TRABAJADOR (no global). Se añaden
--         columnas a worker que, cuando son NULL, caen al default global de time_policy
--         (fallback). flexible_schedule marca a quien tiene horario flexible (clave para la
--         subvención: hay que poder acreditarlo y reportarlo).
-- REQ-27: tope anual de jornada del convenio (1760 h). Default global en time_policy; un
--         trabajador puede tener su propio tope (p.ej. prorrateo a tiempo parcial) en worker.
--         Al superarlo (o acercarse) se emite una alerta annual_cap (reutiliza audit_alert).
-- worker y time_policy son CONFIG MUTABLE: ALTER seguro, sin trigger anti-mutación.
-- Idempotente (ADD COLUMN IF NOT EXISTS + DROP/ADD CONSTRAINT).

-- ---- worker: jornada por trabajador (NULL = usa el default global de time_policy) ----
ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS weekly_hours numeric;
ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS annual_hours_cap numeric;
ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS flexible_schedule boolean NOT NULL DEFAULT false;

-- ---- time_policy: defaults globales del convenio (REQ-27/29) ----
ALTER TABLE time_policy
    ADD COLUMN IF NOT EXISTS annual_hours_cap numeric NOT NULL DEFAULT 1760;
ALTER TABLE time_policy
    ADD COLUMN IF NOT EXISTS annual_vacation_days numeric NOT NULL DEFAULT 22;

-- ---- audit_alert: añade el tipo annual_cap (REQ-27) ----
ALTER TABLE audit_alert DROP CONSTRAINT IF EXISTS audit_alert_type_check;
ALTER TABLE audit_alert ADD CONSTRAINT audit_alert_type_check
    CHECK (alert_type IN (
        'chain_broken','login_failed','account_locked','mutation_attempt',
        'anomalous_access','off_hours','annual_cap'
    ));
