# -*- coding: utf-8 -*-
"""
LUMA — PDF Form Filler
=======================
Takes a completed case (all fields known) and fills PDF form templates.

WHY NOT DOCASSEMBLE:
Docassemble is an interview-driven system — it asks questions and builds docs.
LUMA's flow is the opposite: data already exists, just slot it into PDF fields.
pypdf + reportlab is 50 lines, no framework overhead.

APPROACH:
1. pypdf  — fills interactive form fields in existing PDF templates
           (AcroForm fields in death certificate PDFs, SSA-721, etc.)
2. reportlab — generates new PDFs when no template exists
             (custom intake summaries, case reports)
3. pymupdf  — fallback for complex/unusual PDFs

SUPPORTED FORMS (Phase 1):
- Death Certificate (California template)
- SSA-721 (Statement of Death by Funeral Director)
- Generic intake summary
"""

from pathlib import Path
import os

TEMPLATES_DIR = Path(os.getenv("TEMPLATES_DIR", "./backend/forms/templates"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./data/generated_forms"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def fill_pdf_form(template_name: str, field_data: dict, output_filename: str) -> str:
    """
    Fill a PDF form template with case data.

    Args:
        template_name: Name of template file (e.g. 'death_certificate_ca.pdf')
        field_data: Dict of field_name → value
        output_filename: Name for the output file

    Returns:
        Path to the generated PDF
    """
    template_path = TEMPLATES_DIR / template_name
    output_path = OUTPUT_DIR / output_filename

    if not template_path.exists():
        # No template — generate a summary PDF instead
        return _generate_summary_pdf(field_data, output_path)

    try:
        return _fill_with_pypdf(template_path, field_data, output_path)
    except Exception as e:
        print(f"[FORMS/pypdf] Error: {e}. Trying PyMuPDF...")
        try:
            return _fill_with_pymupdf(template_path, field_data, output_path)
        except Exception as e2:
            print(f"[FORMS/pymupdf] Error: {e2}. Generating summary instead.")
            return _generate_summary_pdf(field_data, output_path)


def _fill_with_pypdf(template_path: Path, field_data: dict, output_path: Path) -> str:
    """
    Fill interactive PDF form fields (AcroForm) using pypdf.
    Best for standardized government forms with defined form fields.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(template_path))
    writer = PdfWriter()
    writer.append(reader)

    # Map our field names to PDF form field names
    # Each PDF has its own field naming convention
    pdf_field_map = _get_field_map(template_path.stem)

    fields_to_write = {}
    for our_field, pdf_field in pdf_field_map.items():
        if our_field in field_data:
            fields_to_write[pdf_field] = str(field_data[our_field])

    # Also try direct field name matching
    for page in reader.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                obj = annot.get_object()
                if obj.get("/Subtype") == "/Widget" and "/T" in obj:
                    field_name = str(obj["/T"])
                    normalized = field_name.lower().replace(" ", "_")
                    if normalized in field_data:
                        fields_to_write[field_name] = str(field_data[normalized])

    writer.update_page_form_field_values(writer.pages[0], fields_to_write)

    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"[FORMS/pypdf] Generated: {output_path} ({len(fields_to_write)} fields filled)")
    return str(output_path)


def _fill_with_pymupdf(template_path: Path, field_data: dict, output_path: Path) -> str:
    """Fallback: use PyMuPDF for complex or unusual PDF formats."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(template_path))

    for page in doc:
        for widget in page.widgets():
            field_name = widget.field_name.lower().replace(" ", "_")
            if field_name in field_data:
                widget.field_value = str(field_data[field_name])
                widget.update()

    doc.save(str(output_path))
    doc.close()

    print(f"[FORMS/pymupdf] Generated: {output_path}")
    return str(output_path)


def _generate_summary_pdf(field_data: dict, output_path: Path) -> str:
    """
    Generate a clean summary PDF when no template exists.
    Uses reportlab — 100% programmatic PDF generation.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )

    styles = getSampleStyleSheet()
    story = []

    # Header
    story.append(Paragraph("LUMA Case Summary", styles["Title"]))
    story.append(Paragraph(
        f"Generated by LUMA — Learning Universal Machine Architecture",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.3 * inch))

    # Deceased info section
    story.append(Paragraph("Decedent Information", styles["Heading2"]))

    # Build table from field data
    key_fields = [
        ("Deceased Name", "deceased_name"),
        ("Date of Birth", "date_of_birth"),
        ("Date of Death", "date_of_death"),
        ("Place of Death", "place_of_death"),
        ("Last Address", "address"),
        ("City", "city"),
        ("State", "state"),
        ("Disposition Method", "disposition_method"),
    ]

    table_data = [["Field", "Value"]]
    for label, field in key_fields:
        value = field_data.get(field, "—")
        table_data.append([label, str(value)])

    # Add any remaining fields
    shown = {f for _, f in key_fields}
    for field, value in field_data.items():
        if field not in shown:
            table_data.append([field.replace("_", " ").title(), str(value)])

    table = Table(table_data, colWidths=[2.5 * inch, 4 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(table)
    doc.build(story)

    print(f"[FORMS/reportlab] Generated summary: {output_path}")
    return str(output_path)


def _get_field_map(template_name: str) -> dict:
    """
    Map LUMA field names to PDF form field names for known templates.
    Each government form has its own field naming convention.
    """
    maps = {
        "death_certificate_ca": {
            "deceased_name": "Decedent Full Legal Name",
            "date_of_birth": "Date of Birth",
            "date_of_death": "Date of Death",
            "gender": "Sex",
            "address": "Residence Street Address",
            "city": "City",
            "state": "State",
            "zip": "Zip",
            "occupation": "Usual Occupation",
            "marital_status": "Marital Status",
            "father_name": "Father Name",
            "mother_maiden_name": "Mother Maiden Name",
            "disposition_method": "Method of Disposition",
            "cemetery_name": "Place of Disposition Name",
        },
        "ssa_721": {
            "deceased_name": "Name of Deceased",
            "date_of_death": "Date of Death",
            "ssn_last4": "Social Security Number",
            "next_of_kin_name": "Name of Surviving Spouse",
        },
    }
    return maps.get(template_name, {})


def generate_all_forms(case_fields: dict, case_id: str) -> list:
    """
    Generate all standard funeral home forms for a case.
    Returns list of generated file paths.
    """
    generated = []

    # Death Certificate Summary
    path = fill_pdf_form(
        "death_certificate_ca.pdf",
        case_fields,
        f"{case_id}_death_certificate.pdf"
    )
    generated.append({"form": "Death Certificate", "path": path})

    # SSA Notification
    path = fill_pdf_form(
        "ssa_721.pdf",
        case_fields,
        f"{case_id}_ssa_721.pdf"
    )
    generated.append({"form": "SSA-721", "path": path})

    # Case Summary (always generated — no template needed)
    path = _generate_summary_pdf(case_fields, OUTPUT_DIR / f"{case_id}_summary.pdf")
    generated.append({"form": "Case Summary", "path": path})

    return generated
