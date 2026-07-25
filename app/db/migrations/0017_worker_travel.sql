-- REQ-01: desplazamiento activable por trabajador.
--
-- El evento de desplazamiento (trabajar fuera de la oficina durante la jornada, p. ej. ir a
-- una feria y volver — "puesta a disposición", art. 34.1 ET) NO es de uso diario: solo lo
-- necesitan quienes hacen ese tipo de salidas (David/Belén). Este flag decide si a un
-- trabajador se le ofrecen los botones de desplazamiento; se puede activar/desactivar en
-- ajustes. Por defecto desactivado.

ALTER TABLE worker ADD COLUMN IF NOT EXISTS travel_enabled boolean NOT NULL DEFAULT false;
