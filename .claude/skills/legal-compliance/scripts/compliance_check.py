#!/usr/bin/env python3
"""
compliance_check.py — Checklist heurístico de cobertura de requisitos legales.

NO es asesoramiento jurídico ni una verificación formal. Escanea el repositorio en
busca de señales (nombres de tablas, endpoints, tests, configuración) que indiquen
que cada REQ tiene alguna cobertura, y lista los que parecen faltar.

Uso:
    python .claude/skills/legal-compliance/scripts/compliance_check.py [ruta_repo]

Salida: tabla REQ -> [OK | REVISAR | FALTA] + resumen. Exit code 1 si algo crítico
(🟢 vigente) parece sin cobertura.
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

# REQ -> (estado, [patrones que, si aparecen en el código, sugieren cobertura])
REQUISITOS: dict[str, tuple[str, list[str]]] = {
    "REQ-01": ("VIGENTE", [r"check_in", r"check_out", r"time_record"]),
    "REQ-02": ("VIGENTE", [r"append.?only", r"immutab", r"prev_hash", r"no.?update"]),
    "REQ-03": ("VIGENTE", [r"retention", r"4\s*a[nñ]os", r"four.?year", r"conserv"]),
    "REQ-04": ("VIGENTE", [r"export", r"\bcsv\b", r"\bpdf\b", r"download"]),
    "REQ-05": ("VIGENTE", [r"worker_id", r"bcrypt", r"\bpin\b"]),
    "REQ-06": ("VIGENTE", [r"presencial", r"teletrabajo", r"movil|m[oó]vil", r"modalidad"]),
    "REQ-07": ("VIGENTE", [r"break_start", r"break_end", r"pausa", r"computable"]),
    "REQ-08": ("VIGENTE", [r"hora.?extra|overtime", r"totaliz", r"compensaci"]),
    "REQ-09": ("VIGENTE", [r"desplaz|displacement", r"puesta.?a.?disposici"]),
    "REQ-10": ("VIGENTE", [r"dpia", r"rgpd|gdpr", r"6\.1\.c|6_1_c"]),
    "REQ-11": ("VIGENTE", [r"alta.?direcci", r"\bett\b", r"subcontrat", r"exclusi"]),
    "REQ-12": ("VIGENTE", [r"globaliz|ponder", r"periodo|period", r"mensual|monthly"]),
    "REQ-13": ("VIGENTE", [r"config", r"convenio", r"parametr|param"]),
    "REQ-14": ("REFORMA", [r"digital", r"no.?excel|sin.?excel"]),
    "REQ-15": ("REFORMA", [r"hash", r"timestamp|sellado", r"chain|encaden"]),
    "REQ-16": ("REFORMA", [r"correction|correcci", r"reason|motivo", r"author|autor"]),
    "REQ-17": ("REFORMA", [r"inspecci|inspection", r"remote|remoto"]),
    "REQ-18": ("REFORMA", [r"portal", r"self.?service|mis.?registros", r"worker.?access"]),
    "REQ-19": ("REFORMA", [r"report|informe", r"\bpdf\b", r"\bcsv\b"]),
    "REQ-20": ("REFORMA", [r"geo|location|geoloc", r"consent|consentim", r"encrypt|cifr"]),
    "REQ-21": ("REFORMA", [r"no.?biometr|sin.?biometr|bcrypt"]),
    "REQ-22": ("REFORMA", [r"offline", r"sync|sincroniz", r"queue|cola"]),
    "REQ-23": ("REFORMA", [r"\btls\b|https", r"encrypt|cifr", r"\beu\b|\bue\b|region"]),
    "REQ-24": ("REFORMA", [r"\brls\b", r"role|rol", r"permiss|permiso"]),
    "REQ-25": ("REFORMA", [r"alert", r"audit", r"anomal"]),
    "REQ-26": ("REFORMA", [r"ordinari", r"complementar", r"desconexi"]),
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}
EXTS = {".py", ".sql", ".md", ".ts", ".tsx", ".js", ".jsx", ".toml", ".yaml", ".yml", ".env"}


def gather_text(root: Path) -> str:
    chunks: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if Path(fn).suffix.lower() in EXTS:
                try:
                    chunks.append(Path(dirpath, fn).read_text(encoding="utf-8", errors="ignore").lower())
                except OSError:
                    pass
    return "\n".join(chunks)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    haystack = gather_text(root)

    print(f"\nCompliance check sobre: {root}\n" + "=" * 60)
    missing_critical: list[str] = []
    for req, (estado, patterns) in REQUISITOS.items():
        hits = sum(bool(re.search(p, haystack)) for p in patterns)
        if hits >= 2:
            status = "OK"
        elif hits == 1:
            status = "REVISAR"
        else:
            status = "FALTA"
        flag = "🟢" if estado == "VIGENTE" else "🟡"
        print(f"{flag} {req} [{estado:7}] {status:8} ({hits}/{len(patterns)} señales)")
        if status == "FALTA" and estado == "VIGENTE":
            missing_critical.append(req)

    print("=" * 60)
    if missing_critical:
        print(f"\n❌ Requisitos VIGENTES sin señal de cobertura: {', '.join(missing_critical)}")
        print("   Revisa: estos son obligación legal HOY.\n")
        return 1
    print("\n✅ Todos los requisitos vigentes muestran alguna cobertura.")
    print("   (Heurístico: confirma con revisión humana y tests reales.)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
