# RLS en runtime (SEC-04a) — estado y activación

> **ACTIVA EN PRODUCCIÓN desde 2026-07-20.** La app web conecta como el rol `app_rw`
> (no superusuario) con `RLS_ENFORCE=true`. Higiene completada (2026-07-21): contraseña de
> `app_rw` rotada y `SUPABASE_REGION` alineada a eu-west-1. Lo que sigue documenta el diseño y
> el procedimiento (para replicar en otro entorno o auditar).

## Qué hay implementado

La Row Level Security es **defensa en profundidad real**, construida y probada, **detrás de un
flag** (`RLS_ENFORCE`, por defecto **OFF**). Con el flag OFF el comportamiento es idéntico al
histórico (la app conecta como el rol privilegiado y la RLS queda inerte). Con el flag ON:

- La **app** (api/web) conecta con un rol **NO superusuario** (`app_database_url`), así que las
  políticas RLS se evalúan. Migraciones, seed y jobs (retention/backup/restore) usan la conexión
  **privilegiada** (`database_url`), fuera de RLS (tareas de sistema).
- Tras autenticar, la app inyecta los claims del JWT en la sesión con
  `set_config('request.jwt.claims', …, is_local=false)` (persiste a los commits de mitad de
  request; `get_db` lo limpia al abrir cada sesión para evitar fugas entre peticiones del pool).
- `app.uid()` / `app.role()` (migración `0016`) leen ese GUC. Las políticas de `time_record`,
  `record_correction`, `absence`, `absence_document` gatean por trabajador (propio) o rol de
  supervisión. `worker` es la tabla de autenticación (se usa antes de tener claims: login,
  lockout) y va **sin RLS**, gestionada por la capa de aplicación.

**Verificado**: la suite completa (246) pasa en **ambos modos**; y `test_rls_enforcement.py`
prueba a nivel de BD que un empleado no ve los registros de otro (deny-by-default sin claims,
supervisión ve todo).

## Activar en producción (pasos)

1. **Crear el rol** en Supabase (SQL Editor como `postgres`):
   ```sql
   CREATE ROLE app_rw LOGIN PASSWORD '<secreto-fuerte>' NOSUPERUSER NOBYPASSRLS;
   ```
   Guarda el secreto en el gestor.
2. **Aplicar migraciones** (ya lo hace el arranque de Railway) y luego **conceder permisos**:
   ejecuta `scripts/rls_grants.sql` como `postgres`.
3. **Variables** del servicio web en Railway:
   - `RLS_ENFORCE=true`
   - `APP_DATABASE_URL=postgresql+asyncpg://app_rw:<secreto>@<host pooler>:5432/postgres?ssl=require`
   - `DATABASE_URL` se mantiene con el rol privilegiado (migraciones/seed/jobs).
   El servicio **cron de backup** conserva solo `DATABASE_URL` (privilegiado); no necesita las
   variables de RLS.
4. **Desplegar** y verificar: login, fichaje, correcciones, ausencias, panel admin, y que un
   empleado no accede a datos de otro (404).

## Validación local (rol restringido)

```bash
docker exec -i fichajes-db-test psql -U fichajes -d fichajes -c \
  "CREATE ROLE app_rw LOGIN PASSWORD 'app_rw_pw' NOSUPERUSER NOBYPASSRLS;"
# aplicar migraciones y luego:
docker exec -i fichajes-db-test psql -U fichajes -d fichajes -f scripts/rls_grants.sql
DATABASE_URL=postgresql+asyncpg://fichajes:localdev@localhost:55432/fichajes \
APP_DATABASE_URL=postgresql+asyncpg://app_rw:app_rw_pw@localhost:55432/fichajes \
RLS_ENFORCE=true DB_REQUIRE_TLS=false pytest -q
```

## Notas

- Al activar, el acceso cruzado devuelve **404** (la RLS oculta la existencia) en vez de 403 —
  más seguro (no filtra existencia). Los tests aceptan ambos.
- La DPIA/RAT deben actualizarse cuando la RLS pase a estar ACTIVA en producción (hoy dicen que
  el control efectivo es la capa de aplicación con la RLS pendiente de activar).
