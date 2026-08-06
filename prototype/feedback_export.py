"""Create an Excel workbook for reviewing copilot conversations."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation


INK = "17151A"
WHITE = "FFFFFF"
MUTED = "756E74"
BURGUNDY = "81264A"
BURGUNDY_SOFT = "F4E9EE"
TEAL = "168B7D"
LIGHT = "F7F5F4"
LINE = "DDD7DA"


def _safe_text(value: Any, limit: int = 32_000) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, default=str)
    value = value[:limit]
    if value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _timestamp(message: dict[str, Any]) -> str:
    return _safe_text(message.get("timestamp"))


def build_feedback_workbook(
    messages: list[dict[str, Any]],
    *,
    session_id: str,
    tenant_code: str | None,
    model: str,
) -> bytes:
    wb = Workbook()
    instructions = wb.active
    instructions.title = "Instructions"
    review = wb.create_sheet("Response Review")
    log = wb.create_sheet("Conversation Log")

    for sheet in (instructions, review, log):
        sheet.sheet_view.showGridLines = False

    instructions.merge_cells("A1:F1")
    instructions["A1"] = "SKAI Growth Copilot — Feedback Workbook"
    instructions["A1"].font = Font(size=18, bold=True, color=WHITE)
    instructions["A1"].fill = PatternFill("solid", fgColor=INK)
    instructions["A1"].alignment = Alignment(vertical="center")
    instructions.row_dimensions[1].height = 34
    instruction_rows = [
        ("Purpose", "Review each assistant response and provide structured feedback for prompt and guidance improvement."),
        ("How to review", "Use the Response Review sheet. Enter a 1–5 rating, select an issue category, and add comments where useful."),
        ("Rating scale", "5 = excellent; 4 = good/minor edits; 3 = partly useful; 2 = substantial problems; 1 = incorrect or unusable."),
        ("Comments", "Describe what was missing, misleading, too verbose, or poorly scoped. Be specific about the desired behavior."),
        ("Suggested answer", "Optionally write or outline the answer you would have preferred."),
        ("Improvement proposal", "Optionally identify a prompt, endpoint-routing, tool-description, or analytical-guideline change."),
        ("Return loop", "Save the completed workbook and provide it back for analysis. Ratings and comments can then be grouped into recurring failure patterns."),
        ("Session ID", session_id),
        ("Tenant", tenant_code or "Default tenant"),
        ("Model", model),
    ]
    for row_index, (label, detail) in enumerate(instruction_rows, start=3):
        instructions.cell(row_index, 1, label)
        instructions.cell(row_index, 2, detail)
        instructions.cell(row_index, 1).font = Font(bold=True, color=BURGUNDY)
        instructions.cell(row_index, 2).alignment = Alignment(wrap_text=True, vertical="top")
    instructions.column_dimensions["A"].width = 24
    instructions.column_dimensions["B"].width = 100

    review_headers = [
        "Review ID",
        "Session ID",
        "Timestamp",
        "Tenant",
        "Model",
        "User question",
        "Assistant response",
        "Conversation context",
        "Tool",
        "Tool arguments",
        "Plan / limitation",
        "Rating (1-5)",
        "Issue category",
        "Reviewer comments",
        "Suggested better answer",
        "Prompt / guideline improvement",
        "Review status",
    ]
    review.append(review_headers)
    transcript: list[str] = []
    review_number = 0
    last_user_question = ""
    for message in messages:
        role = message.get("role", "unknown")
        content = _safe_text(message.get("content"))
        transcript.append(f"{role.upper()}: {content}")
        if role == "user":
            last_user_question = content
            continue
        if role != "assistant":
            continue
        review_number += 1
        plan = message.get("plan") or {}
        review.append(
            [
                f"R{review_number:04d}",
                session_id,
                _timestamp(message),
                tenant_code or "default",
                model,
                last_user_question,
                content,
                _safe_text("\n\n".join(transcript)),
                _safe_text(plan.get("tool")),
                _safe_text(plan.get("arguments")),
                _safe_text(
                    {
                        "interpretation": plan.get("interpretation"),
                        "steps": plan.get("steps"),
                        "limitation": plan.get("limitation"),
                    }
                ),
                "",
                "",
                "",
                "",
                "",
                "Not reviewed",
            ]
        )

    review.freeze_panes = "F2"
    review.auto_filter.ref = f"A1:Q{max(review.max_row, 2)}"
    review.row_dimensions[1].height = 32
    header_fill = PatternFill("solid", fgColor=INK)
    for cell in review[1]:
        cell.fill = header_fill
        cell.font = Font(bold=True, color=WHITE)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    editable_fill = PatternFill("solid", fgColor="FFF4D6")
    for row in review.iter_rows(min_row=2, min_col=12, max_col=17):
        for cell in row:
            cell.fill = editable_fill
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for row in review.iter_rows(min_row=2, max_row=review.max_row):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        review.row_dimensions[row[0].row].height = 78

    widths = [12, 22, 20, 18, 16, 42, 65, 70, 24, 45, 50, 14, 24, 48, 55, 55, 18]
    for index, width in enumerate(widths, start=1):
        review.column_dimensions[chr(64 + index)].width = width

    rating_validation = DataValidation(
        type="list", formula1='"1,2,3,4,5"', allow_blank=True
    )
    issue_validation = DataValidation(
        type="list",
        formula1='"None,Incorrect answer,Missing evidence,Wrong tool or endpoint,Bad scope or filters,Unsupported claim,Too verbose,Too brief,Unclear structure,Other"',
        allow_blank=True,
    )
    status_validation = DataValidation(
        type="list", formula1='"Not reviewed,Reviewed,Action required"'
    )
    review.add_data_validation(rating_validation)
    review.add_data_validation(issue_validation)
    review.add_data_validation(status_validation)
    rating_validation.add(f"L2:L{max(review.max_row, 1000)}")
    issue_validation.add(f"M2:M{max(review.max_row, 1000)}")
    status_validation.add(f"Q2:Q{max(review.max_row, 1000)}")
    review.conditional_formatting.add(
        f"L2:L{max(review.max_row, 1000)}",
        CellIsRule(operator="lessThanOrEqual", formula=["2"], fill=PatternFill("solid", fgColor="F4CCCC")),
    )
    review.conditional_formatting.add(
        f"L2:L{max(review.max_row, 1000)}",
        CellIsRule(operator="greaterThanOrEqual", formula=["4"], fill=PatternFill("solid", fgColor="D9EAD3")),
    )

    log_headers = ["Session ID", "Message #", "Timestamp", "Tenant", "Role", "Message", "Tool", "Plan"]
    log.append(log_headers)
    for index, message in enumerate(messages, start=1):
        plan = message.get("plan") or {}
        log.append(
            [
                session_id,
                index,
                _timestamp(message),
                tenant_code or "default",
                _safe_text(message.get("role")),
                _safe_text(message.get("content")),
                _safe_text(plan.get("tool")),
                _safe_text(plan),
            ]
        )
    log.freeze_panes = "F2"
    log.auto_filter.ref = f"A1:H{max(log.max_row, 2)}"
    for cell in log[1]:
        cell.fill = header_fill
        cell.font = Font(bold=True, color=WHITE)
    for row in log.iter_rows(min_row=2, max_row=log.max_row):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        log.row_dimensions[row[0].row].height = 58
    for column, width in zip("ABCDEFGH", [22, 12, 20, 18, 14, 80, 25, 65]):
        log.column_dimensions[column].width = width

    thin = Side(style="thin", color=LINE)
    for sheet in (review, log):
        used = sheet.iter_rows(min_row=1, max_row=sheet.max_row)
        for row in used:
            for cell in row:
                cell.border = Border(bottom=thin)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

