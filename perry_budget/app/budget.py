"""Envelope math, debt snowball projection, dashboard rollups."""
from . import db

CHECKS = ["14th", "28th"]


def dollars(cents):
    return cents / 100.0


def fmt(cents):
    neg = cents < 0
    s = f"${abs(cents)/100:,.2f}"
    return f"-{s}" if neg else s


def envelope_summary():
    """Per-check available, assigned, remaining + monthly rollup."""
    paychecks = {p["label"]: p for p in db.query("SELECT * FROM paychecks")}
    bills = db.query("SELECT * FROM bills")
    out = {}
    for check in CHECKS:
        p = paychecks.get(check)
        available = 0
        if p:
            available = p["net_cents"] + p["motus_cents"] + p["other_cents"]
        assigned = sum(b["amount_cents"] for b in bills if b["assignment"] == check)
        out[check] = {
            "available": available,
            "assigned": assigned,
            "remaining": available - assigned,
            "bills": [b for b in bills if b["assignment"] == check],
        }
    monthly_available = sum(v["available"] for v in out.values())
    monthly_bills = sum(b["amount_cents"] for b in bills)
    out["monthly"] = {
        "available": monthly_available,
        "assigned": monthly_bills,
        "remaining": monthly_available - monthly_bills,
    }
    return out


def total_debt():
    return sum(d["balance_cents"] for d in db.query("SELECT * FROM debts"))


def snowball_order():
    """Debts ordered by roll_order, then smallest balance first."""
    debts = db.query("SELECT * FROM debts WHERE balance_cents > 0")
    return sorted(debts, key=lambda d: (d["roll_order"], d["balance_cents"]))


def next_target():
    order = snowball_order()
    return order[0]["name"] if order else None


def snowball_projection(extra_cents=0, max_months=120):
    """Simulate snowball payoff. Returns (months, [remaining_cents per month])."""
    debts = [
        {"bal": d["balance_cents"], "min": d["min_payment_cents"], "apr": d["apr"]}
        for d in snowball_order()
    ]
    if not debts:
        return 0, []
    pool = sum(d["min"] for d in debts) + extra_cents
    points = [sum(d["bal"] for d in debts)]
    for _ in range(max_months):
        # accrue monthly interest
        for d in debts:
            if d["bal"] > 0:
                d["bal"] += round(d["bal"] * (d["apr"] / 100.0) / 12.0)
        budget = pool
        # pay minimums first
        for d in debts:
            if d["bal"] <= 0:
                continue
            pay = min(d["min"], d["bal"], budget)
            d["bal"] -= pay
            budget -= pay
        # snowball remainder onto first unpaid debt
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


def svg_area_chart(points, width=900, height=240, pad=4):
    """Build an SVG area+line chart path from a list of cents values."""
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
