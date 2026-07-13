-- 0012_absence: ausencias (vacaciones, bajas y permisos retribuidos).
-- REQ-28: registro de ausencias. Marcar un día como vacaciones/permiso justifica que NO se
--         fiche ese tiempo (no es una ausencia anómala ni un fichaje faltante). Cubre:
--           vacaciones -> días de descanso retribuido (art. 38 ET).
--           baja       -> incapacidad temporal: SOLO fechas + estado, sin dato clínico
--                         (el parte de baja/alta lo gestiona la Seguridad Social/mutua).
--           permiso    -> permiso retribuido (art. 37.3 ET / convenio) con subtipo (cita
--                         médica, acompañamiento a familiar, mudanza, fallecimiento, ingreso
--                         hospitalario, deber inexcusable, matrimonio, lactancia...). Puede ser
--                         de día(s) completo(s) o por horas (start_time/end_time).
-- El alta la hace SOLO admin/gestora (created_by); el trabajador solo consulta lo suyo.
-- absence es CONFIG/HR MUTABLE (se puede cancelar/editar): sin trigger anti-mutación.
-- subtype se valida en la app (PERMISO_SUBTYPES) y NO con CHECK porque el catálogo varía
-- por convenio. Idempotente.

CREATE TABLE IF NOT EXISTS absence (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Trabajador ausente. FK real (worker sí existe en este esquema).
    worker_id    uuid NOT NULL REFERENCES worker(id),
    absence_type text NOT NULL,
    -- Subtipo del permiso retribuido (solo relevante si absence_type='permiso').
    subtype      text,
    start_date   date NOT NULL,
    end_date     date NOT NULL,
    -- Ausencia por horas (p.ej. cita médica). NULL/NULL = día(s) completo(s). Si van
    -- informados, start_date debe = end_date (ausencia de unas horas dentro de un día).
    start_time   time,
    end_time     time,
    status       text NOT NULL DEFAULT 'aprobada',
    -- Justificación: la marca el admin cuando adjunta y verifica el justificante de asistencia.
    justified    boolean NOT NULL DEFAULT false,
    verified_by  uuid REFERENCES worker(id),
    -- Nota administrativa; NUNCA dato clínico/diagnóstico (RGPD, minimización).
    note         text,
    created_by   uuid REFERENCES worker(id),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT absence_type_check
        CHECK (absence_type IN ('vacaciones','baja','permiso')),
    CONSTRAINT absence_status_check
        CHECK (status IN ('pendiente','aprobada','rechazada','cancelada')),
    CONSTRAINT absence_date_order_check
        CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS absence_worker_idx ON absence (worker_id);
CREATE INDEX IF NOT EXISTS absence_dates_idx ON absence (start_date, end_date);

-- RLS (defensa en profundidad, REQ-24): el trabajador ve SUS ausencias; la supervisión todas.
ALTER TABLE absence ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS absence_self_select ON absence;
CREATE POLICY absence_self_select ON absence FOR SELECT
    USING ( auth.uid() = worker_id );

DROP POLICY IF EXISTS absence_oversight_select ON absence;
CREATE POLICY absence_oversight_select ON absence FOR SELECT
    USING ( (auth.jwt() ->> 'role') IN ('supervisor','admin','rlt','inspeccion') );
