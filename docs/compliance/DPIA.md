# DPIA — Evaluación de Impacto relativa a la Protección de Datos

Sistema de **registro de jornada (control horario)** de Global Meats S.L.U.
(`fichajes.globalmeats.es`). REQ-10 (🟢 VIGENTE).

> No es asesoramiento jurídico. Documento técnico de cumplimiento; validar con
> laboralista/DPO antes de producción. Se mantiene vivo: revisar ante cada cambio
> que afecte a datos personales.

## 1. Necesidad y proporcionalidad de la DPIA

El tratamiento implica el control sistemático de la actividad laboral de los
trabajadores y, opcionalmente, datos de geolocalización. Aunque la plantilla es
reducida (≈5 personas), se realiza esta DPIA por prudencia (art. 35 RGPD) dado que
hay monitorización de la jornada y posible tratamiento de ubicación.

## 2. Descripción del tratamiento

- **Responsable**: Global Meats S.L.U.
- **Finalidad**: cumplir la obligación legal de registro diario de jornada
  (art. 34.9 ET / RDL 8/2019) y de horas extraordinarias (art. 35.5 ET), y
  poner los registros a disposición de los trabajadores, sus representantes y la
  Inspección de Trabajo.
- **Interesados**: trabajadores por cuenta ajena de Global Meats.
- **Categorías de datos**:
  - Identificativos: nombre, apellidos, código de empleado.
  - Autenticación: hash bcrypt del PIN (nunca el PIN en claro).
  - Jornada: tipo de evento, sello temporal (UTC del servidor), modalidad,
    desplazamientos, correcciones con autor y motivo.
  - **Geolocalización puntual** (opcional): coordenada del **instante** del
    fichaje, solo en modalidad móvil y **con consentimiento** del trabajador.
- **No se tratan** datos de categorías especiales. **No hay biometría**
  (prohibida por AEPD/reforma). Sin perfilado ni decisiones automatizadas.

## 3. Base jurídica (art. 6 RGPD)

- El registro de jornada se ampara en el **cumplimiento de una obligación legal**
  del responsable: **art. 6.1.c RGPD** en relación con el art. 34.9 ET. No requiere
  el consentimiento del trabajador para el registro en sí.
- La **geolocalización** es accesoria y NO imprescindible para el registro; se trata
  sobre la base del **consentimiento** informado (art. 6.1.a), revocable, y se limita
  al instante del fichaje (jamás rastreo continuo).

## 4. Principio de minimización (art. 5.1.c)

- `worker` solo almacena lo imprescindible para identificar y autenticar; sin email,
  sin biometría, sin datos no necesarios.
- La geo solo se almacena si hay **consentimiento** (`worker.geo_consent`) **y** la
  modalidad es **móvil**; en cualquier otro caso la coordenada se descarta y no se
  persiste (`app/api/fichaje.py::_geo_to_store`).
- No hay seguimiento continuo: solo el punto del evento, nunca un histórico de
  posiciones.

## 5. Medidas técnicas y organizativas

- **Inmutabilidad y sellado** (REQ-02/15): `time_record` append-only con hash SHA-256
  encadenado por trabajador; trigger anti-mutación + REVOKE en BD. Correcciones
  versionadas (`record_correction`), nunca edición in-place, con motivo y autor.
- **Cifrado en reposo** de la geo (REQ-20/23): cifrado a nivel de aplicación con
  Fernet (AES-128-CBC + HMAC, autenticado); la clave vive en variable de entorno,
  **fuera de la base de datos** (`app/core/crypto.py`). Un volcado de Postgres no
  expone coordenadas. El sellado encadena el *ciphertext*: manipularlo rompe el hash.
- **Cifrado en tránsito** (REQ-23): conexión a Postgres con TLS (`sslmode=require`);
  `scripts/check_region.py` falla el despliegue si no se fuerza TLS.
- **Residencia en la UE** (REQ-23): `assert_eu_region()` valida región de deploy y
  Supabase contra allowlist UE/EEE; el arranque y el despliegue **fallan** si no es UE.
  Sin transferencias internacionales.
- **Control de acceso** (REQ-24): aislamiento por trabajador en capa de aplicación;
  roles de supervisión (supervisor/admin/rlt/inspeccion) para acceso global de solo
  lectura; RLS escrita en las tablas con datos personales.
- **Autenticación** (REQ-05/21): código de empleado único + PIN bcrypt; lockout
  anti fuerza bruta; alertas de auditoría (`audit_alert`).
- **Desconexión digital** (REQ-26): los accesos/fichajes fuera de la ventana laboral
  configurada generan una alerta `off_hours` para revisión, sin impedir el trabajo.

## 6. Conservación (REQ-03)

- Los registros se conservan **4 años** (art. 34.9 ET). Ningún proceso borra
  registros con antigüedad inferior. `retention_log` documenta el ciclo de vida.

## 7. Derechos de los interesados

- **Acceso**: portal del trabajador (`GET /me/records`) 24/7 a sus propios registros,
  y exportación verificable PDF/CSV (REQ-04/18).
- **Rectificación**: vía corrección **append-only** con motivo y autor (no se altera
  el original; se deja constancia auditada).
- **Información**: esta DPIA y el registro de actividades de tratamiento (RAT).
- La **supresión** está limitada por el deber legal de conservación (4 años).

## 8. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Acceso no autorizado a registros ajenos | Aislamiento por trabajador + roles + RLS |
| Manipulación de registros | Append-only + hash encadenado + trigger + verificación |
| Exposición de geolocalización | Cifrado en reposo (clave fuera de BD) + minimización + consentimiento |
| Fuga por transferencia fuera de UE | Verificación de región UE en arranque y deploy |
| Interceptación en tránsito | TLS obligatorio a la BD |
| Fuerza bruta sobre PIN | Hash bcrypt + lockout + alertas |
| Exposición de datos de salud por el justificante | Solo justificante de **asistencia** (no diagnósticos); cifrado en reposo; acceso mínimo por rol |
| Inferencia de salud por asociación (acudir a centro médico) | Minimización; la `baja` se registra solo con fechas/estado; acceso restringido a self + supervisión |

## 8.bis Tratamiento de ausencias y justificantes (REQ-28)

El alta de ausencias (vacaciones, bajas y permisos) la realiza solo administración/gestora.
Medidas y límites específicos:

1. **Solo justificantes de asistencia.** Se admite únicamente el documento que acredita
   *que se acudió* a la cita (justificante de asistencia). **Nunca** partes, informes ni
   documentos con diagnóstico o causa clínica (minimización, art. 5.1.c RGPD).
2. **Documento cifrado.** El justificante se almacena **cifrado** (Fernet, clave fuera de la BD)
   en servidores de la UE, con acceso restringido por rol y al propio trabajador.
3. **La `baja` se registra solo con fechas y estado**, sin dato clínico alguno.
4. **Base jurídica y conservación.** Obligación legal/relación contractual (art. 6.1.b/c RGPD);
   el justificante se conserva el tiempo necesario para acreditar la ausencia (retención por
   confirmar, ver `DEFERRED.md`).
5. **Sensibilidad por asociación.** "Asistir a un centro médico" puede ser información sensible
   por asociación; por eso el acceso es el **mínimo necesario** (self + roles de supervisión).

## 9. Conclusión

Con las medidas descritas, el riesgo residual para los derechos y libertades de los
interesados se considera **bajo**. No se aprecia necesidad de consulta previa a la
AEPD (art. 36 RGPD). Revisar esta evaluación ante cualquier cambio sustancial del
tratamiento (p. ej. nuevas categorías de datos o nuevas finalidades).
