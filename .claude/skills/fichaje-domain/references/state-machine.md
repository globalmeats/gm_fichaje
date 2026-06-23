# Máquina de estados — detalle

Estados: `IDLE`, `ABIERTA`, `EN_PAUSA`, `EN_DESPLAZAMIENTO`.

| Estado actual | Evento | Estado siguiente | Validación |
|---|---|---|---|
| IDLE | check_in | ABIERTA | No puede haber otra jornada ABIERTA del mismo worker |
| ABIERTA | break_start | EN_PAUSA | — |
| ABIERTA | travel_start | EN_DESPLAZAMIENTO | — |
| ABIERTA | check_out | IDLE | Cierra jornada; calcula tiempo efectivo |
| EN_PAUSA | break_end | ABIERTA | Debe existir break_start previo abierto |
| EN_DESPLAZAMIENTO | travel_end | ABIERTA | Debe existir travel_start previo abierto |
| cualquiera | evento imposible | (rechazo) | Devolver 409 + registrar incidencia |

## Reglas

- Transiciones se derivan del histórico append-only, NO de un campo de estado mutable.
  El estado se reconstruye leyendo los `time_record` del día.
- Jornada ABIERTA al final del día (sin check_out) → incidencia, nunca autocompletar.
- Doble check_in sin check_out → rechazar y marcar incidencia.
- Los eventos llevan `occurred_at` del servidor; un cliente no puede falsear la hora.
  En offline, se guarda la hora real del fichaje y se valida ventana razonable al sync.
