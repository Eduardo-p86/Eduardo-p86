#!/usr/bin/env python3
"""Gera assets/streak.svg com a sequência de contribuições do GitHub.

Fonte principal: API GraphQL do GitHub (usa GITHUB_TOKEN, histórico completo).
Fallback: página pública de contribuições (último ano), sem token.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Eduardo-p86"
TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/streak.svg"

# Cores (mesmo tema "radical" dos outros cards)
BG, BORDER = "#141321", "#2a2840"
TITLE, TEXT, ACCENT, MUTED = "#fe428e", "#a9fef7", "#A855F7", "#8b8aa8"


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "User-Agent": "streak-svg"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def days_from_api():
    created = graphql(
        "query($u:String!){user(login:$u){createdAt}}", {"u": USER}
    )["user"]["createdAt"]
    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    q = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){
      contributionsCollection(from:$f,to:$t){contributionCalendar{weeks{
      contributionDays{date contributionCount}}}}}}"""
    days = {}
    cur = start
    while cur < now:
        end = min(cur + timedelta(days=365), now)
        d = graphql(q, {"u": USER, "f": cur.isoformat(), "t": end.isoformat()})
        for w in d["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in w["contributionDays"]:
                days[day["date"]] = day["contributionCount"]
        cur = end
    return days


def days_from_page():
    url = f"https://github.com/users/{USER}/contributions"
    req = urllib.request.Request(url, headers={"User-Agent": "streak-svg"})
    html = urllib.request.urlopen(req, timeout=30).read().decode()
    cells = re.findall(r'data-date="([\d-]+)" id="([^"]+)"', html)
    tips = dict(re.findall(r'for="([^"]+)"[^>]*>\s*(No|\d+) contributions?', html))
    days = {}
    for d, cid in cells:
        n = tips.get(cid, "No")
        days[d] = 0 if n == "No" else int(n)
    return days


def compute(days):
    today = date.today()
    items = sorted((date.fromisoformat(d), n) for d, n in days.items() if date.fromisoformat(d) <= today)
    total = sum(n for _, n in items)
    first = next((d for d, n in items if n > 0), None)

    longest, longest_range, run, run_start = 0, None, 0, None
    prev = None
    for d, n in items:
        if n > 0:
            if prev is not None and (d - prev).days == 1 and run > 0:
                run += 1
            else:
                run, run_start = 1, d
            if run > longest:
                longest, longest_range = run, (run_start, d)
            prev = d
        else:
            run, prev = 0, None

    # sequência atual: se hoje ainda não tem commit, conta a partir de ontem
    by_date = {d: n for d, n in items}
    cur_day = today if by_date.get(today, 0) > 0 else today - timedelta(days=1)
    current, cur_end = 0, cur_day
    while by_date.get(cur_day, 0) > 0:
        current += 1
        cur_day -= timedelta(days=1)
    cur_range = (cur_day + timedelta(days=1), cur_end) if current else None
    return total, first, current, cur_range, longest, longest_range


def fmt(d):
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    return f"{d.day} {meses[d.month - 1]}"


def rng(r):
    if not r:
        return "—"
    a, b = r
    return fmt(a) if a == b else f"{fmt(a)} – {fmt(b)}"


def svg(total, first, current, cur_range, longest, longest_range):
    since = f"desde {fmt(first)} {first.year}" if first else "sem contribuições ainda"
    cols = [
        (100, f"{total:,}".replace(",", "."), "Total de contribuições", since, TEXT),
        (300, str(current), "Sequência atual (dias)", rng(cur_range), ACCENT),
        (500, str(longest), "Maior sequência (dias)", rng(longest_range), TEXT),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="170" viewBox="0 0 600 170" role="img" aria-label="Sequência de contribuições no GitHub">',
        "<style>",
        "text{font-family:'Segoe UI',Ubuntu,Sans-Serif}",
        f".n{{font-size:34px;font-weight:700}} .l{{font-size:14px;font-weight:600;fill:{TITLE}}} .s{{font-size:12px;fill:{MUTED}}}",
        "@keyframes pop{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}",
        ".c{opacity:0;animation:pop .6s ease-out forwards}",
        "@keyframes glow{0%,100%{opacity:1}50%{opacity:.55}} .ring{animation:glow 2.4s ease-in-out infinite}",
        "</style>",
        f'<rect x="0.5" y="0.5" width="599" height="169" rx="6" fill="{BG}" stroke="{BORDER}"/>',
        f'<line x1="200" y1="30" x2="200" y2="140" stroke="{BORDER}"/>',
        f'<line x1="400" y1="30" x2="400" y2="140" stroke="{BORDER}"/>',
    ]
    for i, (x, num, label, sub, color) in enumerate(cols):
        delay = f"animation-delay:{i * 0.2:.1f}s"
        parts.append(f'<g class="c" style="{delay}">')
        if i == 1:
            parts.append(f'<circle class="ring" cx="{x}" cy="68" r="38" fill="none" stroke="{ACCENT}" stroke-width="3"/>')
        parts.append(f'<text class="n" x="{x}" y="80" text-anchor="middle" fill="{color}">{num}</text>')
        parts.append(f'<text class="l" x="{x}" y="125" text-anchor="middle">{label}</text>')
        parts.append(f'<text class="s" x="{x}" y="145" text-anchor="middle">{sub}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    days = None
    if TOKEN:
        try:
            days = days_from_api()
        except Exception as e:  # noqa: BLE001
            print("API falhou, usando a página pública:", e, file=sys.stderr)
    if days is None:
        days = days_from_page()
    result = compute(days)
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg(*result))
    print("OK:", result[0], "contribuições | atual", result[2], "| maior", result[4])


if __name__ == "__main__":
    main()
