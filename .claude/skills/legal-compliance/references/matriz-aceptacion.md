# Matriz de criterios de aceptación

Para cada REQ: qué prueba demuestra que está cumplido. Úsalo al escribir tests y al
cerrar tareas. `[V]` = vigente, `[R]` = reforma.

## Bloque dominio / contenido

- **REQ-01 [V]** — Test: crear jornada → existe `check_in` y `check_out` con timestamp
  UTC; sin `check_out` la jornada queda "abierta" y se marca como incidencia.
- **REQ-07 [V]** — Test: insertar `break_start`/`break_end`; el tiempo efectivo =
  (fin−inicio) − pausas computables. Verificar pausa no computable no resta.
- **REQ-08 [V]** — Test: jornada que supera la ordinaria genera horas extra; el resumen
  del periodo totaliza y exporta; flag `compensacion ∈ {abono, descanso}`.
- **REQ-09 [V]** — Test: evento de desplazamiento con `puesta_a_disposicion=true` no
  computa como trabajo efectivo pero queda registrado y trazable.
- **REQ-12 [V]** — Test: 5 jornadas de 9h + jornadas cortas que cuadran el mes a la
  ordinaria → NO se marcan horas extra. Cambiar el cómputo a semanal y verificar.
- **REQ-06 [V]** — Test: cada modalidad (`presencial|teletrabajo|movil`) acepta fichaje
  y aplica sus reglas (p.ej. geo solo en móvil/teletrabajo si configurado).

## Bloque inmutabilidad / auditoría

- **REQ-02 [V] / REQ-15 [R]** — Test: intentar `UPDATE`/`DELETE` sobre `time_records`
  falla (trigger/permiso). Cada registro tiene `hash` y `prev_hash`; recomputar la
  cadena detecta cualquier alteración.
- **REQ-16 [R]** — Test: corregir un fichaje crea una fila nueva `correction` que
  referencia el original, con `author_id`, `reason` (obligatorio) y timestamp. El
  original permanece consultable.
- **REQ-25 [R]** — Test: N accesos fallidos o lectura masiva fuera de patrón generan
  una entrada en `audit_alerts`.

## Bloque RGPD / acceso

- **REQ-05 [V] / REQ-21 [R]** — Test: login por `worker_id`+PIN bcrypt; no existe campo
  ni endpoint biométrico. PIN nunca se almacena en claro.
- **REQ-24 [R]** — Test: con rol `empleado`, una query a registros de otro trabajador
  devuelve 0 filas (RLS). Con rol `inspeccion`, acceso de solo lectura global.
- **REQ-04 [V] / REQ-17 [R] / REQ-18 [R]** — Test: endpoint export disponible para
  inspección (global, solo lectura) y para trabajador (solo lo suyo). Devuelve PDF/CSV.
- **REQ-19 [R]** — Test: el export incluye identificación, detalle diario, registro de
  correcciones y totalización del periodo.
- **REQ-20 [R]** — Test: geo solo se captura en el evento de fichaje; no hay job de
  tracking continuo; requiere flag de consentimiento por trabajador; coordenada cifrada.
- **REQ-23 [R]** — Test: TLS forzado; columnas sensibles cifradas en reposo; check de
  región UE en el script de deploy (falla si la región no es UE).
- **REQ-10 [V]** — Documental: existe DPIA y registro de actividad de tratamiento.

## Bloque operación / conservación

- **REQ-03 [V]** — Test: job de retención intenta borrar un registro de hace 1 año →
  rechazado; uno de hace 4 años + 1 día → elegible (con log).
- **REQ-22 [R]** — Test: fichaje en modo offline se encola y, al recuperar red, se
  sincroniza sin duplicar ni perder, conservando el timestamp real del fichaje.
- **REQ-13 [V]** — Test: cambiar parámetros de pausa/flex por configuración (no código)
  altera el cómputo sin redeploy.
- **REQ-11 [V]** — Test: marcar a un trabajador como alta dirección lo excluye del
  registro obligatorio; relación ETT asigna obligación a empresa usuaria.
- **REQ-14 [R]** — Documental: no hay ruta de importación de Excel como registro de
  verdad; la app es el único origen.
- **REQ-26 [R]** — Test: el desglose clasifica automáticamente ordinarias/extra/
  complementarias; módulo de desconexión digital marca avisos fuera de horario.
