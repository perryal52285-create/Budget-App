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
