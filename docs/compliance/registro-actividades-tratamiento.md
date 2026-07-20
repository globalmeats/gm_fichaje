# Registro de Actividades de Tratamiento (RAT)

Art. 30 RGPD / art. 31 LOPDGDD. Actividad de tratamiento del sistema de **registro
de jornada** de Global Meats S.L.U. REQ-10 (🟢 VIGENTE).

> No es asesoramiento jurídico. Documento vivo; actualizar ante cambios del tratamiento.

## 1. Responsable del tratamiento

- **Responsable**: Global Meats S.L.U.
- **Contacto / DPO**: (a completar por la empresa antes de producción).

## 2. Actividad de tratamiento: "Registro de jornada laboral"

| Campo | Detalle |
|---|---|
| **Fines** | Cumplir la obligación legal de registro diario de jornada (art. 34.9 ET) y de horas extraordinarias (art. 35.5 ET); puesta a disposición de trabajadores, RLT e Inspección de Trabajo. |
| **Base jurídica** | Cumplimiento de obligación legal — **art. 6.1.c RGPD** (art. 34.9 ET). Geolocalización accesoria: **consentimiento** — art. 6.1.a RGPD. |
| **Categorías de interesados** | Trabajadores por cuenta ajena de Global Meats. |
| **Categorías de datos** | Identificativos (nombre, apellidos, código de empleado); autenticación (hash de PIN); jornada (eventos, sellos temporales UTC, modalidad, desplazamientos, correcciones con autor y motivo); geolocalización **puntual** opcional (solo móvil + consentimiento). |
| **Categorías especiales** | Ninguna. Sin biometría. |
| **Destinatarios** | Internos: administración/supervisión, RLT. Externos: Inspección de Trabajo (acceso de solo lectura). **Encargados del tratamiento (art. 28 RGPD)**: ver §5. |
| **Transferencias internacionales** | **Ninguna fuera de la UE/EEE.** Región de despliegue y de Supabase verificada en arranque y deploy (`assert_eu_region`); el bucket de backups es de jurisdicción UE (verificado por `app/jobs/backup.py`). |
| **Plazo de conservación** | **4 años** desde el registro (art. 34.9 ET). No se borran registros más recientes. Ciclo documentado en `retention_log`. |
| **Ámbito (excepciones)** | Personal de **alta dirección** excluido del registro obligatorio (art. 2.1.a ET). En **ETT/subcontrata**, la obligación de registro recae en la empresa **usuaria/principal** (`worker.relation_type`, `usuaria_id`). |

## 2.bis Actividad de tratamiento: "Ausencias y justificantes" (REQ-28)

| Campo | Detalle |
|---|---|
| **Fines** | Gestionar vacaciones, bajas y permisos del trabajador y acreditar la justificación de la ausencia. |
| **Base jurídica** | Ejecución del contrato y cumplimiento de obligaciones laborales — **art. 6.1.b y 6.1.c RGPD**. |
| **Categorías de interesados** | Trabajadores por cuenta ajena de Global Meats. |
| **Categorías de datos** | Tipo de ausencia, subtipo de permiso, fechas/horas, estado, nota administrativa (sin dato clínico) y **justificante de asistencia** (documento cifrado). La `baja` se registra solo con fechas/estado, sin diagnóstico. |
| **Categorías especiales (art. 9 RGPD)** | **SÍ.** El tipo `baja` (incapacidad temporal) es **dato de salud** por el mero hecho de existir, aun sin diagnóstico. **Base del art. 9.2.b RGPD** (cumplimiento de obligaciones en materia de Derecho laboral y de la seguridad social). Minimización estricta: solo fechas/estado y justificante de **asistencia** (nunca diagnósticos), cifrado y con acceso restringido. |
| **Destinatarios** | Internos: administración/gestora (alta y gestión); el propio trabajador (consulta de lo suyo). Encargados (art. 28): ver §5. |
| **Transferencias internacionales** | **Ninguna fuera de la UE/EEE.** |
| **Plazo de conservación** | El necesario para acreditar la ausencia y sus efectos (retención del justificante por confirmar, ver `DEFERRED.md`). |
| **Alta** | Solo administración/gestora (roles admin/supervisor); el trabajador no da de alta ausencias. |

## 3. Medidas técnicas y organizativas (art. 32 RGPD)

- **Cifrado en reposo** de la geolocalización (Fernet, clave fuera de la BD).
- **Cifrado en tránsito**: TLS obligatorio contra la base de datos.
- **Residencia en la UE**: verificación automática de región (deploy + Supabase).
- **Integridad/inmutabilidad**: append-only + hash SHA-256 encadenado + trigger
  anti-mutación + verificación de cadena; correcciones versionadas y selladas.
- **Control de acceso** (doble barrera): (1) **Row Level Security (RLS) activa en la base de
  datos** (desde 2026-07-20) — la aplicación conecta con un rol NO superusuario y sin BYPASSRLS,
  e inyecta los claims del trabajador por sesión; las políticas de las tablas con datos
  personales (`time_record`, `record_correction`, `absence`, `absence_document`) solo dejan ver
  las filas propias del trabajador o, a roles de supervisión, el conjunto. (2) **Capa de
  aplicación**: comprobación self-vs-supervisión en cada endpoint. Más autenticación por PIN
  bcrypt con lockout, versión de token para revocación de sesión y alertas de auditoría. Las
  migraciones y tareas de sistema (backups) usan una conexión privilegiada separada.
- **Minimización**: solo los datos imprescindibles; geo solo con consentimiento; en ausencias,
  solo justificante de **asistencia** (nunca diagnósticos) y la `baja` sin dato clínico.
- **Cifrado del justificante**: el documento de ausencia se almacena cifrado (Fernet, clave
  fuera de la BD), con acceso restringido por rol y al propio trabajador.
- **Derecho a la desconexión digital**: alertas `off_hours` fuera de la ventana laboral.

## 4. Ejercicio de derechos

- Acceso y portabilidad: portal del trabajador + exportación PDF/CSV.
- Rectificación: corrección append-only con motivo y autor (auditada).
- Supresión: limitada por el deber legal de conservación (4 años).
- Reclamación ante la AEPD: derecho del interesado.

## 5. Encargados del tratamiento (art. 28 RGPD)

Todos procesan datos personales en la **UE/EEE**. Debe existir un **contrato de encargo (DPA)**
firmado con cada uno a nombre de Global Meats S.L.U.

| Encargado | Rol | Ubicación | DPA |
|---|---|---|---|
| **Supabase** | Alojamiento de la base de datos (PostgreSQL) | UE (`eu-west-1`, Irlanda) | Solicitado 16/07/2026; pendiente de confirmar/archivar |
| **Railway** | Hosting/cómputo de la aplicación (procesa los datos en memoria) | UE (`europe-west4`) | **Pendiente** de verificar y archivar |
| **Cloudflare** | Proxy/CDN delante de la app (ve IP y tráfico, incluidos PIN en tránsito) | UE | **Pendiente** (Fase 3 del go-live) |
| **Cloudflare R2** | Almacena los **backups cifrados** de toda la BD | UE (bucket con jurisdicción European Union) | **Pendiente**; los dumps viajan cifrados (Fernet) antes de salir de la app |

> Los backups a R2 contienen una copia de todas las categorías de datos (incluidas las del
> art. 9): van cifrados en origen con clave que vive solo en el entorno de la app, nunca en R2.
