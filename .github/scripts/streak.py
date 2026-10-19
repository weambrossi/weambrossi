"""Regenerates the ./streak.sh block in README.md from the GitHub contribution calendar."""
import datetime as dt
import json
import os
import re
import urllib.request

USER = "weambrossi"
README = "README.md"


def graphql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as resp:
        body = json.load(resp)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def contribution_days():
    years = graphql(
        "query($u:String!){user(login:$u){contributionsCollection{contributionYears}}}",
        {"u": USER},
    )["user"]["contributionsCollection"]["contributionYears"]
    days = {}
    for year in years:
        cal = graphql(
            """query($u:String!,$from:DateTime!,$to:DateTime!){user(login:$u){
                 contributionsCollection(from:$from,to:$to){contributionCalendar{
                   weeks{contributionDays{date contributionCount}}}}}}""",
            {"u": USER, "from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"},
        )["user"]["contributionsCollection"]["contributionCalendar"]
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                days[dt.date.fromisoformat(day["date"])] = day["contributionCount"]
    today = dt.datetime.now(dt.timezone.utc).date()
    return sorted((d, c) for d, c in days.items() if d <= today)


def streaks(days):
    longest = (0, None, None)
    run, start = 0, None
    for d, count in days:
        if count:
            run, start = run + 1, start or d
            if run > longest[0]:
                longest = (run, start, d)
        else:
            run, start = 0, None

    # Today without contributions yet doesn't break the current streak.
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    current, end = 0, days[i][0] if i >= 0 else None
    while i >= 0 and days[i][1]:
        current, i = current + 1, i - 1
    cur_start = days[i + 1][0] if current else None
    return (current, cur_start, end if current else None), longest


def fmt_range(start, end):
    if not start:
        return "-"
    f = lambda d: d.strftime("%b %-d, %Y")
    return f(start) if start == end else f"{f(start)} - {f(end)}"


def render(days):
    total = sum(c for _, c in days)
    first = next((d for d, c in days if c), days[0][0])
    (cur, cs, ce), (best, bs, be) = streaks(days)
    plural = lambda n: f"{n:,} day" + ("" if n == 1 else "s")
    rows = [
        ("total contributions", f"{total:,}", f"{first.strftime('%b %-d, %Y')} - present"),
        ("current streak", plural(cur), fmt_range(cs, ce)),
        ("longest streak", plural(best), fmt_range(bs, be)),
    ]
    lines = ["weambrossi@github:~$ ./streak.sh", ""]
    lines += [f"  {label:<21}{value:<12}{span}" for label, value, span in rows]
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    lines += ["", f"  last updated {stamp} UTC"]
    return "```console\n" + "\n".join(lines) + "\n```"


def main():
    block = render(contribution_days())
    with open(README) as f:
        readme = f.read()
    readme = re.sub(
        r"<!-- streak:start -->.*<!-- streak:end -->",
        lambda _: f"<!-- streak:start -->\n{block}\n<!-- streak:end -->",
        readme,
        flags=re.S,
    )
    with open(README, "w") as f:
        f.write(readme)


if __name__ == "__main__":
    main()
