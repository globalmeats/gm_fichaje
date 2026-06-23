# Fichajes Global Meats — Plan de implementación para Claude Code

Andamiaje listo para arrancar el desarrollo de `fichajes.globalmeats.es` con Claude Code,
diseñado para cumplir el registro de jornada español (RDL 8/2019, art. 34.9/35.5 ET) y
los requisitos anticipados de la reforma 2026.

## Qué hay aquí

```
.
├── CLAUDE.md                         # Contexto, stack, reglas de oro, mapa de skills
├── docs/
│   └── IMPLEMENTATION_PLAN.md        # Roadmap por fases con criterios de aceptación
└── .claude/skills/
    ├── legal-compliance/             # Matriz legal ↔ implementación (skill central)
    │   ├── SKILL.md
    │   ├── references/normativa-oficial.md
    │   ├── references/matriz-aceptacion.md
    │   └── scripts/compliance_check.py
    ├── fichaje-domain/               # Modelo de dominio (eventos, pausas, horas, flex)
    │   ├── SKILL.md
    │   └── references/{state-machine,calculo-horas}.md
    ├── audit-trail/                  # Inmutabilidad, sellado, hash, correcciones
    │   └── SKILL.md
    ├── rgpd-dataguard/               # RLS, roles, cifrado, geo, retención, derechos
    │   └── SKILL.md
    └── fastapi-supabase/             # Convenciones del stack + deploy
        ├── SKILL.md
        └── references/{rls-patterns,api-conventions}.md
```

## Cómo empezar

1. Copia `CLAUDE.md`, `.claude/` y `.claudeignore` a la raíz de tu repo de fichajes.
2. Abre la carpeta del repo con Claude Code (extensión de VS Code, publicador anthropic).
   **No ejecutes `/init`**: el `CLAUDE.md` ya está escrito a mano; `/init` lo sobrescribe.
3. Arranca por fases: *"Vamos con la Fase 0 del plan. Lee CLAUDE.md y las skills
   implicadas e impleméntala."* Recomendado usar **Plan mode** al arrancar cada fase.
4. Claude Code consultará la skill adecuada antes de cada bloque y atará cada commit a
   un REQ-XX.

### Configuración incluida

- **`.claude/settings.json`** — Lista de permisos para el stack (FastAPI, pytest, ruff,
  mypy, mise, alembic) para que no pida confirmación en cada comando seguro. En `deny`:
  push, despliegues a Railway/Supabase, borrados destructivos y lectura de `.env`/secretos.
  Ajusta la lista a tu gusto; revísala antes de habilitar auto-accept.
- **`.claudeignore`** — Excluye del contexto secretos (`.env`, credenciales), entornos
  virtuales, artefactos y lockfiles. Refuerza la regla "datos sensibles nunca en el repo".

## Verificación de cumplimiento

```bash
python .claude/skills/legal-compliance/scripts/compliance_check.py .
```

Heurístico: marca qué requisitos tienen cobertura en el código. Los 🟢 (vigentes) son
obligatorios; si alguno sale `FALTA`, el script devuelve error.

## Distinción importante: vigente vs reforma

- 🟢 **Vigente (obligatorio hoy)**: registro diario inicio/fin, inmutabilidad,
  conservación 4 años, disponibilidad, identificación, pausas, horas extra,
  desplazamientos, RGPD, excepciones de ámbito, cómputo flexible, configurabilidad.
- 🟡 **Reforma 2026 (objetivo de diseño, NO en vigor)**: digital obligatorio, sellado
  temporal, log de modificaciones, acceso remoto Inspección, export verificable, geo
  puntual, prohibición de biometría, offline, cifrado/UE, roles, alertas, desglose.

A 22/06/2026 el Decreto-ley de la reforma sigue sin fecha de entrada en vigor tras el
dictamen crítico del Consejo de Estado (23/03/2026). Construimos para cumplirlo desde
el día 1 por robustez, pero no debe presentarse como obligación legal ya vigente.

## Aviso

Soporte técnico, no asesoramiento jurídico. Valida con un laboralista y con el texto
publicado en BOE antes de producción.
