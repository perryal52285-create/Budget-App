"""Command-driven web TUI for Perry Budget.

`run(line)` parses a single command line and returns plain text, the way a
shell would. Pure-text in, pure-text out — the browser terminal just POSTs the
line and prints the result. Read commands query the budget engine; write
commands mutate the SQLite template/month data through the same helpers the
web forms use.
"""
import shlex

from . import budget, db

PROMPT = "perry//budget $"


def _cents(value):
    try:
        return round(float(str(value).replace(",", "").replace("$", "").strip()) * 100)
    except (ValueError, AttributeError):
        return 0


def _resolve_month(args):
    """Parse trailing month args -> (year, month). Accepts: '', 'june',
    'july 2026', '2026-07', '7'. Falls back to current period."""
    cy, cm = budget.current_period()
    if not args:
        return cy, cm
    text = " ".join(args).strip().lower()
    names = {n.lower(): i for i, n in enumerate(budget.MONTH_NAMES) if n}
    abbr = {n.lower()[:3]: i for i, n in enumerate(budget.MONTH_NAMES) if n}
    year, month = cy, None
    if "-" in text:  # 2026-07
        try:
            y, m = text.split("-")[:2]
            return int(y), int(m)
        except ValueError:
            pass
    for tok in text.split():
        if tok in names:
            month = names[tok]
        elif tok in abbr:
            month = abbr[tok]
        elif tok.isdigit():
            n = int(tok)
            if n > 12:
                year = n
            else:
                month = n
    return year, (month or cm)


def _bar(pct, width=20):
    fill = max(0, min(width, round(pct / 100 * width)))
    return "[" + "#" * fill + "-" * (width - fill) + f"] {pct}%"


# ---- command handlers ----------------------------------------------------

def _help(_):
    return (
        "commands:\n"
        "  help                         this list\n"
        "  bal [month]                  income / bills / left + total debt\n"
        "  show [month]                 paychecks + funded bills for a month\n"
        "  show debts                   snowball order + balances\n"
        "  show budget [month]          category budgets vs spend\n"
        "  next                         next upcoming paycheck\n"
        "  alerts [month]               current nudges\n"
        "  add bill <name> <amount> [due <day>]\n"
        "  add debt <name> <balance> <min> <apr>\n"
        "  spend <category> <amount> [note...]\n"
        "  budget <category> <amount>   set a monthly category cap\n"
        "  clear                        clear the screen\n"
        "months: 'june', 'july 2026', '2026-07', or blank = current"
    )


def _bal(args):
    y, m = _resolve_month(args)
    v = budget.month_view(y, m)
    return (f"{v['label']}\n"
            f"  income   {budget.fmt(v['total_in'])}\n"
            f"  bills    {budget.fmt(v['total_bills'])}\n"
            f"  left     {budget.fmt(v['remaining'])}\n"
            f"  debt     {budget.fmt(budget.total_debt())}")


def _show(args):
    if args and args[0].lower() in ("debt", "debts"):
        return _show_debts()
    if args and args[0].lower() in ("budget", "budgets"):
        return _show_budget(args[1:])
    y, m = _resolve_month(args)
    v = budget.month_view(y, m)
    extras = sum(1 for p in v["paychecks"] if p["is_extra"])
    out = [f"{v['label']}  ·  {len(v['paychecks'])} paychecks"
           + (f"  ·  {extras} extra (surplus)" if extras else ""),
           "-" * 52]
    if not v["paychecks"]:
        out.append("  (no paychecks land this month)")
    for p in v["paychecks"]:
        tag = "  EXTRA/surplus" if p["is_extra"] else ""
        reimb = f"  (+{budget.fmt(p['reimb_cents'])} {p['reimb_name']})" if p["reimb_cents"] else ""
        out.append(f"{p['date'].strftime('%m/%d')}  {p['earner_name']:<8} "
                   f"{budget.fmt(p['amount_cents'])}{reimb}{tag}")
        for b in p["bills"]:
            out.append(f"   └ {b['name']:<22} {budget.fmt(b['amount_cents'])}  due {b['due_dom']}")
        out.append(f"        left {budget.fmt(p['remaining'])}")
    if v["unassigned"]:
        out.append("-" * 52)
        out.append("UNFUNDED:")
        for b in v["unassigned"]:
            out.append(f"   ! {b['name']:<22} {budget.fmt(b['amount_cents'])}")
    out.append("-" * 52)
    out.append(f"in {budget.fmt(v['total_in'])}  ·  bills {budget.fmt(v['total_bills'])}"
               f"  ·  left {budget.fmt(v['remaining'])}")
    return "\n".join(out)


def _show_debts():
    order = budget.snowball_order()
    if not order:
        return "no debts. add one:  add debt <name> <balance> <min> <apr>"
    months_, _ = budget.snowball_projection()
    out = [f"SNOWBALL  ·  total {budget.fmt(budget.total_debt())}  ·  payoff ~{months_} mo", "-" * 52]
    for i, d in enumerate(order, 1):
        out.append(f"{i}. {d['name']:<20} {budget.fmt(d['balance_cents'])}"
                   f"   min {budget.fmt(d['min_payment_cents'])}  {d['apr']:.1f}%")
    return "\n".join(out)


def _show_budget(args):
    y, m = _resolve_month(args)
    rows, untracked = budget.budget_status(y, m)
    if not rows and not untracked:
        return "no budgets set.  budget <category> <amount>"
    out = [f"BUDGETS  ·  {budget.month_label(y, m)}", "-" * 52]
    for r in rows:
        flag = "  OVER" if r["over"] else ""
        out.append(f"{r['category']:<16} {budget.fmt(r['spent_cents'])} / "
                   f"{budget.fmt(r['limit_cents'])}{flag}")
        out.append(f"   {_bar(r['pct'])}")
    if untracked:
        out.append("-" * 52)
        out.append("no cap set:")
        for u in untracked:
            out.append(f"   {u['category']:<16} {budget.fmt(u['spent_cents'])}")
    return "\n".join(out)


def _next(_):
    nxt = budget.next_paycheck()
    if not nxt:
        return "no upcoming paychecks found."
    days = budget.days_to_next_paycheck()
    when = "today" if days == 0 else f"in {days} day(s)"
    reimb = f"  (+{budget.fmt(nxt['reimb_cents'])} {nxt['reimb_name']})" if nxt["reimb_cents"] else ""
    return (f"next: {nxt['earner_name']}  {nxt['date'].strftime('%a %b %-d, %Y')}  {when}\n"
            f"      {budget.fmt(nxt['amount_cents'])}{reimb}  ·  {nxt['source_name']}")


def _alerts(args):
    y, m = _resolve_month(args)
    al = budget.detect_alerts(y, m)
    if not al:
        return "all clear — no alerts. ✓"
    return "\n".join(f"[{a['level'].upper()}] {a['text']}" for a in al)


def _add(args):
    if not args:
        return "usage: add bill <name> <amount> [due <day>]  |  add debt <name> <balance> <min> <apr>"
    kind, rest = args[0].lower(), args[1:]
    if kind == "bill":
        if len(rest) < 2:
            return "usage: add bill <name> <amount> [due <day>]"
        name, amount = rest[0], rest[1]
        due = 1
        if "due" in rest:
            try:
                due = int(rest[rest.index("due") + 1])
            except (ValueError, IndexError):
                pass
        db.execute(
            "INSERT INTO bills (name, amount_cents, due_dom, funding_mode) VALUES (?,?,?,'auto')",
            (name, _cents(amount), due))
        return f"+ bill '{name}' {budget.fmt(_cents(amount))} due {due}"
    if kind == "debt":
        if len(rest) < 2:
            return "usage: add debt <name> <balance> <min> <apr>"
        name = rest[0]
        bal = _cents(rest[1])
        minp = _cents(rest[2]) if len(rest) > 2 else 0
        apr = float(rest[3]) if len(rest) > 3 else 0.0
        db.execute(
            "INSERT INTO debts (name, balance_cents, min_payment_cents, apr, roll_order) VALUES (?,?,?,?,0)",
            (name, bal, minp, apr))
        return f"+ debt '{name}' {budget.fmt(bal)}  min {budget.fmt(minp)}  {apr:.1f}%"
    return f"don't know how to add '{kind}'. try: add bill | add debt"


def _spend(args):
    if len(args) < 2:
        return "usage: spend <category> <amount> [note...]"
    cat, amount = args[0], args[1]
    note = " ".join(args[2:])
    y, m = budget.current_period()
    db.execute(
        "INSERT INTO transactions (year, month, category, description, amount_cents, txn_date) "
        "VALUES (?,?,?,?,?,?)",
        (y, m, cat, note, _cents(amount), budget.now_ct().date().isoformat()))
    return f"+ spent {budget.fmt(_cents(amount))} on {cat}" + (f" — {note}" if note else "")


def _budget_cmd(args):
    if len(args) < 2:
        return "usage: budget <category> <amount>"
    cat, amount = args[0], args[1]
    db.execute(
        "INSERT INTO budgets (category, monthly_limit_cents) VALUES (?,?) "
        "ON CONFLICT(category) DO UPDATE SET monthly_limit_cents=excluded.monthly_limit_cents",
        (cat, _cents(amount)))
    return f"budget for {cat} set to {budget.fmt(_cents(amount))}/mo"


HANDLERS = {
    "help": _help, "?": _help,
    "bal": _bal, "balance": _bal,
    "show": _show, "ls": _show,
    "next": _next,
    "alerts": _alerts,
    "add": _add,
    "spend": _spend,
    "budget": _budget_cmd,
}


def run(line):
    line = (line or "").strip()
    if not line:
        return ""
    if line.lower() in ("clear", "cls"):
        return "\x0c"  # sentinel the frontend treats as "clear screen"
    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.split()
    cmd, args = parts[0].lower(), parts[1:]
    handler = HANDLERS.get(cmd)
    if not handler:
        return f"unknown command: {cmd}\ntype 'help' for the list."
    try:
        return handler(args)
    except Exception as e:  # never let a bad command kill the terminal
        return f"error: {e}"
