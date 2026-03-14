"""Vues de génération des rapports PDF RH SYGEPE."""

from collections import defaultdict
from datetime import date, datetime as dt

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Conge, Employe, Permission, Presence
from ..services.pdf import make_data_table, make_section_header, pdf_styles
from .decorators import get_departement_responsable, rh_ou_responsable_requis

_EXPORT_MAX_ROWS = getattr(settings, 'EXPORT_MAX_ROWS', 5_000)


# ── Helpers privés ────────────────────────────────────────────────────────────

def _trop_de_lignes(qs, label):
    """Retourne HttpResponse 400 si le queryset dépasse EXPORT_MAX_ROWS, None sinon."""
    count = qs.count()
    if count > _EXPORT_MAX_ROWS:
        return HttpResponse(
            f"Rapport limité à {_EXPORT_MAX_ROWS:,} lignes. "
            f"{label} contient {count:,} enregistrements. "
            f"Affinez la période ou contactez l'administrateur.",
            status=400,
            content_type='text/plain; charset=utf-8',
        )
    return None


def _init_pdf_rapport(filename, titre, nom_mois_upper):
    """Initialise la réponse HTTP + document ReportLab avec l'en-tête commun.

    Returns:
        (response, doc, PAGE_W, s, elems) prêts à être utilisés par la vue.
        elems contient déjà "JEC PROMO" et le sous-titre du rapport.
    """
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    doc = SimpleDocTemplate(response, pagesize=A4,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    PAGE_W = A4[0] - 3 * cm
    s = pdf_styles()
    elems = [
        Paragraph("JEC PROMO", s['titre']),
        Paragraph(f"{titre} — {nom_mois_upper}", s['sous_titre']),
    ]
    return response, doc, PAGE_W, s, elems


def _finaliser_pdf(doc, elems, s, response):
    """Ajoute le footer SYGEPE, construit le document et retourne la HttpResponse."""
    elems += [
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=0.5, color=s['GREEN'], spaceBefore=4, spaceAfter=4),
        Paragraph(
            f"Document généré le {dt.now().strftime('%d/%m/%Y à %H:%M')} — SYGEPE / JEC PROMO",
            s['footer'],
        ),
    ]
    doc.build(elems)
    return response


# ── Vues publiques ────────────────────────────────────────────────────────────

@rh_ou_responsable_requis
def rapports(request):
    """Page d'accueil des rapports téléchargeables."""
    today          = date.today()
    mois_courant   = int(request.GET.get('mois',  today.month))
    annee_courante = int(request.GET.get('annee', today.year))
    premiere = Presence.objects.order_by('date').values_list('date__year', flat=True).first()
    debut    = premiere if premiere else today.year
    annees   = list(range(today.year, debut - 1, -1))
    MOIS = [
        (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
        (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
        (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
    ]
    return render(request, 'SYGEPE/rapports.html', {
        'mois_courant': mois_courant,
        'annee_courante': annee_courante,
        'annees': annees,
        'mois_liste': MOIS,
    })


@rh_ou_responsable_requis
def rapport_presences(request):
    """PDF : Rapport mensuel de présence."""
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    presences = (
        Presence.objects
        .filter(date__year=annee, date__month=mois)
        .select_related('employe')
        .order_by('employe__nom', 'employe__prenom')
    )
    dept = get_departement_responsable(request.user)
    if dept:
        presences = presences.filter(employe__departement=dept)

    guard = _trop_de_lignes(presences, f'présences {mois:02d}/{annee}')
    if guard:
        return guard

    bilan = defaultdict(lambda: {'present': 0, 'absent': 0, 'retard': 0,
                                  'conge': 0, 'permission': 0, 'employe': None})
    for p in presences.iterator(chunk_size=500):
        key = p.employe.pk
        bilan[key]['employe'] = p.employe
        bilan[key][p.statut]  = bilan[key].get(p.statut, 0) + 1

    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response, doc, PAGE_W, s, elems = _init_pdf_rapport(
        f'rapport_presences_{annee}_{mois:02d}.pdf',
        'RAPPORT DE PRÉSENCE',
        nom_mois.upper(),
    )
    elems.append(make_section_header("RÉCAPITULATIF PAR EMPLOYÉ", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Présent', 'Absent', 'Retard',
               'En congé', 'Permission', 'Total']]
    cw   = [2.5*cm, 5.5*cm, 1.7*cm, 1.7*cm, 1.7*cm, 1.9*cm, 2.0*cm, 1.6*cm]
    rows = []
    for data in bilan.values():
        emp   = data['employe']
        total = (data['present'] + data['absent'] + data['retard']
                 + data['conge'] + data['permission'])
        rows.append([
            Paragraph(emp.matricule,           s['tdc']),
            Paragraph(emp.get_full_name(),     s['td']),
            Paragraph(str(data['present']),    s['tdc']),
            Paragraph(str(data['absent']),     s['tdc']),
            Paragraph(str(data['retard']),     s['tdc']),
            Paragraph(str(data['conge']),      s['tdc']),
            Paragraph(str(data['permission']), s['tdc']),
            Paragraph(str(total),              s['tdc']),
        ])
    if rows:
        elems.append(make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucune donnée de présence pour cette période.", s['td']))

    return _finaliser_pdf(doc, elems, s, response)


@rh_ou_responsable_requis
def rapport_conges(request):
    """PDF : Rapport des congés du mois."""
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    conges = (
        Conge.objects
        .filter(date_demande__year=annee, date_demande__month=mois)
        .select_related('employe')
        .order_by('employe__nom', 'date_debut')
    )
    dept = get_departement_responsable(request.user)
    if dept:
        conges = conges.filter(employe__departement=dept)

    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response, doc, PAGE_W, s, elems = _init_pdf_rapport(
        f'rapport_conges_{annee}_{mois:02d}.pdf',
        'RAPPORT DES CONGÉS',
        nom_mois.upper(),
    )
    elems.append(make_section_header("LISTE DES DEMANDES DE CONGÉS", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Type', 'Date début', 'Date fin', 'Durée', 'Statut']]
    cw   = [2.3*cm, 4.8*cm, 2.8*cm, 2.3*cm, 2.3*cm, 1.6*cm, 2.5*cm]
    rows = [
        [
            Paragraph(c.employe.matricule,               s['tdc']),
            Paragraph(c.employe.get_full_name(),         s['td']),
            Paragraph(c.get_type_conge_display(),        s['td']),
            Paragraph(c.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(c.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{(c.date_fin - c.date_debut).days + 1} j", s['tdc']),
            Paragraph(c.get_statut_display(),            s['tdc']),
        ]
        for c in conges
    ]
    if rows:
        elems.append(make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucun congé pour cette période.", s['td']))

    return _finaliser_pdf(doc, elems, s, response)


@rh_ou_responsable_requis
def rapport_permissions(request):
    """PDF : Rapport des permissions du mois."""
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    perms = (
        Permission.objects
        .filter(date_demande__year=annee, date_demande__month=mois)
        .select_related('employe')
        .order_by('employe__nom', 'date_debut')
    )
    dept = get_departement_responsable(request.user)
    if dept:
        perms = perms.filter(employe__departement=dept)

    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response, doc, PAGE_W, s, elems = _init_pdf_rapport(
        f'rapport_permissions_{annee}_{mois:02d}.pdf',
        'RAPPORT DES PERMISSIONS',
        nom_mois.upper(),
    )
    elems.append(make_section_header("LISTE DES DEMANDES DE PERMISSION", PAGE_W, s))

    header = [Paragraph(h, s['th']) for h in
              ['Matricule', 'Nom & Prénoms', 'Date début', 'Date fin', 'Durée', 'Motif', 'Statut']]
    cw   = [2.3*cm, 4.5*cm, 2.3*cm, 2.3*cm, 1.6*cm, 4.2*cm, 2.4*cm]
    rows = [
        [
            Paragraph(p.employe.matricule,               s['tdc']),
            Paragraph(p.employe.get_full_name(),         s['td']),
            Paragraph(p.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(p.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{p.nb_jours} j",                 s['tdc']),
            Paragraph(p.motif[:35] + ('…' if len(p.motif) > 35 else ''), s['td']),
            Paragraph(p.get_statut_display(),            s['tdc']),
        ]
        for p in perms
    ]
    if rows:
        elems.append(make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("Aucune demande de permission pour cette période.", s['td']))

    return _finaliser_pdf(doc, elems, s, response)


@rh_ou_responsable_requis
def rapport_rh_complet(request):
    """PDF : Rapport RH complet (synthèse mensuelle)."""
    today = date.today()
    mois  = int(request.GET.get('mois',  today.month))
    annee = int(request.GET.get('annee', today.year))

    dept = get_departement_responsable(request.user)

    emp_qs = Employe.objects.filter(statut='actif')
    if dept:
        emp_qs = emp_qs.filter(departement=dept)
    total_employes = emp_qs.count()

    presences_mois = Presence.objects.filter(date__year=annee, date__month=mois)
    if dept:
        presences_mois = presences_mois.filter(employe__departement=dept)

    # 1 seul aggregate au lieu de 5 filter().count() séparés
    stats = presences_mois.aggregate(
        nb_present=Count('id', filter=Q(statut='present')),
        nb_absent =Count('id', filter=Q(statut='absent')),
        nb_retard =Count('id', filter=Q(statut='retard')),
        nb_conge_p=Count('id', filter=Q(statut='conge')),
        nb_perm_p =Count('id', filter=Q(statut='permission')),
    )

    conges_mois = (Conge.objects
                   .filter(date_debut__year=annee, date_debut__month=mois)
                   .select_related('employe'))
    perms_mois  = (Permission.objects
                   .filter(date_debut__year=annee, date_debut__month=mois)
                   .select_related('employe'))
    if dept:
        conges_mois = conges_mois.filter(employe__departement=dept)
        perms_mois  = perms_mois.filter(employe__departement=dept)

    nom_mois = dt(annee, mois, 1).strftime('%B %Y')
    response, doc, PAGE_W, s, elems = _init_pdf_rapport(
        f'rapport_rh_complet_{annee}_{mois:02d}.pdf',
        'RAPPORT RH COMPLET',
        nom_mois.upper(),
    )
    elems.append(make_section_header("SYNTHÈSE GÉNÉRALE", PAGE_W, s))

    base  = getSampleStyleSheet()
    lbl_s = ParagraphStyle('Lbl', parent=base['Normal'], fontSize=8.5, fontName='Helvetica-Bold')
    val_s = ParagraphStyle('Val', parent=base['Normal'], fontSize=8.5, textColor=s['ORANGE'])

    LBL = 4 * cm
    VAL = (PAGE_W - 2 * LBL) / 2
    kpi_data = [
        [Paragraph("Total employés actifs :", lbl_s), Paragraph(str(total_employes),          val_s),
         Paragraph("Jours présents :",        lbl_s), Paragraph(str(stats['nb_present']),      val_s)],
        [Paragraph("Jours absents :",         lbl_s), Paragraph(str(stats['nb_absent']),       val_s),
         Paragraph("Jours en retard :",       lbl_s), Paragraph(str(stats['nb_retard']),       val_s)],
        [Paragraph("Jours en congé :",        lbl_s), Paragraph(str(stats['nb_conge_p']),      val_s),
         Paragraph("Jours en permission :",   lbl_s), Paragraph(str(stats['nb_perm_p']),       val_s)],
    ]
    kt = Table(kpi_data, colWidths=[LBL, VAL, LBL, VAL])
    kt.setStyle(TableStyle([
        ('TOPPADDING',     (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 5),
        ('LEFTPADDING',    (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, s['LGRAY']]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#CCCCCC')),
    ]))
    elems.append(kt)
    elems.append(Spacer(1, 8))

    # ── Congés du mois ────────────────────────────────────────────────
    elems.append(make_section_header("CONGÉS DU MOIS", PAGE_W, s))
    if conges_mois.exists():
        header = [Paragraph(h, s['th']) for h in
                  ['Employé', 'Type', 'Du', 'Au', 'Durée', 'Statut']]
        cw = [5.0*cm, 3.2*cm, 2.5*cm, 2.5*cm, 1.8*cm, 3.6*cm]
        rows = [[
            Paragraph(c.employe.get_full_name(),         s['td']),
            Paragraph(c.get_type_conge_display(),        s['td']),
            Paragraph(c.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(c.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{(c.date_fin - c.date_debut).days + 1} j", s['tdc']),
            Paragraph(c.get_statut_display(),            s['tdc']),
        ] for c in conges_mois]
        elems.append(make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("  Aucun congé ce mois.", s['td']))
    elems.append(Spacer(1, 8))

    # ── Permissions du mois ───────────────────────────────────────────
    elems.append(make_section_header("PERMISSIONS DU MOIS", PAGE_W, s))
    if perms_mois.exists():
        header = [Paragraph(h, s['th']) for h in
                  ['Employé', 'Date début', 'Date fin', 'Durée', 'Motif', 'Statut']]
        cw = [4.5*cm, 2.5*cm, 2.5*cm, 1.8*cm, 4.5*cm, 2.8*cm]
        rows = [[
            Paragraph(p.employe.get_full_name(),         s['td']),
            Paragraph(p.date_debut.strftime('%d/%m/%Y'), s['tdc']),
            Paragraph(p.date_fin.strftime('%d/%m/%Y'),   s['tdc']),
            Paragraph(f"{p.nb_jours} j",                 s['tdc']),
            Paragraph(p.motif[:40] + ('…' if len(p.motif) > 40 else ''), s['td']),
            Paragraph(p.get_statut_display(),            s['tdc']),
        ] for p in perms_mois]
        elems.append(make_data_table(header, rows, cw, s))
    else:
        elems.append(Paragraph("  Aucune permission ce mois.", s['td']))

    return _finaliser_pdf(doc, elems, s, response)
