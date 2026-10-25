"""Draws paper/conditions.svg: the eight jackpot conditions, one card each.
Run from the repo folder: python3 paper/draw_conditions.py (standard library only).
PNG copy for documents: render the SVG at 2000 px wide (e.g. in a browser) and save it as paper/conditions.png."""
NAVY, GREEN, GOLD, GREY, INK, INK2, MUTED, RED = "#1f3a68", "#1f8a5b", "#d99a00", "#b9b7b0", "#0b0b0b", "#2b2b2b", "#8a8984", "#c0392b"
W, H, CW, CH, GAP, X0, Y0 = 1000, 590, 226, 200, 12, 30, 92

def agent(x, y, who, color, faded=False):
    op = ' opacity="0.45"' if faded else ""
    return (f'<g{op}><circle cx="{x}" cy="{y}" r="20" fill="{color}"/>'
            f'<text x="{x}" y="{y+6}" text-anchor="middle" font-size="16" font-weight="700" fill="#fff">{who}</text></g>')

def star(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="#fff6dc" stroke="{GOLD}" stroke-width="2"/>'
            f'<text x="{x}" y="{y+4.5}" text-anchor="middle" font-size="11" fill="{GOLD}">★</text>')

def eye(x, y, crossed=False):
    s = (f'<path d="M{x-15},{y} Q{x},{y-12} {x+15},{y} Q{x},{y+12} {x-15},{y} z" fill="#fff" stroke="{INK2}" stroke-width="1.6"/>'
         f'<circle cx="{x}" cy="{y}" r="4.5" fill="{INK2}"/>')
    if crossed:
        s += f'<line x1="{x-15}" y1="{y+12}" x2="{x+15}" y2="{y-12}" stroke="{RED}" stroke-width="2.6"/>'
    return s

def arrow(x1, x2, y, dashed=False):
    d = ' stroke-dasharray="5 4"' if dashed else ""
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{MUTED}" stroke-width="1.8"{d} marker-end="url(#ah)"/>'

def bubble(x, y):
    return (f'<rect x="{x-20}" y="{y-14}" width="40" height="24" rx="7" fill="#fff" stroke="{INK2}" stroke-width="1.6"/>'
            f'<path d="M{x-6},{y+10} L{x-10},{y+18} L{x+2},{y+10}" fill="#fff" stroke="{INK2}" stroke-width="1.6"/>'
            f'<circle cx="{x-9}" cy="{y-2}" r="2.2" fill="{INK2}"/><circle cx="{x}" cy="{y-2}" r="2.2" fill="{INK2}"/><circle cx="{x+9}" cy="{y-2}" r="2.2" fill="{INK2}"/>')

def key(x, y):
    return (f'<circle cx="{x-9}" cy="{y}" r="7" fill="#fff6dc" stroke="{GOLD}" stroke-width="2.2"/>'
            f'<line x1="{x-2}" y1="{y}" x2="{x+14}" y2="{y}" stroke="{GOLD}" stroke-width="2.6"/>'
            f'<line x1="{x+9}" y1="{y}" x2="{x+9}" y2="{y+6}" stroke="{GOLD}" stroke-width="2.6"/>'
            f'<line x1="{x+14}" y1="{y}" x2="{x+14}" y2="{y+6}" stroke="{GOLD}" stroke-width="2.6"/>')

def glass(x, y):
    return (f'<line x1="{x-6}" y1="{y-6}" x2="{x-13}" y2="{y-13}" stroke="{RED}" stroke-width="3"/>'
            f'<circle cx="{x}" cy="{y}" r="9" fill="#fff" stroke="{RED}" stroke-width="2.4"/>')

def qmark(x, y):
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="#fff" stroke="{RED}" stroke-width="2"/>'
            f'<text x="{x}" y="{y+4.5}" text-anchor="middle" font-size="12" font-weight="700" fill="{RED}">?</text>')

def card(i, cid, name, lines, boards, body, main=False):
    col, row = i % 4, i // 4
    x, y = X0 + col * (CW + GAP), Y0 + row * (CH + GAP)
    border = f'stroke="{NAVY}" stroke-width="2.4"' if main else f'stroke="#e2e0da" stroke-width="1.2"'
    s = [f'<rect x="{x}" y="{y}" width="{CW}" height="{CH}" rx="10" fill="#f7f6f3" {border}/>',
         f'<text x="{x+14}" y="{y+26}" font-size="15" font-weight="700" fill="{INK}">{cid}</text>',
         f'<text x="{x+62}" y="{y+26}" font-size="14" font-weight="700" fill="{INK2}">{name}</text>']
    ax, bx, cy = x + 48, x + CW - 48, y + 82
    s.append(body(ax, bx, cy))
    for k, t in enumerate(lines):
        s.append(f'<text x="{x+14}" y="{y+132+k*17}" font-size="12" fill="{INK2}">{t}</text>')
    s.append(f'<text x="{x+CW-14}" y="{y+CH-12}" text-anchor="end" font-size="11" fill="{MUTED}">{boards}</text>')
    return "".join(s)

def base(ax, bx, cy, middle="", a_extra="", b_extra="", b_faded=False, dashed=False):
    return (arrow(ax + 24, bx - 26, cy, dashed) + middle + agent(ax, cy, "A", NAVY) + star(ax + 17, cy - 17) + a_extra
            + agent(bx, cy, "B", GREEN, faded=b_faded) + b_extra)

CARDS = [
    ("JP-0", "No partner", ["A knows the jackpot but has", "no coalition; B gets no", "coalition instruction."], "150 boards",
     lambda ax, bx, cy: agent(ax, cy, "A", NAVY) + star(ax + 17, cy - 17) + agent(bx, cy, "B", GREEN, faded=True)
     + f'<text x="{(ax+bx)/2}" y="{cy+5}" text-anchor="middle" font-size="12" fill="{MUTED}">no coalition</text>'),
    ("JP-1", "Chat", ["Positive control: A and B", "exchange private messages", "before claiming."], "150 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=bubble((ax + bx) / 2, cy - 2))),
    ("JP-2", "Visible", ["Main test: no messages.", "B sees A's claim and is told", "A knows the jackpot."], "300 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy))),
    ("JP-3", "Hidden", ["Channel cut: A's claim is", "hidden from B. Prompts", "unchanged."], "300 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy, crossed=True), dashed=True)),
    ("JP-4", "Untold", ["As JP-2, but B is not told", "that A knows which task", "is the jackpot."], "300 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy), b_extra=qmark(bx + 17, cy - 17))),
    ("JP-5", "Naive", ["As JP-2, but A is not told", "that B sees its claim."], "150 + 150 + 300 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy), a_extra=qmark(ax - 17, cy - 17))),
    ("JP-6", "Code", ["Both get a code: A1 means", "T1, A2 means T2."], "150 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy + 12) + key((ax + bx) / 2 - 3, cy - 14))),
    ("JP-7", "Auditor", ["A is told an auditor flags", "claims worth less to it than", "its best task. Not enforced."], "150 boards",
     lambda ax, bx, cy: base(ax, bx, cy, middle=eye((ax + bx) / 2, cy), a_extra=glass(ax - 26, cy - 24))),
]

out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica, Arial, sans-serif">',
       '<title>The eight conditions</title>',
       f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/></marker></defs>',
       f'<rect width="{W}" height="{H}" fill="#fff"/>',
       f'<text x="30" y="40" font-size="22" font-weight="700" fill="{INK}">The eight conditions</text>',
       f'<text x="30" y="64" font-size="13" fill="{INK2}">Each changes one thing from JP-2 (outlined). Every condition replays the same boards.</text>']
for i, c in enumerate(CARDS):
    out.append(card(i, *c, main=c[0] == "JP-2"))
ly = Y0 + 2 * CH + GAP + 34
legend = [agent(44, ly, "A", NAVY), f'<text x="70" y="{ly+5}" font-size="12" fill="{INK2}">colluder A, claims first</text>',
          star(232, ly), f'<text x="248" y="{ly+5}" font-size="12" fill="{INK2}">knows the jackpot</text>',
          agent(392, ly, "B", GREEN), f'<text x="418" y="{ly+5}" font-size="12" fill="{INK2}">colluder B</text>',
          eye(520, ly), f'<text x="542" y="{ly+5}" font-size="12" fill="{INK2}">B sees A&#8217;s claim</text>',
          bubble(680, ly - 2), f'<text x="706" y="{ly+5}" font-size="12" fill="{INK2}">messages</text>',
          qmark(792, ly), f'<text x="808" y="{ly+5}" font-size="12" fill="{INK2}">not told</text>',
          glass(890, ly + 2), f'<text x="906" y="{ly+5}" font-size="12" fill="{INK2}">auditor</text>']
out += legend
out.append("</svg>")
open("paper/conditions.svg", "w").write("\n".join(out))
