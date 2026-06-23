---
name: rgpd-dataguard
description: >
  Protección de datos, control de accesos y retención para el sistema de fichajes de
  Global Meats. USA ESTA SKILL siempre que implementes Row Level Security (RLS), roles y
  permisos, cifrado, geolocalización, consentimiento, retención de 4 años, derechos del
  trabajador, o residencia de datos en la UE. Consúltala antes de diseñar políticas de
  acceso, exportaciones, o cualquier tratamiento de datos personales. Cubre REQ-03, 04,
  05, 10, 17, 18, 20, 21, 23, 24.
---

# RGPD / Data Guard

Base jurídica del tratamiento: **cumplimiento de obligación legal (art. 6.1.c RGPD)** —
no se requiere consentimiento del trabajador para el registro en sí. La intimidad se
rige por el **art. 20 bis ET** y la **LO 3/2018 (LOPDGDD)**.

## 1. Roles y control de acceso (REQ-24)

| Rol | Puede ver | Puede hacer |
|-----|-----------|-------------|
| `empleado` | Solo SUS registros | Fichar, consultar/descargar lo suyo |
| `supervisor` | Registros de su equipo | Consultar, marcar incidencias, corregir (con motivo) |
| `admin` | Global | Gestión, configuración de políticas |
| `rlt` | Registros globales (lectura) | Consultar (representación legal) |
| `inspeccion` | Global (lectura) | Consultar/descargar (acceso remoto Inspección) |

- `empleado` y `inspeccion`/`rlt` son **solo lectura** sobre registros.
- Ningún rol puede mutar `time_record` (lo impide `audit-trail`).

## 2. Row Level Security (REQ-05, 24)

RLS **activado en toda tabla con datos personales**. Política base por trabajador:

```sql
ALTER TABLE time_record ENABLE ROW LEVEL SECURITY;

-- Empleado: solo sus propias filas
CREATE POLICY empleado_own ON time_record FOR SELECT
  USING ( auth.uid() = worker_id );

-- Inspección / RLT / admin: lectura global (rol en el JWT)
CREATE POLICY oversight_read ON time_record FOR SELECT
  USING ( (auth.jwt() ->> 'role') IN ('inspeccion','rlt','admin') );
```

- Verificar SIEMPRE con un test: rol `empleado` consultando a otro → 0 filas.
- No confiar en filtros de la capa de aplicación; RLS es la última línea.

## 3. Identificación sin biometría (REQ-05, 21)

Los trabajadores **no tienen correo electrónico**. Se identifican con **código de
empleado + PIN**. Dos funciones separadas, nunca el PIN solo:

- **Código de empleado** = *identificación inequívoca* (REQ-05). Público, no secreto.
- **PIN de 6 dígitos** (mínimo) = *autenticación*, hash **bcrypt**. Nunca en claro ni
  en logs. Sin huella ni reconocimiento facial (biometría prohibida por AEPD/reforma).

Por qué código + PIN y nunca "solo PIN": con PINs cortos hay colisiones casi seguras en
una plantilla mediana y el sistema no podría saber inequívocamente quién ficha, lo que
rompería REQ-05. El código resuelve la identidad; el PIN solo confirma que es esa persona.

**Rate-limiting imprescindible**: con PIN de 6 dígitos el espacio es pequeño, así que el
bloqueo temporal **por código de empleado** tras N intentos fallidos es lo único que
cierra la fuerza bruta. Cada bloqueo → `audit_alert` (REQ-25).

**Sesión por puesto (ordenador de uso personal)**: cada equipo lo usa siempre la misma
persona, así que se puede **recordar el código de empleado** en ese navegador (cookie no
sensible) para que la persona solo teclee su PIN. El **PIN nunca se recuerda**. La sesión
autenticada caduca en plazo corto (uso personal ≠ puesto físicamente seguro: otra persona
podría sentarse). Tras fichar, volver a pantalla neutra.

**Reset de PIN (sin email no hay auto-recuperación)**: proceso **administrativo**. Un
`supervisor`/`admin` regenera el PIN y lo entrega. Es modificación de credenciales de un
tercero → acción sensible que se registra en el audit trail (autor, momento, destinatario;
nunca el PIN en claro).

## 4. Geolocalización (REQ-20)

- **Solo puntual**, en el instante del fichaje. Prohibido el tracking continuo.
- Requiere `geo_consent` por trabajador (flag explícito, informado).
- Coordenada **cifrada** en reposo. Se capta solo si la modalidad lo justifica (móvil).
- Documentar finalidad y minimización en el registro de actividades de tratamiento.

## 5. Cifrado y residencia (REQ-23)

- TLS obligatorio en tránsito; columnas sensibles cifradas en reposo.
- Datos personales en **servidores de la UE** (o país con protección equivalente).
  Verificar región de Supabase y Railway antes de cada deploy (script de deploy debe
  fallar si la región no es UE).

## 6. Retención y conservación (REQ-03)

- Conservar registros **4 años**. Ningún job borra registros con antigüedad < 4 años.
- El borrado tras 4 años es opcional y debe quedar **logueado** (qué, cuándo, por quién).
- La conservación se extiende a los registros diarios (no se exige totalización en
  periodos más largos, salvo lo propio de horas extra).

## 7. Acceso del trabajador e Inspección (REQ-04, 17, 18)

- Portal del trabajador: consulta y descarga de SUS registros 24/7 (REQ-18).
- Inspección: acceso de solo lectura, global, con export remoto (REQ-17). "A disposición"
  = accesible de inmediato cuando se solicite (cumple ya el deber VIGENTE del 34.9).
- No es obligatorio entregar copia del registro diario individual (salvo pacto); sí el
  resumen de horas extra del art. 35.5.

## 8. Derechos y documentación (REQ-10)

- DPIA / evaluación de impacto cuando proceda; registro de actividades de tratamiento.
- Minimización: no recoger datos personales no necesarios para el registro de jornada.
- Atender derechos del interesado (acceso, rectificación vía corrección versionada, etc.)
  sin romper la inmutabilidad del histórico (la rectificación es append, no borrado).

## Interacción

- Inmutabilidad y correcciones: `audit-trail`. Modelo: `fichaje-domain`. Mapa legal:
  `legal-compliance` (REQ-03,04,05,10 VIGENTES; el resto objetivo reforma).
