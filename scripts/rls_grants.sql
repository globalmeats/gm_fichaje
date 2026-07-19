-- SEC-04a: permisos mínimos del rol de aplicación NO superusuario para operar bajo RLS.
--
-- Ejecutar como propietario/superusuario de la BD, DESPUÉS de aplicar las migraciones
-- (el rol necesita permisos sobre las tablas y funciones ya creadas).
--
-- El rol y su contraseña se gestionan por entorno (NUNCA en el repo). Crea el rol antes:
--   CREATE ROLE app_rw LOGIN PASSWORD '<secreto>' NOSUPERUSER NOBYPASSRLS;
-- En Supabase: SQL Editor como postgres. En local de test: psql como el superusuario.
--
-- Idempotente: los GRANT se pueden reaplicar sin efecto adverso.

GRANT USAGE ON SCHEMA public, app TO app_rw;

-- Datos: la app lee/inserta/actualiza; NUNCA borra (inmutabilidad) — no se concede DELETE.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_rw;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_rw;

-- Funciones de contexto de la petición (app.uid()/app.role()/app.claims()).
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO app_rw;

-- Objetos futuros (si se añaden tablas/secuencias en migraciones posteriores).
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_rw;

-- La RLS de las tablas de datos (time_record, absence, record_correction, absence_document)
-- gatea las filas por los claims del JWT que la app inyecta por sesión. `worker` no tiene RLS
-- (tabla de autenticación gestionada por la app). Este rol NO es superusuario ni BYPASSRLS,
-- así que las políticas se evalúan de verdad.
