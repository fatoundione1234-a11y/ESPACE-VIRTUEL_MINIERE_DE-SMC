"""
Modèles PDF vierges imprimables pour le terrain — ESPACE VIRTUELLE MINIÈRE DE SMC.

Génère des gabarits papier prêts à imprimer : section géologique vierge, plan de position
vierge, feuille de rapport journalier vierge, feuille de présence vierge.
"""
from fpdf import FPDF


def _clean(text):
    return text.encode("latin-1", "replace").decode("latin-1")


def _header_box(pdf, title, fields, prospect=""):
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(27, 38, 49)
    pdf.cell(0, 10, _clean(title), ln=True)
    pdf.set_draw_color(180, 180, 180)
    pdf.set_line_width(0.3)
    y0 = pdf.get_y()
    box_h = 8 * ((len(fields) + 1) // 2 + 1)
    pdf.rect(10, y0, pdf.w - 20, box_h)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    col_w = (pdf.w - 20) / 2
    for i, f in enumerate(fields):
        x = 12 + (i % 2) * col_w
        y = y0 + 2 + (i // 2) * 8
        pdf.set_xy(x, y)
        pdf.cell(col_w - 4, 6, _clean(f + " : " + "_" * 30), border=0)
    pdf.set_xy(10, y0 + box_h + 4)


def build_blank_section_pdf(prospect="", permis=""):
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    _header_box(pdf, "SECTION GEOLOGIQUE - GABARIT VIERGE",
                ["Prospect", "N Section", "Azimut section", "Echelle Horiz.",
                 "Echelle Vert.", "Date", "Geologue", "Permis"])
    y_grid_top = pdf.get_y() + 2
    grid_bottom = pdf.h - 30
    grid_left, grid_right = 10, pdf.w - 60
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.15)
    step = 10
    x = grid_left
    while x <= grid_right:
        pdf.line(x, y_grid_top, x, grid_bottom)
        x += step
    y = y_grid_top
    while y <= grid_bottom:
        pdf.line(grid_left, y, grid_right, y)
        y += step
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)
    pdf.rect(grid_left, y_grid_top, grid_right - grid_left, grid_bottom - y_grid_top)

    # légende à droite
    leg_x = grid_right + 6
    pdf.set_xy(leg_x, y_grid_top)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "LEGENDE", ln=True)
    pdf.set_x(leg_x)
    pdf.set_font("Helvetica", "", 8)
    for i in range(10):
        yy = y_grid_top + 10 + i * 9
        pdf.rect(leg_x, yy, 6, 6)
        pdf.set_xy(leg_x + 8, yy)
        pdf.cell(35, 6, "_" * 18)
    pdf.set_xy(leg_x, grid_bottom - 20)
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(pdf.w - leg_x - 10, 5, "N (nord) : fleche a tracer\nEchelle : trait 0-10-20-30m")
    return bytes(pdf.output(dest="S"))


def build_blank_plan_map_pdf(prospect="", permis=""):
    pdf = FPDF(orientation="P", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    _header_box(pdf, "PLAN DE POSITION - GABARIT VIERGE",
                ["Prospect", "Permis", "Echelle", "Date", "Leve par", "Zone UTM"])
    y_top = pdf.get_y() + 2
    bottom = pdf.h - 25
    left, right = 12, pdf.w - 12
    pdf.set_draw_color(225, 225, 225)
    pdf.set_line_width(0.15)
    step = 10
    x = left
    while x <= right:
        pdf.line(x, y_top, x, bottom)
        x += step
    y = y_top
    while y <= bottom:
        pdf.line(left, y, right, y)
        y += step
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)
    pdf.rect(left, y_top, right - left, bottom - y_top)

    # rose des vents (nord)
    cx, cy = right - 20, y_top + 20
    pdf.set_line_width(0.6)
    pdf.line(cx, cy + 12, cx, cy - 12)
    pdf.line(cx - 5, cy - 5, cx, cy - 12)
    pdf.line(cx + 5, cy - 5, cx, cy - 12)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_xy(cx - 3, cy - 22)
    pdf.cell(6, 6, "N")

    # échelle graphique
    sx = left + 10
    sy = bottom - 8
    pdf.set_line_width(0.5)
    pdf.line(sx, sy, sx + 50, sy)
    for i in range(6):
        pdf.line(sx + i * 10, sy - 2, sx + i * 10, sy + 2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_xy(sx, sy + 3)
    pdf.cell(50, 4, "0        50m       100m")
    return bytes(pdf.output(dest="S"))


def build_blank_daily_report_pdf(prospect="", permis=""):
    pdf = FPDF(orientation="P", format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    _header_box(pdf, "RAPPORT JOURNALIER - GABARIT VIERGE",
                ["Date", "Prospect", "Meteo", "Equipe presente", "Superviseur", "N pages"])
    sections = [
        ("ACTIVITES DU JOUR", 60),
        ("TROUS FORES / AVANCEMENT", 35),
        ("ECHANTILLONS PRELEVES", 25),
        ("PROBLEMES / INCIDENTS RENCONTRES", 35),
        ("RECOMMANDATIONS / ACTIONS A SUIVRE", 35),
    ]
    for title, height in sections:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(27, 38, 49)
        pdf.cell(0, 8, _clean(title), ln=True)
        y0 = pdf.get_y()
        pdf.set_draw_color(180, 180, 180)
        pdf.set_line_width(0.3)
        pdf.rect(10, y0, pdf.w - 20, height)
        n_lines = int(height // 7)
        for i in range(1, n_lines):
            yy = y0 + i * 7
            pdf.set_draw_color(230, 230, 230)
            pdf.line(12, yy, pdf.w - 12, yy)
        pdf.set_y(y0 + height + 5)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(pdf.w / 2 - 15, 6, "Signature Geologue : " + "_" * 25)
    pdf.cell(pdf.w / 2 - 15, 6, "Signature Superviseur : " + "_" * 25)
    return bytes(pdf.output(dest="S"))


def build_blank_attendance_sheet_pdf(prospect="", permis=""):
    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    _header_box(pdf, "FEUILLE DE PRESENCE - GABARIT VIERGE",
                ["Prospect", "Semaine du", "au", "Superviseur"])
    y0 = pdf.get_y() + 2
    headers = ["N", "Nom & Prenom", "Fonction", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim", "Signature"]
    widths = [8, 55, 35, 16, 16, 16, 16, 16, 16, 16, 55]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(27, 38, 49)
    pdf.set_text_color(255, 255, 255)
    x0 = 10
    pdf.set_xy(x0, y0)
    for h, w in zip(headers, widths):
        pdf.cell(w, 8, _clean(h), border=1, fill=True, align="C")
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    row_h = 8
    available_height = (pdf.h - 15) - pdf.get_y()
    n_rows = max(1, int(available_height // row_h))
    for r in range(n_rows):
        pdf.set_x(x0)
        pdf.cell(widths[0], row_h, str(r + 1), border=1, align="C")
        for w in widths[1:]:
            pdf.cell(w, row_h, "", border=1)
        pdf.ln(row_h)
    return bytes(pdf.output(dest="S"))
