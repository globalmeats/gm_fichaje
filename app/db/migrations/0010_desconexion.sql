-- 0010_desconexion: desconexión digital y desglose horario (REQ-26).
-- REQ-26: derecho a la desconexión digital. Se define una ventana laboral en time_policy
--         (desconexion_start..desconexion_end); un fichaje o acceso FUERA de esa ventana
--         genera una alerta `off_hours` (severity info) reutilizando audit_alert (REQ-25).
--         No bloquea: deja constancia para revisión, en línea con el deber de la empresa de
--         garantizar la desconexión sin impedir el trabajo puntual justificado.
-- Reutiliza la tabla audit_alert de 0006: solo se amplía el CHECK de alert_type.
-- time_policy es CONFIG MUTABLE (singleton): ALTER seguro, sin trigger. La ventana es
-- opcional (NULL = sin control de desconexión configurado).
-- Idempotente (ADD COLUMN IF NOT EXISTS + DROP/ADD CONSTRAINT).

-- ---- audit_alert: añade el tipo off_hours (REQ-26) ----
ALTER TABLE audit_alert DROP CONSTRAINT IF EXISTS audit_alert_type_check;
ALTER TABLE audit_alert ADD CONSTRAINT audit_alert_type_check
    CHECK (alert_type IN (
        'chain_broken','login_failed','account_locked','mutation_attempt',
        'anomalous_access','off_hours'
    ));

-- ---- time_policy: ventana de desconexión digital (REQ-26) ----
ALTER TABLE time_policy
    ADD COLUMN IF NOT EXISTS desconexion_start time;
ALTER TABLE time_policy
    ADD COLUMN IF NOT EXISTS desconexion_end time;
