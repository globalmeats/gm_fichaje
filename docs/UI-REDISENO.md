# Rediseño de UI — "Documento de origen" (solo CSS/diseño)

> **Estado (2026-07-19): IMPLEMENTADO.** Sistema de diseño aplicado en
> `app/web/static/app.css` (tokens + base + componentes), fuentes self-hosted en
> `app/web/static/fonts/` (CSP intacta, sin CDN externo), y `base.html` enlaza el CSS
> (retirado el `<style>` inline antiguo). Enhancements de clase en `login`, `fichar`/`_estado`
> y tarjetas de estado admin. **243 tests en verde sin modificar ningún test**; cero cambios de
> backend/JS/textos. Verificado visualmente (login, fichar, alta) con capturas headless. Queda
> como iteración futura opcional pulir pantalla por pantalla los formularios admin más densos.

> Reestilizado de la interfaz de `fichajes.globalmeats.es`
> para alinearla con el sistema de diseño corporativo de GlobalMeats. **Solo CSS/diseño: NO
> cambia el comportamiento de la app.** Registrada aquí para abordarla en una sesión dedicada,
> siguiendo el proceso por pasos con aprobación explícita entre cada uno.
>
> Relacionado: la skill `frontend-fichaje` (convenciones de front: Jinja2 + Alpine/htmx, sin
> build de JS) y los estáticos vendorizados en `app/web/static/`.

---

# Prompt para Claude Code — Reestilizado UI de fichajes.globalmeats.es (solo CSS/diseño)

<contexto>
Esta aplicación es el registro horario (fichajes) interno de GlobalMeats. Funciona correctamente y NO debe cambiar su comportamiento. El objetivo es únicamente alinear su interfaz con el nuevo sistema de diseño corporativo de GlobalMeats, llamado "Documento de origen": una estética de documento comercial — precisa, sobria, verificable — construida sobre los dos colores del logo (rojo bermellón y gris pizarra) y tres roles tipográficos estrictos.
</contexto>

<alcance>
PERMITIDO (y solo esto):
- Modificar ficheros CSS existentes o crear un fichero nuevo de tokens/estilos.
- Ediciones mínimas en plantillas (Jinja2/HTML) estrictamente presentacionales: añadir clases, envolver elementos para maquetación, enlazar webfonts y el nuevo CSS, ajustar atributos visuales (aria-* de mejora incluida).
- Añadir CSS de estados (hover, focus, disabled) y transiciones.

PROHIBIDO:
- Tocar cualquier código backend (rutas, modelos, servicios, auth, base de datos, migraciones, configuración, CI/CD).
- Modificar lógica JavaScript existente: ni handlers, ni fetch/llamadas, ni validaciones, ni cálculos de tiempo.
- Renombrar o eliminar ids, names de formularios, clases existentes o atributos data-* — el JS y los tests pueden depender de ellos. Las clases nuevas se AÑADEN junto a las existentes, nunca las sustituyen.
- Cambiar textos visibles, literales, formatos de fecha/hora o claves i18n.
- Cambiar la estructura del DOM de la que dependa el JS (verifica antes con grep de querySelector/getElementById/closest/classList en todo el JS).
- Añadir frameworks, preprocesadores, bundlers o dependencias. Solo CSS y HTML vanilla.
</alcance>

<design_tokens>
Crea (o sustituye si ya existe de una iteración anterior) el fichero de tokens y úsalo como única fuente de color. Ningún color hardcodeado fuera de él:

<code>
:root{
  --seal:      #CE3E28;  /* rojo del logo: acciones primarias, acentos, estados activos */
  --seal-deep: #A5311E;  /* hover/active de --seal; texto rojo sobre fondos tintados */
  --seal-tint: #F7E4DF;  /* fondo suave de etiquetas/estados destacados */
  --ink:       #26262B;  /* texto principal, cabeceras oscuras */
  --slate:     #505052;  /* gris del logo: texto secundario */
  --slate-soft:#8A8A90;  /* metadatos, placeholders, líneas de detalle */
  --paper:     #F7F5F1;  /* fondo base de la app */
  --paper-2:   #EFECE6;  /* fondos alternos, filas pares, paneles */
  --line:      #DCD9D2;  /* bordes y separadores hairline */
  --white:     #FFFFFF;  /* superficies de tarjeta/campo */
  --ok:        #2F7A46;  /* verde funcional SOLO para estados correctos (fichaje válido) */
  --warn:      #B07A1E;  /* ámbar funcional SOLO para avisos (p. ej. jornada abierta) */
}
</code>

Nota: --ok y --warn son colores funcionales de estado permitidos en una app operativa (a diferencia de la web corporativa); úsalos con moderación y siempre acompañados de texto, nunca como único indicador.
</design_tokens>

<tipografia>
Tres roles estrictos, vía webfonts (Google Fonts o self-host si el proyecto ya sirve estáticos):
- 'Source Serif 4' (600/700): SOLO títulos de página y cifras grandes (p. ej. el reloj/hora actual, total de horas).
- 'Public Sans' (400/500/600): todo el cuerpo, botones, formularios, tablas.
- 'IBM Plex Mono' (400/500): SOLO etiquetas de estado, códigos, timestamps de registros y metadatos. Es la "voz trazabilidad" del sistema: cada hora fichada impresa en mono refuerza la idea de registro verificable.
Tamaño base 16px; en móvil los botones de fichar deben ser grandes y cómodos (mín. 48px de alto táctil).
</tipografia>

<lenguaje_visual>
Aplica estos patrones adaptando los componentes existentes SIN cambiar su comportamiento:

1. **Etiqueta de origen** (componente firma): labels en IBM Plex Mono, mayúsculas, letter-spacing .08em, borde 1px --line, fondo --white, con un pequeño "ojal" circular a la izquierda (círculo de 0.5em con borde). Úsala para estados de fichaje:
   - ENTRADA REGISTRADA / SALIDA REGISTRADA → variante con ojal verde --ok
   - JORNADA ABIERTA → ojal ámbar --warn
   - Estados destacados → texto --seal-deep sobre fondo --seal-tint
2. **Tarjetas tipo documento**: paneles con fondo --white, borde 1px --line, radio 3px, sombra muy sutil; cabecera de tarjeta en mono con separador de línea discontinua (border-bottom dashed), imitando una ficha/albarán.
3. **Tablas de registros**: cabecera en mono uppercase --slate-soft, filas separadas por hairline --line, hora en mono, fila hover --paper-2. Sin zebra striping pesado.
4. **Botones**: primario fondo --seal (hover --seal-deep), texto blanco, radio 3px; secundario contorno --ink. El botón de fichar es la acción principal de la app: prominente, ancho en móvil.
5. **Formularios**: campos fondo --white, borde --line, focus con outline 2px --seal; labels en mono pequeño uppercase.
6. **Cabecera de la app**: barra superior fondo --ink con el wordmark del logo (variante clara si existe; si no, texto) y, si hay nombre de usuario/fecha, en mono.
7. **Motion**: transiciones de 150ms en hover/focus únicamente; sin animaciones decorativas; respeta prefers-reduced-motion con un bloque que desactive transiciones.
</lenguaje_visual>

<accesibilidad>
- Contraste AA en todas las combinaciones (verifica especialmente mono pequeño sobre --paper-2 y estados sobre --seal-tint).
- Focus visible en todos los elementos interactivos.
- Los estados nunca se comunican solo por color (icono o texto siempre presentes).
- Nada de font-size por debajo de 12px.
</accesibilidad>

<proceso>
Trabaja en pasos individuales. DETENTE al final de cada paso y espera mi aprobación explícita antes de continuar:

PASO 1 — Auditoría (solo lectura, cero cambios):
- Lista los ficheros CSS y plantillas implicados, el mecanismo actual de estilos, y TODAS las dependencias del JS sobre clases/ids/estructura (salida del grep incluida).
- Lista las pantallas/vistas existentes (login, fichar, historial, etc.).
- Propón el mapeo: qué componente actual recibe qué patrón de <lenguaje_visual>.
- Señala cualquier riesgo donde estilo y comportamiento estén acoplados (p. ej. clases usadas como selectores JS o en tests).

PASO 2 — Tokens y base:
- Crea el fichero de tokens + estilos base (reset ligero, tipografía, fondo, cabecera). Enlázalo sin retirar aún el CSS antiguo. Muéstrame el diff.

PASO 3 — Componentes por pantalla:
- Una pantalla por iteración (empezando por la de fichar, que es la crítica), con diff y captura/descripción del resultado. Aprobación pantalla a pantalla.

PASO 4 — Retirada del CSS antiguo y QA:
- Elimina o vacía los estilos antiguos ya sustituidos (sin borrar clases del HTML que use el JS).
- Ejecuta la suite de tests completa y confírmame que pasa igual que antes de empezar.
- Checklist final de <definicion_de_hecho>.
</proceso>

<definicion_de_hecho>
- [ ] La app funciona exactamente igual: mismos flujos, mismos datos, mismos endpoints, tests en verde sin modificar ningún test.
- [ ] Cero cambios en backend, lógica JS, textos o claves i18n.
- [ ] Ningún id, name, data-* ni clase preexistente renombrado o eliminado.
- [ ] Todos los colores salen de los tokens; ningún hex fuera del fichero de tokens.
- [ ] Tres roles tipográficos respetados (serif solo títulos/cifras, mono solo estados/horas/metadatos).
- [ ] El botón de fichar es cómodo en móvil (≥48px táctil) y toda la app es usable a 360px.
- [ ] Contraste AA, focus visible, prefers-reduced-motion respetado.
- [ ] La app se percibe inmediatamente como parte de la familia GlobalMeats "Documento de origen".
</definicion_de_hecho>

---

## Nota de implementación (contexto del repo)

- El front es SSR con Jinja2 servido por FastAPI + Alpine.js/htmx vendorizados en
  `app/web/static/vendor/` (sin build de JS). Ver skill `frontend-fichaje`.
- **CSP (SEC-07)**: hay una `Content-Security-Policy` en `app/main.py`. Si se enlazan
  **webfonts externas** (Google Fonts), habrá que añadir `font-src`/`style-src` con el host de
  Google — o, preferible y coherente con el proyecto, **self-hostear las fuentes** en
  `app/web/static/` para no relajar la CSP ni depender de un tercero (mejor para RGPD: Google
  Fonts desde CDN filtra IPs). Recomendado: self-host.
- Verificar dependencias JS→DOM con grep antes de tocar plantillas:
  `grep -rn "querySelector\|getElementById\|closest\|classList\|x-data\|hx-" app/web/static app/web/templates`.
- Los tests web (`app/tests/test_web_*.py`) comprueban textos y algunos fragmentos htmx: no
  cambiar literales ni ids/targets de htmx.
