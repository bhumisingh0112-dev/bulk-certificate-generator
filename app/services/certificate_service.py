from pathlib import Path
import re

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_part(value: str) -> str:
    cleaned = _FILENAME_SAFE.sub("_", value.strip())
    return cleaned.strip("._") or "certificate"


def generate_certificate(
    *,
    output_dir: Path,
    recipient_id: str,
    recipient_name: str,
    certificate_id: str,
    certificate_title: str,
    course_name: str,
    issuer_name: str,
    issue_date: str,
) -> Path:
    """Generate one PDF certificate using the single predefined template."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_part(recipient_name)}_{_safe_part(certificate_id)}_{recipient_id[:8]}.pdf"
    output_path = output_dir / filename

    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    pdf.setTitle(f"{certificate_title} - {recipient_name}")

    # Predefined template: double border + centered certificate content.
    margin = 28
    pdf.setLineWidth(3)
    pdf.rect(margin, margin, page_width - 2 * margin, page_height - 2 * margin)
    pdf.setLineWidth(1)
    pdf.rect(margin + 9, margin + 9, page_width - 2 * (margin + 9), page_height - 2 * (margin + 9))

    center_x = page_width / 2
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(center_x, page_height - 105, certificate_title)

    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(center_x, page_height - 155, "This certificate is proudly presented to")

    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(center_x, page_height - 210, recipient_name)

    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(center_x, page_height - 255, "for successfully completing")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(center_x, page_height - 295, course_name)

    pdf.setFont("Helvetica", 11)
    pdf.drawString(75, 82, f"Issued by: {issuer_name}")
    pdf.drawCentredString(center_x, 82, f"Issue date: {issue_date}")
    pdf.drawRightString(page_width - 75, 82, f"Certificate ID: {certificate_id}")

    pdf.save()
    return output_path
