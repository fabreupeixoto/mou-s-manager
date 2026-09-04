"""Report generation: PDF (reportlab) and Analytics JPG (matplotlib)."""
import io
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether
)
from flask import Response

from app import app, db, MOU, MOUPartner


USJ_BLUE = HexColor('#1a365d')
USJ_GOLD = HexColor('#D4AF37')
MPL_BLUE = '#1a365d'
MPL_GOLD = '#D4AF37'
MPL_GREEN = '#28a745'
MPL_RED = '#dc3545'
MPL_GRAY = '#6c757d'
MPL_ORANGE = '#fd7e14'


# ============================================================
# PDF EXPORT - formatted report with result cards
# ============================================================
def generate_pdf(mous, search_info='', short_name=''):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title='USJ MOU Report'
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('USTitle', parent=styles['Title'],
        fontSize=18, textColor=USJ_BLUE, alignment=TA_CENTER, spaceAfter=4)
    subtitle_style = ParagraphStyle('USSub', parent=styles['Normal'],
        fontSize=9, textColor=HexColor('#6c757d'), alignment=TA_CENTER, spaceAfter=12)
    card_title = ParagraphStyle('CardTitle', parent=styles['Normal'],
        fontSize=11, textColor=USJ_BLUE, fontName='Helvetica-Bold', spaceAfter=2)
    card_small = ParagraphStyle('CardSmall', parent=styles['Normal'],
        fontSize=7.5, textColor=HexColor('#666666'), leading=9)

    story = []
    story.append(Paragraph('USJ MOU Dashboard Report', title_style))
    subtitle_style_filter = ParagraphStyle('USSubFilter', parent=subtitle_style,
        fontSize=11, textColor=HexColor('#1a365d'), fontName='Helvetica-Bold', spaceAfter=4)
    story.append(Paragraph(search_info, subtitle_style_filter))
    meta = 'Generated: ' + datetime.now().strftime('%d %b %Y %H:%M')
    meta += ' | ' + str(len(mous)) + ' records'
    story.append(Paragraph(meta, subtitle_style))

    sep = Table([['']], colWidths=[doc.width])
    sep.setStyle(TableStyle([('LINEBELOW', (0,0), (-1,-1), 2, USJ_GOLD)]))
    story.append(sep)
    story.append(Spacer(1, 12))

    if not mous:
        story.append(Paragraph('No results matching the current filters.', subtitle_style))
    else:
        page_count = 0
        for mou in mous:
            if page_count >= 6:
                story.append(PageBreak())
                page_count = 0

            status_text = (mou.status or 'UNKNOWN')
            if status_text == 'ACTIVE':
                status_color = HexColor('#28a745')
            elif status_text == 'NOT ACTIVE':
                status_color = HexColor('#dc3545')
            else:
                status_color = HexColor('#6c757d')

            _partners = list(mou.partners) if hasattr(mou, 'partners') else []
            _pp = mou.primary_partner() if hasattr(mou, 'primary_partner') else None
            inst_obj = _pp if _pp else mou
            institution = (getattr(inst_obj, 'institution', None) or 'Unknown').replace('https://', '').replace('http://', '').strip()
            if len(_partners) > 1:
                institution += ' (+ ' + str(len(_partners) - 1) + ' more partner' + ('s' if len(_partners) > 2 else '') + ')'
            if len(institution) > 100:
                institution = institution[:98] + '...'

            fields = []
            def add_field(label, value):
                if value:
                    fields.append((label, str(value)))

            def _uniq(vals):
                seen, out = set(), []
                for v in vals:
                    if v and str(v) not in seen:
                        seen.add(str(v))
                        out.append(str(v))
                return out

            if _partners:
                add_field('Country', ', '.join(_uniq(p.country for p in _partners)))
                add_field('Country Code', ', '.join(_uniq(p.country_code for p in _partners)))
                add_field('Institution No.', ', '.join(str(p.institution_number) for p in _partners if p.institution_number))
                add_field('Partner Institutions', '; '.join(
                    (p.institution or 'Unknown') + ((' (' + p.country + ')') if p.country else '') for p in _partners))
                _sig = []
                for p in _partners:
                    names = ', '.join(
                        (s.name or '') + ((' (' + s.role + ')') if s.role else '') for s in (p.signees or []) if s and s.name)
                    if names:
                        _sig.append((p.institution or 'Unknown') + ': ' + names)
                add_field('Signees', '; '.join(_sig))
                _fac = []
                for p in _partners:
                    fnames = None
                    if p.faculties:
                        fnames = ', '.join(f.name for f in p.faculties)
                    elif p.faculty_names:
                        fnames = p.faculty_names
                    if fnames:
                        _fac.append((p.institution or 'Unknown') + ': ' + fnames)
                add_field('Faculties', '; '.join(_fac))
            else:
                add_field('Country', getattr(inst_obj, 'country', None))
                add_field('Country Code', getattr(inst_obj, 'country_code', None))
                add_field('Institution No.', getattr(inst_obj, 'institution_number', None))
            add_field('Signed Date', mou.signed_date.strftime('%d %b %Y') if mou.signed_date else '')
            add_field('Expiry Date', mou.expiry_date.strftime('%d %b %Y') if mou.expiry_date else '')
            add_field('Duration', mou.duration)
            add_field('Status', status_text)
            add_field('Notice Period', mou.notice_period)
            add_field('Website Status', mou.website_status)
            add_field('Renewal Terms', mou.renewal_terms)
            add_field('Mobility Info', mou.mobility_info)
            add_field('Other Projects', mou.other_projects)
            add_field('Additional Info', mou.additional_info)

            flags = []
            if mou.portuguese_speaking: flags.append('Portuguese-Speaking')
            if mou.asean: flags.append('ASEAN')
            if mou.mobility_available: flags.append('Mobility Available')
            if mou.signed_file: flags.append('Has Signed File')
            if flags:
                fields.append(('Flags', ', '.join(flags)))

            from reportlab.lib.colors import Color
            title_cell = Paragraph(institution, card_title)
            status_para = Paragraph(
                '<font color="white"> ' + status_text + ' </font>',
                ParagraphStyle('badge', parent=card_small, fontSize=8,
                               textColor=HexColor('#ffffff'),
                               backColor=status_color,
                               alignment=TA_CENTER, borderPadding=2)
            )

            data = [[title_cell, status_para]]
            title_table = Table(data, colWidths=[doc.width - 3*cm, 3*cm])
            title_table.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (1,0), (1,0), 'RIGHT'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(KeepTogether([title_table, Spacer(1, 4)]))

            if fields:
                row_data = [
                    [Paragraph('<b>' + l + '</b>', card_small), Paragraph(v, card_small)]
                    for l, v in fields
                ]
                c = Table(row_data, colWidths=[4*cm, doc.width - 4*cm])
                c.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 2),
                    ('RIGHTPADDING', (0,0), (-1,-1), 2),
                    ('TOPPADDING', (0,0), (-1,-1), 1),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                    ('ROWBACKGROUNDS', (0,0), (-1,-1), [HexColor('#f8f9fa'), HexColor('#ffffff')]),
                    ('BOX', (0,0), (-1,-1), 0.5, HexColor('#dee2e6')),
                    ('INNERGRID', (0,0), (-1,-1), 0.25, HexColor('#e9ecef')),
                ]))
                story.append(KeepTogether([c, Spacer(1, 14)]))

            page_count += 1

    doc.build(story)
    buf.seek(0)
    date_str = datetime.now().strftime('%Y%m%d')
    fname = f'usj_mou_report_{short_name}_{date_str}.pdf' if short_name else f'usj_mou_report_{date_str}.pdf' 
    return Response(
        buf.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename={fname}'}
    )


# ============================================================
# ANALYTICS JPG EXPORT - publication-quality image for meetings
# ============================================================
def _draw_stats(ax, stats):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    cards = [
        ('Total', stats['total'], MPL_BLUE),
        ('Active', stats['active'], MPL_GREEN),
        ('Not Active', stats['not_active'], MPL_RED),
        ('Expiring 60d', stats['expiring_60'], MPL_ORANGE),
        ('Portg-Sp.', stats['portuguese_speaking'], MPL_GOLD),
        ('Renewal Risk', stats['renewal_risk'], MPL_RED),
    ]
    n = len(cards)
    w = 10 / n
    for i, (label, val, color) in enumerate(cards):
        x = i * w
        ax.add_patch(plt.Rectangle((x + 0.15, 1), w - 0.3, 8, facecolor=color, edgecolor='none', alpha=0.85))
        ax.text(x + w/2, 6.5, str(val), ha='center', va='center', fontsize=24, fontweight='bold', color='white')
        ax.text(x + w/2, 3, label, ha='center', va='center', fontsize=11, color='white')


def _draw_status_pie(ax):
    with app.app_context():
        results = db.session.query(MOU.status, db.func.count(MOU.id)).group_by(MOU.status).all()
    if not results:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        return
    labels = [r[0] or 'Unknown' for r in results]
    sizes = [r[1] for r in results]
    colors = [MPL_GREEN if ('ACTIVE' in l.upper() and 'NOT' not in l.upper()) else
              MPL_RED if 'NOT' in l.upper() else MPL_GRAY for l in labels]
    ax.pie(sizes, labels=labels, autopct='%1.0f%%', colors=colors, startangle=90, textprops={'fontsize': 10})
    ax.set_title('MOUs by Status', fontsize=13, fontweight='bold', color=MPL_BLUE)


def _draw_country_bar(ax):
    with app.app_context():
        results = db.session.query(MOUPartner.country, db.func.count(db.func.distinct(MOUPartner.mou_id)).label('c')).filter(
            MOUPartner.country != None, MOUPartner.country != ''
        ).group_by(MOUPartner.country).order_by(db.desc('c')).limit(15).all()
    if not results:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        return
    countries = [r[0][:18] for r in results]
    counts = [r[1] for r in results]
    ax.barh(range(len(countries)), counts, color=MPL_BLUE, edgecolor='none')
    ax.set_yticks(range(len(countries)))
    ax.set_yticklabels(countries, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel('Count', fontsize=10)
    ax.set_title('Top 15 Countries', fontsize=13, fontweight='bold', color=MPL_BLUE)
    for i, v in enumerate(counts):
        ax.text(v + 0.1, i, str(v), va='center', fontsize=9, color=MPL_BLUE)
    ax.grid(axis='x', alpha=0.3)


def _draw_expiry_timeline(ax):
    today = datetime.now().date()
    one_year_later = today + timedelta(days=365)
    with app.app_context():
        results = db.session.query(
            db.func.to_char(MOU.expiry_date, 'YYYY-MM').label('month'),
            db.func.count(MOU.id).label('c')
        ).filter(
            MOU.status == 'ACTIVE', MOU.expiry_date != None,
            MOU.expiry_date >= today, MOU.expiry_date <= one_year_later
        ).group_by('month').order_by('month').all()
    if not results:
        ax.text(0.5, 0.5, 'No upcoming expiries', ha='center', va='center', transform=ax.transAxes)
        return
    months = [r[0] for r in results]
    counts = [r[1] for r in results]
    ax.fill_between(range(len(months)), counts, color=MPL_GOLD, alpha=0.3)
    ax.plot(range(len(months)), counts, color=MPL_GOLD, marker='o', linewidth=2)
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels(months, fontsize=9, rotation=45, ha='right')
    ax.set_ylabel('Count', fontsize=10)
    ax.set_title('Expiry Timeline (12 months)', fontsize=13, fontweight='bold', color=MPL_BLUE)
    ax.grid(axis='y', alpha=0.3)


def _draw_regional_pie(ax):
    regions = {
        'Europe': ['Portugal', 'Spain', 'France', 'Germany', 'Italy', 'Austria', 'Belgium', 'Croatia', 'Poland', 'Russia', 'Slovakia', 'Romania', 'Georgia', 'England'],
        'Asia': ['Philippines', 'Indonesia', 'Thailand', 'Vietnam', 'India', 'Japan', 'Korea', 'Taiwan', 'Cambodia', 'Bangladesh', 'Malaysia', 'Hong Kong SAR (CHINA)'],
        'Americas': ['Brazil', 'Argentina', 'Colombia', 'Mexico', 'Canada', 'United States of America'],
        'Africa': ['Angola', 'Mozambique', 'Cape Verde', 'Rwanda', 'Democratic Republic of Congo'],
        'Oceania': ['Australia', 'Papa New Guinea'],
    }
    with app.app_context():
        results = db.session.query(MOUPartner.country, db.func.count(db.func.distinct(MOUPartner.mou_id)).label('c')).filter(
            MOUPartner.country != None, MOUPartner.country != ''
        ).group_by(MOUPartner.country).all()
    region_counts = {}
    for country, count in results:
        for region, countries in regions.items():
            if any(c in country for c in countries):
                region_counts[region] = region_counts.get(region, 0) + count
                break
    if not region_counts:
        ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
        return
    colors = [MPL_BLUE, MPL_GOLD, MPL_GREEN, MPL_RED, '#6f42c1']
    ax.pie(list(region_counts.values()), labels=list(region_counts.keys()), autopct='%1.0f%%',
           colors=colors[:len(region_counts)], startangle=90, textprops={'fontsize': 10})
    ax.set_title('Regional Distribution', fontsize=13, fontweight='bold', color=MPL_BLUE)


def _draw_flags_bar(ax):
    today = datetime.now().date()
    with app.app_context():
        data = [
            ('Portg-Sp.', MOU.query.filter_by(portuguese_speaking=True).count()),
            ('ASEAN', MOU.query.filter_by(asean=True).count()),
            ('Mobility', MOU.query.filter_by(mobility_available=True).count()),
            ('Recent12mo', MOU.query.filter(MOU.signed_date != None, MOU.signed_date >= today - timedelta(days=365)).count()),
            ('Exp+Act', MOU.query.filter(MOU.expiry_date != None, MOU.expiry_date < today, MOU.status == 'ACTIVE').count()),
        ]
    labels = [d[0] for d in data]
    values = [d[1] for d in data]
    colors = [MPL_GOLD, MPL_GREEN, MPL_BLUE, MPL_ORANGE, MPL_RED]
    ax.bar(labels, values, color=colors, edgecolor='none')
    ax.set_title('Special Filters Distribution', fontsize=13, fontweight='bold', color=MPL_BLUE)
    ax.tick_params(axis='x', labelsize=9)
    ax.set_ylabel('Count', fontsize=10)
    ax.grid(axis='y', alpha=0.3)
    for i, v in enumerate(values):
        ax.text(i, v + 0.3, str(v), ha='center', fontsize=9, color=MPL_BLUE)


CHART_DRAWERS = {
    'stats': _draw_stats,
    'status_pie': _draw_status_pie,
    'country_bar': _draw_country_bar,
    'expiry_timeline': _draw_expiry_timeline,
    'regional_pie': _draw_regional_pie,
    'flags_bar': _draw_flags_bar,
}

CHART_LABELS = {
    'stats': 'Summary Stats Cards (Total, Active, Not Active, Expiring, etc.)',
    'status_pie': 'Status Distribution (pie chart)',
    'country_bar': 'Top 15 Countries (horizontal bar chart)',
    'expiry_timeline': 'Expiry Timeline - next 12 months (area line chart)',
    'regional_pie': 'Regional Distribution (pie chart)',
    'flags_bar': 'Special Filters Distribution (bar chart: Portuguese, ASEAN, Mobility, etc.)',
}


def generate_analytics_jpg(options, search_info=''):
    if not options:
        return None
    selected = [o for o in options if o in CHART_DRAWERS]
    if not selected:
        return None

    has_stats = 'stats' in selected
    charts = [o for o in selected if o != 'stats']
    n_charts = max(len(charts), 1)

    n_cols = 2
    n_rows = (n_charts + 1) // 2 + (1 if has_stats else 0)

    import matplotlib.gridspec as gridspec
    fig = plt.figure(figsize=(14, 3.5 + 4 * n_rows), dpi=110, facecolor='white')
    fig.suptitle('USJ MOU Dashboard - Analytics Report', fontsize=20, fontweight='bold', color=MPL_BLUE, y=0.985)
    if search_info:
        fig.text(0.5, 0.955, search_info + ' | Generated: ' + datetime.now().strftime('%d %b %Y %H:%M'),
                 ha='center', fontsize=11, color='#666666')

    gs = gridspec.GridSpec(n_rows, n_cols, figure=fig, hspace=0.5, wspace=0.25,
                            top=0.92, bottom=0.05, left=0.07, right=0.96)

    with app.app_context():
        total = MOU.query.count()
        active = MOU.query.filter_by(status='ACTIVE').count()
        not_active = MOU.query.filter_by(status='NOT ACTIVE').count()
        today = datetime.now().date()
        expiring_60 = MOU.query.filter(
            MOU.status == 'ACTIVE', MOU.expiry_date != None,
            MOU.expiry_date >= today, MOU.expiry_date <= today + timedelta(days=60)
        ).count()
        portuguese = MOU.query.filter_by(portuguese_speaking=True).count()
        renewal_risk = MOU.query.filter(
            MOU.status == 'ACTIVE', MOU.expiry_date != None, MOU.expiry_date < today
        ).count()
        stats = {
            'total': total, 'active': active, 'not_active': not_active,
            'expiring_60': expiring_60, 'portuguese_speaking': portuguese,
            'renewal_risk': renewal_risk
        }

    row = 0
    if has_stats:
        ax_stats = fig.add_subplot(gs[row, :])
        _draw_stats(ax_stats, stats)
        row += 1

    for i, chart_key in enumerate(charts):
        r, c = row + i // 2, i % 2
        ax = fig.add_subplot(gs[r, c])
        CHART_DRAWERS[chart_key](ax)

    buf = io.BytesIO()
    fig.savefig(buf, format='jpg', dpi=110, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    fname = 'mou_analytics_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.jpg'
    return Response(
        buf.getvalue(),
        mimetype='image/jpeg',
        headers={'Content-Disposition': f'attachment; filename={fname}'}
    )
