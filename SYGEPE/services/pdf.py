"""Helpers PDF communs à tous les rapports SYGEPE (ReportLab)."""

from datetime import date, datetime

from django.conf import settings
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)


def pdf_styles():
    """Retourne les styles et couleurs communs aux rapports PDF."""
    GREEN  = colors.HexColor('#2E7D32')
    ORANGE = colors.HexColor('#E65100')
    LGRAY  = colors.HexColor('#F5F5F5')
    styles = getSampleStyleSheet()
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=15, fontName='Helvetica-Bold',
        textColor=GREEN, alignment=TA_CENTER, spaceAfter=2,
    )
    sous_titre_style = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=9, textColor=colors.black,
        alignment=TA_CENTER, spaceAfter=10,
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Normal'],
        fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.white,
    )
    th_style = ParagraphStyle(
        'TH', parent=styles['Normal'],
        fontSize=8, fontName='Helvetica-Bold',
        textColor=colors.white, alignment=TA_CENTER,
    )
    td_style  = ParagraphStyle('TD',  parent=styles['Normal'], fontSize=8, textColor=colors.black)
    tdc_style = ParagraphStyle('TDC', parent=styles['Normal'], fontSize=8,
                               textColor=colors.black, alignment=TA_CENTER)
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, textColor=colors.grey, alignment=TA_CENTER,
    )
    return {
        'GREEN': GREEN, 'ORANGE': ORANGE, 'LGRAY': LGRAY,
        'titre': titre_style, 'sous_titre': sous_titre_style,
        'section': section_style, 'th': th_style,
        'td': td_style, 'tdc': tdc_style, 'footer': footer_style,
    }


def make_section_header(titre, page_w, styles):
    """Barre verte avec titre de section pour les rapports PDF."""
    t = Table([[Paragraph(f"  {titre}", styles['section'])]], colWidths=[page_w])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), styles['GREEN']),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    return t


def make_data_table(header_row, data_rows, col_widths, styles):
    """Tableau avec en-tête vert et lignes alternées (blanc / gris clair)."""
    all_rows = [header_row] + data_rows
    t = Table(all_rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1,  0),  styles['GREEN']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, styles['LGRAY']]),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
        ('LEFTPADDING',    (0, 0), (-1, -1), 5),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 5),
        ('LINEBELOW',      (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def generer_pdf_profil(employe):
    """Génère et retourne une HttpResponse PDF pour un employé donné."""
    response = HttpResponse(content_type='application/pdf')
    nom_fichier = f"profil_{employe.matricule}_{employe.nom}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'

    doc = SimpleDocTemplate(
        response, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    PAGE_W = A4[0] - 3 * cm
    GREEN  = colors.HexColor('#2E7D32')
    ORANGE = colors.HexColor('#E65100')
    LGRAY  = colors.HexColor('#F5F5F5')

    base = getSampleStyleSheet()
    titre_style      = ParagraphStyle('Titre',     parent=base['Normal'], fontSize=16,
                                      fontName='Helvetica-Bold', textColor=GREEN,
                                      alignment=TA_CENTER, spaceAfter=1)
    sous_titre_style = ParagraphStyle('SousTitre', parent=base['Normal'], fontSize=9,
                                      textColor=colors.black, alignment=TA_CENTER, spaceAfter=8)
    section_style    = ParagraphStyle('Section',   parent=base['Normal'], fontSize=10,
                                      fontName='Helvetica-Bold', textColor=colors.white)
    lbl_style        = ParagraphStyle('Lbl',       parent=base['Normal'], fontSize=8.5,
                                      fontName='Helvetica-Bold', textColor=colors.black)
    val_style        = ParagraphStyle('Val',       parent=base['Normal'], fontSize=8.5,
                                      textColor=ORANGE)
    mat_style        = ParagraphStyle('Mat',       parent=base['Normal'], fontSize=8,
                                      fontName='Helvetica-Bold', textColor=GREEN,
                                      alignment=TA_CENTER)
    footer_style     = ParagraphStyle('Footer',    parent=base['Normal'], fontSize=7,
                                      textColor=colors.grey, alignment=TA_CENTER)

    elements = []
    elements.append(Paragraph("JEC PROMO", titre_style))
    elements.append(Paragraph("FICHE EMPLOYÉ", sous_titre_style))

    # ── Helpers locaux ────────────────────────────────────────────────
    def section_header(titre):
        t = Table([[Paragraph(f"  {titre}", section_style)]], colWidths=[PAGE_W])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), GREEN),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        ]))
        return t

    def v(val):
        return '—' if val is None or str(val).strip() == '' else str(val)

    def make_grid(data, col_widths):
        t = Table(data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, LGRAY]),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
        ]))
        return t

    def row4(l1, v1, l2='', v2=None):
        return [
            Paragraph(l1, lbl_style),
            Paragraph(v(v1), val_style),
            Paragraph(l2, lbl_style),
            Paragraph(v(v2) if l2 else '', val_style),
        ]

    # ══════════════════════════════════════════════════════════════
    # SECTION 1 : INFORMATIONS GÉNÉRALES
    # ══════════════════════════════════════════════════════════════
    elements.append(section_header("INFORMATIONS GÉNÉRALES"))

    PHOTO_W = 3.5 * cm
    INFO_W  = PAGE_W - PHOTO_W - 0.3 * cm
    LBL_W   = 4.5 * cm
    VAL_W   = INFO_W - LBL_W

    side_rows = [
        [Paragraph("Matricule :", lbl_style),     Paragraph(v(employe.matricule), val_style)],
        [Paragraph("Nom et Prénoms :", lbl_style), Paragraph(employe.get_full_name().upper(), val_style)],
    ]
    if employe.date_naissance:
        side_rows.append([Paragraph("Date de Naissance :", lbl_style),
                          Paragraph(employe.date_naissance.strftime('%d/%m/%Y'), val_style)])
    if employe.lieu_naissance:
        side_rows.append([Paragraph("Lieu de Naissance :", lbl_style),
                          Paragraph(v(employe.lieu_naissance).upper(), val_style)])
    if employe.age:
        side_rows.append([Paragraph("Âge actuel :", lbl_style),
                          Paragraph(f"{employe.age} ans", val_style)])
    if employe.annee_retraite:
        side_rows.append([Paragraph("Année de Retraite :", lbl_style),
                          Paragraph(v(employe.annee_retraite), val_style)])

    info_left = make_grid(side_rows, [LBL_W, VAL_W])

    if employe.photo:
        try:
            photo_elem = RLImage(employe.photo.path, width=PHOTO_W, height=4.5 * cm)
        except Exception:
            photo_elem = Paragraph('', val_style)
    else:
        photo_elem = Paragraph('', val_style)

    photo_block = Table(
        [[photo_elem], [Paragraph(v(employe.matricule), mat_style)]],
        colWidths=[PHOTO_W],
    )
    photo_block.setStyle(TableStyle([
        ('TOPPADDING',    (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('ALIGN',         (0, 1), (0, 1),   'CENTER'),
    ]))

    top_layout = Table([[info_left, photo_block]], colWidths=[INFO_W, PHOTO_W])
    top_layout.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(top_layout)

    LBL2 = 3.5 * cm
    VAL2 = (PAGE_W - 2 * LBL2) / 2
    extra = []
    if employe.sexe:
        extra.append(row4("Sexe :", employe.get_sexe_display().upper(), "Email :", employe.email))
    elif employe.email:
        extra.append(row4("Email :", employe.email))
    if employe.num_cnps:
        extra.append(row4("Numéro CNPS :", employe.num_cnps, "Commune :", employe.commune))
    if employe.telephone:
        extra.append(row4("Téléphone :", employe.telephone,
                          "Nombre d'enfants :", employe.nombre_enfants))
    if employe.ville:
        extra.append(row4("Ville :", v(employe.ville).upper()))
    if employe.situation_familiale:
        extra.append(row4("Situation Familiale :",
                          employe.get_situation_familiale_display().upper()))
    if extra:
        elements.append(make_grid(extra, [LBL2, VAL2, LBL2, VAL2]))

    elements.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════
    # SECTION 2 : EMPLOI
    # ══════════════════════════════════════════════════════════════
    elements.append(section_header("EMPLOI"))

    LBL3 = 3.8 * cm
    VAL3 = (PAGE_W - 2 * LBL3) / 2
    emploi_rows = [
        row4("Entreprise :", "JEC PROMO",
             "Date d'embauche :",
             employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else None),
    ]
    if employe.departement:
        emploi_rows.append([Paragraph("Direction :", lbl_style),
                            Paragraph(str(employe.departement).upper(), val_style),
                            Paragraph('', lbl_style), Paragraph('', val_style)])
    emploi_rows.append(row4("Emploi :", v(employe.poste).upper(),
                            "Lieu de travail :",
                            employe.ville))
    if employe.adresse:
        emploi_rows.append([Paragraph("Adresse :", lbl_style),
                            Paragraph(employe.adresse, val_style),
                            Paragraph('', lbl_style), Paragraph('', val_style)])
    elements.append(make_grid(emploi_rows, [LBL3, VAL3, LBL3, VAL3]))
    elements.append(Spacer(1, 6))

    # ══════════════════════════════════════════════════════════════
    # SECTION 3 : ETAT AGENT
    # ══════════════════════════════════════════════════════════════
    elements.append(section_header("ETAT AGENT"))

    conges_approuves = employe.conges.filter(statut='approuve')
    jours_pris = sum((c.date_fin - c.date_debut).days + 1 for c in conges_approuves)
    today = date.today()
    if employe.date_embauche:
        mois_anciennete = (today.year - employe.date_embauche.year) * 12 + \
                          (today.month - employe.date_embauche.month)
        solde = max(0, round(mois_anciennete * 2.5) - jours_pris)
    else:
        solde = 0

    depart_retraite = '—'
    if employe.date_naissance:
        try:
            depart_retraite = employe.date_naissance.replace(
                year=employe.date_naissance.year + settings.AGE_RETRAITE
            ).strftime('%d/%m/%Y')
        except ValueError:
            depart_retraite = str(employe.date_naissance.year + settings.AGE_RETRAITE)

    LBL4 = 4.0 * cm
    VAL4 = (PAGE_W - 2 * LBL4) / 2
    etat = [
        row4("Date prise de service :",
             employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else None,
             "Solde Congés :", f"{solde} jour(s)"),
        row4("Date départ retraite :", depart_retraite,
             "Congés Pris :", f"{jours_pris} jour(s)"),
        row4("Etat :", employe.get_statut_display().upper()),
    ]
    elements.append(make_grid(etat, [LBL4, VAL4, LBL4, VAL4]))
    elements.append(Spacer(1, 12))

    elements.append(HRFlowable(width="100%", thickness=0.5,
                                color=GREEN, spaceBefore=6, spaceAfter=4))
    elements.append(Paragraph(
        f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
        footer_style,
    ))

    doc.build(elements)
    return response
