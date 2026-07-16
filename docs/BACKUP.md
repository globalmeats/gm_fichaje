# Backup y restauración (plan Free de Supabase)

> Contexto: producción corre en Supabase plan Free, **sin backups gestionados**
> (decisión registrada en `DEFERRED.md`). Este job es la red de seguridad de la
> conservación de 4 años (REQ-03) y hace también de keep-alive del proyecto.

## Qué hace

`python -m app.jobs.backup` (cron diario en Railway, servicio dedicado):

1. Exporta los **datos** de todas las tablas (`COPY ... TO STDOUT` CSV). El **esquema**
   no se exporta: se reconstruye con las migraciones; el manifest guarda las versiones
   aplicadas y la restauración exige que coincidan.
2. Empaqueta (`tar.gz`) con un `manifest.json` (filas, columnas, SHA-256 por tabla,
   orden de restauración calculado del grafo de FKs).
3. **Cifra con Fernet** (`BACKUP_ENCRYPTION_KEY`) antes de salir del proceso.
4. Sube a **Cloudflare R2 con jurisdicción UE** (REQ-23; el job rechaza endpoints que
   no sean `*.eu.r2.cloudflarestorage.com`) y verifica el tamaño remoto.
5. Aplica retención: 30 diarios (`daily/`) + 12 mensuales (`monthly/`, copia del día 1).

## Variables de entorno (solo el servicio cron)

| Variable | Valor |
|---|---|
| `DATABASE_URL` | la misma del servicio web (Session pooler, `?ssl=require`) |
| `BACKUP_ENCRYPTION_KEY` | secreto largo aleatorio — **sin él los backups son irrecuperables: gestor de contraseñas obligatorio** |
| `R2_ENDPOINT` | `https://<account_id>.eu.r2.cloudflarestorage.com` |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | token R2 con Object Read & Write limitado al bucket |
| `R2_BUCKET` | `gm-fichaje-backups` (creado con jurisdicción **European Union**) |
| `BACKUP_KEEP_DAILY` / `BACKUP_KEEP_MONTHLY` | opcionales (30 / 12) |

## Restauración

Sobre una BD **recién migrada** al mismo punto que el backup:

```bash
python -m app.db.migrate
python -m app.jobs.restore r2:daily/gm_fichaje_<STAMP>.tar.gz.enc   # o ruta local
```

Guardas: verifica SHA-256 por tabla y que `schema_migrations` coincida exactamente;
se niega si el destino tiene datos (`--force` trunca antes: **solo simulacros en el
Postgres local** — regla del proyecto: nada de pruebas contra producción). Tras el
COPY recoloca las secuencias serial/identity.

## Simulacro de restauración (recomendado trimestral)

```bash
docker start fichajes-db-test   # Postgres local de test (puerto 55432)
export DATABASE_URL=postgresql+asyncpg://fichajes:localdev@localhost:55432/fichajes
python -m app.db.migrate
python -m app.jobs.restore <último backup descargado> --force
pytest -q app/tests/test_backup_restore.py
```

## RGPD

Los dumps contienen datos personales: R2 (Cloudflare) actúa como encargado —
pendiente de reflejar en el RAT junto con el alta de Cloudflare como proxy (Fase 5
del go-live). Jurisdicción UE del bucket verificada por el propio job en cada run.
