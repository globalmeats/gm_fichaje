-- SEC-05 (REQ-02): la inmutabilidad append-only también frente a TRUNCATE.
--
-- Los triggers de 0003/0006 son BEFORE UPDATE OR DELETE FOR EACH ROW: no cubren TRUNCATE,
-- que no dispara triggers de fila y (al conectar la app como superusuario) tampoco lo frena
-- el REVOKE. Un TRUNCATE vaciaría el ledger saltándose la garantía de inmutabilidad. Estos
-- triggers a nivel de sentencia lo bloquean. Reutilizan prevent_mutation() (0003), que ignora
-- NEW/OLD y por tanto vale también para STATEMENT-level (TG_OP será 'TRUNCATE').
--
-- Nota: el restore (app/jobs/restore.py) desactiva estos triggers dentro de su transacción
-- vía `SET session_replication_role = 'replica'` para poder reconstruir la BD.

DROP TRIGGER IF EXISTS no_truncate_time_record ON time_record;
CREATE TRIGGER no_truncate_time_record
  BEFORE TRUNCATE ON time_record
  FOR EACH STATEMENT EXECUTE FUNCTION prevent_mutation();

DROP TRIGGER IF EXISTS no_truncate_record_correction ON record_correction;
CREATE TRIGGER no_truncate_record_correction
  BEFORE TRUNCATE ON record_correction
  FOR EACH STATEMENT EXECUTE FUNCTION prevent_mutation();
