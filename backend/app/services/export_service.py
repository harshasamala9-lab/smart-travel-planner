"""Printable PDF itinerary export with embedded Unicode font."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from app.core.exceptions import ServiceUnavailableError

ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
REGULAR_FONT_PATH = ASSET_DIR / "DejaVuSans.ttf"
BOLD_FONT_PATH = ASSET_DIR / "DejaVuSans-Bold.ttf"

REGULAR_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
_FONTS_REGISTERED = False


def _register_fonts() -> None:
    global REGULAR_FONT, BOLD_FONT, _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if REGULAR_FONT_PATH.exists() and BOLD_FONT_PATH.exists():
            pdfmetrics.registerFont(TTFont("SmartTravelSans", str(REGULAR_FONT_PATH)))
            pdfmetrics.registerFont(
                TTFont("SmartTravelSans-Bold", str(BOLD_FONT_PATH))
            )
            REGULAR_FONT = "SmartTravelSans"
            BOLD_FONT = "SmartTravelSans-Bold"
    except Exception:
        # Standard PDF fonts remain usable for Latin text if font registration fails.
        REGULAR_FONT = "Helvetica"
        BOLD_FONT = "Helvetica-Bold"
    _FONTS_REGISTERED = True


def _money(value: Any, currency: str) -> str:
    try:
        return f"{currency} {float(value):,.2f}"
    except (TypeError, ValueError):
        return f"{currency} 0.00"


class ExportService:
    """Build a self-contained PDF without any external rendering service."""

    def build_itinerary_pdf(self, itinerary: dict[str, Any]) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_LEFT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                KeepTogether,
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise ServiceUnavailableError(
                "PDF export is unavailable because ReportLab is not installed."
            ) from exc

        _register_fonts()
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=str(itinerary.get("title") or "Travel Itinerary"),
            author="Smart Travel Planner",
            subject="Itinerary export",
        )
        base = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TravelTitle",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=20,
            leading=24,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#123B5D"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "TravelSubtitle",
            parent=base["Normal"],
            fontName=REGULAR_FONT,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5B6A"),
            spaceAfter=10,
        )
        heading_style = ParagraphStyle(
            "TravelHeading",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#123B5D"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "TravelBody",
            parent=base["BodyText"],
            fontName=REGULAR_FONT,
            fontSize=9.2,
            leading=13,
            textColor=colors.HexColor("#1F2933"),
            spaceAfter=2,
        )
        small_style = ParagraphStyle(
            "TravelSmall",
            parent=body_style,
            fontSize=7.8,
            leading=10,
            textColor=colors.HexColor("#5B6770"),
        )

        currency = str(itinerary.get("currency") or "")
        elements: list[Any] = [
            Paragraph(escape(str(itinerary.get("title") or "Travel Itinerary")), title_style),
            Paragraph(
                escape(
                    f"{itinerary.get('destination_name', '')} · "
                    f"{itinerary.get('start_date', '')} to {itinerary.get('end_date', '')} · "
                    f"{itinerary.get('travellers', 1)} traveller(s)"
                ),
                subtitle_style,
            ),
        ]
        summary = itinerary.get("summary")
        if summary:
            elements.append(Paragraph(escape(str(summary)), body_style))
            elements.append(Spacer(1, 4))

        budget = itinerary.get("budget_estimate")
        if isinstance(budget, dict):
            elements.append(Paragraph("Estimated budget", heading_style))
            line_items = budget.get("line_items") if isinstance(budget.get("line_items"), dict) else {}
            rows = [["Category", "Estimated amount"]]
            for label, key in (
                ("Transportation", "transportation"),
                ("Accommodation", "accommodation"),
                ("Food", "food"),
                ("Activities", "activities"),
                ("Other / contingency", "other"),
            ):
                rows.append([label, _money(line_items.get(key, 0), currency)])
            rows.append(["Total", _money(budget.get("total", 0), currency)])
            rows.append(["Per person", _money(budget.get("per_person", 0), currency)])
            rows.append(["Total trip budget", _money(budget.get("total_budget", 0), currency)])
            rows.append(["Remaining", _money(budget.get("remaining", 0), currency)])
            table = Table(rows, colWidths=[95 * mm, 65 * mm], hAlign="LEFT")
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8F0F7")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
                        ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
                        ("FONTNAME", (0, 1), (-1, -1), REGULAR_FONT),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C8D6E5")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -4), [colors.white, colors.HexColor("#F7FAFC")]),
                        ("FONTNAME", (0, -4), (-1, -1), BOLD_FONT),
                        ("BACKGROUND", (0, -4), (-1, -4), colors.HexColor("#E8F0F7")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 5),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            elements.extend([table, Spacer(1, 2)])
            if budget.get("warning"):
                elements.append(
                    Paragraph(
                        f"<b>Budget warning:</b> {escape(str(budget['warning']))}",
                        body_style,
                    )
                )
            elements.append(
                Paragraph(
                    escape(
                        str(
                            budget.get(
                                "disclaimer",
                                "All amounts are planning estimates, not verified live prices.",
                            )
                        )
                    ),
                    small_style,
                )
            )

        for day in itinerary.get("days") or []:
            day_title = (
                f"Day {day.get('day_number', '')} · {day.get('date', '')} · "
                f"{day.get('title', '')}"
            )
            day_elements: list[Any] = [Paragraph(escape(day_title), heading_style)]
            if day.get("summary"):
                day_elements.append(Paragraph(escape(str(day["summary"])), body_style))
            activities = day.get("activities") or []
            if not activities:
                day_elements.append(Paragraph("No activities planned.", body_style))
            for activity in activities:
                time_range = " · ".join(
                    value
                    for value in (activity.get("start_time"), activity.get("end_time"))
                    if value
                )
                prefix = f"{time_range} · " if time_range else ""
                cost = _money(activity.get("estimated_cost", 0), currency)
                category = str(activity.get("category") or "activity").replace("_", " ")
                line = (
                    f"{prefix}<b>{escape(str(activity.get('name') or 'Activity'))}</b> "
                    f"({escape(category)}) — {escape(cost)}"
                )
                day_elements.append(Paragraph(line, body_style))
                if activity.get("address"):
                    day_elements.append(
                        Paragraph(escape(str(activity["address"])), small_style)
                    )
                route = activity.get("route_to_next")
                if isinstance(route, dict) and route.get("distance_km") is not None:
                    day_elements.append(
                        Paragraph(
                            escape(
                                f"To next stop: {route.get('distance_km')} km, "
                                f"{route.get('duration_minutes')} min "
                                f"({route.get('travel_mode')}). Source: Google Routes."
                            ),
                            small_style,
                        )
                    )
            elements.append(KeepTogether(day_elements))

        warnings = itinerary.get("warnings") or []
        if warnings:
            elements.append(Paragraph("Important notes", heading_style))
            for warning in warnings:
                elements.append(
                    Paragraph(f"• {escape(str(warning))}", body_style)
                )
        elements.extend(
            [
                Spacer(1, 10),
                Paragraph(
                    escape(
                        "Places and ratings are sourced from Google Places. Opening hours, "
                        "prices, availability, and access details can change. All budget "
                        "figures are planning estimates and not verified live prices. "
                        "Confirm details with providers before booking."
                    ),
                    small_style,
                ),
            ]
        )
        document.build(elements)
        return buffer.getvalue()
