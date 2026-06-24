# Cálculo de horas por periodo — pseudocódigo

```python
def horas_periodo(worker_id, periodo, policy):
    registros = leer_time_records(worker_id, periodo)        # append-only
    jornadas  = reconstruir_jornadas(registros)              # via state machine
    efectivo_total = 0
    for j in jornadas:
        bruto = j.check_out - j.check_in
        pausas_comp = sum(p.dur for p in j.pausas if p.computable)
        # travel_computes=false -> ese desplazamiento NO computa -> se resta.
        traslado_no_efect = sum(t.dur for t in j.desplaz if not t.travel_computes)
        efectivo_total += bruto - pausas_comp - traslado_no_efect

    ordinaria = policy.ordinary_hours_per_period
    extra = max(0, efectivo_total - ordinaria)               # REQ-12: por periodo
    return {
        "efectivo": efectivo_total,
        "ordinarias": min(efectivo_total, ordinaria),
        "extra": extra,
    }
```

## Notas
- `extra` se calcula sobre la VENTANA (`policy.computation_period`), no por día (REQ-12).
- El resumen del periodo (REQ-08) añade `compensacion` por cada bloque de extra:
  `abono` o `descanso`, confirmado por el trabajador.
- Clasificación ordinarias/extra/complementarias (REQ-26): complementarias aplican a
  contratos a tiempo parcial; tratarlas con su propia regla de `time_policy`.
