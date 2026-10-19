"""Render the "Languages across my repositories" card for the profile README.

Counts the primary language of every public, non-fork repository the user
owns (all pages, not just the first 100), and writes a light and a dark SVG.

Usage:  GITHUB_TOKEN=... python scripts/languages.py [login]
"""

import json
import os
import sys
import urllib.request
from collections import Counter
from html import escape
from pathlib import Path

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "ChaoukiBayoudhi"
OUT = Path(__file__).resolve().parent.parent / "assets"
TOP = 9  # bars before folding the rest into "Other"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { primaryLanguage { name } }
    }
  }
}
"""

THEMES = {
    # Bar colours validated (lightness, chroma, 3:1 contrast) on GitHub's surfaces.
    "light": {"bg": "#ffffff", "bar": "#0A8F80", "track": "#eff2f5",
              "text": "#1f2328", "muted": "#59636e", "border": "#d1d9e0"},
    "dark": {"bg": "#0d1117", "bar": "#14A898", "track": "#1c232c",
             "text": "#e6edf3", "muted": "#9198a1", "border": "#3d444d"},
}


def fetch_languages(token):
    counts, after = Counter(), None
    while True:
        body = json.dumps({"query": QUERY, "variables": {"login": LOGIN, "after": after}})
        req = urllib.request.Request(
            "https://api.github.com/graphql", data=body.encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
        if "errors" in data:
            raise RuntimeError(data["errors"])
        repos = data["data"]["user"]["repositories"]
        for node in repos["nodes"]:
            lang = (node["primaryLanguage"] or {}).get("name")
            counts[lang or "No code"] += 1
        if not repos["pageInfo"]["hasNextPage"]:
            return counts
        after = repos["pageInfo"]["endCursor"]


def rows_for(counts):
    ranked = [(k, v) for k, v in counts.most_common() if k != "No code"]
    rows = ranked[:TOP]
    rest = sum(v for _, v in ranked[TOP:])
    if rest:
        rows.append(("Other", rest))
    return rows


def bar_path(x, y, w, h, r=4):
    """Bar anchored square at the baseline, rounded only at the data end."""
    r = min(r, w, h / 2)
    return (f"M{x},{y} H{x + w - r} A{r},{r} 0 0 1 {x + w},{y + r} "
            f"V{y + h - r} A{r},{r} 0 0 1 {x + w - r},{y + h} H{x} Z")


def render(rows, total, theme):
    t = THEMES[theme]
    width, left, right, top = 495, 132, 76, 66
    row_h, bar_h = 26, 12
    height = top + row_h * len(rows) + 14
    plot_w = width - left - right
    peak = max(v for _, v in rows)
    font = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
        f'<title id="t">Languages across {total} public repositories</title>',
        '<desc id="d">' + escape(", ".join(f"{k}: {v}" for k, v in rows)) + "</desc>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" '
        f'fill="{t["bg"]}" stroke="{t["border"]}"/>',
        f'<text x="20" y="30" font-family="{font}" font-size="16" font-weight="600" '
        f'fill="{t["text"]}">Languages across my repositories</text>',
        f'<text x="20" y="49" font-family="{font}" font-size="12" fill="{t["muted"]}">'
        f"Primary language of {total} public repositories (forks excluded)</text>",
    ]
    for i, (name, value) in enumerate(rows):
        y = top + i * row_h
        cy = y + bar_h / 2
        w = max(plot_w * value / peak, 2)
        out += [
            f'<text x="{left - 10}" y="{cy + 4}" text-anchor="end" font-family="{font}" '
            f'font-size="12" fill="{t["text"]}">{escape(name)}</text>',
            f'<rect x="{left}" y="{y}" width="{plot_w}" height="{bar_h}" rx="2" fill="{t["track"]}"/>',
            f'<path d="{bar_path(left, y, w, bar_h)}" fill="{t["bar"]}"/>',
            f'<text x="{left + plot_w + 8}" y="{cy + 4}" font-family="{font}" font-size="12" '
            f'fill="{t["muted"]}">{value} repo{"s" if value != 1 else ""}</text>',
        ]
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("Set GITHUB_TOKEN")
    counts = fetch_languages(token)
    total = sum(counts.values())
    rows = rows_for(counts)
    OUT.mkdir(exist_ok=True)
    for theme in THEMES:
        (OUT / f"languages-{theme}.svg").write_text(render(rows, total, theme), encoding="utf-8")
    print(f"{total} repositories:", ", ".join(f"{k} {v}" for k, v in rows))


if __name__ == "__main__":
    main()
