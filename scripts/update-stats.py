"""Build the profile cards from GitHub's public statistics."""
import json
import os
import subprocess
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

OWNER = "owasikohu"
OUTPUT = Path(__file__).resolve().parents[1] / "img"
TODAY = datetime.now(ZoneInfo("Asia/Tokyo")).date()
DAY = timedelta(days=1)
COLORS = {
    "Python": "#639dff", "C": "#a8a8a8", "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a", "C++": "#f34b7d", "Verilog": "#b2aafb",
    "Shell": "#adff2f", "Lua": "#7e85ff", "Kotlin": "#a97bff",
    "CSS": "#bc83e2", "Other": "#858585",
}
PALETTE = ("#68d6bc", "#ffab70", "#e78bd1", "#76c8ee", "#e8cf7a")


def api(*args):
    result = subprocess.check_output(["gh", "api", *args], text=True)
    return json.loads(result)


def graphql(query, **variables):
    args = [item for key, value in variables.items() for item in ("-f", f"{key}={value}")]
    response = api("graphql", "-f", f"query={query}", "-f", f"login={OWNER}", *args)
    return response["data"]["user"]


def language_totals():
    repos = subprocess.check_output([
        "gh", "api", "--paginate", f"/users/{OWNER}/repos?type=owner&per_page=100",
        "--jq", '.[] | select(.fork == false and .private == false) | .name',
    ], text=True)
    totals = Counter()
    for name in repos.splitlines():
        totals.update(api(f"/repos/{OWNER}/{name}/languages"))
    return totals


def contributions():
    user = graphql("query($login:String!){user(login:$login){createdAt}}")
    start = date.fromisoformat(user["createdAt"][:10])
    counts = {}
    while start <= TODAY:
        end = min(start + timedelta(days=364), TODAY)
        user = graphql(
            """query($login:String!, $from:DateTime!, $to:DateTime!) {
              user(login:$login) {
                contributionsCollection(from:$from, to:$to) {
                  contributionCalendar { weeks { contributionDays { date contributionCount } } }
                }
              }
            }""",
            **{"from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"},
        )
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                when = date.fromisoformat(day["date"])
                if start <= when <= end:
                    counts[when] = day["contributionCount"]
        start = end + DAY
    return counts


def streaks(counts):
    longest = run = 0
    previous = None
    for when in sorted(day for day, count in counts.items() if count):
        run = run + 1 if previous is not None and when - previous == DAY else 1
        longest = max(longest, run)
        previous = when
    current = run if previous in (TODAY, TODAY - DAY) else 0
    return sum(counts.values()), current, longest


def card(title, description, height, content, definitions=""):
    definitions = f"  {definitions}\n" if definitions else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="520" height="{height}" viewBox="0 0 520 {height}" role="img" aria-labelledby="title description">
  <title id="title">{escape(title)}</title>
  <desc id="description">{escape(description)}</desc>
  <style>
    text {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
    .reveal {{ animation: reveal 800ms ease-out; }}
    @keyframes reveal {{ from {{ opacity: .25; }} to {{ opacity: 1; }} }}
    @media (prefers-reduced-motion: reduce) {{ .reveal {{ animation: none; }} }}
  </style>
{definitions}  <rect x=".5" y=".5" width="519" height="{height - 1}" rx="8" fill="#222" stroke="#555"/>
  <text x="24" y="34" fill="#639dff" font-size="21" font-weight="650">{escape(title)}</text>
  <path d="M24 46H496" stroke="#808080"/>
  {content}
</svg>
"""


def streak_card(counts):
    total, current, longest = streaks(counts)
    metrics = [("Contributions", f"{total:,}"), ("Current streak", str(current)),
               ("Longest streak", str(longest))]
    content = ['<path d="M181 66V134M339 66V134" stroke="#555"/>']
    for index, (label, value) in enumerate(metrics):
        x = (102, 260, 418)[index]
        color = "#adff2f" if index == 1 else "#fff"
        content.append(
            f'<text x="{x}" y="101" text-anchor="middle" fill="{color}" font-size="34" '
            f'font-weight="700" class="reveal">{value}</text>'
            f'<text x="{x}" y="126" text-anchor="middle" fill="#ddd" font-size="16">{label}</text>'
        )
    description = f"{total:,} contributions. Current streak: {current} days. Longest streak: {longest} days."
    return card("/streak", description, 154, "\n  ".join(content))


def language_card(totals):
    total = sum(totals.values())
    if not total:
        return card("/languages", "No language data", 106,
                    '<text x="24" y="78" fill="#ddd" font-size="16">No language data</text>')
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) > 10:
        ranked = ranked[:9] + [("Other", sum(size for _, size in ranked[9:]))]

    bar, legend, description = [], [], []
    offset = 24
    row_count = (len(ranked) + 1) // 2
    for index, (name, size) in enumerate(ranked):
        fraction = size / total
        color = COLORS.get(name, PALETTE[index % len(PALETTE)])
        width = 472 * fraction
        bar.append(f'<rect x="{offset:.6f}" y="61" width="{width:.6f}" height="10" fill="{color}"/>')
        offset += width
        column, row = divmod(index, row_count)
        x, y = 24 + column * 244, 101 + row * 25
        percentage = f"{fraction:.1%}"
        legend.append(
            f'<circle cx="{x + 5}" cy="{y - 5}" r="5" fill="{color}"/>'
            f'<text x="{x + 17}" y="{y}" fill="#fff" font-size="16">{escape(name)}</text>'
            f'<text x="{x + 228}" y="{y}" fill="#ddd" font-size="16" text-anchor="end">{percentage}</text>'
        )
        description.append(f"{name} {percentage}")
    content = '<g clip-path="url(#bar)" class="reveal">' + "".join(bar) + "</g>\n  " + "\n  ".join(legend)
    definitions = '<defs><clipPath id="bar"><rect x="24" y="61" width="472" height="10" rx="5"/></clipPath></defs>'
    return card("/languages", ", ".join(description), 122 + (row_count - 1) * 25, content, definitions)


def main():
    cards = {
        "streak.svg": streak_card(contributions()),
        "languages.svg": language_card(language_totals()),
    }
    for filename, svg in cards.items():
        destination = OUTPUT / filename
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(svg, encoding="utf-8")
        os.replace(temporary, destination)


if __name__ == "__main__":
    main()
