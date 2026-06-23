---
name: onboarding-empleados
description: >
  Alta de trabajadores en la plataforma de fichajes de Global Meats: generación del código
  de empleado a partir del nombre con desambiguación sin colisiones, generación del PIN
  inicial aleatorio mostrado una sola vez, y cambio de PIN obligatorio en el primer login.
  USA ESTA SKILL al implementar el alta de empleados por el administrador, la generación o
  validación de employee_code, el flujo de PIN temporal, o cualquier lógica que dependa de
  la unicidad del código. El código de empleado es la identificación inequívoca (REQ-05),
  así que su unicidad es crítica. Consúltala antes de tocar el alta o la generación de
  credenciales. Se apoya en rgpd-dataguard (auth) y audit-trail (registro de la acción).
---

# Onboarding de empleados

El **administrador** da de alta a cada trabajador. La plataforma genera el **código de
empleado** (a partir del nombre) y un **PIN inicial aleatorio**. El código es la
identificación inequívoca de la que depende todo el cumplimiento (REQ-05): su **unicidad
es crítica y se garantiza en base de datos**, no solo en código.

## 1. Generación del código de empleado

### Normalización (siempre primero)
- Quitar acentos / pasar a ASCII (José → Jose, Peña → Pena).
- Quedarse con **primer nombre + primer apellido** (no hay segundo apellido en juego).
- Eliminar espacios internos y caracteres no alfabéticos.
- **No distingue mayúsculas**: la unicidad y el login se comparan sobre la forma
  **normalizada en minúsculas** (`code_norm`). El código visible se guarda en CamelCase
  (`PeGa`) solo por legibilidad.

### Escalado determinista (misma regla para todos)
Tomar N letras del nombre + N del apellido, subiendo N hasta encontrar hueco:

```
Nivel 1: 2+2  -> "PeGa"      (Pepe Garcia)
Nivel 2: 3+3  -> "PepGar"    (si "pega" ya existe)
Nivel 3: 4+4  -> "PepeGarc"
...hasta agotar letras del nombre/apellido más corto.
Comodín final: sufijo numérico incremental -> "PeGa2", "PeGa3", ...
```

Ejemplo del caso real: "Pepe Garcia" → `PeGa`. "Penelope Garza" colisiona en `pega` →
sube a nivel 2 → `PenGar`. Una tercera colisión que agotara letras caería al sufijo
numérico. **Nunca se queda sin salida.**

### Unicidad garantizada en BD (imprescindible)
- `employee_code` (o mejor, una columna `code_norm` en minúsculas) lleva **constraint
  UNIQUE** en Postgres.
- La generación ocurre **dentro de una transacción con reintento**: se intenta insertar;
  si la BD rechaza por duplicado, se sube de nivel y se reintenta. El chequeo en Python
  ("¿existe ya?") NO basta: dos altas casi simultáneas podrían pasar el chequeo a la vez;
  solo la restricción UNIQUE evita el código duplicado. Ver pseudocódigo en
  `references/codigo-pin.md`.

## 2. Generación del PIN inicial

- **6 dígitos**, solo números, con generador **criptográficamente seguro** (`secrets`,
  nunca `random`).
- Evitar PINs triviales: `000000`, `123456`, repeticiones, el propio código, fechas obvias.
- Se almacena **solo el hash bcrypt**. El PIN en claro existe **una única vez**, en la
  respuesta del alta, para que el administrador lo entregue a la persona.
- Marcar el PIN como **temporal** (`pin_temporary = true`).

## 3. Entrega y primer login

- El PIN inicial se **muestra una sola vez** al administrador (aviso explícito: no se podrá
  recuperar después; si se pierde, hay que regenerarlo). El administrador lo transmite a
  la persona.
- En el **primer login**, `employee_code` + PIN temporal **lleva obligatoriamente a la
  pantalla de cambio de PIN** (no se puede fichar hasta cambiarlo). Al cambiarlo,
  `pin_temporary = false`. Ver flujo de UI en la skill `frontend-fichaje`.
- El nuevo PIN lo elige el trabajador (6 dígitos, mismas reglas anti-trivial), se guarda
  como hash bcrypt.

## 4. Trazabilidad de la acción (audit-trail)

Tanto el alta como cualquier **reset de PIN** posterior (proceso administrativo) se
registran: autor (admin/supervisor), momento, trabajador afectado. **Nunca se loguea el
PIN en claro ni el hash.** El reset regenera un PIN temporal y vuelve a forzar el cambio.

## 5. Casos límite a contemplar

- Nombre o apellido muy cortos (1 letra): el escalado se topa antes; pasar al sufijo
  numérico cuando no haya más letras.
- Nombres compuestos ("José Luis"): tomar el primer token como nombre tras normalizar
  (decisión por defecto; documentar si Global Meats prefiere otra).
- Bajas y reincorporaciones: no reutilizar un `code_norm` de un trabajador dado de baja
  mientras sus registros estén en conservación (4 años) para no romper la trazabilidad.

## Referencias
- `references/codigo-pin.md` — Pseudocódigo de generación de código (con reintento
  transaccional) y de PIN, más casos de prueba.
