
import os
import re
import html

from datetime import datetime, date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
    CondPageBreak
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


# =========================================================
# CONFIGURATION
# =========================================================

OUTPUT_DIR = "generated_reports"

DEFAULT_DOCTOR_NAME = "Dr. Chopper"

os.makedirs(OUTPUT_DIR, exist_ok=True)

PAGE_WIDTH, PAGE_HEIGHT = A4

NAVY = colors.HexColor("#123047")
TEAL = colors.HexColor("#087E8B")
LIGHT_TEAL = colors.HexColor("#E8F4F5")
LIGHT_BLUE = colors.HexColor("#EFF5F9")
LIGHT_GREY = colors.HexColor("#F4F6F8")
MID_GREY = colors.HexColor("#64748B")
DARK = colors.HexColor("#263746")
BORDER = colors.HexColor("#DCE4EA")
RED = colors.HexColor("#B42318")
LIGHT_RED = colors.HexColor("#FDECEC")
GREEN = colors.HexColor("#16794B")
LIGHT_GREEN = colors.HexColor("#EAF6EF")
WHITE = colors.white


# =========================================================
# FONT CONFIGURATION
# =========================================================

def register_fonts():

    """
    Uses standard ReportLab fonts by default.

    Optional custom fonts can be placed in:
        assets/fonts/DejaVuSans.ttf
        assets/fonts/DejaVuSans-Bold.ttf
    """

    regular_path = os.path.join(
        "assets",
        "fonts",
        "DejaVuSans.ttf"
    )

    bold_path = os.path.join(
        "assets",
        "fonts",
        "DejaVuSans-Bold.ttf"
    )

    if os.path.exists(regular_path) and os.path.exists(bold_path):

        if "NexEHR-Regular" not in pdfmetrics.getRegisteredFontNames():

            pdfmetrics.registerFont(
                TTFont("NexEHR-Regular", regular_path)
            )

            pdfmetrics.registerFont(
                TTFont("NexEHR-Bold", bold_path)
            )

        return "NexEHR-Regular", "NexEHR-Bold"

    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = register_fonts()


# =========================================================
# TEXT HELPERS
# =========================================================

def safe_text(value):

    if value is None:
        return "Not documented"

    value = str(value).strip()

    if not value:
        return "Not documented"

    value = html.escape(value)

    value = value.replace("\n", "<br/>")

    return value


def clean_filename(value):

    value = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        str(value)
    )

    return value.strip("_") or "Patient"


def format_date(value):

    if not value:
        return "Not documented"

    try:

        if isinstance(value, datetime):
            return value.strftime("%d %B %Y")

        if isinstance(value, date):
            return value.strftime("%d %B %Y")

        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        return parsed.strftime("%d %B %Y")

    except (ValueError, TypeError):

        return str(value)


def format_datetime(value):

    if not value:
        return "Not documented"

    try:

        if isinstance(value, datetime):
            parsed = value

        else:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

        return parsed.strftime("%d %B %Y, %I:%M %p")

    except (ValueError, TypeError):

        return str(value)


def normalize_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    return [value]


def get_item_value(item, key, default="Not documented"):

    if isinstance(item, dict):

        value = item.get(key)

    else:

        value = getattr(item, key, None)

    if value is None or str(value).strip() == "":
        return default

    return str(value)


# =========================================================
# STYLE DEFINITIONS
# =========================================================

def create_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            fontName=FONT_BOLD,
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=4
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
            textColor=MID_GREY,
            spaceAfter=10
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontName=FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=TEAL,
            spaceBefore=11,
            spaceAfter=6,
            keepWithNext=True
        )
    )

    styles.add(
        ParagraphStyle(
            name="SubHeading",
            fontName=FONT_BOLD,
            fontSize=9,
            leading=12,
            textColor=NAVY,
            spaceBefore=6,
            spaceAfter=4,
            keepWithNext=True
        )
    )

    styles.add(
        ParagraphStyle(
            name="ClinicalBody",
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=13,
            textColor=DARK,
            spaceAfter=5
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallBody",
            fontName=FONT_REGULAR,
            fontSize=7.5,
            leading=10,
            textColor=MID_GREY
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=WHITE
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName=FONT_REGULAR,
            fontSize=7.3,
            leading=10,
            textColor=DARK
        )
    )

    styles.add(
        ParagraphStyle(
            name="Label",
            fontName=FONT_BOLD,
            fontSize=7.5,
            leading=10,
            textColor=MID_GREY
        )
    )

    styles.add(
        ParagraphStyle(
            name="Value",
            fontName=FONT_REGULAR,
            fontSize=8.5,
            leading=12,
            textColor=DARK
        )
    )

    styles.add(
        ParagraphStyle(
            name="AlertText",
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=12,
            textColor=RED
        )
    )

    styles.add(
        ParagraphStyle(
            name="Signature",
            fontName=FONT_REGULAR,
            fontSize=8,
            leading=12,
            textColor=DARK
        )
    )

    return styles


# =========================================================
# BASIC PDF COMPONENTS
# =========================================================

def section_heading(title, styles):

    return Paragraph(
        safe_text(title.upper()),
        styles["SectionHeading"]
    )


def body_paragraph(value, styles):

    return Paragraph(
        safe_text(value),
        styles["ClinicalBody"]
    )


def bullet_list(items, styles):

    items = normalize_list(items)

    if not items:

        return [
            body_paragraph("Not documented.", styles)
        ]

    result = []

    for item in items:

        if isinstance(item, dict):

            item_text = " | ".join(
                f"{key.replace('_', ' ').title()}: {value}"
                for key, value in item.items()
                if value is not None and str(value).strip()
            )

        else:

            item_text = str(item)

        result.append(
            Paragraph(
                "&#8226;&nbsp; " + safe_text(item_text),
                styles["ClinicalBody"]
            )
        )

    return result


def information_table(rows, styles, col_widths=None):

    formatted_rows = []

    for label, value in rows:

        formatted_rows.append([
            Paragraph(
                safe_text(label),
                styles["Label"]
            ),
            Paragraph(
                safe_text(value),
                styles["Value"]
            )
        ])

    if col_widths is None:

        col_widths = [43 * mm, 137 * mm]

    table = Table(
        formatted_rows,
        colWidths=col_widths,
        hAlign="LEFT"
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
            ("BACKGROUND", (1, 0), (1, -1), WHITE),
            ("GRID", (0, 0), (-1, -1), 0.45, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )

    return table


def data_table(headers, rows, widths, styles):

    header_row = [
        Paragraph(
            safe_text(header),
            styles["TableHeader"]
        )
        for header in headers
    ]

    formatted_rows = [header_row]

    if not rows:

        formatted_rows.append([
            Paragraph(
                "Not documented",
                styles["TableCell"]
            )
        ] + [
            Paragraph("", styles["TableCell"])
            for _ in range(len(headers) - 1)
        ])

    else:

        for row in rows:

            formatted_rows.append([
                Paragraph(
                    safe_text(value),
                    styles["TableCell"]
                )
                for value in row
            ])

    table = Table(
        formatted_rows,
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT"
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                WHITE,
                LIGHT_GREY
            ]),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )

    return table


# =========================================================
# MEDICATION TABLE
# =========================================================

def medication_table(medications, styles):

    medications = normalize_list(medications)

    rows = []

    for medication in medications:

        rows.append([

            get_item_value(medication, "name"),

            get_item_value(medication, "dosage"),

            get_item_value(medication, "route"),

            get_item_value(medication, "frequency"),

            get_item_value(medication, "duration"),

            get_item_value(medication, "status")

        ])

    return data_table(
        [
            "Medication",
            "Dosage",
            "Route",
            "Frequency",
            "Duration",
            "Status"
        ],
        rows,
        [
            32 * mm,
            23 * mm,
            20 * mm,
            27 * mm,
            25 * mm,
            32 * mm
        ],
        styles
    )


# =========================================================
# INVESTIGATION TABLE
# =========================================================

def investigation_table(investigations, styles):

    investigations = normalize_list(investigations)

    rows = []

    for investigation in investigations:

        rows.append([

            get_item_value(investigation, "name"),

            get_item_value(investigation, "reason"),

            get_item_value(investigation, "priority"),

            get_item_value(investigation, "status")

        ])

    return data_table(
        [
            "Investigation",
            "Clinical Reason",
            "Priority",
            "Status"
        ],
        rows,
        [
            42 * mm,
            55 * mm,
            25 * mm,
            37 * mm
        ],
        styles
    )


# =========================================================
# TREATMENT PLAN TABLE
# =========================================================

def treatment_table(treatments, styles):

    treatments = normalize_list(treatments)

    rows = []

    for treatment in treatments:

        rows.append([

            get_item_value(treatment, "category"),

            get_item_value(treatment, "recommendation"),

            get_item_value(treatment, "rationale"),

            get_item_value(treatment, "priority")

        ])

    return data_table(
        [
            "Category",
            "Recommendation",
            "Rationale",
            "Priority"
        ],
        rows,
        [
            27 * mm,
            53 * mm,
            54 * mm,
            25 * mm
        ],
        styles
    )


# =========================================================
# FOLLOW-UP TABLE
# =========================================================

def followup_table(followups, styles):

    followups = normalize_list(followups)

    rows = []

    for item in followups:

        rows.append([

            get_item_value(item, "instruction"),

            get_item_value(item, "timeframe")

        ])

    return data_table(
        [
            "Follow-up Instruction",
            "Timeframe"
        ],
        rows,
        [
            105 * mm,
            75 * mm
        ],
        styles
    )


# =========================================================
# PAGE HEADER AND FOOTER
# =========================================================

def make_page_decorator(
    patient_id,
    consultation_id,
    report_date
):

    def decorate(canvas, document):

        canvas.saveState()

        # Header line
        canvas.setStrokeColor(BORDER)

        canvas.setLineWidth(0.6)

        canvas.line(
            15 * mm,
            PAGE_HEIGHT - 13 * mm,
            PAGE_WIDTH - 15 * mm,
            PAGE_HEIGHT - 13 * mm
        )

        canvas.setFont(FONT_BOLD, 7)

        canvas.setFillColor(NAVY)

        canvas.drawString(
            15 * mm,
            PAGE_HEIGHT - 10 * mm,
            "NEXEHR COPILOT"
        )

        canvas.setFont(FONT_REGULAR, 7)

        canvas.setFillColor(MID_GREY)

        canvas.drawRightString(
            PAGE_WIDTH - 15 * mm,
            PAGE_HEIGHT - 10 * mm,
            f"MRN-{patient_id:05d}"
        )

        # Footer line
        canvas.setStrokeColor(BORDER)

        canvas.line(
            15 * mm,
            12 * mm,
            PAGE_WIDTH - 15 * mm,
            12 * mm
        )

        canvas.setFont(FONT_REGULAR, 7)

        canvas.setFillColor(MID_GREY)

        canvas.drawString(
            15 * mm,
            8 * mm,
            "CONFIDENTIAL | Clinical Documentation"
        )

        canvas.drawCentredString(
            PAGE_WIDTH / 2,
            8 * mm,
            f"Consultation #{consultation_id or 'Draft'}"
        )

        canvas.drawRightString(
            PAGE_WIDTH - 15 * mm,
            8 * mm,
            f"Page {document.page}"
        )

        canvas.restoreState()

    return decorate


# =========================================================
# MAIN PDF GENERATOR
# =========================================================

def generate_clinical_pdf(
    patient_data,
    final_soap,
    all_consultations=None,
    doctor_name=DEFAULT_DOCTOR_NAME,
    consultation_type="General",
    consultation_id=None
):

    """
    Generates a professional multi-page clinical PDF.

    Arguments:
        patient_data:
            Dictionary containing patient information.

        final_soap:
            Complete Gemini-generated clinical documentation.

        all_consultations:
            Optional previous consultation records.

        doctor_name:
            Defaults to Dr. Chopper.

        consultation_type:
            General, Follow-up, Emergency, etc.

        consultation_id:
            Optional database consultation ID.

    Returns:
        Absolute path to the generated PDF.
    """

    if not patient_data:

        raise ValueError(
            "Patient information is required."
        )

    if not final_soap:

        raise ValueError(
            "Clinical documentation is required."
        )

    patient_id = int(
        patient_data["id"]
    )

    patient_name = patient_data.get(
        "name",
        "Unknown Patient"
    )

    doctor_name = (
        doctor_name.strip()
        if doctor_name and doctor_name.strip()
        else DEFAULT_DOCTOR_NAME
    )

    # Use the required doctor name if no other value is supplied.
    if not doctor_name:
        doctor_name = "Dr. Chopper"

    timestamp = datetime.now()

    report_date = timestamp.strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"Clinical_Report_"
        f"{patient_id}_"
        f"{report_date}.pdf"
    )

    filepath = os.path.abspath(
        os.path.join(
            OUTPUT_DIR,
            filename
        )
    )

    styles = create_styles()

    doc = SimpleDocTemplate(

        filepath,

        pagesize=A4,

        rightMargin=15 * mm,
        leftMargin=15 * mm,

        topMargin=19 * mm,
        bottomMargin=19 * mm,

        title=f"Clinical Report - {patient_name}",

        author="NexEHR Copilot",

        subject="Clinical Consultation Report",

        pageCompression=1
    )

    story = []

    # =====================================================
    # 1. REPORT COVER HEADER
    # =====================================================

    story.append(Spacer(1, 4 * mm))

    story.append(
        Paragraph(
            "NEXEHR COPILOT",
            styles["ReportTitle"]
        )
    )

    story.append(
        Paragraph(
            "CLINICAL CONSULTATION REPORT",
            styles["ReportSubtitle"]
        )
    )

    story.append(
        Paragraph(
            "CONFIDENTIAL PATIENT MEDICAL DOCUMENT",
            ParagraphStyle(
                "Confidential",
                fontName=FONT_BOLD,
                fontSize=7,
                alignment=TA_CENTER,
                textColor=TEAL,
                spaceAfter=9
            )
        )
    )

    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=TEAL
        )
    )

    story.append(Spacer(1, 5 * mm))

    # =====================================================
    # 2. PATIENT INFORMATION
    # =====================================================

    story.append(
        section_heading(
            "01. Patient Information",
            styles
        )
    )

    patient_rows = [

        ("Patient Name", patient_name),

        (
            "Medical Record Number",
            f"MRN-{patient_id:05d}"
        ),

        (
            "Date of Birth",
            format_date(patient_data.get("dob"))
        ),

        (
            "Gender",
            patient_data.get("gender", "Not documented")
        ),

        (
            "Known Allergies",
            patient_data.get("allergies", "Not documented")
        ),

        (
            "Current Medications",
            patient_data.get("medications", "Not documented")
        )

    ]

    story.append(
        information_table(
            patient_rows,
            styles
        )
    )

    story.append(Spacer(1, 3 * mm))

    # =====================================================
    # 3. CONSULTATION INFORMATION
    # =====================================================

    story.append(
        section_heading(
            "02. Consultation Details",
            styles
        )
    )

    consultation_rows = [

        (
            "Consultation Date",
            timestamp.strftime("%d %B %Y")
        ),

        (
            "Consultation Time",
            timestamp.strftime("%I:%M %p")
        ),

        (
            "Consultation Type",
            consultation_type
        ),

        (
            "Attending Physician",
            doctor_name
        ),

        (
            "Consultation ID",
            str(consultation_id or "Not assigned")
        )

    ]

    story.append(
        information_table(
            consultation_rows,
            styles
        )
    )

    # =====================================================
    # 4. CHIEF COMPLAINT
    # =====================================================

    story.append(
        section_heading(
            "03. Chief Complaint",
            styles
        )
    )

    story.append(
        body_paragraph(
            final_soap.get("chief_complaint"),
            styles
        )
    )

    # =====================================================
    # 5. CLINICAL SUMMARY
    # =====================================================

    story.append(
        section_heading(
            "04. Clinical Summary",
            styles
        )
    )

    story.append(
        body_paragraph(
            final_soap.get("clinical_summary"),
            styles
        )
    )

    # =====================================================
    # 6. RELEVANT HISTORY
    # =====================================================

    story.append(
        section_heading(
            "05. Relevant Medical History",
            styles
        )
    )

    story.append(
        body_paragraph(
            final_soap.get("relevant_history"),
            styles
        )
    )

    story.append(
        body_paragraph(
            "Current Medication Summary: "
            + str(
                final_soap.get(
                    "current_medications_summary",
                    "Not documented"
                )
            ),
            styles
        )
    )

    story.append(
        body_paragraph(
            "Allergy Summary: "
            + str(
                final_soap.get(
                    "allergies_summary",
                    "Not documented"
                )
            ),
            styles
        )
    )

    # =====================================================
    # 7. SOAP NOTES
    # =====================================================

    story.append(
        section_heading(
            "06. Clinical SOAP Documentation",
            styles
        )
    )

    soap_sections = [

        ("S", "SUBJECTIVE", "subjective"),

        ("O", "OBJECTIVE", "objective"),

        ("A", "ASSESSMENT", "assessment"),

        ("P", "PLAN", "plan")

    ]

    for letter_label, title, key in soap_sections:

        block = [

            Paragraph(
                f"{letter_label}. {title}",
                styles["SubHeading"]
            ),

            body_paragraph(
                final_soap.get(key),
                styles
            )

        ]

        story.append(
            KeepTogether(block)
        )

    # =====================================================
    # 8. TREATMENT PLAN
    # =====================================================

    story.append(
        section_heading(
            "07. Detailed Treatment Plan",
            styles
        )
    )

    story.append(
        body_paragraph(
            "The following recommendations are recorded "
            "for physician review. Their status is shown "
            "separately from actual clinical orders.",
            styles
        )
    )

    story.append(
        treatment_table(
            final_soap.get("treatment_plan", []),
            styles
        )
    )

    # =====================================================
    # 9. MEDICATIONS
    # =====================================================

    story.append(
        section_heading(
            "08. Medication Details",
            styles
        )
    )

    story.append(
        body_paragraph(
            "Medication status must be checked before "
            "any prescription is issued or administered.",
            styles
        )
    )

    story.append(
        medication_table(
            final_soap.get("medications", []),
            styles
        )
    )

    # =====================================================
    # 10. INVESTIGATIONS
    # =====================================================

    story.append(
        section_heading(
            "09. Investigations and Diagnostic Tests",
            styles
        )
    )

    story.append(
        investigation_table(
            final_soap.get("investigations", []),
            styles
        )
    )

    # =====================================================
    # 11. DIFFERENTIAL DIAGNOSES
    # =====================================================

    story.append(
        section_heading(
            "10. Differential Diagnoses",
            styles
        )
    )

    story.extend(
        bullet_list(
            final_soap.get(
                "differential_diagnoses",
                []
            ),
            styles
        )
    )

    # =====================================================
    # 12. ICD-10 CODES
    # =====================================================

    story.append(
        section_heading(
            "11. Suggested ICD-10 Codes",
            styles
        )
    )

    story.extend(
        bullet_list(
            final_soap.get(
                "icd_10_codes",
                []
            ),
            styles
        )
    )

    # =====================================================
    # 13. PATIENT INSTRUCTIONS
    # =====================================================

    story.append(
        section_heading(
            "12. Patient Counselling and Instructions",
            styles
        )
    )

    story.extend(
        bullet_list(
            final_soap.get(
                "patient_instructions",
                []
            ),
            styles
        )
    )

    # =====================================================
    # 14. FOLLOW-UP
    # =====================================================

    story.append(
        section_heading(
            "13. Follow-up and Review",
            styles
        )
    )

    story.append(
        followup_table(
            final_soap.get(
                "follow_up",
                []
            ),
            styles
        )
    )

    # =====================================================
    # 15. RISK ASSESSMENT
    # =====================================================

    story.append(
        section_heading(
            "14. Clinical Risk Assessment",
            styles
        )
    )

    risk_level = str(
        final_soap.get(
            "risk_level",
            "Not Assessed"
        )
    )

    risk_background = (
        LIGHT_RED
        if risk_level.lower() in [
            "high",
            "critical"
        ]
        else LIGHT_BLUE
    )

    risk_table = Table(
        [[
            Paragraph(
                "<b>Risk Level</b>",
                styles["Value"]
            ),

            Paragraph(
                safe_text(risk_level),
                styles["Value"]
            )
        ]],
        colWidths=[
            43 * mm,
            137 * mm
        ]
    )

    risk_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), risk_background),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8)
        ])
    )

    story.append(risk_table)

    # =====================================================
    # 16. RED FLAGS
    # =====================================================

    red_flags = normalize_list(
        final_soap.get("red_flags", [])
    )

    story.append(
        section_heading(
            "15. Red Flags and Safety Considerations",
            styles
        )
    )

    if red_flags:

        alert_rows = []

        for flag in red_flags:

            alert_rows.append([
                Paragraph(
                    "&#8226;&nbsp;" + safe_text(flag),
                    styles["AlertText"]
                )
            ])

        alert_table = Table(
            alert_rows,
            colWidths=[180 * mm]
        )

        alert_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_RED),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#F4B4AE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
            ])
        )

        story.append(alert_table)

    else:

        story.append(
            body_paragraph(
                "No specific red flags were identified "
                "in the generated documentation.",
                styles
            )
        )

    # =====================================================
    # 17. MISSING INFORMATION
    # =====================================================

    story.append(
        section_heading(
            "16. Information Requiring Clarification",
            styles
        )
    )

    story.extend(
        bullet_list(
            final_soap.get(
                "missing_information",
                []
            ),
            styles
        )
    )

    # =====================================================
    # 18. AI INSIGHTS
    # =====================================================

    story.append(
        section_heading(
            "17. Additional Clinical Considerations",
            styles
        )
    )

    story.append(
        body_paragraph(
            final_soap.get("ai_insights"),
            styles
        )
    )

    # =====================================================
    # 19. PHYSICIAN APPROVAL
    # =====================================================

    story.append(
        section_heading(
            "18. Physician Review and Approval",
            styles
        )
    )

    approval_text = (
        "I have reviewed this clinical documentation "
        "and verified the information before approving "
        "it for inclusion in the patient's medical record."
    )

    story.append(
        body_paragraph(
            approval_text,
            styles
        )
    )

    story.append(Spacer(1, 15 * mm))

    signature_table = Table(
        [
            [
                Paragraph(
                    "____________________________",
                    styles["Signature"]
                ),

                Paragraph(
                    "____________________________",
                    styles["Signature"]
                )
            ],
            [
                Paragraph(
                    f"<b>{safe_text(doctor_name)}</b>",
                    styles["Signature"]
                ),

                Paragraph(
                    "Date and Time",
                    styles["Signature"]
                )
            ],
            [
                Paragraph(
                    "Attending Physician",
                    styles["SmallBody"]
                ),

                Paragraph(
                    "Physician Approval",
                    styles["SmallBody"]
                )
            ]
        ],
        colWidths=[
            90 * mm,
            90 * mm
        ]
    )

    signature_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)
        ])
    )

    story.append(
        KeepTogether(signature_table)
    )

    # =====================================================
    # 20. DISCLAIMER
    # =====================================================

    story.append(Spacer(1, 10 * mm))

    story.append(
        HRFlowable(
            width="100%",
            thickness=0.6,
            color=BORDER
        )
    )

    story.append(Spacer(1, 3 * mm))

    disclaimer = (
        "CONFIDENTIALITY AND CLINICAL USE: This document "
        "contains confidential patient information. "
        "AI-generated content is intended to assist clinical "
        "documentation and must be verified by the attending "
        "physician. Suggested diagnoses, medication options "
        "and investigations are not automatically authorized "
        "medical orders or prescriptions."
    )

    story.append(
        Paragraph(
            safe_text(disclaimer),
            styles["SmallBody"]
        )
    )

    # =====================================================
    # BUILD PDF
    # =====================================================

    page_decorator = make_page_decorator(
        patient_id=patient_id,
        consultation_id=consultation_id,
        report_date=timestamp
    )

    doc.build(
        story,
        onFirstPage=page_decorator,
        onLaterPages=page_decorator
    )

    if not os.path.exists(filepath):

        raise RuntimeError(
            "PDF generation failed: output file was not created."
        )

    if os.path.getsize(filepath) == 0:

        raise RuntimeError(
            "PDF generation failed: output file is empty."
        )

    return filepath
