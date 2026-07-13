---
name: legal-compliance
description: >
  Matriz maestra de cumplimiento legal para el sistema de fichajes de Global Meats.
  USA ESTA SKILL SIEMPRE que la tarea implique decidir qué datos registrar, conservar,
  exportar o exponer; cualquier funcionalidad que toque jornada, pausas, horas extra,
  desplazamientos, acceso de Inspección, derechos del trabajador o conservación.
  Contiene cada requisito legal (vigente RDL 8/2019 art. 34.9/35.5 ET, y los anticipados
  de la reforma 2026) mapeado a su implementación técnica y a su criterio de aceptación.
  Consúltala antes de implementar cualquier endpoint, modelo o regla de negocio, aunque
  el usuario no mencione "ley" explícitamente.
---

# Legal Compliance — Registro de Jornada

Esta skill es la fuente de verdad del PROYECTO sobre qué exige la normativa. La fuente
de verdad LEGAL es la Guía oficial del Ministerio de Trabajo y el art. 34.9/35.5 ET
(ver `references/normativa-oficial.md`). No uses blogs comerciales como fuente.

## Cómo usar esta skill

1. Identifica qué requisito(s) toca tu tarea en la matriz de abajo.
2. Lee la fila completa: estado legal, qué implementar, criterio de aceptación.
3. Si es un requisito **VIGENTE**, es obligatorio y no negociable.
4. Si es **REFORMA 2026**, es objetivo de diseño: impleméntalo, pero NO afirmes que
   es obligación legal en vigor.
5. Para detalle profundo de un bloque, abre el reference correspondiente.

## Leyenda de estado

- 🟢 **VIGENTE**: exigible hoy (RDL 8/2019). Obligatorio.
- 🟡 **REFORMA**: anticipado por la reforma 2026, pendiente de BOE. Objetivo de diseño.

## Matriz de requisitos

| ID | Requisito | Estado | Qué implementar | Criterio de aceptación |
|----|-----------|--------|-----------------|------------------------|
| REQ-01 | Registro diario inicio/fin | 🟢 | Evento `check_in`/`check_out` por trabajador y día | Cada jornada tiene timestamp de inicio y fin verificables |
| REQ-02 | Información inmodificable | 🟢 | Append-only + hash encadenado (skill `audit-trail`) | No existe UPDATE/DELETE sobre `time_records` |
| REQ-03 | Conservación 4 años | 🟢 | Política de retención; ningún borrado < 4 años | Job de retención rechaza borrar registros recientes |
| REQ-04 | Disponibilidad inmediata | 🟢 | Endpoints consulta + export PDF/CSV siempre activos | Inspección/trabajador/RLT acceden on-demand |
| REQ-05 | Identificación inequívoca | 🟢 | `worker_id` + PIN bcrypt; sin fichajes compartidos | Cada registro asociado a un trabajador único |
| REQ-06 | Todas las modalidades | 🟢 | Presencial, teletrabajo, móvil, jornada partida | Tipos de modalidad soportados en el modelo |
| REQ-07 | Pausas / interrupciones | 🟢 | Eventos `break_start`/`break_end`, computables o no | Tiempo efectivo distinguible del intervalo bruto |
| REQ-08 | Horas extra (art. 35.5) | 🟢 | Cómputo diario + totalización periodo + resumen | Resumen exportable; flag abono/compensación |
| REQ-09 | Desplazamientos | 🟢 | Solo tiempo efectivo; marcar puesta a disposición | Intervalos separados y trazables |
| REQ-10 | RGPD/LOPDGDD | 🟢 | Base legal art.6.1.c; intimidad art.20bis ET | DPIA documentada; sin datos de más |
| REQ-11 | Excepciones de ámbito | 🟢 | Excluir alta dirección; ETT→usuaria; subcontrata | Configuración de exclusiones por tipo de relación |
| REQ-12 | Cómputo > diario (flex) | 🟢 | Globalizar jornada (p.ej. mensual) | Excesos diarios no marcados como extra si cuadra el mes |
| REQ-13 | Config. por convenio | 🟢 | Parámetros de pausas/flex configurables | Reglas ajustables sin tocar código |
| REQ-14 | Sistema 100% digital | 🟡 | Sin papel/Excel como soporte de verdad | Único origen de registro es la app |
| REQ-15 | Sellado temporal | 🟡 | Timestamp servidor UTC + hash criptográfico | Cada registro sellado e inmutable (skill `audit-trail`) |
| REQ-16 | Log de modificaciones | 🟡 | Versionado: original + corrección + autor + motivo | Toda corrección deja rastro con justificación |
| REQ-17 | Acceso remoto Inspección | 🟡 | Export/descarga remota con rol Inspección | Inspector descarga sin personarse |
| REQ-18 | Acceso permanente trabajador | 🟡 | Portal del trabajador a SUS registros | Consulta/descarga propia 24/7 |
| REQ-19 | Export verificable | 🟡 | PDF/CSV con id, detalle diario, mods, totales | Informe oficial generado on-demand |
| REQ-20 | Geolocalización puntual | 🟡 | Solo al fichar, con consentimiento, cifrada | Nunca rastreo continuo (skill `rgpd-dataguard`) |
| REQ-21 | Sin biometría | 🟡 | PIN/tarjeta, jamás huella/facial | No hay captura biométrica |
| REQ-22 | Funcionamiento offline | 🟡 | Cola local + sync al recuperar red | Fichaje offline se sincroniza sin pérdida |
| REQ-23 | Cifrado + datos en UE | 🟡 | TLS + cifrado en reposo; región UE | Verificación de región en deploy |
| REQ-24 | Control de accesos por rol | 🟡 | Roles admin/supervisor/empleado/RLT/inspección | RLS + permisos por rol (skill `rgpd-dataguard`) |
| REQ-25 | Alertas / auditoría | 🟡 | Detección de accesos/manipulación anómalos | Alertas automáticas registradas |
| REQ-26 | Desglose horas + desconexión | 🟡 | Ordinarias/extra/complementarias; desconexión digital | Clasificación automática de horas |
| REQ-27 | Tope anual de jornada (convenio) | 🟢 | Cómputo anual sobre 1760 h del convenio | Cómputo anual + alerta `annual_cap` |
| REQ-28 | Registro de ausencias | 🟡 | Vacaciones/bajas/permisos + justificante de asistencia | Tabla `absence` + balance + documento cifrado (minimización art. 9/5.1.c) |
| REQ-29 | Jornada flexible por trabajador | 🟢 | Jornada pactada por trabajador (subvención) | `weekly_hours`/`flexible_schedule` + cómputo > diario + informe |

## Referencias

- `references/normativa-oficial.md` — Extracto fiel de la Guía del Ministerio y art. ET.
- `references/matriz-aceptacion.md` — Criterios de aceptación detallados por REQ con
  ejemplos de test.
- `scripts/compliance_check.py` — Checklist ejecutable que valida que cada REQ tiene
  cobertura en el código (heurístico, no sustituye revisión humana ni legal).

## Aviso

Esta skill es soporte técnico, NO asesoramiento jurídico. Para validación legal
definitiva, contrastar con un laboralista y con el texto del BOE vigente.
