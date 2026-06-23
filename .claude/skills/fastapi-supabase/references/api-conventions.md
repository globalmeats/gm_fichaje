# Convenciones de API

## Endpoints núcleo (orientativo)

```
POST /fichaje/event          # crea un time_record (pasa por audit/chain)
GET  /fichaje/today          # estado de la jornada del trabajador (reconstruido)
GET  /me/records?from&to     # registros propios (REQ-18)
POST /corrections            # crea record_correction con reason (REQ-16)
GET  /export/csv?worker&from&to   # export verificable (REQ-04,17,19)
GET  /export/pdf?worker&from&to   # idem en PDF
GET  /inspection/records     # acceso global solo lectura (rol inspeccion, REQ-17)
GET  /reports/overtime?period     # resumen horas extra (REQ-08)
```

## Reglas
- Todos `async def`. Errores con códigos claros: 409 para transición inválida de jornada,
  403 cuando RLS/rol no autoriza, 422 validación Pydantic.
- Export siempre disponible (REQ-04). Incluye id trabajador, detalle diario, correcciones
  y totalización (REQ-19).
- Nunca devolver datos de otros trabajadores a un rol `empleado` (RLS + check en API).
- Paginación por cursor para listados largos; rango temporal obligatorio en consultas.
- Respuestas con timestamps en UTC ISO-8601; el cliente formatea a zona local.
