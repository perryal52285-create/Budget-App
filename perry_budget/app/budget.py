"""Pay-date engine, hybrid bill funding, per-month view (with retained actuals),
debt snowball, and timezone-aware "now".
"""
import calendar
from datetime import date, datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from . import db

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


# ---- formatting ----------------------------------------------------------

def dollars(cents):
    return cents / 100.0


def fmt(cents):
    neg = cents < 0
    s = f"${abs(cents)/100:,.2f}"
    return f"-{s}" if neg else s


# ---- timezone / current period ------------------------------------------

def get_tz():
    name = db.get_setting("timezone", "America/Chicago")
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("America/Chicago")


def now_ct():
    tz = get_tz()
    return datetime.now(tz) if tz else datetime.now()


def current_period():
    n = now_ct()
    return n.year, n.month


def month_label(year, month):
    return f"{MONTH_NAMES[month]} {year}"


def shift_month(year, month, delta):
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1


# ---- pay-date generation -------------------------------------------------

def _last_day(year, month):
    return calendar.monthrange(year, month)[1]


def _dom(year, month, day):
    """Day-of-month clamped; 0 or >last => last day of month."""
    last = _last_day(year, month)
    if not day or day > last:
        return date(year, month, last)
    return date(year, month, max(1, day))


def source_dates(source, year, month):
    """All dates this source pays within the given month."""
    freq = source["frequency"]
    som = date(year, month, 1)
    eom = date(year, month, _last_day(year, month))
    out = []

    if freq in ("biweekly", "weekly"):
        step = 14 if freq == "biweekly" else 7
        if not source["anchor_date"]:
            return out
        try:
            anchor = date.fromisoformat(source["anchor_date"])
        except ValueError:
            return out
        offset = (som - anchor).days
        d = anchor + timedelta(days=step * (offset // step))
        while d < som:
            d += timedelta(days=step)
        while d <= eom:
            out.append(d)
            d += timedelta(days=step)

    elif freq == "semimonthly":
        out.append(_dom(year, month, source["day1"]))
        d2 = _dom(year, month, source["day2"])
        if d2 not in out:
            out.append(d2)

    elif freq == "monthly":
        out.append(_dom(year, month, source["day1"]))

    elif freq == "annual":
        if source["month"] == month:
            out.append(_dom(year, month, source["day1"]))

    elif freq == "one_time":
        try:
            d = date.fromisoformat(source["anchor_date"])
            if d.year == year and d.month == month:
                out.append(d)
        except (ValueError, TypeError):
            pass

    return sorted(out)


def month_paychecks(year, month):
    """Occurrences across all active sources in the month, with reimbursements
    folded onto each earner's first payroll check. is_extra = 3rd+ biweekly check."""
    sources = db.query("SELECT * FROM income_sources WHERE active=1")
    earners = {e["id"]: e for e in db.query("SELECT * FROM earners")}
    reimbs = [s for s in sources if s["kind"] == "reimbursement"]
    paychecks = [s for s in sources if s["kind"] != "reimbursement"]

    occs = []
    for s in paychecks:
        dates = source_dates(s, year, month)
        for i, d in enumerate(dates, start=1):
            e = earners.get(s["earner_id"], {})
            occs.append({
                "key": f"{s['id']}-{i}",
                "source_id": s["id"],
                "source_name": s["name"],
                "employer": s.get("employer", ""),
                "kind": s["kind"],
                "earner_id": s["earner_id"],
                "earner_name": e.get("name", "?"),
                "color": e.get("color", "#888"),
                "occurrence": i,
                "date": d,
                "base_cents": s["amount_cents"],
                "reimb_cents": 0,
                "reimb_name": "",
                "is_extra": s["frequency"] == "biweekly" and i >= 3,
            })

    # attach each reimbursement to its earner's first payroll check of the month
    for r in reimbs:
        cand = sorted([o for o in occs if o["earner_id"] == r["earner_id"]
                       and o["kind"] == "payroll"], key=lambda o: o["date"])
        if cand:
            cand[0]["reimb_cents"] += r["amount_cents"]
            cand[0]["reimb_name"] = r["name"]

    # apply recorded actuals (override the estimate for that specific check)
    actuals = {(a["source_id"], a["occurrence"]): a
               for a in db.query("SELECT * FROM paycheck_actuals WHERE year=? AND month=?",
                                 (year, month))}
    for o in occs:
        a = actuals.get((o["source_id"], o["occurrence"]))
        if a:
            o["base_cents"] = a["amount_cents"]
            o["reimb_cents"] = a["motus_cents"]
            o["is_actual"] = True
        else:
            o["is_actual"] = False
        o["amount_cents"] = o["base_cents"] + o["reimb_cents"]

    occs.sort(key=lambda o: (o["date"], o["earner_name"]))
    return occs


def _find_occ(occs, source_id, occurrence):
    for o in occs:
        if o["source_id"] == source_id and o["occurrence"] == occurrence:
            return o
    return None


def assign_bills(occs, year, month):
    """Hybrid funding. Returns dict occ_key -> [bills] and a list of unassigned bills."""
    bills = db.query("SELECT * FROM bills")
    payments = {p["bill_id"]: p for p in
                db.query("SELECT * FROM bill_payments WHERE year=? AND month=?", (year, month))}
    by_occ = {o["key"]: [] for o in occs}
    unassigned = []

    for b in bills:
        pay = payments.get(b["id"])
        # per-month manual override beats template
        src = pay["funding_source_id"] if pay and pay["funding_source_id"] else b["funding_source_id"]
        occn = pay["funding_occurrence"] if pay and pay["funding_occurrence"] else b["funding_occurrence"]
        mode = b["funding_mode"]
        b = dict(b)
        b["paid"] = bool(pay["paid"]) if pay else False
        b["paid_cents"] = pay["paid_cents"] if pay else 0

        target = None
        if (mode == "manual" or (pay and pay["funding_source_id"])) and src and occn:
            target = _find_occ(occs, src, occn)

        if target is None:  # auto
            pool = [o for o in occs if not o["is_extra"]]
            if b["responsible_earner_id"]:
                owned = [o for o in pool if o["earner_id"] == b["responsible_earner_id"]]
                pool = owned or pool
            before = [o for o in pool if o["date"].day <= (b["due_dom"] or 31)]
            if before:
                target = max(before, key=lambda o: o["date"])
            elif pool:
                target = min(pool, key=lambda o: o["date"])

        if target is not None:
            by_occ[target["key"]].append(b)
        else:
            unassigned.append(b)

    return by_occ, unassigned


def month_view(year, month):
    occs = month_paychecks(year, month)
    by_occ, unassigned = assign_bills(occs, year, month)

    rows = []
    total_in = total_bills = 0
    for o in occs:
        funded = by_occ.get(o["key"], [])
        assigned = sum(x["amount_cents"] for x in funded)
        total_in += o["amount_cents"]
        total_bills += assigned
        rows.append({**o, "bills": funded, "assigned": assigned,
                     "remaining": o["amount_cents"] - assigned})

    return {
        "year": year, "month": month, "label": month_label(year, month),
        "paychecks": rows,
        "unassigned": unassigned,
        "extras": [r for r in rows if r["is_extra"]],
        "total_in": total_in,
        "total_bills": total_bills,
        "remaining": total_in - total_bills,
    }


def three_check_months(year):
    src = db.query("SELECT * FROM income_sources WHERE active=1 AND frequency='biweekly'")
    out = []
    for m in range(1, 13):
        if any(len(source_dates(s, year, m)) >= 3 for s in src):
            out.append(m)
    return out


def source_preview(source, count=6):
    """Next `count` pay dates from today for a source (for the Manage preview)."""
    today = now_ct().date()
    dates = []
    y, m = today.year, today.month
    guard = 0
    while len(dates) < count and guard < 36:
        for d in source_dates(source, y, m):
            if d >= today:
                dates.append(d)
        y, m = shift_month(y, m, 1)
        guard += 1
    return dates[:count]


# ---- debts (unchanged logic) --------------------------------------------

def total_debt():
    return sum(d["balance_cents"] for d in db.query("SELECT * FROM debts"))


def snowball_order():
    debts = db.query("SELECT * FROM debts WHERE balance_cents > 0")
    return sorted(debts, key=lambda d: (d["roll_order"], d["balance_cents"]))


def next_target():
    order = snowball_order()
    return order[0]["name"] if order else None


def snowball_projection(extra_cents=0, max_months=120):
    debts = [{"bal": d["balance_cents"], "min": d["min_payment_cents"], "apr": d["apr"]}
             for d in snowball_order()]
    if not debts:
        return 0, []
    pool = sum(d["min"] for d in debts) + extra_cents
    points = [sum(d["bal"] for d in debts)]
    for _ in range(max_months):
        for d in debts:
            if d["bal"] > 0:
                d["bal"] += round(d["bal"] * (d["apr"] / 100.0) / 12.0)
        budget = pool
        for d in debts:
            if d["bal"] <= 0:
                continue
            pay = min(d["min"], d["bal"], budget)
            d["bal"] -= pay
            budget -= pay
        for d in debts:
            if budget <= 0:
                break
            if d["bal"] <= 0:
                continue
            pay = min(d["bal"], budget)
            d["bal"] -= pay
            budget -= pay
        remaining = sum(max(0, d["bal"]) for d in debts)
        points.append(remaining)
        if remaining <= 0:
            return len(points) - 1, points
    return max_months, points


def snapshot_debts(year, month):
    """Record current debt balances for this month (history for payoff trend)."""
    for d in db.query("SELECT * FROM debts"):
        db.execute(
            "INSERT INTO debt_snapshots (year, month, debt_id, balance_cents) VALUES (?,?,?,?) "
            "ON CONFLICT(year, month, debt_id) DO UPDATE SET balance_cents=excluded.balance_cents",
            (year, month, d["id"], d["balance_cents"]))


# ---- budgets (category spending caps) -----------------------------------

def category_spend(year, month):
    """Spent per category this month = recurring bills in that category
    (the monthly template) + ad-hoc transactions recorded for the month."""
    spend = {}
    for b in db.query("SELECT category, amount_cents FROM bills"):
        cat = (b["category"] or "").strip()
        if cat:
            spend[cat] = spend.get(cat, 0) + b["amount_cents"]
    for t in db.query("SELECT category, amount_cents FROM transactions WHERE year=? AND month=?",
                      (year, month)):
        cat = (t["category"] or "").strip()
        if cat:
            spend[cat] = spend.get(cat, 0) + t["amount_cents"]
    return spend


def budget_status(year, month):
    """Per-budget rows with limit, spent, remaining, pct, over flag."""
    spend = category_spend(year, month)
    rows = []
    budgets = db.query("SELECT * FROM budgets ORDER BY category")
    budgeted = set()
    for b in budgets:
        cat = b["category"]
        budgeted.add(cat)
        limit = b["monthly_limit_cents"]
        spent = spend.get(cat, 0)
        pct = round(spent / limit * 100) if limit else 0
        rows.append({
            "id": b["id"], "category": cat, "limit_cents": limit,
            "spent_cents": spent, "remaining_cents": limit - spent,
            "pct": pct, "over": spent > limit,
        })
    # categories with spend but no budget set yet (informational)
    untracked = [{"category": c, "spent_cents": v} for c, v in sorted(spend.items())
                 if c not in budgeted]
    return rows, untracked


# ---- next paycheck / alerts ---------------------------------------------

def next_paycheck(from_date=None):
    """The soonest upcoming paycheck occurrence on/after from_date (default today)."""
    today = from_date or now_ct().date()
    y, m = today.year, today.month
    guard = 0
    while guard < 14:
        for o in sorted(month_paychecks(y, m), key=lambda o: o["date"]):
            if o["date"] >= today:
                return o
        y, m = shift_month(y, m, 1)
        guard += 1
    return None


def days_to_next_paycheck(from_date=None):
    today = from_date or now_ct().date()
    nxt = next_paycheck(today)
    return (nxt["date"] - today).days if nxt else None


def detect_alerts(year, month):
    """Surface conditions worth a nudge: unfunded bills, over-budget categories,
    and an imminent paycheck. Returns list of {level, kind, text}."""
    alerts = []
    view = month_view(year, month)
    if view["unassigned"]:
        total = sum(b["amount_cents"] for b in view["unassigned"])
        alerts.append({"level": "warn", "kind": "unfunded",
                       "text": f"{len(view['unassigned'])} unfunded bill(s) totaling {fmt(total)} this month."})

    rows, _ = budget_status(year, month)
    for r in rows:
        if r["over"]:
            alerts.append({"level": "warn", "kind": "budget",
                           "text": f"Over budget on {r['category']}: {fmt(r['spent_cents'])} of {fmt(r['limit_cents'])}."})

    ahead = int(db.get_setting("alert_days_ahead", "3") or 3)
    nxt = next_paycheck()
    if nxt:
        d = (nxt["date"] - now_ct().date()).days
        if 0 <= d <= ahead:
            when = "today" if d == 0 else f"in {d} day(s)"
            alerts.append({"level": "info", "kind": "paycheck",
                           "text": f"{nxt['earner_name']} paycheck {when} ({nxt['date'].strftime('%a %b %-d')}, {fmt(nxt['amount_cents'])})."})
    return alerts


def sensor_payload(year, month):
    """Snapshot of headline numbers for export as Home Assistant sensors."""
    view = month_view(year, month)
    months_, _ = snowball_projection()
    rows, _ = budget_status(year, month)
    over = sum(1 for r in rows if r["over"])
    days = days_to_next_paycheck()
    return {
        "total_debt": {"state": f"{dollars(total_debt()):.2f}", "unit": "USD",
                       "name": "Perry Budget Total Debt", "icon": "mdi:credit-card-outline"},
        "remaining_this_month": {"state": f"{dollars(view['remaining']):.2f}", "unit": "USD",
                                 "name": "Perry Budget Remaining This Month", "icon": "mdi:wallet"},
        "income_this_month": {"state": f"{dollars(view['total_in']):.2f}", "unit": "USD",
                              "name": "Perry Budget Income This Month", "icon": "mdi:cash-plus"},
        "bills_this_month": {"state": f"{dollars(view['total_bills']):.2f}", "unit": "USD",
                             "name": "Perry Budget Bills This Month", "icon": "mdi:receipt"},
        "payoff_months": {"state": str(months_), "unit": "mo",
                          "name": "Perry Budget Payoff Months", "icon": "mdi:calendar-clock"},
        "next_target": {"state": next_target() or "none",
                        "name": "Perry Budget Next Payoff Target", "icon": "mdi:target"},
        "days_to_paycheck": {"state": "unknown" if days is None else str(days), "unit": "d",
                             "name": "Perry Budget Days To Paycheck", "icon": "mdi:cash-clock"},
        "unfunded_bills": {"state": str(len(view["unassigned"])),
                           "name": "Perry Budget Unfunded Bills", "icon": "mdi:alert-circle-outline"},
        "over_budget": {"state": str(over),
                        "name": "Perry Budget Over-Budget Categories", "icon": "mdi:chart-bell-curve"},
    }


# ---- net worth / accounts -----------------------------------------------

def accounts_with_balance():
    """Active accounts, each with its most recent recorded balance."""
    out = []
    for a in db.query("SELECT * FROM accounts WHERE active=1 ORDER BY sort_order, name"):
        a = dict(a)
        bal = db.query(
            "SELECT balance_cents, as_of FROM account_balances WHERE account_id=? "
            "ORDER BY as_of DESC, id DESC LIMIT 1", (a["id"],))
        a["balance_cents"] = bal[0]["balance_cents"] if bal else 0
        a["as_of"] = bal[0]["as_of"] if bal else None
        out.append(a)
    return out


def net_worth_summary():
    accts = accounts_with_balance()
    assets = sum(a["balance_cents"] for a in accts if not a["is_liability"])
    liab = sum(a["balance_cents"] for a in accts if a["is_liability"])
    return {"assets_cents": assets, "liabilities_cents": liab,
            "net_cents": assets - liab, "accounts": accts}


def net_worth_series():
    """Net worth at each snapshot date = sum of the latest balance per account
    on or before that date (liabilities subtracted)."""
    dates = [r["as_of"] for r in
             db.query("SELECT DISTINCT as_of FROM account_balances ORDER BY as_of")]
    accts = db.query("SELECT id, is_liability FROM accounts")
    out = []
    for d in dates:
        net = 0
        for a in accts:
            row = db.query(
                "SELECT balance_cents FROM account_balances WHERE account_id=? AND as_of<=? "
                "ORDER BY as_of DESC, id DESC LIMIT 1", (a["id"], d))
            if row:
                b = row[0]["balance_cents"]
                net += -b if a["is_liability"] else b
        out.append({"date": d, "net_cents": net})
    return out


# ---- reports -------------------------------------------------------------

def cashflow_series(months=12):
    """Projected income vs funded bills vs leftover for the last `months`."""
    cy, cm = current_period()
    y, m = shift_month(cy, cm, -(months - 1))
    out = []
    for _ in range(months):
        v = month_view(y, m)
        out.append({
            "label": f"{MONTH_NAMES[m][:3]} '{str(y)[2:]}",
            "year": y, "month": m,
            "income_cents": v["total_in"],
            "bills_cents": v["total_bills"],
            "net_cents": v["remaining"],
        })
        y, m = shift_month(y, m, 1)
    return out


def category_breakdown(year, month):
    """Spend per category this month, sorted desc (bills + ad-hoc transactions)."""
    spend = category_spend(year, month)
    return [{"category": c, "amount_cents": v}
            for c, v in sorted(spend.items(), key=lambda kv: -kv[1])]


DONUT_PALETTE = ["#5b9bff", "#ff5b5b", "#e3b341", "#b07cff", "#ff79b0",
                 "#28b487", "#ff944d", "#46d970"]


def month_allocation(view):
    """Where this month's income goes: assigned bills grouped by category,
    plus a 'Left / Spending' slice for what remains."""
    cats = {}
    for p in view["paychecks"]:
        for b in p["bills"]:
            c = (b.get("category") or "").strip() or "Other"
            cats[c] = cats.get(c, 0) + b["amount_cents"]
    segs = [{"label": c, "value": v} for c, v in sorted(cats.items(), key=lambda kv: -kv[1])]
    if view["remaining"] > 0:
        segs.append({"label": "Left / Spending", "value": view["remaining"], "rest": True})
    return segs


def donut_chart(segments, size=220, thickness=30, pad=6):
    """Server-rendered SVG donut. Each segment -> a circle slice via
    stroke-dasharray, so it themes cleanly and needs no JS/chart lib."""
    import math
    vals = [s for s in segments if s["value"] > 0]
    total = sum(s["value"] for s in vals)
    r = size / 2 - thickness / 2 - pad
    circ = 2 * math.pi * r
    out = []
    acc = 0.0
    for i, s in enumerate(vals):
        frac = s["value"] / total if total else 0
        color = "#2c9a52" if s.get("rest") else DONUT_PALETTE[i % len(DONUT_PALETTE)]
        out.append({
            "label": s["label"], "value": s["value"], "color": color,
            "pct": round(frac * 100),
            "dash": frac * circ, "gap": circ - frac * circ,
            "offset": -acc * circ,
        })
        acc += frac
    return {"segments": out, "total": total, "n": len(vals),
            "size": size, "r": r, "cx": size / 2, "cy": size / 2,
            "thickness": thickness, "circ": circ}


def svg_area_chart(points, width=900, height=240, pad=4):
    if not points or len(points) < 2:
        return {"line": "", "area": "", "width": width, "height": height,
                "lo": 0, "hi": 0, "n": len(points)}
    hi = max(points)
    lo = min(points)
    span = (hi - lo) or 1
    n = len(points) - 1
    xs = lambda i: pad + (width - 2 * pad) * (i / n)
    ys = lambda v: pad + (height - 2 * pad) * (1 - (v - lo) / span)
    pts = [(xs(i), ys(v)) for i, v in enumerate(points)]
    line = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M {pts[0][0]:.1f},{height-pad} " + \
           " ".join(f"L {x:.1f},{y:.1f}" for x, y in pts) + \
           f" L {pts[-1][0]:.1f},{height-pad} Z"
    return {"line": line, "area": area, "width": width, "height": height,
            "lo": lo, "hi": hi, "n": len(points)}
