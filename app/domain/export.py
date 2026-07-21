"""Construcción y serialización del informe de jornada verificable (REQ-04, REQ-19).

Lógica pura (sin BD ni HTTP): ensambla `ExportReport` desde los registros + correcciones +
totales del periodo, y lo serializa a CSV (stdlib) y a PDF (fpdf2). El informe incluye el
sellado (hash/prev_hash) de cada registro para que sea verificable y, junto a cada uno, sus
correcciones (audit-trail §3).
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fpdf import FPDF

from app.core.crypto import decrypt_geo
from app.core.time import iso8601, to_madrid, utc_now
from app.schemas.export import (
    ExportAbsenceRow,
    ExportCorrectionRow,
    ExportRecordRow,
    ExportReport,
)


class _Worker(Protocol):
    id: object
    code: str
    first_name: str
    last_name: str


def _minutes(td: timedelta) -> int:
    return int(td.total_seconds() // 60)


def _corrected_local(c) -> str | None:
    """Para una corrección de `occurred_at`, el valor corregido en hora local de Madrid (solo
    presentación web). Devuelve None para otros campos o si el valor no es una fecha válida."""
    if c.field != "occurred_at":
        return None
    try:
        dt = datetime.fromisoformat(c.corrected_value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return to_madrid(dt).strftime("%d/%m/%Y %H:%M:%S")


def build_report(
    worker: _Worker,
    records: list,
    corrections: list,
    summary: dict,
    *,
    annual: dict | None = None,
    vacation: dict | None = None,
    absences: list[ExportAbsenceRow] | None = None,
    pausa_min: int = 0,
    flexible_schedule: bool = False,
    discrepancies: list[str] | None = None,
) -> ExportReport:
    """Ensambla el `ExportReport` (identificación + detalle + correcciones + totales).

    `annual` (tope anual, REQ-27), `vacation` (saldo de vacaciones, REQ-28) y `absences`
    (ausencias del periodo) son opcionales: si no se pasan, el informe sale con ceros/lista
    vacía (compatibilidad hacia atrás).
    """
    by_record: dict[object, list] = defaultdict(list)
    for c in corrections:
        by_record[c.original_record_id].append(c)

    rows: list[ExportRecordRow] = []
    for r in records:
        # La geo se almacena cifrada (REQ-20/23): se descifra para mostrarla en el informe;
        # el sellado (hash) sigue calculado sobre el ciphertext, así el informe es verificable.
        corr_rows = [
            ExportCorrectionRow(
                seq=c.seq,
                field=c.field,
                corrected_value=(
                    decrypt_geo(c.corrected_value) or "" if c.field == "geo"
                    else c.corrected_value
                ),
                corrected_value_local=_corrected_local(c),
                reason=c.reason,
                author_id=c.author_id,
                occurred_at=c.occurred_at,
                hash=c.hash,
            )
            for c in by_record.get(r.id, [])
        ]
        rows.append(
            ExportRecordRow(
                id=r.id,
                seq=r.seq,
                event_type=r.event_type,
                occurred_at=r.occurred_at,
                modalidad=r.modalidad,
                source=r.source,
                travel_computes=r.travel_computes,
                geo=decrypt_geo(r.geo),
                prev_hash=r.prev_hash,
                hash=r.hash,
                corrections=corr_rows,
            )
        )

    return ExportReport(
        worker_id=worker.id,
        employee_code=worker.code,
        full_name=f"{worker.first_name} {worker.last_name}",
        period=summary["period"],
        start=summary["start"],
        end=summary["end"],
        efectivo_min=_minutes(summary["efectivo"]),
        ordinarias_min=_minutes(summary["ordinarias"]),
        extra_min=_minutes(summary["extra"]),
        complementarias_min=_minutes(summary["complementarias"]),
        ordinary_min=_minutes(summary["ordinary"]),
        pausa_min=pausa_min,
        flexible_schedule=flexible_schedule,
        annual_worked_min=_minutes(annual["worked"]) if annual else 0,
        annual_cap_min=_minutes(annual["cap"]) if annual else 0,
        annual_remaining_min=_minutes(annual["remaining"]) if annual else 0,
        vacation_days_entitled=vacation["entitled"] if vacation else 0,
        vacation_days_taken=vacation["taken"] if vacation else 0,
        vacation_days_remaining=vacation["remaining"] if vacation else 0,
        absences=absences or [],
        discrepancies=discrepancies or [],
        generated_at=utc_now(),
        records=rows,
    )


def to_csv(report: ExportReport) -> str:
    """Serializa el informe a CSV: cabecera de identificación/totales + eventos + correcciones."""
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(["# Informe de jornada (export verificable) - Global Meats"])
    w.writerow(["trabajador", report.full_name])
    w.writerow(["codigo_empleado", report.employee_code])
    w.writerow(["worker_id", str(report.worker_id)])
    w.writerow(["periodo", report.period])
    w.writerow(["inicio", iso8601(report.start)])
    w.writerow(["fin", iso8601(report.end)])
    w.writerow(["efectivo_min", report.efectivo_min])
    w.writerow(["ordinarias_min", report.ordinarias_min])
    w.writerow(["extra_min", report.extra_min])
    w.writerow(["complementarias_min", report.complementarias_min])
    w.writerow(["ordinary_min", report.ordinary_min])
    w.writerow(["pausa_min", report.pausa_min])
    w.writerow(["horario_flexible", "si" if report.flexible_schedule else "no"])
    w.writerow(["anual_trabajado_min", report.annual_worked_min])
    w.writerow(["anual_tope_min", report.annual_cap_min])
    w.writerow(["anual_restante_min", report.annual_remaining_min])
    w.writerow(["vacaciones_derecho_dias", report.vacation_days_entitled])
    w.writerow(["vacaciones_disfrutadas_dias", report.vacation_days_taken])
    w.writerow(["vacaciones_restantes_dias", report.vacation_days_remaining])
    w.writerow(["generado", iso8601(report.generated_at)])
    w.writerow([])

    w.writerow(["# Ausencias del periodo (vacaciones/bajas/permisos)"])
    w.writerow(
        ["tipo", "subtipo", "inicio", "fin", "hora_inicio", "hora_fin",
         "estado", "justificada", "horas", "tiene_justificante"]
    )
    for a in report.absences:
        w.writerow(
            [a.absence_type, a.subtype or "", a.start_date.isoformat(), a.end_date.isoformat(),
             a.start_time.isoformat() if a.start_time else "",
             a.end_time.isoformat() if a.end_time else "",
             a.status, "si" if a.justified else "no",
             a.hours if a.hours is not None else "",
             "si" if a.has_document else "no"]
        )
    w.writerow([])

    w.writerow(
        ["seq", "event_type", "occurred_at", "occurred_at_madrid", "modalidad", "source",
         "travel_computes", "geo", "prev_hash", "hash"]
    )
    for r in report.records:
        w.writerow(
            [r.seq, r.event_type, iso8601(r.occurred_at), _madrid(r.occurred_at),
             r.modalidad, r.source,
             r.travel_computes, r.geo or "", r.prev_hash, r.hash]
        )

    w.writerow([])
    w.writerow(["# Correcciones"])
    w.writerow(
        ["record_seq", "correction_seq", "field", "corrected_value", "reason",
         "author_id", "occurred_at", "occurred_at_madrid", "hash"]
    )
    for r in report.records:
        for c in r.corrections:
            w.writerow(
                [r.seq, c.seq, c.field, c.corrected_value, c.reason,
                 str(c.author_id), iso8601(c.occurred_at), _madrid(c.occurred_at), c.hash]
            )

    return buf.getvalue()


def _madrid(dt) -> str:
    """Hora local de Madrid para presentación (junto a UTC en el export verificable)."""
    return to_madrid(dt).strftime("%Y-%m-%d %H:%M:%S %Z")


def _ascii(text: str) -> str:
    """fpdf2 con fuente core (latin-1) no admite todo Unicode; degradamos a ASCII seguro."""
    return text.encode("latin-1", "replace").decode("latin-1")


def to_pdf(report: ExportReport) -> bytes:
    """Serializa el informe a PDF (fpdf2). Devuelve bytes (`%PDF` al inicio)."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, _ascii("Informe de jornada - Global Meats"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 10)
    for label, value in [
        ("Trabajador", report.full_name),
        ("Codigo empleado", report.employee_code),
        ("Periodo", f"{report.period} ({iso8601(report.start)} - {iso8601(report.end)})"),
        (
            "Totales (min)",
            f"efectivo {report.efectivo_min} | ordinarias {report.ordinarias_min} | "
            f"extra {report.extra_min} | complementarias {report.complementarias_min} | "
            f"jornada {report.ordinary_min} | pausa {report.pausa_min}",
        ),
        ("Horario flexible", "si" if report.flexible_schedule else "no"),
        (
            "Tope anual (min)",
            f"trabajado {report.annual_worked_min} | tope {report.annual_cap_min} | "
            f"restante {report.annual_remaining_min}",
        ),
        (
            "Vacaciones (dias)",
            f"derecho {report.vacation_days_entitled} | "
            f"disfrutadas {report.vacation_days_taken} | "
            f"restantes {report.vacation_days_remaining}",
        ),
        ("Generado", iso8601(report.generated_at)),
    ]:
        pdf.cell(0, 6, _ascii(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")

    if report.absences:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, _ascii("Ausencias del periodo"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Courier", "", 7)
        for a in report.absences:
            tramo = (
                f" {a.start_time}-{a.end_time}" if a.start_time and a.end_time else ""
            )
            sub = f"/{a.subtype}" if a.subtype else ""
            linea = (
                f"{a.absence_type}{sub} {a.start_date}..{a.end_date}{tramo} "
                f"[{a.status}] justificada={'si' if a.justified else 'no'}"
            )
            pdf.cell(0, 4, _ascii(linea), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, _ascii("Detalle de eventos (con sellado)"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 7)
    for r in report.records:
        line = (
            f"#{r.seq} {r.event_type} {iso8601(r.occurred_at)} "
            f"(Madrid: {_madrid(r.occurred_at)}) {r.modalidad}/{r.source} "
            f"hash={r.hash[:16]}..."
        )
        pdf.cell(0, 4, _ascii(line), new_x="LMARGIN", new_y="NEXT")
        for c in r.corrections:
            corr = (
                f"    correccion #{c.seq} {c.field}={c.corrected_value} "
                f"motivo='{c.reason}' hash={c.hash[:16]}..."
            )
            pdf.cell(0, 4, _ascii(corr), new_x="LMARGIN", new_y="NEXT")

    out = pdf.output()
    return bytes(out)
