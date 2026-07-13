-- 0013_absence_document: justificante de asistencia adjunto a una ausencia (REQ-28).
-- Lo que se adjunta es el justificante de ASISTENCIA (acredita que se acudió a la cita),
-- que NO contiene diagnóstico. La app instruye explícitamente: subir solo justificantes de
-- asistencia, NUNCA partes/informes con diagnóstico (minimización, art. 5.1.c RGPD).
-- Aun así, acudir a un centro médico puede ser información sensible por asociación: el
-- documento se guarda CIFRADO en reposo (Fernet, capa de aplicación; la clave vive en el
-- entorno, no en la BD) y permanece en la BD de la UE (cubierto por el backup).
-- Acceso restringido por rol (self + oversight). Tabla MUTABLE (se puede reemplazar/borrar
-- un adjunto erróneo). Idempotente.

CREATE TABLE IF NOT EXISTS absence_document (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Relación 1:N (una ausencia puede tener varios justificantes).
    absence_id        uuid NOT NULL REFERENCES absence(id) ON DELETE CASCADE,
    filename          text NOT NULL,
    content_type      text NOT NULL,
    byte_size         integer NOT NULL,
    -- Justificante CIFRADO (Fernet). Nunca se almacena en claro.
    content_encrypted bytea NOT NULL,
    uploaded_by       uuid REFERENCES worker(id),
    uploaded_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT absence_document_content_type_check
        CHECK (content_type IN ('application/pdf','image/jpeg','image/png')),
    CONSTRAINT absence_document_size_check
        CHECK (byte_size > 0 AND byte_size <= 5242880)  -- <= 5 MB
);

CREATE INDEX IF NOT EXISTS absence_document_absence_idx ON absence_document (absence_id);

-- RLS (defensa en profundidad, REQ-24): el documento solo es visible para el dueño de la
-- ausencia y para la supervisión; se resuelve por join con absence.
ALTER TABLE absence_document ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS absence_document_self_select ON absence_document;
CREATE POLICY absence_document_self_select ON absence_document FOR SELECT
    USING ( EXISTS (
        SELECT 1 FROM absence a
        WHERE a.id = absence_document.absence_id AND a.worker_id = auth.uid()
    ) );

DROP POLICY IF EXISTS absence_document_oversight_select ON absence_document;
CREATE POLICY absence_document_oversight_select ON absence_document FOR SELECT
    USING ( (auth.jwt() ->> 'role') IN ('supervisor','admin','rlt','inspeccion') );
