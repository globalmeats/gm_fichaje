-- REQ-28 + SEC-04a: políticas RLS para el flujo de vacaciones y el calendario compartido.
--
-- Con la RLS activa (rol app_rw), las políticas de `absence` eran self-select + oversight-select
-- e insert/update solo para admin/supervisor. Eso rompía dos flujos nuevos:
--   1) El CALENDARIO lo ve todo el mundo y muestra las vacaciones APROBADAS de TODOS. Un empleado
--      solo veía las suyas. -> política que hace públicas (dentro de la empresa) las vacaciones
--      aprobadas. Las bajas/permisos (datos de salud/sensibles) siguen restringidas.
--   2) El trabajador SOLICITA sus propias vacaciones (INSERT status 'pendiente') y puede
--      CANCELAR su solicitud pendiente (UPDATE a 'cancelada'). -> políticas self acotadas.

-- 1) Lectura pública (intraempresa) de vacaciones aprobadas (para el calendario).
DROP POLICY IF EXISTS absence_vacaciones_public_select ON absence;
CREATE POLICY absence_vacaciones_public_select ON absence FOR SELECT
    USING ( absence_type = 'vacaciones' AND status = 'aprobada' );

-- 2a) El trabajador crea SU solicitud de vacaciones (siempre pendiente; no puede autoaprobarse).
DROP POLICY IF EXISTS absence_self_request_insert ON absence;
CREATE POLICY absence_self_request_insert ON absence FOR INSERT
    WITH CHECK (
        app.uid() = worker_id
        AND absence_type = 'vacaciones'
        AND status = 'pendiente'
    );

-- 2b) El trabajador cancela SU propia vacación (solo puede dejarla en pendiente/cancelada,
--     nunca aprobarla/rechazarla — eso es de administración).
DROP POLICY IF EXISTS absence_self_cancel_update ON absence;
CREATE POLICY absence_self_cancel_update ON absence FOR UPDATE
    USING ( app.uid() = worker_id AND absence_type = 'vacaciones' )
    WITH CHECK ( app.uid() = worker_id AND status IN ('pendiente', 'cancelada') );
