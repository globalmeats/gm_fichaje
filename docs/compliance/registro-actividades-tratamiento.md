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
| **Destinatarios** | Internos: administración/supervisión, RLT. Externos: Inspección de Trabajo (acceso de solo lectura). Encargado del tratamiento: Supabase (alojamiento de BD, región UE). |
| **Transferencias internacionales** | **Ninguna fuera de la UE/EEE.** Región de despliegue y de Supabase verificada en arranque y deploy (`assert_eu_region`). |
| **Plazo de conservación** | **4 años** desde el registro (art. 34.9 ET). No se borran registros más recientes. Ciclo documentado en `retention_log`. |
| **Ámbito (excepciones)** | Personal de **alta dirección** excluido del registro obligatorio (art. 2.1.a ET). En **ETT/subcontrata**, la obligación de registro recae en la empresa **usuaria/principal** (`worker.relation_type`, `usuaria_id`). |

## 3. Medidas técnicas y organizativas (art. 32 RGPD)

- **Cifrado en reposo** de la geolocalización (Fernet, clave fuera de la BD).
- **Cifrado en tránsito**: TLS obligatorio contra la base de datos.
- **Residencia en la UE**: verificación automática de región (deploy + Supabase).
- **Integridad/inmutabilidad**: append-only + hash SHA-256 encadenado + trigger
  anti-mutación + verificación de cadena; correcciones versionadas y selladas.
- **Control de acceso**: roles, aislamiento por trabajador, RLS, autenticación por
  PIN bcrypt con lockout y alertas de auditoría.
- **Minimización**: solo los datos imprescindibles; geo solo con consentimiento.
- **Derecho a la desconexión digital**: alertas `off_hours` fuera de la ventana laboral.

## 4. Ejercicio de derechos

- Acceso y portabilidad: portal del trabajador + exportación PDF/CSV.
- Rectificación: corrección append-only con motivo y autor (auditada).
- Supresión: limitada por el deber legal de conservación (4 años).
- Reclamación ante la AEPD: derecho del interesado.
