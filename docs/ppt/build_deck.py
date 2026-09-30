"""
Build the upgraded SIH26070 deck from the team's original template deck.

  .venv/Scripts/python docs/ppt/build_deck.py

* Slide 1 is kept byte-for-byte.
* Slides 2-6 keep the template frame (team badge, title, SIH logo, footer band, page number = the
  first five top-level shapes of each slide) and get newly generated content: native DrawingML shapes,
  flowcharts, highlight callouts, Lucide icons (SVG + PNG fallback), real prototype screenshots, a
  Cyclo-Nexus logo, clickable reference links and a footer tagline.
Coordinates are written in px of a 1600 x 900 canvas (the 20 in x 11.25 in slide): 1 px = 11 430 EMU.
"""
import json, os, re, shutil, subprocess, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
SRC = HERE / 'SIH26070_original.pptx'
OUT = HERE / 'SIH26070_Cyclo-Nexus.pptx'
WORK = HERE / 'build'
ICONS = HERE / 'assets' / 'icons_svg'
SHOTS = HERE / 'assets' / 'shots'
GEN = HERE / 'assets' / 'gen'
E = 11430  # EMU per px

# ── palette (template blue family + one warm accent) ─────────────────────────
BLUE = '0070C0'; NAVY = '0A2540'; INK = '1E293B'; MUTED = '5B6B80'; LINE = 'D5E2F1'
SOFT = 'EEF5FC'; SOFT2 = 'F6F9FD'; ORANGE = 'F28C28'; ORANGE_SOFT = 'FEF1E4'
RED = 'C62828'; RED_SOFT = 'FDECEC'; GREEN = '15803D'; GREEN_SOFT = 'E7F6EC'; AMBER = 'B45309'; AMBER_SOFT = 'FEF6E0'
PURPLE = '6D28D9'; PURPLE_SOFT = 'F1EAFE'; TEAL = '0E7490'; TEAL_SOFT = 'E3F4F8'; WHITE = 'FFFFFF'
FONT = 'Arial'

# ── low-level XML helpers ────────────────────────────────────────────────────
class Slide:
    def __init__(self, n):
        self.n = n; self.shapes = []; self.nid = 1000; self.rels = []  # (rid, type, target, external)
        self.rid = 100

    def id(self):
        self.nid += 1; return self.nid

    def rel(self, typ, target, external=False):
        for rid, t, tg, ex in self.rels:
            if t == typ and tg == target: return rid
        self.rid += 1; rid = f'rId{self.rid}'
        self.rels.append((rid, typ, target, external)); return rid

    def add(self, xml): self.shapes.append(xml)


def xf(x, y, w, h, rot=0, flipH=False, flipV=False):
    a = f' rot="{int(rot * 60000)}"' if rot else ''
    a += ' flipH="1"' if flipH else ''
    a += ' flipV="1"' if flipV else ''
    return f'<a:xfrm{a}><a:off x="{int(x * E)}" y="{int(y * E)}"/><a:ext cx="{max(1, int(w * E))}" cy="{max(1, int(h * E))}"/></a:xfrm>'


def fill_xml(fill, alpha=None):
    if fill is None: return '<a:noFill/>'
    a = f'<a:alpha val="{int(alpha * 1000)}"/>' if alpha is not None else ''
    return f'<a:solidFill><a:srgbClr val="{fill}">{a}</a:srgbClr></a:solidFill>'


def line_xml(color=None, w=1.0, dash=None, head=None, tail=None):
    if color is None: return '<a:ln><a:noFill/></a:ln>'
    d = f'<a:prstDash val="{dash}"/>' if dash else ''
    h = f'<a:headEnd type="{head}" w="med" len="med"/>' if head else ''
    t = f'<a:tailEnd type="{tail}" w="med" len="med"/>' if tail else ''
    return f'<a:ln w="{int(w * 12700)}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>{d}<a:round/>{h}{t}</a:ln>'


def shadow_xml(kind):
    if not kind: return ''
    blur, dist, alpha = {'soft': (22, 4, 14), 'card': (16, 3, 12), 'strong': (28, 6, 22)}[kind]
    return (f'<a:effectLst><a:outerShdw blurRad="{blur * 12700}" dist="{dist * 12700}" dir="5400000" algn="t" rotWithShape="0">'
            f'<a:srgbClr val="{NAVY}"><a:alpha val="{alpha * 1000}"/></a:srgbClr></a:outerShdw></a:effectLst>')


def run(text, size=14, bold=False, color=INK, italic=False, font=FONT, link=None, cs=None):
    """A text run. link = rId of an external hyperlink."""
    b = ' b="1"' if bold else ''
    i = ' i="1"' if italic else ''
    u = ' u="sng"' if link else ''
    hl = f'<a:hlinkClick r:id="{link}"/>' if link else ''
    csf = cs or ('Nirmala UI' if re.search(r'[ऀ-ॿ]', text) else font)
    t = escape(text)
    sp = ' xml:space="preserve"' if text != text.strip() else ''
    return (f'<a:r><a:rPr lang="en-IN" sz="{int(size * 100)}"{b}{i}{u} dirty="0">{fill_xml(color)}'
            f'<a:latin typeface="{font}"/><a:ea typeface="{font}"/><a:cs typeface="{csf}"/>{hl}</a:rPr><a:t{sp}>{t}</a:t></a:r>')


def para(runs, align='l', bullet=None, before=0, after=0, line=None, indent=0):
    if isinstance(runs, str): runs = [run(runs)]
    ppr = f' algn="{align}"'
    inner = ''
    if line: inner += f'<a:lnSpc><a:spcPct val="{int(line * 1000)}"/></a:lnSpc>'
    if before: inner += f'<a:spcBef><a:spcPts val="{int(before * 100)}"/></a:spcBef>'
    if after: inner += f'<a:spcAft><a:spcPts val="{int(after * 100)}"/></a:spcAft>'
    if bullet:
        mar = int((indent or 14) * E)
        ppr += f' marL="{mar}" indent="-{mar}"'
        inner += f'<a:buClr><a:srgbClr val="{bullet}"/></a:buClr><a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>'
    else:
        inner += '<a:buNone/>'
    return f'<a:p><a:pPr{ppr}>{inner}</a:pPr>{"".join(runs)}</a:p>'


def body(paras, anchor='t', ins=(0, 0, 0, 0), wrap=True, autofit=False):
    l, t, r, b = (int(v * E) for v in ins)
    fit = '<a:normAutofit/>' if autofit else ''
    return (f'<p:txBody><a:bodyPr wrap="{"square" if wrap else "none"}" lIns="{l}" tIns="{t}" rIns="{r}" bIns="{b}" '
            f'anchor="{anchor}" rtlCol="0">{fit}</a:bodyPr><a:lstStyle/>{"".join(paras)}</p:txBody>')


def shape(s, x, y, w, h, prst='rect', fill=None, line=None, lw=1.0, dash=None, radius=None, shadow=None,
          paras=None, anchor='t', ins=(0, 0, 0, 0), rot=0, alpha=None, adj=None, name='Shape', flipH=False, flipV=False):
    sid = s.id()
    av = ''
    if radius is not None: av = f'<a:gd name="adj" fmla="val {int(radius)}"/>'
    if adj: av = ''.join(f'<a:gd name="{k}" fmla="val {int(v)}"/>' for k, v in adj.items())
    txb = body(paras, anchor, ins) if paras else body([para([run('', 10)])], anchor, ins)
    s.add(f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name} {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
          f'<p:spPr>{xf(x, y, w, h, rot, flipH, flipV)}<a:prstGeom prst="{prst}"><a:avLst>{av}</a:avLst></a:prstGeom>'
          f'{fill_xml(fill, alpha)}{line_xml(line, lw, dash)}{shadow_xml(shadow)}</p:spPr>{txb}</p:sp>')


def text(s, x, y, w, h, paras, anchor='t', ins=(0, 0, 0, 0), name='Text'):
    sid = s.id()
    s.add(f'<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="{name} {sid}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
          f'<p:spPr>{xf(x, y, w, h)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
          f'{body(paras, anchor, ins)}</p:sp>')


def line(s, x1, y1, x2, y2, color=BLUE, w=1.5, dash=None, tail='triangle', head=None):
    sid = s.id()
    x, y = min(x1, x2), min(y1, y2)
    s.add(f'<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="{sid}" name="Connector {sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
          f'<p:spPr>{xf(x, y, abs(x2 - x1), abs(y2 - y1), flipH=x2 < x1, flipV=y2 < y1)}<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
          f'{line_xml(color, w, dash, head, tail)}</p:spPr></p:cxnSp>')


def picture(s, png, x, y, w, h, svg=None, prst='rect', radius=None, border=None, bw=1.0, shadow=None, descr='', crop=None):
    """Embed a PNG (and optional SVG vector, which PowerPoint shows instead of the PNG)."""
    sid = s.id()
    rp = s.rel('image', media(png))
    ext = ''
    if svg:
        rs = s.rel('image', media(svg))
        ext = (f'<a:extLst><a:ext uri="{{96DAC541-7B7A-43D3-8B79-37D633B846F1}}"><asvg:svgBlip '
               f'xmlns:asvg="http://schemas.microsoft.com/office/drawing/2016/SVG/main" r:embed="{rs}"/></a:ext></a:extLst>')
    av = f'<a:gd name="adj" fmla="val {int(radius)}"/>' if radius is not None else ''
    src = ''
    if crop:
        l, t, r, b = crop
        src = f'<a:srcRect l="{int(l * 1000)}" t="{int(t * 1000)}" r="{int(r * 1000)}" b="{int(b * 1000)}"/>'
    s.add(f'<p:pic><p:nvPicPr><p:cNvPr id="{sid}" name="Picture {sid}" descr="{escape(descr)}"/>'
          f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
          f'<p:blipFill><a:blip r:embed="{rp}">{ext}</a:blip>{src}<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
          f'<p:spPr>{xf(x, y, w, h)}<a:prstGeom prst="{prst}"><a:avLst>{av}</a:avLst></a:prstGeom>'
          f'{line_xml(border, bw) if border else "<a:ln><a:noFill/></a:ln>"}{shadow_xml(shadow)}</p:spPr></p:pic>')


# ── media registry: copies files into ppt/media once, returns the relative target ──
MEDIA = {}
def media(path):
    path = Path(path)
    if str(path) in MEDIA: return MEDIA[str(path)]
    name = f'cn_{len(MEDIA) + 1}{path.suffix.lower()}'
    shutil.copy(path, WORK / 'ppt' / 'media' / name)
    MEDIA[str(path)] = f'../media/{name}'
    return MEDIA[str(path)]


# ── icons: Lucide SVG recoloured, with rendered PNG fallback ─────────────────
ICON_JOBS = []
def icon_files(name, color, size=256):
    svg = GEN / f'{name}_{color}.svg'
    png = GEN / f'{name}_{color}.png'
    if not svg.exists():
        src = (ICONS / f'{name}.svg').read_text(encoding='utf-8').replace('COLOR', f'#{color}')
        svg.write_text(src, encoding='utf-8')
    if not png.exists(): ICON_JOBS.append({'svg': str(svg), 'png': str(png), 'size': size})
    return png, svg


def icon(s, name, x, y, size, color):
    png, svg = icon_files(name, color)
    ICON_USES.append((s, png, x, y, size, svg))


ICON_USES = []  # rendered after all PNGs exist


def icon_badge(s, name, cx, cy, d, bg, fg=WHITE, ring=None, shadow='card'):
    """Icon centred in a filled circle — the deck's visual motif."""
    shape(s, cx - d / 2, cy - d / 2, d, d, 'ellipse', fill=bg, line=ring, lw=2 if ring else 1, shadow=shadow, name='Badge')
    k = d * 0.52
    icon(s, name, cx - k / 2, cy - k / 2, k, fg)


LOGO_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="#{bg}"/>
<path d="M16 16c0-5 3.5-8.5 9-8-4 .6-6.6 3.4-7 8z M16 16c0 5-3.5 8.5-9 8 4-.6 6.6-3.4 7-8z M16 16c-5 0-8.5-3.5-8-9 .6 4 3.4 6.6 8 7z M16 16c5 0 8.5 3.5 8 9-.6-4-3.4-6.6-8-7z" fill="#{fg}"/>
<circle cx="16" cy="16" r="2.6" fill="#{bg}" stroke="#{fg}" stroke-width="1.6"/></svg>'''


def logo_files(bg, fg):
    svg = GEN / f'logo_{bg}_{fg}.svg'; png = GEN / f'logo_{bg}_{fg}.png'
    svg.write_text(LOGO_SVG.format(bg=bg, fg=fg), encoding='utf-8')
    if not png.exists(): ICON_JOBS.append({'svg': str(svg), 'png': str(png), 'size': 256})
    return png, svg


def logo(s, x, y, d, bg=BLUE, fg=WHITE):
    png, svg = logo_files(bg, fg)
    ICON_USES.append((s, png, x, y, d, svg))


# ── building blocks ──────────────────────────────────────────────────────────
def section_heading(s, x, y, w, label, icon_name):
    icon_badge(s, icon_name, x + 15, y + 17, 30, BLUE, shadow=None)
    text(s, x + 40, y, w - 40, 34, [para([run(label, 19, True, BLUE)])], anchor='ctr', name='Heading')


def card(s, x, y, w, h, fill=WHITE, line=LINE, radius=9000, shadow='card', lw=1.0):
    shape(s, x, y, w, h, 'roundRect', fill=fill, line=line, lw=lw, radius=radius, shadow=shadow, name='Card')


def pill(s, x, y, w, h, label, fill, color, size=12, bold=True, line=None, icon_name=None):
    shape(s, x, y, w, h, 'roundRect', fill=fill, line=line, radius=50000, name='Pill')
    if icon_name:
        icon(s, icon_name, x + 10, y + (h - 16) / 2, 16, color)
        text(s, x + 30, y, w - 36, h, [para([run(label, size, bold, color)], 'l')], anchor='ctr')
    else:
        text(s, x, y, w, h, [para([run(label, size, bold, color)], 'ctr')], anchor='ctr')


def footer_tagline(s, tagline):
    """Tagline inside the template's blue footer band (band: y 833-898; page number sits at the right)."""
    logo(s, 54, 846, 38, bg=WHITE, fg=BLUE)
    text(s, 102, 836, 1000, 58, [
        para([run('CYCLO-NEXUS', 15, True, WHITE), run('   |   ', 13, False, 'A9CDEE'), run(tagline, 13, False, WHITE, italic=True)]),
        para([run('Team Tikka Techies  ·  SIH26070  ·  Ministry of Earth Sciences  ·  Disaster Management', 10.5, False, 'CFE3F7')], before=1),
    ], anchor='ctr', name='Footer tagline')


# ════════════════════════════════════════════════════════════════════════════
# Slide 2 — Proposed solution
# ════════════════════════════════════════════════════════════════════════════
def slide2(s):
    section_heading(s, 54, 150, 1000, 'Proposed Solution: detailed explanation of the proposed solution', 'sparkles')
    steps = [
        ('IDENTIFY', 'scan-eye', BLUE, ['YOLO-OBB oriented boxes on the eye and cloud system', 'Physics (DAV) check flags developing systems early'], 'Every 30 min'),
        ('CLASSIFY', 'layers', TEAL, ['IMD 7-tier scale, Depression to Super Cyclone', 'Yellow / Orange / Red alert levels'], 'D  →  SuCS'),
        ('PREDICT', 'route', PURPLE, ['6 to 72 h track, wind and pressure', 'ConvLSTM + Bi-GRU deep learning'], '+6 h … +72 h'),
        ('WARN', 'bell-ring', ORANGE, ['Auto-advisories for fishers, public, officials', 'English, Hindi and local languages'], 'EN  ·  हिंदी'),
    ]
    x0, y0, cw, ch, gap = 54, 196, 226, 236, 30
    for i, (title, ic, col, pts, chip) in enumerate(steps):
        x = x0 + i * (cw + gap)
        card(s, x, y0 + 22, cw, ch - 22)
        icon_badge(s, ic, x + cw / 2, y0 + 30, 58, col, ring=WHITE)
        shape(s, x + cw - 40, y0 + 34, 28, 28, 'ellipse', fill=SOFT, line=None,
              paras=[para([run(str(i + 1), 12, True, col)], 'ctr')], anchor='ctr')
        text(s, x + 14, y0 + 66, cw - 28, 30, [para([run(title, 17, True, col)], 'ctr')], anchor='ctr')
        text(s, x + 16, y0 + 100, cw - 30, ch - 110,
             [para([run(p, 12.5, False, INK)], bullet=col, after=5, indent=12) for p in pts])
        pill(s, x + 30, y0 + ch - 42, cw - 60, 28, chip, SOFT, col, 12)
        if i < 3:
            ax = x + cw + 3
            shape(s, ax, y0 + 118, gap - 6, 26, 'rightArrow', fill=col, adj={'adj1': 50000, 'adj2': 60000}, name='Flow arrow')

    # Working prototype in a browser frame
    bx, by, bw, bh = 1090, 196, 456, 236
    card(s, bx, by, bw, bh, fill=WHITE, line='C9D8EA', shadow='soft', radius=5000)
    shape(s, bx, by, bw, 26, 'rect', fill='EEF2F7', line=None, name='Browser bar')
    for k, c in enumerate(['EF4444', 'F59E0B', '22C55E']):
        shape(s, bx + 12 + k * 14, by + 9, 8, 8, 'ellipse', fill=c, name='Dot')
    text(s, bx + 60, by + 2, 300, 22, [para([run('cyclo-nexus  ·  live dashboard', 10, False, MUTED)])], anchor='ctr')
    picture(s, SHOTS / 'hero.png', bx + 4, by + 28, bw - 8, bh - 32, descr='Cyclo-Nexus home page', crop=(0, 0, 0, 8))
    pill(s, bx + bw - 240, by + bh - 34, 232, 26, 'Working prototype · demo scenario', NAVY, WHITE, 10.5)

    # How it addresses the problem
    section_heading(s, 54, 452, 740, 'How it addresses the problem', 'target')
    rows = [
        ('Fragmented data', 'Many agencies, many formats', 'INSAT-3DS + GPM IMERG + JTWC/IBTrACS fused into one grid', 'boxes'),
        ('Manual tracking', 'Slow and error-prone', 'Automated 30-minute pipeline, every satellite cycle', 'timer'),
        ('Forecast uncertainty', 'Weak systems get missed', 'Physics check + validated watch threshold flag weak systems', 'radar'),
        ('Coastal risk', 'High population exposure', 'People-in-path estimate, landfall ETA, EN/HI alerts', 'users'),
    ]
    y = 494
    for prob, sub, sol, ic in rows:
        shape(s, 54, y, 250, 64, 'roundRect', fill=RED_SOFT, line=None, radius=14000)
        icon(s, 'triangle-alert', 68, y + 12, 18, RED)
        text(s, 92, y + 8, 206, 50, [para([run(prob, 13.5, True, RED)]), para([run(sub, 11, False, '7F1D1D')], before=1)])
        shape(s, 316, y + 18, 28, 28, 'ellipse', fill=BLUE, line=None, name='Arrow bubble')
        icon(s, 'arrow-right', 322, y + 24, 16, WHITE)
        shape(s, 356, y, 440, 64, 'roundRect', fill=SOFT, line=None, radius=14000)
        icon_badge(s, ic, 384, y + 32, 36, WHITE, fg=BLUE, shadow=None, ring=LINE)
        text(s, 412, y, 376, 64, [para([run(sol, 13, True, NAVY)])], anchor='ctr')
        y += 80

    # Innovation and uniqueness
    section_heading(s, 820, 452, 730, 'Innovation and uniqueness of the solution', 'rocket')
    inno = [
        ('satellite', 'Indian + NASA fusion', 'INSAT-3DS and GPM IMERG in one 4-channel AI tensor', '4 sources', BLUE),
        ('shield-check', 'Hard-fail quality gates', 'Corrupt or blank tensors are blocked before inference', '0 bad inputs', GREEN),
        ('eye', 'Early weak-system flags', 'Satellite watch areas before a system is named', 'Watch layer', PURPLE),
        ('badge-check', 'Clearly labelled, open', 'Official vs AI tags; low-cost open-source stack', 'Official first', ORANGE),
    ]
    for k, (ic, t1, t2, tag, col) in enumerate(inno):
        cx = 820 + (k % 2) * 370; cy = 494 + (k // 2) * 160
        card(s, cx, cy, 355, 146)
        icon_badge(s, ic, cx + 44, cy + 44, 52, col)
        text(s, cx + 82, cy + 22, 262, 48, [para([run(t1, 15, True, NAVY)])], anchor='ctr')
        text(s, cx + 22, cy + 78, 318, 40, [para([run(t2, 12, False, MUTED)])])
        pill(s, cx + 22, cy + 112, 128, 24, tag, SOFT, col, 10.5)
    footer_tagline(s, 'Detect early. Warn clearly. Protect every coast.')


# ════════════════════════════════════════════════════════════════════════════
# Slide 3 — Technical approach
# ════════════════════════════════════════════════════════════════════════════
def slide3(s):
    section_heading(s, 54, 150, 1040, 'Technologies to be used: architecture, one signed and monitored path', 'network')
    srcs = [('INSAT-3DS (ISRO)', 'IR + WV · every 30 min', 'satellite', BLUE), ('GPM IMERG (NASA)', 'Rain rate · 30 min', 'cloud-rain', TEAL),
            ('JTWC + IBTrACS', 'Official warnings + tracks', 'radar', PURPLE), ('Open-Meteo + GIBS', 'Wind, SST, map tiles', 'globe', ORANGE)]
    for i, (t1, t2, ic, col) in enumerate(srcs):
        x = 54 + i * 262
        card(s, x, 192, 246, 62, shadow='card')
        icon_badge(s, ic, x + 32, 223, 40, col, shadow=None)
        text(s, x + 60, 196, 182, 54, [para([run(t1, 13.5, True, NAVY)]), para([run(t2, 11, False, MUTED)], before=1)], anchor='ctr')
        line(s, x + 123, 254, x + 123, 282, col, 1.75)

    # two server groups
    for gx, gw, label, col, boxes in [
        (54, 508, 'ORACLE ALWAYS-FREE VM  ·  MUMBAI', BLUE, [('AI inference', 'FastAPI · PyTorch\nYOLO-OBB · ConvLSTM + GRU', 'cpu'),
                                                              ('Pipeline runner', 'Calibrate + fuse · 6-frame tensor\nPhysics detector', 'workflow')]),
        (590, 508, 'HOSTINGER BACKEND', TEAL, [('Express API', 'Zod + HMAC checks\nAdvisories · REST', 'server'),
                                              ('MySQL + workers', 'Official feed · wind grid\nHealth checks', 'database')])]:
        shape(s, gx, 284, gw, 196, 'roundRect', fill=SOFT2, line=col, dash='dash', lw=1.25, radius=6000, name='Group')
        text(s, gx + 14, 290, gw - 28, 22, [para([run(label, 11.5, True, col)])], anchor='ctr')
        for k, (t1, t2, ic) in enumerate(boxes):
            bx = gx + 14 + k * (gw - 28 + 14) / 2
            bw = (gw - 28 - 14) / 2
            card(s, bx, 318, bw, 148)
            icon_badge(s, ic, bx + bw / 2, 350, 44, col)
            text(s, bx + 8, 378, bw - 16, 84, [para([run(t1, 14, True, NAVY)], 'ctr')] +
                 [para([run(l, 11, False, MUTED)], 'ctr', before=1) for l in t2.split('\n')])
    # signed hop
    line(s, 562, 382, 590, 382, ORANGE, 2)
    shape(s, 556, 364, 40, 40, 'ellipse', fill=ORANGE, line=WHITE, lw=2, shadow='card', name='HMAC')
    icon(s, 'lock', 566, 374, 20, WHITE)
    pill(s, 460, 484, 232, 20, 'HMAC-SHA256 signed + gzip hop', ORANGE_SOFT, ORANGE, 9.5)

    # outputs
    line(s, 844, 480, 844, 508, NAVY, 1.75)
    shape(s, 590, 508, 330, 64, 'roundRect', fill=NAVY, line=None, radius=14000, shadow='card')
    icon(s, 'monitor-smartphone', 608, 524, 32, WHITE)
    text(s, 650, 508, 262, 64, [para([run('React web app', 14, True, WHITE)]), para([run('Map · advisories · impact · expert panel', 10.5, False, 'BFD3EA')], before=1)], anchor='ctr')
    line(s, 920, 540, 944, 540, ORANGE, 2)
    shape(s, 944, 508, 154, 64, 'roundRect', fill=ORANGE, line=None, radius=14000, shadow='card')
    icon(s, 'users', 956, 528, 24, WHITE)
    text(s, 986, 508, 108, 64, [para([run('Citizens, fishers,', 11, True, WHITE)]), para([run('disaster officials', 11, True, WHITE)])], anchor='ctr')
    for k, (num, lab) in enumerate([('4', 'data sources'), ('2', 'servers'), ('1', 'web app')]):
        x = 54 + k * 172
        shape(s, x, 508, 160, 64, 'roundRect', fill=SOFT, line=None, radius=14000)
        text(s, x + 12, 508, 60, 64, [para([run(num, 30, True, BLUE)])], anchor='ctr')
        text(s, x + 58, 508, 100, 64, [para([run(lab, 12.5, True, NAVY)])], anchor='ctr')

    # Tech stack panel
    card(s, 1120, 150, 430, 422, shadow='soft')
    shape(s, 1120, 150, 430, 54, 'roundRect', fill=NAVY, line=None, radius=12000)
    shape(s, 1120, 180, 430, 24, 'rect', fill=NAVY, line=None)
    icon(s, 'layers', 1138, 164, 26, WHITE)
    text(s, 1174, 150, 360, 54, [para([run('TECH STACK', 17, True, WHITE)])], anchor='ctr')
    stack = [('Frontend', 'monitor-smartphone', BLUE, ['React', 'Vite', 'MapLibre GL']),
             ('Backend', 'server', TEAL, ['Node.js', 'Express', 'MySQL']),
             ('AI / ML', 'brain', PURPLE, ['PyTorch', 'YOLO-OBB', 'ConvLSTM', 'FastAPI']),
             ('Data', 'database', ORANGE, ['INSAT-3DS', 'GPM IMERG', 'JTWC', 'IBTrACS']),
             ('Deploy', 'rocket', GREEN, ['Oracle Cloud', 'Hostinger', 'Vercel'])]
    for k, (lab, ic, col, chips) in enumerate(stack):
        y = 218 + k * 70
        icon_badge(s, ic, 1152, y + 22, 36, col, shadow=None)
        text(s, 1178, y + 6, 120, 32, [para([run(lab, 13, True, NAVY)])], anchor='ctr')
        cx = 1178
        for ch in chips:
            wch = 14 + len(ch) * 7.2
            if cx + wch > 1538: cx = 1178; y += 0  # keep one row; widths are sized to fit
            pill(s, cx, y + 38, wch, 22, ch, SOFT, col, 10, True)
            cx += wch + 6

    # Methodology flowchart
    section_heading(s, 54, 592, 1400, 'Methodology and process for implementation: flow chart', 'git-branch')
    flow = [('1', 'Fetch', 'every 30 min', 'satellite', 'INSAT-3DS + GPM IMERG', BLUE),
            ('2', 'Merge', '6 frames · 15 h window', 'layers', '[4×1024×1024] tensor', TEAL),
            ('3', 'AI inference', 'detect · classify · forecast', 'brain', 'YOLO-OBB → ConvLSTM', ORANGE),
            ('4', 'Match + alert', 'official tracks first', 'shield-check', 'JTWC / IBTrACS check', PURPLE),
            ('5', 'Publish', 'live map · advisories', 'bell-ring', 'REST API → React map', GREEN)]
    fx, fw = 54, 298
    for k, (num, t1, t2, ic, det, col) in enumerate(flow):
        x = fx + k * fw
        shape(s, x, 634, fw + 14, 88, 'chevron' if k else 'homePlate', fill=col, line=None, adj={'adj': 26000}, shadow='card', name='Flow')
        tx = x + (46 if k else 24)
        icon_badge(s, ic, tx + 20, 678, 40, WHITE, fg=col, shadow=None)
        text(s, tx + 48, 640, fw - 110, 76, [para([run(f'{num}  {t1}', 15, True, WHITE)]), para([run(t2, 11, False, WHITE)], before=1)], anchor='ctr')
        text(s, x + 10, 728, fw - 10, 26, [para([run(det, 11.5, True, col, font='Consolas')], 'ctr')], anchor='ctr')
    shape(s, 54, 766, 1496, 50, 'roundRect', fill=SOFT, line=None, radius=30000)
    icon(s, 'lock', 72, 779, 24, BLUE)
    text(s, 106, 766, 1420, 50, [para([run('Every hop is signed (HMAC-SHA256), validated (Zod + tensor checks) and health-monitored — ', 13.5, False, NAVY, italic=True),
                                       run('from satellite pixel to citizen.', 13.5, True, BLUE, italic=True)])], anchor='ctr')
    footer_tagline(s, 'One signed, monitored path from satellite pixel to citizen.')


# ════════════════════════════════════════════════════════════════════════════
# Slide 4 — Feasibility and viability
# ════════════════════════════════════════════════════════════════════════════
def slide4(s):
    section_heading(s, 54, 150, 1000, 'Analysis of the feasibility of the idea', 'circle-check-big')
    feas = [('circle-check-big', 'Feasible', '4', 'free public data sources', 'ISRO, NASA, JTWC and NOAA — no paid feeds', GREEN),
            ('indian-rupee', 'Low cost', '₹0', 'licence cost', 'Open-source stack on free cloud tiers', BLUE),
            ('monitor-smartphone', 'Scalable', 'Any', 'phone or browser', 'Cloud-hosted web app; 15 MB per AI cycle', PURPLE)]
    for k, (ic, t1, big, unit, desc, col) in enumerate(feas):
        x = 54 + k * 336
        card(s, x, 192, 322, 132)
        icon_badge(s, ic, x + 42, 234, 54, col)
        text(s, x + 80, 202, 230, 32, [para([run(t1, 17, True, NAVY)])], anchor='ctr')
        text(s, x + 80, 234, 230, 42, [para([run(big + ' ', 28, True, col), run(unit, 12.5, True, MUTED)])], anchor='ctr')
        text(s, x + 20, 282, 290, 36, [para([run(desc, 11.5, False, MUTED)])], anchor='ctr')
    # validation evidence panel
    card(s, 1070, 192, 480, 132, fill=NAVY, line=None, shadow='soft')
    icon(s, 'flask-conical', 1088, 206, 24, 'FDBA74')
    text(s, 1120, 200, 420, 30, [para([run('Validated on real satellite data', 14.5, True, WHITE)])], anchor='ctr')
    for k, (num, lab) in enumerate([('20', 'real INSAT-3DS +\nIMERG cases'), ('0 / 6', 'false-alarm days\n(threshold 0.95)'), ('83→15', 'MB per 6-frame\nAI window')]):
        x = 1088 + k * 154
        text(s, x, 236, 150, 44, [para([run(num, 24, True, 'FDBA74')])], anchor='ctr')
        text(s, x, 278, 150, 40, [para([run(l, 10.5, False, 'C7D6EA')]) for l in lab.split('\n')])

    # Risk table (native shapes)
    tx, ty = 54, 346
    cols = [(tx, 330, 'Potential challenges and risks'), (tx + 330, 106, 'Probability'), (tx + 436, 106, 'Impact'), (tx + 542, 456, 'Strategies for overcoming these challenges')]
    shape(s, tx, ty, 998, 44, 'roundRect', fill=NAVY, line=None, radius=14000)
    for x, w, h in cols:
        text(s, x + 14, ty, w - 20, 44, [para([run(h, 12.5, True, WHITE)], 'l' if w > 200 else 'ctr')], anchor='ctr')
    risks = [('Large satellite files (~24 MB each)', 'database', 'High', 'High', 'uint8 transport, compression and frame caching'),
             ('Cloud imagery hides the cyclone centre', 'cloud-rain', 'Medium', 'High', 'Official tracks first; add rainfall (IMERG) data'),
             ('False alarms from monsoon clouds', 'triangle-alert', 'Medium', 'Medium', 'Persistence, sea-temperature and organisation checks'),
             ('Delayed data', 'clock', 'Low', 'Medium', 'Live health checks and a "data delayed" banner'),
             ('Misinformation', 'shield-alert', 'Low', 'High', 'Official vs AI labels; users directed to IMD')]
    lvl = {'High': (RED_SOFT, RED), 'Medium': (AMBER_SOFT, AMBER), 'Low': (GREEN_SOFT, GREEN)}
    for k, (risk, ic, p, i, strat) in enumerate(risks):
        y = ty + 52 + k * 72
        shape(s, tx, y, 998, 64, 'roundRect', fill=WHITE if k % 2 else SOFT2, line=LINE, radius=12000)
        icon_badge(s, ic, tx + 26, y + 32, 32, SOFT, fg=BLUE, shadow=None)
        text(s, tx + 50, y, 276, 64, [para([run(risk, 12.5, True, INK)])], anchor='ctr')
        for x, v in [(tx + 342, p), (tx + 448, i)]:
            bg, fg = lvl[v]
            pill(s, x, y + 19, 84, 26, v, bg, fg, 11)
        icon(s, 'check', tx + 552, y + 23, 18, GREEN)
        text(s, tx + 576, y, 414, 64, [para([run(strat, 12.5, False, INK)])], anchor='ctr')

    # Quality gate flowchart
    gx = 1070
    card(s, gx, 346, 480, 404, fill=SOFT2, line=LINE, shadow=None)
    text(s, gx + 20, 354, 440, 30, [para([run('Hard-fail data quality gate', 15, True, BLUE)])], anchor='ctr')
    shape(s, gx + 70, 392, 340, 48, 'roundRect', fill=WHITE, line=BLUE, lw=1.5, radius=20000,
          paras=[para([run('Raw satellite tensor · 4×1024×1024', 12.5, True, NAVY)], 'ctr')], anchor='ctr')
    line(s, gx + 240, 440, gx + 240, 462, BLUE, 1.75)
    shape(s, gx + 70, 462, 340, 48, 'roundRect', fill=WHITE, line=BLUE, lw=1.5, radius=20000,
          paras=[para([run('Normalise 0–1 + variance check', 12.5, True, NAVY)], 'ctr')], anchor='ctr')
    line(s, gx + 240, 510, gx + 240, 530, BLUE, 1.75)
    shape(s, gx + 150, 530, 180, 96, 'diamond', fill=BLUE, line=None, shadow='card',
          paras=[para([run('σ > 0.02 ?', 15, True, WHITE)], 'ctr')], anchor='ctr')
    line(s, gx + 150, 578, gx + 90, 578, RED, 2, tail=None); line(s, gx + 90, 578, gx + 90, 648, RED, 2)
    line(s, gx + 330, 578, gx + 390, 578, GREEN, 2, tail=None); line(s, gx + 390, 578, gx + 390, 648, GREEN, 2)
    text(s, gx + 94, 552, 50, 22, [para([run('NO', 11, True, RED)])])
    text(s, gx + 340, 552, 50, 22, [para([run('YES', 11, True, GREEN)])])
    for bx, col, soft, t1, t2, ic in [(gx + 20, RED, RED_SOFT, 'BLOCK', 'log + alert', 'x-octagon'), (gx + 262, GREEN, GREEN_SOFT, 'PASS', 'to AI inference', 'circle-check-big')]:
        shape(s, bx, 648, 198, 84, 'roundRect', fill=soft, line=col, lw=1.5, radius=14000)
        icon(s, ic, bx + 16, 672, 34, col)
        text(s, bx + 58, 648, 136, 84, [para([run(t1, 16, True, col)]), para([run(t2, 11.5, False, col)])], anchor='ctr')

    shape(s, 54, 766, 1496, 50, 'roundRect', fill=SOFT, line=None, radius=30000)
    icon(s, 'shield-check', 72, 779, 24, BLUE)
    text(s, 106, 766, 1420, 50, [para([run('The architecture anticipates data failure, model-input failure, mobile performance limits and API limits — ', 13.5, False, NAVY, italic=True),
                                       run('and says so on screen.', 13.5, True, BLUE, italic=True)])], anchor='ctr')
    footer_tagline(s, 'Built on free public data, open source and free cloud tiers.')


# ════════════════════════════════════════════════════════════════════════════
# Slide 5 — Impact and benefits
# ════════════════════════════════════════════════════════════════════════════
def slide5(s):
    section_heading(s, 54, 150, 1000, 'Potential impact on the target audience', 'target')
    stats = [('waves', '11,098 km', "India's coastline", 'MoPSW revision, Apr 2025', BLUE),
             ('fish', '3.77 million', 'marine fisherfolk', 'CMFRI census 2016', TEAL),
             ('timer', '~30%', 'less damage with a 24 h warning', 'Global Commission on Adaptation', ORANGE),
             ('life-buoy', '~1 million', 'evacuated for Cyclone Phailin', 'Odisha, 2013 (World Bank)', GREEN)]
    for k, (ic, big, lab, src, col) in enumerate(stats):
        x = 54 + k * 378
        card(s, x, 192, 364, 124)
        icon_badge(s, ic, x + 44, 246, 56, col)
        text(s, x + 84, 200, 272, 56, [para([run(big, 30, True, col)])], anchor='ctr')
        text(s, x + 84, 254, 272, 26, [para([run(lab, 13, True, NAVY)])], anchor='ctr')
        text(s, x + 84, 280, 272, 24, [para([run(src, 10.5, False, MUTED, italic=True)])], anchor='ctr')
    text(s, 54, 332, 140, 36, [para([run('Target users:', 14, True, NAVY)])], anchor='ctr')
    for k, (lab, ic) in enumerate([('Coastal residents', 'map-pin'), ('Fisherfolk', 'anchor'), ('Disaster officials', 'building-2'), ('Researchers', 'microscope')]):
        pill(s, 190 + k * 212, 332, 200, 36, lab, SOFT, BLUE, 12.5, line=LINE, icon_name=ic)

    section_heading(s, 54, 386, 1000, 'Benefits of the solution (social, economic, environmental, etc.)', 'heart-pulse')
    ben = [('users', 'Social', BLUE, ['Earlier warnings in local language save lives',
                                     'Phailin (2013): ~1 million evacuated; deaths far below the ~10,000 of 1999',
                                     'Alerts reach any phone or browser']),
           ('indian-rupee', 'Economic and livelihood', ORANGE, ['A 24 h warning can cut damage by ~30%',
                                                                'Amphan (2020): ~US$14 billion (≈ ₹1 lakh crore) losses in India',
                                                                '"Do not go to sea" alerts protect boats and nets']),
           ('leaf', 'Environmental', GREEN, ['Rainfall hot-spot tracking supports flood preparedness',
                                            'People-in-path estimates guide evacuation and relief',
                                            'Open data supports climate research'])]
    callouts = [('~1 million', 'people evacuated before Cyclone Phailin (2013)'),
                ('~US$14 billion', 'Amphan (2020) losses in India — WMO 2020'),
                ('Every 30 min', 'rainfall hot-spots refreshed from NASA IMERG')]
    for k, (ic, title, col, pts) in enumerate(ben):
        x = 54 + k * 346
        card(s, x, 428, 334, 332)
        shape(s, x, 428, 334, 70, 'roundRect', fill=col, line=None, radius=14000)
        shape(s, x, 470, 334, 28, 'rect', fill=col, line=None)
        icon_badge(s, ic, x + 38, 463, 44, WHITE, fg=col, shadow=None)
        text(s, x + 70, 428, 256, 70, [para([run(title, 16, True, WHITE)])], anchor='ctr')
        text(s, x + 22, 512, 296, 160, [para([run(p, 13, False, INK)], bullet=col, after=8, indent=14) for p in pts])
        big, small = callouts[k]
        shape(s, x + 18, 672, 298, 74, 'roundRect', fill=SOFT if col == BLUE else (ORANGE_SOFT if col == ORANGE else GREEN_SOFT), line=None, radius=16000)
        text(s, x + 32, 672, 272, 74, [para([run(big, 20, True, col)]), para([run(small, 10.5, False, MUTED)], before=1)], anchor='ctr')

    # Phone with the real Hindi alert screen
    px, py, pw, ph = 1110, 392, 188, 380
    shape(s, px, py, pw, ph, 'roundRect', fill=NAVY, line=None, radius=14000, shadow='strong', name='Phone')
    picture(s, SHOTS / 'phone_alert_hi.png', px + 9, py + 12, pw - 18, ph - 24, prst='roundRect', radius=9000,
            descr='Cyclo-Nexus safety alert in Hindi', crop=(0, 0, 0, 12))
    text(s, px - 10, py + ph + 4, pw + 20, 22, [para([run('Real app screen · Hindi advisory', 10, False, MUTED, italic=True)], 'ctr')])
    # callouts beside the phone
    for k, (ic, t1, t2, col) in enumerate([('bell-ring', 'RED / ORANGE / YELLOW', 'IMD-aligned alert levels', RED),
                                           ('languages', 'हिंदी + English', 'advisories for every audience', BLUE),
                                           ('users', 'People in path', 'towns and population exposed', ORANGE),
                                           ('badge-check', 'Official + AI', 'always labelled', GREEN)]):
        y = 420 + k * 84
        icon_badge(s, ic, 1340, y + 26, 40, col, shadow=None)
        text(s, 1366, y + 4, 184, 48, [para([run(t1, 12.5, True, NAVY)]), para([run(t2, 10.5, False, MUTED)])], anchor='ctr')
    text(s, 1320, 758, 230, 22, [para([run('Turning satellite data into early action that protects lives.', 10.5, True, BLUE, italic=True)])])
    footer_tagline(s, 'Turning satellite data into early action that protects lives.')


# ════════════════════════════════════════════════════════════════════════════
# Slide 6 — Research and references
# ════════════════════════════════════════════════════════════════════════════
def slide6(s):
    section_heading(s, 54, 150, 1000, 'Details / Links of the reference and research work', 'book-open')
    L = lambda url: s.rel('http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', url, True)
    colsdef = [
        ('Data sources', 'database', BLUE, [
            ('ISRO MOSDAC — INSAT-3DS Imager L1C', 'https://www.mosdac.gov.in', 'mosdac.gov.in'),
            ('NASA GPM IMERG (via GES DISC)', 'https://gpm.nasa.gov/data/imerg', 'gpm.nasa.gov/data/imerg'),
            ('JTWC — warnings and forecast tracks', 'https://www.metoc.navy.mil/jtwc/jtwc.html', 'metoc.navy.mil/jtwc'),
            ('NOAA NCEI IBTrACS v04 best tracks', 'https://www.ncei.noaa.gov/products/international-best-track-archive', 'ncei.noaa.gov/products/…best-track-archive'),
            ('IMD — RSMC New Delhi', 'https://mausam.imd.gov.in', 'mausam.imd.gov.in'),
            ('Open-Meteo · NASA GIBS · GeoNames', 'https://open-meteo.com', 'open-meteo.com · geonames.org'),
        ]),
        ('Research papers', 'graduation-cap', NAVY, [
            ('Shi et al. (2015) Convolutional LSTM Network — NeurIPS', 'https://arxiv.org/abs/1506.04214', 'arxiv.org/abs/1506.04214'),
            ('Piñeros, Ritchie & Tyo (2008) Deviation-Angle Variance — IEEE TGRS 46(10)', 'https://doi.org/10.1109/TGRS.2008.2000819', 'doi.org/10.1109/TGRS.2008.2000819'),
            ('Dvorak (1975) TC intensity from satellite imagery — Mon. Wea. Rev.', 'https://doi.org/10.1175/1520-0493(1975)103<0420:TCIAAF>2.0.CO;2', 'doi.org/10.1175/1520-0493(1975)103…'),
            ('Atkinson & Holliday (1977) wind–pressure relationship — Mon. Wea. Rev.', 'https://doi.org/10.1175/1520-0493(1977)105<0421:TCMSLP>2.0.CO;2', 'doi.org/10.1175/1520-0493(1977)105…'),
            ('Knapp et al. (2010) IBTrACS — Bull. Amer. Meteor. Soc.', 'https://doi.org/10.1175/2009BAMS2755.1', 'doi.org/10.1175/2009BAMS2755.1'),
            ('Mohapatra & Sharma — Cyclone warning services in India, MAUSAM 70(4)', 'https://doi.org/10.54302/mausam.v70i4.204', 'doi.org/10.54302/mausam.v70i4.204'),
        ]),
        ('Impact evidence', 'newspaper', ORANGE, [
            ('MoPSW circular (29 Apr 2025): coastline 11,098.81 km', 'https://shipmin.gov.in/en/content/revised-length-indias-coastline-0', 'shipmin.gov.in'),
            ('CMFRI Marine Fisheries Census 2016 — 3.77 million fisherfolk', 'http://eprints.cmfri.org.in/17490/', 'eprints.cmfri.org.in/17490'),
            ('WMO / Global Commission on Adaptation (2019) — 24 h warning cuts damage 30%', 'https://wmo.int/news/media-centre/early-warning-systems-must-protect-everyone-within-five-years', 'wmo.int — Early Warnings for All'),
            ('World Bank — India averts devastation from Cyclone Phailin', 'https://www.worldbank.org/en/results/2014/04/10/india-averts-cyclone-phailin-devastation', 'worldbank.org/en/results/2014/04/10/…'),
            ('WMO State of Global Climate 2020 — Amphan ~US$14 bn loss (ThePrint)', 'https://theprint.in/india/amphan-costliest-cyclone-in-north-indian-ocean-resulted-in-loss-of-14-billion-un-report/642754/', 'theprint.in — UN report'),
            ('Ultralytics YOLO — oriented bounding boxes (OBB)', 'https://docs.ultralytics.com/tasks/obb/', 'docs.ultralytics.com/tasks/obb'),
        ]),
    ]
    for k, (title, ic, col, items) in enumerate(colsdef):
        x = 54 + k * 504; w = 488
        card(s, x, 192, w, 478)
        shape(s, x, 192, w, 52, 'roundRect', fill=col, line=None, radius=14000)
        shape(s, x, 222, w, 22, 'rect', fill=col, line=None)
        icon(s, ic, x + 18, 204, 28, WHITE)
        text(s, x + 56, 192, w - 70, 52, [para([run(title, 17, True, WHITE)])], anchor='ctr')
        for j, (t1, url, shown) in enumerate(items):
            y = 256 + j * 69
            shape(s, x + 16, y + 6, 26, 26, 'ellipse', fill=SOFT, line=None,
                  paras=[para([run(str(j + 1), 11, True, col)], 'ctr')], anchor='ctr')
            text(s, x + 50, y, w - 64, 66, [para([run(t1, 12, True, INK)]),
                                            para([run(shown, 10.5, False, BLUE, link=L(url))], before=2)])
    # QR / links strip
    shape(s, 54, 688, 1496, 128, 'roundRect', fill=SOFT, line=None, radius=12000)
    for k, (ic, t1, t2) in enumerate([('video', 'Demo video', 'Scan to watch the working prototype'),
                                      ('github', 'GitHub repository', 'Scan to view the source code'),
                                      ('file-text', 'Project report', 'Scan for the full technical report')]):
        x = 74 + k * 496
        shape(s, x, 700, 104, 104, 'roundRect', fill=WHITE, line='9DB8D8', lw=1.25, dash='dash', radius=10000)
        icon(s, 'qr-code', x + 30, 718, 44, '9DB8D8')
        text(s, x, 766, 104, 28, [para([run('QR', 10, True, '9DB8D8')], 'ctr')], anchor='ctr')
        icon_badge(s, ic, x + 144, 752, 44, BLUE, shadow=None)
        text(s, x + 176, 718, 290, 70, [para([run(t1, 16, True, NAVY)]), para([run(t2, 12, False, MUTED)], before=2)], anchor='ctr')
    footer_tagline(s, 'Built on open science and public satellite data.')


# ════════════════════════════════════════════════════════════════════════════
def main():
    if WORK.exists(): shutil.rmtree(WORK)
    zipfile.ZipFile(SRC).extractall(WORK)
    GEN.mkdir(parents=True, exist_ok=True)
    slides = {n: Slide(n) for n in range(2, 7)}
    for n, fn in [(2, slide2), (3, slide3), (4, slide4), (5, slide5), (6, slide6)]:
        fn(slides[n])

    # render icon/logo PNG fallbacks (Chrome), then place them
    if ICON_JOBS:
        jobs = GEN / 'jobs.json'
        jobs.write_text(json.dumps(ICON_JOBS), encoding='utf-8')
        subprocess.run(['node', str(HERE / 'assets' / 'render_icons.js'), str(jobs)], check=True)
    for s, png, x, y, size, svg in ICON_USES:
        picture(s, png, x, y, size, size, svg=svg, descr='icon')

    rel_types = {'image': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'}
    for n, s in slides.items():
        p = WORK / 'ppt' / 'slides' / f'slide{n}.xml'
        x = p.read_text(encoding='utf-8')
        start = x.index('<p:spTree>'); end = x.index('</p:spTree>')
        tree = x[start:end]
        # keep the group header + the first five top-level template shapes
        head_end = tree.index('</p:grpSpPr>') + len('</p:grpSpPr>')
        kids, pos, depth = [], head_end, 0
        for m in re.finditer(r'<(/?)p:(grpSp|sp|pic|cxnSp|graphicFrame)\b[^>]*?(/?)>', tree[head_end:]):
            tag_close, name, self_close = m.group(1), m.group(2), m.group(3)
            if tag_close: depth -= 1
            elif not self_close: depth += 1
            if depth == 0 and (tag_close or self_close):
                kids.append(tree[pos:head_end + m.end()]); pos = head_end + m.end()
        keep = ''.join(kids[:5])
        new_tree = tree[:head_end] + keep + ''.join(s.shapes)
        x = x[:start] + new_tree + x[end:]
        if 'xmlns:r=' not in x[:400]:
            x = x.replace('<p:sld ', '<p:sld xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" ', 1)
        p.write_text(x, encoding='utf-8')

        # relationships: keep layout + images used by the kept template shapes, add ours
        rp = WORK / 'ppt' / 'slides' / '_rels' / f'slide{n}.xml.rels'
        r = rp.read_text(encoding='utf-8')
        used = set(re.findall(r'r:(?:embed|id|link)="([^"]+)"', keep))
        rels = re.findall(r'<Relationship [^>]*/>', r)
        kept = [rel for rel in rels if 'slideLayout' in rel or re.search(r'Id="([^"]+)"', rel).group(1) in used]
        for rid, typ, target, ext in s.rels:
            t = rel_types.get(typ, typ)
            mode = ' TargetMode="External"' if ext else ''
            kept.append(f'<Relationship Id="{rid}" Type="{t}" Target="{escape(target, {chr(34): "&quot;"})}"{mode}/>')
        rp.write_text('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                      + ''.join(kept) + '</Relationships>', encoding='utf-8')

    ct = WORK / '[Content_Types].xml'
    c = ct.read_text(encoding='utf-8')
    for ext, mime in [('png', 'image/png'), ('svg', 'image/svg+xml'), ('jpeg', 'image/jpeg')]:
        if f'Extension="{ext}"' not in c:
            c = c.replace('<Default ', f'<Default Extension="{ext}" ContentType="{mime}"/><Default ', 1)
    ct.write_text(c, encoding='utf-8')

    if OUT.exists(): OUT.unlink()
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml first, as Office expects
        z.write(ct, '[Content_Types].xml')
        for f in sorted(WORK.rglob('*')):
            if f.is_file() and f.name != '[Content_Types].xml':
                z.write(f, f.relative_to(WORK).as_posix())
    print('wrote', OUT, f'{OUT.stat().st_size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
