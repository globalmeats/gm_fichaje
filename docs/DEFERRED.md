# Decisiones diferidas y deuda técnica conocida

Registro vivo de decisiones aplazadas. **Consultar al planificar cada nueva fase** para
reconsiderar los pendientes en el momento oportuno (ver `CLAUDE.md`). Una entrada por ítem.

- **Validación legal de "puesta a disposición" / `travel_computes` (Fase 2)** — la spec resta el
  tiempo de desplazamiento que no computa; confirmar con abogado laboralista contra el ET.
- **Compensación de horas extra, abono vs descanso (Fase 3)** — hoy marcado "pending"; el registro
  inmutable/sellado de esa decisión queda diferido a una fase posterior.
- ~~**REQ-26 horas complementarias (Fase 3)** — diferido hasta modelar `relation_type` (contratos a
  tiempo parcial) en el trabajador.~~ **RESUELTO (Fase 6)**: `worker.relation_type` incluye
  `tiempo_parcial` y `app/domain/hours.py::classify_overtime` etiqueta el exceso como
  `complementarias` (no extra) para ese tipo de relación; expuesto en el export (`complementarias_min`).
- ~~**Cifrado del campo `geo` al corregirlo (Fase 4)** — confirmar que corregir `geo` no salta el
  cifrado; revisar en Fase 6 cuando entre la geolocalización real.~~ **RESUELTO (Fase 6)**:
  `app/api/corrections.py` cifra el `corrected_value` con `encrypt_geo` antes de sellarlo y
  almacenarlo cuando `field == 'geo'`; el export lo descifra para mostrarlo.
- **FK `retention_log.worker_id` (Fase 5)** — al implementar el borrado físico de `time_record`,
  asegurar que el FK no bloquea el borrado ni deja el log huérfano (probablemente
  `ON DELETE SET NULL`); además es un punto RGPD (derecho de supresión vs deber de conservación
  4 años).
- **Calendario laboral de festivos (Fase 8)** — `leave_days`/cómputo anual cuentan L–V sin
  descontar festivos nacionales/autonómicos; falta un calendario laboral configurable.
- **¿Vacaciones/permisos descuentan del tope anual de 1760 h? (Fase 8)** — hoy el tope se mide
  solo sobre tiempo efectivo trabajado; confirmar con el convenio si las ausencias reducen el tope.
- **¿Las ausencias justificadas computan como tiempo trabajado? (Fase 8)** — operativamente el
  tiempo justificado no exige fichaje (no es anómalo), pero no se suma como trabajado; confirmar
  con convenio.
- **Flag de pausa computable por evento (Fase 8)** — distinguir comida vs otras pausas a nivel de
  evento; toca el sellado de `time_record`, por eso se difiere (hoy es política global).
- **Devengo/prorrateo de vacaciones por antigüedad y carryover entre años (Fase 8)** — hoy el
  balance es derecho anual fijo (`annual_vacation_days`) menos lo disfrutado del año en curso.
- **Catálogo de subtipos de permiso configurable por convenio (Fase 8)** — hoy `PERMISO_SUBTYPES`
  es constante en código; debería poder editarse como config del convenio.
- **Antivirus/escaneo y política de retención/borrado del justificante (Fase 8)** — los
  justificantes subidos no se escanean ni tienen política de borrado documentada.
