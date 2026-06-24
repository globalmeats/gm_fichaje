---
name: fichaje-domain
description: >
  Modelo de dominio del sistema de fichajes de Global Meats: tipos de evento, máquina de
  estados de la jornada, pausas computables/no computables, horas extra y su totalización,
  desplazamientos con puesta a disposición, jornada flexible con cómputo en periodos
  superiores al día, y modalidades (presencial/teletrabajo/móvil). USA ESTA SKILL al
  diseñar o modificar entidades, esquemas de base de datos, reglas de cálculo de tiempo
  efectivo, o cualquier lógica de negocio sobre la jornada. Consúltala antes de crear
  tablas o endpoints relacionados con eventos de fichaje.
---

# Fichaje Domain Model

Cubre los requisitos REQ-01, 06, 07, 08, 09, 12 (ver skill `legal-compliance`). La
inmutabilidad de estos registros la gobierna la skill `audit-trail`; aquí solo el modelo.

## Entidades núcleo

### `worker`
- `id` (uuid), `employee_code` (público, identificación inequívoca — REQ-05),
  `code_norm` (minúsculas, **UNIQUE** — garantiza unicidad del código),
  `full_name`, `pin_hash` (bcrypt, 6 dígitos mín.), `pin_temporary` (bool, fuerza
  cambio en primer login), `role`,
  `relation_type` (`ordinaria|alta_direccion|tiempo_parcial|ett|subcontrata`),
  `modalidad_default` (`presencial|teletrabajo|movil`), `active`.
- Alta por administrador; código y PIN inicial generados (ver skill
  `onboarding-empleados`). Login = `employee_code` + PIN (no hay email).
- `alta_direccion` → excluido del registro obligatorio (REQ-11).
- `ett` → la obligación de registro es de la empresa usuaria; modelar `usuaria_id`.

### `time_record` (append-only — ver `audit-trail`)
Un evento atómico de fichaje. NUNCA se modifica ni borra.
- `id`, `worker_id`, `event_type`, `occurred_at` (UTC, sellado por servidor),
  `modalidad`, `source` (`web|kiosk|mobile|offline_sync`),
  `geo` (nullable, cifrado, solo si consentimiento — REQ-20),
  `travel_computes` (bool, para desplazamientos — REQ-09; `true` = ese tramo computa
  como tiempo efectivo, `false` = no computa),
  `hash`, `prev_hash`, `created_at`.

### `event_type` (enum)
```
check_in        # inicio jornada
check_out       # fin jornada
break_start     # inicio pausa
break_end       # fin pausa
travel_start    # inicio desplazamiento
travel_end      # fin desplazamiento
```

### `record_correction` (REQ-16)
Corrección de un registro sin tocar el original.
- `id`, `original_record_id`, `corrected_value`, `reason` (obligatorio),
  `author_id`, `created_at`. El original sigue siendo la verdad histórica.

### `time_policy` (REQ-13, configurable)
- `pause_computable_default`, `computation_period` (`daily|weekly|monthly`),
  `ordinary_hours_per_period`, reglas de convenio. Editable sin redeploy.

## Máquina de estados de la jornada

```
        check_in
  ─────────────────▶ ABIERTA
 IDLE                  │  break_start ▶ EN_PAUSA ──break_end──▶ ABIERTA
  ▲                    │  travel_start ▶ EN_DESPLAZAMIENTO ─travel_end─▶ ABIERTA
  │   check_out        │
  └────────────────────┘
```
- Una jornada sin `check_out` queda **ABIERTA** → marcar incidencia (no autocompletar
  con datos inventados; la inmutabilidad lo prohíbe).
- Validar secuencias imposibles (`break_end` sin `break_start`) en la capa de dominio.

## Cálculo de tiempo efectivo (REQ-07)

```
tiempo_bruto      = check_out − check_in
pausas_computables= Σ (break_end − break_start) marcadas como computables
desplaz_no_efect  = Σ intervalos travel con travel_computes = false
tiempo_efectivo   = tiempo_bruto − pausas_computables − desplaz_no_efect
```
- Pausa **no computable** (descanso retribuido) NO se resta.
- Regla de oro: nunca asumir que todo el intervalo bruto es trabajo efectivo. La
  presunción legal se evita registrando pausas (ver `legal-compliance`).

## Horas extra (REQ-08)

- Se calculan **por periodo de cómputo**, no por día (ver flexibilidad abajo).
- Al cierre del periodo de abono: totalizar, generar resumen, marcar
  `compensacion ∈ {abono, descanso}`. El resumen es exportable (art. 35.5).

## Jornada flexible / cómputo supra-diario (REQ-12)

- `computation_period` define la ventana (p.ej. `monthly`).
- Un exceso en un día NO es hora extra si, sumado el periodo, se cumple la jornada
  ordinaria pactada. Solo el excedente del **periodo** es hora extra.
- Implementar el cálculo de extras como agregación sobre la ventana, no por fila diaria.

## Desplazamientos (REQ-09)

- `travel_start`/`travel_end` con el flag `travel_computes` para separar el tiempo efectivo
  del mero traslado. `travel_computes=false` → ese tramo se registra (trazabilidad) pero no
  computa como trabajo; puede compensarse vía dietas (fuera del alcance del registro de
  jornada). `travel_computes=true` → computa como tiempo efectivo.
- **Nota terminológica:** evitamos el nombre `puesta_a_disposicion`. En el ET, el tiempo de
  *puesta a disposición* del empresario ES tiempo de trabajo efectivo, justo lo contrario de
  lo que marcaba aquel campo. `travel_computes` expresa la semántica sin usar el término
  legal al revés.

## Modalidades (REQ-06)

- `presencial`: típicamente kiosk/web; geo no exigible.
- `teletrabajo`: web/móvil; autogestión válida; geo no necesaria.
- `movil`: móvil; geo puntual recomendable (solo al fichar, con consentimiento).

## Detalle adicional

- `references/state-machine.md` — Transiciones completas y validaciones.
- `references/calculo-horas.md` — Pseudocódigo del agregador de horas por periodo.
