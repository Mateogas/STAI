from io import BytesIO

from reportlab.pdfgen.canvas import Canvas

from stai.medical import detect_upload_kind, extract_local_text, preflight_upload


def synthetic_pdf() -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(72, 720, "Patient Name: Alyssa Reyes")
    canvas.drawString(72, 700, "Consultation Date: 08/08/2026")
    canvas.save()
    return buffer.getvalue()


def test_detects_magic_bytes_not_filename() -> None:
    data = synthetic_pdf()
    assert detect_upload_kind(data) == "pdf"
    assert preflight_upload(data, "certificate.pdf").kind == "pdf"
    assert preflight_upload(data, "certificate.png").code == "extension_content_mismatch"


def test_local_pdf_text_layer_extraction() -> None:
    text = extract_local_text(synthetic_pdf(), "pdf")
    assert "Alyssa Reyes" in text
    assert "08/08/2026" in text


def test_active_or_embedded_pdf_content_is_rejected() -> None:
    result = preflight_upload(b"%PDF-1.7\n/JavaScript /EmbeddedFile", "certificate.pdf")
    assert result.code == "active_or_embedded_content"
