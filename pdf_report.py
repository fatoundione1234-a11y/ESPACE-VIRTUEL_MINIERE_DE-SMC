"""Génération de PDF simple (texte structuré) à partir du rapport géologique Markdown-like."""
from fpdf import FPDF
import re


def _clean(text):
    # remplace markdown bold **x** et caractères non latin-1 par des équivalents simples
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf_report(sections, prospect, permis):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(27, 38, 49)
    pdf.cell(0, 12, _clean(f"ESPACE VIRTUELLE MINIERE DE SMC"), ln=True)
    pdf.set_font("Helvetica", "", 13)
    title = f"Rapport geologique - {prospect}" + (f" (permis {permis})" if permis else "")
    pdf.cell(0, 10, _clean(title), ln=True)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "Genere automatiquement - document de travail, non certifie", ln=True)
    pdf.ln(4)

    for title, text in sections.items():
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(123, 36, 28)
        pdf.set_x(10)
        pdf.cell(0, 10, _clean(title), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(30, 30, 30)
        for line in text.split("\n"):
            pdf.set_x(10)
            clean_line = _clean(line) if line.strip() else " "
            pdf.multi_cell(190, 6, clean_line)
        pdf.ln(3)

    return bytes(pdf.output(dest="S"))
