# Decisiones diferidas y deuda técnica conocida

Registro vivo de decisiones aplazadas. **Consultar al planificar cada nueva fase** para
reconsiderar los pendientes en el momento oportuno (ver `CLAUDE.md`). Una entrada por ítem.
Las tareas ya completadas se retiran de aquí (quedan en el historial de commits y en
`docs/AUDITORIA-2026-07.md`).

## Requiere decisión de convenio / laboralista / DPO

- **Validación legal de "puesta a disposición" / `travel_computes`** — el desplazamiento
  durante la jornada computa como trabajo (art. 34.1 ET); confirmar con laboralista los casos
  límite. El mecanismo (evento desplazamiento + flag `travel_enabled` por trabajador) ya existe.
- **Compensación de horas extra: abono vs descanso (art. 35 ET)** — `compensacion` está hoy en
  "pending"; falta resolver la política e incluirla en el export (CMP-03), y valorar un
  artefacto de "resumen entregado" (tope 80 h/año, art. 35.2).
- **¿Vacaciones/permisos descuentan del tope anual de 1760 h?** — hoy el tope se mide solo sobre
  tiempo efectivo trabajado; confirmar con el convenio si las ausencias lo reducen.
- **¿Las ausencias justificadas computan como tiempo trabajado?** — hoy el tiempo justificado no
  exige fichaje pero no se suma como trabajado; confirmar con convenio.
- **Vacaciones en jornada normal vs intensiva** — cuántos días corresponden en cada régimen;
  depende de definir la jornada intensiva de agosto (abajo).
- **Borrado tras los 4 años vs derecho de supresión (CMP-04)** — hoy nada se borra tras la
  retención (tensión con art. 5.1.e RGPD). Decisión de política con DPO y su encaje con la
  inmutabilidad (borrado físico controlado vs anonimización). Relacionado: FK
  `retention_log.worker_id` al implementar el borrado físico (probablemente `ON DELETE SET NULL`).

## Requisitos de la oficina aplazados (24/07/2026)

- **Horario estándar y jornadas (42 h/sem, agosto 30 h intensiva, 07–17 con 2 h de descanso)** —
  NO se modela por ahora; el control de horas es el **tope anual por empleado** (`annual_hours_cap`,
  ya implementado). Reconsiderar si hace falta un modelo de horario esperado.
- **Horario definido de las trabajadoras a tiempo parcial** — se les fija su tope anual por
  contrato (ya soportado); definir un "horario" queda aplazado (depende del punto anterior).
- **Notificar a quien no ha fichado (10 min tras inicio/salida)** — aplazado. Bloqueado por: (a)
  los trabajadores no tienen email (solo código+PIN), (b) depende del modelo de horario. Opción
  realista futura: aviso a la admin + panel "pendientes de fichar"; canal directo al trabajador
  exigiría teléfono + servicio de pago.
- **Festivos locales/municipales en el calendario** — los nacionales + Comunidad de Madrid salen
  automáticos (librería `holidays`); los 2 patronales del municipio cambian cada año y no vienen
  en la librería → si se quieren, definirlos en una pequeña config anual (falta el municipio).

## Producto / UX pendiente

- **Alerta de jornada/pausa abierta demasiado tiempo o que cruza la medianoche** — el caso de la
  pausa nocturna que dejó 1h8m efectivas; conviene avisar cuando una jornada/pausa lleva abierta
  > X horas. Recomendada como primera mejora (se repetirá con uso real).
- **Catálogo de subtipos de permiso configurable por convenio** — hoy `PERMISO_SUBTYPES` es
  constante en código.
- **Devengo/prorrateo de vacaciones por antigüedad y carryover entre años** — hoy el balance es
  derecho anual fijo menos lo disfrutado del año en curso.
- **Flag de pausa computable por evento** — distinguir comida vs otras pausas a nivel de evento;
  toca el sellado de `time_record` (hoy es política global).
- **Pulir formularios admin más densos** en el nuevo diseño (el rediseño dejó todo consistente;
  esto es refinamiento).

## Operación / infraestructura

- **Supabase plan Free — keep-alive anti-pausa** — el cron de backup diario genera actividad
  (hace de keep-alive). Vigilar las primeras semanas que el proyecto no se pausa. Reconsiderar
  Supabase Pro para eliminar el riesgo (y de paso los backups gestionados).
- **Reflejar destino/retención del backup en el RAT** — el RAT lista R2 como encargado; falta
  detallar la retención (30 diarios + 12 mensuales).
- **SEC-11: `--forwarded-allow-ips '*'`** — confía XFF de cualquier upstream (envenenamiento de
  logs). Se cierra en la Fase 3 (Cloudflare) con `TRUST_CF_CONNECTING_IP` y rangos del proxy.
- **Antivirus/escaneo y política de borrado del justificante** — los justificantes subidos no se
  escanean ni tienen política de borrado documentada.

## Seguridad diferida

- **BUG-05 (resto)** — se acotaron los escaneos O(N) del estado y del tope anual; el resumen del
  trabajador (`/summary`) y el export siguen cargando todo el histórico del trabajador (aceptable
  a la escala actual). Optimizar solo si crece el volumen.
