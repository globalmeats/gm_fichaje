# Tarea — UI responsive en todos los dispositivos (solo CSS/diseño)

> **Pendiente.** El rediseño "Documento de origen" (`docs/UI-REDISENO.md`, ya implementado en
> `app/web/static/app.css`) dejó la base estilada pero **no es plenamente responsive**: en móvil
> y tablet varias pantallas desbordan horizontalmente. Esta tarea lo corrige. **Solo CSS y
> ediciones presentacionales de plantilla; NO cambia el comportamiento de la app.**

## Contexto y diagnóstico (estado 2026-07-19)

Front SSR con Jinja2 + Alpine/htmx (skill `frontend-fichaje`); estilos en
`app/web/static/app.css`; fuentes self-hosted en `app/web/static/fonts/`. Problemas detectados:

1. **Tablas anchas que desbordan** (causa principal). No hay contenedor con scroll ni estrategia
   móvil. Columnas por tabla:
   - `_registros.html` — ~7 columnas (registros del trabajador + correcciones).
   - `mis_ausencias.html` — ~9 columnas.
   - `admin/horas.html` — ~8 columnas (horas extra / tope anual).
   - `admin/alertas.html` — ~7 columnas.
   - `_estado.html` — tabla de "tiempo efectivo" de ~6 columnas.
   A <600px estas tablas se comprimen ilegibles o empujan el ancho de la página (scroll
   horizontal de todo el body).
2. **Un solo breakpoint** (`@media max-width:560px`) y sin tratamiento de **tablet** (~600–900px).
3. **Sin `overflow-x`** en ningún contenedor: nada evita que el `<body>` scrollee en horizontal.
4. **Cabecera**: el `nav` (5 enlaces en mono) puede envolver de forma pobre en pantallas
   estrechas; revisar el wrap y el espaciado.
5. **Formularios**: las filas con `display:flex` inline (filtros de fecha en `mis_registros`,
   ausencias por horas) deben apilar limpio en móvil (hoy dependen de `flex-wrap` sin QA móvil).

## Alcance

PERMITIDO (y solo esto):
- Modificar `app/web/static/app.css` (media queries, contenedores responsive, utilidades).
- Ediciones **presentacionales** en plantillas: envolver tablas en un contenedor de scroll,
  añadir clases, `data-label` para el patrón "tabla→tarjeta" en móvil. Añadir clases junto a las
  existentes, **nunca** renombrar/eliminar ids, names, `data-*` ni clases preexistentes.

PROHIBIDO (igual que `docs/UI-REDISENO.md`):
- Backend, lógica JS, textos/i18n, estructura del DOM de la que dependa el JS (verifica con grep
  de `getElementById`/`querySelector`/`hx-target`/`data-event-type` — p. ej. `#estado`,
  `#registros`, `#offline-banner`, `#offline-count` **no se tocan**).
- Frameworks, preprocesadores, dependencias. Solo CSS y HTML vanilla.
- Colores fuera de los tokens de `:root`.

## Estrategia responsive

**Breakpoints** (mobile-first; usa los tokens tipográficos y de color ya existentes):
- Base: móvil (≥360px). Todo usable a **360px** sin scroll horizontal del body.
- `@media (min-width:600px)`: tablet.
- `@media (min-width:900px)`: escritorio (ancho de `main` actual).

**Tablas** — dos patrones, elige por tabla:
- **A) Scroll contenido (rápido, seguro):** envolver cada `<table>` en
  `<div class="table-scroll">` con `overflow-x:auto` + `-webkit-overflow-scrolling:touch`, y un
  indicador visual sutil de que hay más contenido. La tabla conserva su estructura; el scroll
  vive dentro del contenedor, nunca en el body. Aplica a las tablas densas (horas, ausencias,
  alertas, registros).
- **B) Tabla→tarjeta en móvil (más pulido):** en <600px, `thead` oculto y cada `<tr>` se muestra
  como bloque tipo ficha, con la etiqueta de columna vía `td::before{content:attr(data-label)}`.
  Requiere añadir `data-label="..."` a cada `<td>` en la plantilla (presentacional, permitido).
  Recomendado al menos para la tabla de fichajes de hoy (`_estado.html`) y "mis registros", que
  son las que ve el trabajador a diario.

Regla dura: **el `<body>` nunca scrollea en horizontal en ningún ancho** (usa `overflow-x` en el
contenedor de tabla, no en el body).

**Cabecera**: en móvil, `nav` con wrap limpio o menú compacto; los enlaces mono deben mantener
área táctil ≥44px y separación cómoda.

**Formularios**: filas de campos que apilan en vertical en móvil; inputs a ancho completo (ya
está para `max-width`); botones cómodos (el de fichar ≥48px, ya cubierto).

## Proceso (pasos individuales; el ejecutor puede iterar sin parar si así se le indica)

1. **Auditoría** (solo lectura): confirmar el grep de dependencias JS→DOM y listar cada tabla y
   su plantilla; decidir patrón A o B por tabla.
2. **CSS base responsive**: añadir `.table-scroll`, breakpoints 600/900, y (si se opta por B) el
   patrón tabla→tarjeta con `data-label`.
3. **Plantillas**: envolver tablas en `.table-scroll` (y/o añadir `data-label`), una pantalla por
   iteración empezando por **fichar** y **mis registros** (las del trabajador).
4. **QA**: verificar a 360px, 390px, 768px y 1200px (capturas headless con `--window-size`), que
   ninguna página scrollea en horizontal en el body y que las tablas densas son legibles. Correr
   `pytest -q` completo y confirmar que pasa igual (sin modificar tests).

## Verificación sugerida (headless, sin backend)

```bash
# Servir la app en local (Postgres de test) y capturar anchos representativos:
#   360 (móvil pequeño), 390 (móvil), 768 (tablet), 1200 (escritorio)
# Chrome headless: --window-size=360,780 --screenshot=... file/URL
# Revisar cada pantalla: login, fichar, mis-registros, mis-ausencias,
#   admin/registros, admin/horas, admin/alertas, admin/ausencias.
```

## Definición de hecho

- [ ] Ninguna página produce scroll horizontal del `<body>` a 360px.
- [ ] Todas las tablas densas (registros, ausencias, horas, alertas, tiempo efectivo) son
      legibles y navegables en móvil (scroll contenido o patrón tarjeta).
- [ ] Breakpoints móvil/tablet/escritorio coherentes; sin saltos rotos entre ellos.
- [ ] Cabecera y navegación usables y táctiles (≥44px) en móvil.
- [ ] Cero cambios de backend, lógica JS, textos o claves i18n.
- [ ] Ningún id/name/data-*/clase preexistente renombrado o eliminado; `#estado`, `#registros`,
      `#offline-banner`, `#offline-count` y `data-event-type` intactos.
- [ ] Colores solo desde tokens; tres roles tipográficos respetados.
- [ ] `pytest -q` en verde sin modificar ningún test.
