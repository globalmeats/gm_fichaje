-- SEC-04(a): RLS efectiva en runtime.
--
-- Hasta ahora las políticas referenciaban auth.uid()/auth.jwt() (stubs que devuelven NULL) y
-- la app conectaba como superusuario (bypassa RLS): la RLS era inerte. Esta migración:
--   1) Define funciones PROPIAS app.uid()/app.role() que leen los claims del JWT inyectados
--      por la app en el GUC `request.jwt.claims` (no dependemos del esquema auth.* de Supabase,
--      que usa el claim 'sub'; nosotros inyectamos 'worker_id' y 'role').
--   2) Reescribe las políticas de las tablas de DATOS para usar esas funciones y AÑADE las
--      políticas de ESCRITURA que faltaban (correcciones, ausencias, justificantes), sin las
--      cuales un rol restringido no podría operar.
--   3) `worker` es la tabla de AUTENTICACIÓN (se lee/actualiza ANTES de tener claims: login,
--      lockout): se gestiona a nivel de aplicación, por eso se DESACTIVA su RLS. El acceso a
--      `worker` desde la API sigue gateado por rol en la capa de aplicación.
--
-- La activación real requiere además que la app conecte con un rol NO superusuario y con los
-- claims inyectados (flag `rls_enforce` + `app_database_url`); con la conexión privilegiada
-- (por defecto) estas políticas quedan inertes y el comportamiento no cambia.

-- 1) Funciones de contexto de la petición.
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.claims() RETURNS jsonb
    LANGUAGE sql STABLE AS $$
        SELECT nullif(current_setting('request.jwt.claims', true), '')::jsonb
    $$;

CREATE OR REPLACE FUNCTION app.uid() RETURNS uuid
    LANGUAGE sql STABLE AS $$ SELECT (app.claims() ->> 'worker_id')::uuid $$;

CREATE OR REPLACE FUNCTION app.role() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT app.claims() ->> 'role' $$;

-- 2) worker: tabla de autenticación, gestionada por la aplicación -> sin RLS.
ALTER TABLE worker DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS worker_self_select ON worker;
DROP POLICY IF EXISTS worker_oversight_select ON worker;
DROP POLICY IF EXISTS worker_admin_insert ON worker;
DROP POLICY IF EXISTS worker_self_or_admin_update ON worker;

-- 3) time_record: lectura propia + supervisión; inserción propia (fichaje).
DROP POLICY IF EXISTS time_record_self_select ON time_record;
CREATE POLICY time_record_self_select ON time_record FOR SELECT
    USING ( app.uid() = worker_id );
DROP POLICY IF EXISTS time_record_oversight_select ON time_record;
CREATE POLICY time_record_oversight_select ON time_record FOR SELECT
    USING ( app.role() IN ('supervisor','admin','rlt','inspeccion') );
DROP POLICY IF EXISTS time_record_self_insert ON time_record;
CREATE POLICY time_record_self_insert ON time_record FOR INSERT
    WITH CHECK ( app.uid() = worker_id );

-- 4) record_correction: lectura propia + supervisión; inserción por admin/supervisor.
DROP POLICY IF EXISTS record_correction_self_select ON record_correction;
CREATE POLICY record_correction_self_select ON record_correction FOR SELECT
    USING ( app.uid() = worker_id );
DROP POLICY IF EXISTS record_correction_oversight_select ON record_correction;
CREATE POLICY record_correction_oversight_select ON record_correction FOR SELECT
    USING ( app.role() IN ('supervisor','admin','rlt','inspeccion') );
DROP POLICY IF EXISTS record_correction_write_insert ON record_correction;
CREATE POLICY record_correction_write_insert ON record_correction FOR INSERT
    WITH CHECK ( app.role() IN ('admin','supervisor') );

-- 5) absence: lectura propia + supervisión; alta y actualización por admin/supervisor.
DROP POLICY IF EXISTS absence_self_select ON absence;
CREATE POLICY absence_self_select ON absence FOR SELECT
    USING ( app.uid() = worker_id );
DROP POLICY IF EXISTS absence_oversight_select ON absence;
CREATE POLICY absence_oversight_select ON absence FOR SELECT
    USING ( app.role() IN ('supervisor','admin','rlt','inspeccion') );
DROP POLICY IF EXISTS absence_write_insert ON absence;
CREATE POLICY absence_write_insert ON absence FOR INSERT
    WITH CHECK ( app.role() IN ('admin','supervisor') );
DROP POLICY IF EXISTS absence_write_update ON absence;
CREATE POLICY absence_write_update ON absence FOR UPDATE
    USING ( app.role() IN ('admin','supervisor') );

-- 6) absence_document: lectura propia (vía la ausencia) + supervisión; alta por admin/supervisor.
DROP POLICY IF EXISTS absence_document_self_select ON absence_document;
CREATE POLICY absence_document_self_select ON absence_document FOR SELECT
    USING ( EXISTS (
        SELECT 1 FROM absence a
        WHERE a.id = absence_document.absence_id AND a.worker_id = app.uid()
    ) );
DROP POLICY IF EXISTS absence_document_oversight_select ON absence_document;
CREATE POLICY absence_document_oversight_select ON absence_document FOR SELECT
    USING ( app.role() IN ('supervisor','admin','rlt','inspeccion') );
DROP POLICY IF EXISTS absence_document_write_insert ON absence_document;
CREATE POLICY absence_document_write_insert ON absence_document FOR INSERT
    WITH CHECK ( app.role() IN ('admin','supervisor') );
