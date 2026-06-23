---
name: frontend-fichaje
description: >
  Convenciones de frontend para la app de fichajes de Global Meats: HTML server-rendered
  con Jinja2 servido por FastAPI, islas de interactividad con Alpine.js y htmx, sin paso
  de build de JavaScript. USA ESTA SKILL al crear o modificar pantallas (login código+PIN,
  fichar, mis registros, panel admin/export), el cronómetro de jornada, o la red de
  seguridad offline ligera. El fichaje se hace desde el ordenador de escritorio de cada
  trabajador (uso personal, red de oficina estable). Consúltala antes de escribir
  plantillas o JS de interfaz. Cubre la parte de UI de REQ-01,04,18,22.
---

# Frontend — Jinja2 + Alpine/htmx

**Contexto de uso**: cada trabajador ficha desde el **ordenador de su puesto** (uso
personal, navegador de escritorio, red de oficina estable). No es móvil ni kiosko
compartido. Esto simplifica el offline y el manejo de sesión.

**Decisión de stack**: HTML renderizado por el servidor (Jinja2 desde FastAPI) + islas
de interactividad con **Alpine.js** (~15 KB, vía `<script>`, sin build) y **htmx** para
intercambios con el servidor sin recarga. **Sin pipeline de build de JS** → no reintroduce
el fallo de build conocido y mantiene un único stack (Python sirve todo).

## Por qué no una SPA

Pocas pantallas, red estable, prioridad en fiabilidad del fichaje. Una SPA (Svelte/Vue +
Vite) añadiría un paso de build y superficie de fallo en CI sin beneficio real aquí. Si en
el futuro el panel de informes crece mucho, se reevalúa solo esa parte.

## Pantallas

| Pantalla | Render | Interactividad |
|----------|--------|----------------|
| Login | Jinja2 | Alpine: validación de PIN, foco; código recordado |
| Fichar | Jinja2 | Alpine: cronómetro de jornada; htmx: enviar evento |
| Mis registros | Jinja2 | htmx: filtros por rango; enlace a export (REQ-18) |
| Admin / export | Jinja2 | htmx: tablas, descarga PDF/CSV (REQ-04,19); reset PIN |

## Login (código + PIN)

- Dos campos: **código de empleado** (recordado en el navegador, cookie no sensible) y
  **PIN de 6 dígitos** (nunca recordado). Ver `rgpd-dataguard`/`fastapi-supabase`.
- **Primer login con PIN temporal**: si el trabajador tiene `pin_temporary = true`,
  el login lleva **obligatoriamente** a la pantalla de cambio de PIN; no puede fichar
  hasta cambiarlo (ver skill `onboarding-empleados`). Al guardar el nuevo PIN →
  `pin_temporary = false` → pantalla de fichar.
- Tras login normal → pantalla de fichar. Sesión de caducidad corta; al cerrar/expirar,
  volver a login con el código precargado pero el PIN vacío.
- Mostrar bloqueo temporal claro tras N intentos (rate-limit por código).

## Pantalla de cambio de PIN (primer login / reset)

- Pide nuevo PIN dos veces (confirmación); 6 dígitos; rechaza triviales y el PIN temporal.
- Aviso de que el PIN es personal e intransferible. Tras guardar, va a fichar.

## Pantalla de fichar

- Estado de jornada reconstruido por el servidor (ABIERTA/EN_PAUSA/…); el front solo lo
  refleja. No calcular el estado en el cliente.
- Botones según estado: check_in / break_start / break_end / travel_* / check_out.
- **Cronómetro** con Alpine (solo visual; la hora válida la sella el servidor — REQ-15).
- Enviar evento con htmx (`POST /fichaje/event`); refrescar el estado con la respuesta.
- Tras fichar, volver a pantalla neutra (equipo personal, pero sesión corta).

## Offline (red de seguridad ligera — REQ-22)

En escritorio de oficina la red rara vez cae, así que **no** se monta Service Worker +
IndexedDB completo. Basta:

- Si el `POST` del evento falla por red, **encolar en memoria/localStorage** el evento con
  su **hora real de fichaje** y mostrar "pendiente de sincronizar".
- Reintentar al recuperar conexión; el servidor valida una ventana de tolerancia y sella.
- Nunca duplicar: usar una clave de idempotencia por evento encolado.

## Reglas de UI

- Accesibilidad básica: foco, teclado, etiquetas. Trabajadores sin perfil técnico.
- Nada de exponer datos de otros trabajadores en una pantalla de empleado (RLS + API).
- Timestamps que muestra el front en zona local, pero el dato válido es UTC del servidor.
- Mensajes de error claros y en español (jornada ya abierta, transición inválida, bloqueo).

## Dependencias

- Alpine.js y htmx por `<script>` (CDN con SRI o servidos como estáticos). Sin npm/bundler.
- Jinja2 ya viene con el stack FastAPI.
