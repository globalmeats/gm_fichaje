-- SEC-06 (REQ-21): versión de token para revocación de sesiones.
--
-- El JWT lleva un claim `tv` que debe coincidir con worker.token_version en cada request.
-- Al incrementar esta columna (reset de PIN, bloqueo por fuerza bruta, cambio de rol o de
-- PIN) todos los JWT emitidos antes dejan de validar: logout efectivo del lado servidor.

ALTER TABLE worker ADD COLUMN IF NOT EXISTS token_version integer NOT NULL DEFAULT 0;
