-- 0008_worker_scope: excepciones de ámbito (REQ-11) y consentimiento de geo (REQ-20).
-- REQ-11: no todos los trabajadores generan obligación de registro de jornada para Global
--         Meats. relation_type distingue:
--           ordinaria      -> trabajador propio con jornada registrable (caso normal).
--           alta_direccion -> excluido del registro obligatorio (art. 2.1.a ET / RDL 8/2019).
--           tiempo_parcial -> registrable; su exceso son horas COMPLEMENTARIAS (REQ-26).
--           ett            -> cedido por ETT; la obligación recae en la empresa usuaria.
--           subcontrata    -> trabajador de contrata; obligación de su propia empresa.
--         usuaria_id apunta a la empresa usuaria/principal cuando el obligado no somos
--         nosotros (informativo; no es FK porque la usuaria no está en `worker`).
-- REQ-20: geo_consent registra el consentimiento informado para captar geolocalización
--         PUNTUAL en el instante del fichaje (nunca rastreo continuo). Sin consentimiento,
--         la coordenada no se almacena (minimización).
-- worker NO es append-only (es dato de cuenta, mutable): ALTER seguro, sin trigger.
-- Idempotente (ADD COLUMN IF NOT EXISTS + DROP/ADD CONSTRAINT).

ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS relation_type text NOT NULL DEFAULT 'ordinaria';
ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS usuaria_id uuid;
ALTER TABLE worker
    ADD COLUMN IF NOT EXISTS geo_consent boolean NOT NULL DEFAULT false;

ALTER TABLE worker DROP CONSTRAINT IF EXISTS worker_relation_type_check;
ALTER TABLE worker ADD CONSTRAINT worker_relation_type_check
    CHECK (relation_type IN
        ('ordinaria','alta_direccion','tiempo_parcial','ett','subcontrata'));
