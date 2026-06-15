"""JSON API for the React frontend.

Exposes the budget engine + auth + net-worth/goals/reports over JSON. Coexists
with the Jinja UI during the migration. Money is integer cents end to end; the
frontend converts dollars->cents before sending.

FastAPI's jsonable_encoder serializes the engine's date objects to ISO strings
automatically, so view dicts can be returned as-is.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import budget, auth, db, ha, tui
from .meta import VERSION

router = APIRouter(prefix="/api")


# ======================= auth =======================

class LoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


class ThemeBody(BaseModel):
    theme: str


def require_user(request: Request):
    user = auth.get_session_user(request.cookies.get(auth.COOKIE_NAME))
    if not user:
        raise HTTPException(status_code=401, detail="authentication required")
    return user


def _set_session_cookie(request: Request, response: Response, token: str):
    secure = request.url.scheme == "https" or \
        request.headers.get("x-forwarded-proto", "") == "https"
    response.set_cookie(auth.COOKIE_NAME, token, max_age=auth.SESSION_TTL,
                        httponly=True, samesite="lax", secure=secure, path="/")


@router.post("/login")
def login(request: Request, response: Response, body: LoginBody):
    key = f"{body.username.strip().lower()}|{request.client.host if request.client else '?'}"
    if auth.throttled(key):
        raise HTTPException(status_code=429, detail="too many attempts; wait a few minutes")
    user = auth.authenticate(body.username, body.password)
    if not user:
        auth.record_fail(key)
        raise HTTPException(status_code=401, detail="invalid username or password")
    auth.clear_fails(key)
    token = auth.create_session(user["id"])
    _set_session_cookie(request, response, token)
    return {"user": auth.public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response):
    auth.delete_session(request.cookies.get(auth.COOKIE_NAME))
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = auth.get_session_user(request.cookies.get(auth.COOKIE_NAME))
    return {"user": auth.public_user(user) if user else None}


@router.post("/change-password")
def change_password(body: ChangePasswordBody, user=Depends(require_user)):
    if not auth.verify_password(body.current_password, user["password_salt"], user["password_hash"]):
        raise HTTPException(status_code=400, detail="current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="new password must be at least 6 characters")
    auth.set_password(user["id"], body.new_password)
    return {"ok": True}


@router.post("/theme")
def set_theme(body: ThemeBody, user=Depends(require_user)):
    t = body.theme if body.theme in ("terminal", "bubbly") else ""
    db.execute("UPDATE users SET theme=? WHERE id=?", (t, user["id"]))
    return {"ok": True}


# ======================= health =======================

@router.get("/health")
def health():
    y, m = budget.current_period()
    return {"ok": True, "app": "perry_budget", "version": VERSION,
            "now": budget.now_ct().isoformat(), "period": {"year": y, "month": m}}


# ======================= helpers =======================

def _period(year, month):
    cy, cm = budget.current_period()
    year = year or cy
    month = month or cm
    if month < 1 or month > 12:
        year, month = cy, cm
    return year, month


# ======================= dashboard =======================

@router.get("/dashboard")
def dashboard(year: int | None = None, month: int | None = None, user=Depends(require_user)):
    y, m = _period(year, month)
    cy, cm = budget.current_period()
    if (y, m) == (cy, cm):
        budget.snapshot_debts(y, m)
        if db.get_setting("sensors_enabled", "1") == "1":
            ha.push_sensors(budget.sensor_payload(y, m))

    view = budget.month_view(y, m)
    months_, points = budget.snowball_projection()

    seen, upcoming = set(), []
    for p in view["paychecks"]:
        for b in p["bills"]:
            if b["id"] not in seen:
                seen.add(b["id"])
                upcoming.append({**b, "earner_color": p["color"], "earner_name": p["earner_name"]})
    for b in view["unassigned"]:
        if b["id"] not in seen:
            seen.add(b["id"])
            upcoming.append({**b, "earner_color": "#888", "earner_name": "unassigned"})
    upcoming.sort(key=lambda b: b.get("due_dom") or 99)

    py, pm = budget.shift_month(y, m, -1)
    ny, nm = budget.shift_month(y, m, 1)
    return {
        "view": view,
        "allocation": budget.month_allocation(view),
        "upcoming": upcoming,
        "prev": {"year": py, "month": pm}, "next": {"year": ny, "month": nm},
        "is_current": (y, m) == (cy, cm),
        "three_check": budget.three_check_months(y),
        "total_debt_cents": budget.total_debt(),
        "next_target": budget.next_target(),
        "payoff_months": months_,
        "snowball_points": points,
        "net_worth": budget.net_worth_summary(),
        "alerts": budget.detect_alerts(y, m),
    }


# ======================= manage: data =======================

@router.get("/manage")
def manage(user=Depends(require_user)):
    sources = db.query("SELECT * FROM income_sources ORDER BY earner_id, name")
    for s in sources:
        s["preview"] = budget.source_preview(s)
    return {
        "earners": db.query("SELECT * FROM earners ORDER BY is_primary DESC, name"),
        "sources": sources,
        "bills": db.query("SELECT * FROM bills ORDER BY name"),
        "debts": db.query("SELECT * FROM debts ORDER BY roll_order, balance_cents"),
        "frequencies": ["weekly", "biweekly", "semimonthly", "monthly", "annual", "one_time"],
        "kinds": ["payroll", "reimbursement", "bonus_annual", "one_time", "other"],
        "settings": {
            "timezone": db.get_setting("timezone", "America/Chicago"),
            "sensors_enabled": db.get_setting("sensors_enabled", "1") == "1",
            "notify_service": db.get_setting("notify_service", "notify"),
            "alert_days_ahead": int(db.get_setting("alert_days_ahead", "3") or 3),
        },
        "ha_available": ha.available(),
    }


# ---- earners ----
class EarnerIn(BaseModel):
    name: str
    color: str = "#46d970"
    is_primary: int = 0


@router.post("/earners")
def add_earner(body: EarnerIn, user=Depends(require_user)):
    eid = db.execute("INSERT INTO earners (name, color, is_primary) VALUES (?,?,?)",
                     (body.name, body.color, body.is_primary))
    return {"id": eid}


@router.put("/earners/{eid}")
def update_earner(eid: int, body: EarnerIn, user=Depends(require_user)):
    db.execute("UPDATE earners SET name=?, color=? WHERE id=?", (body.name, body.color, eid))
    return {"ok": True}


@router.delete("/earners/{eid}")
def delete_earner(eid: int, user=Depends(require_user)):
    db.execute("DELETE FROM earners WHERE id=?", (eid,))
    return {"ok": True}


# ---- income sources ----
class IncomeIn(BaseModel):
    earner_id: int
    name: str
    employer: str = ""
    kind: str = "payroll"
    amount_cents: int = 0
    frequency: str = "biweekly"
    anchor_date: str = ""
    day1: int = 1
    day2: int = 0
    month: int = 1
    active: int = 1
    notes: str = ""


def _income_tuple(b: IncomeIn):
    return (b.earner_id, b.name, b.employer, b.kind, b.amount_cents, b.frequency,
            b.anchor_date, b.day1, b.day2, b.month, b.active, b.notes)


@router.post("/income")
def add_income(body: IncomeIn, user=Depends(require_user)):
    iid = db.execute(
        "INSERT INTO income_sources (earner_id, name, employer, kind, amount_cents, frequency,"
        " anchor_date, day1, day2, month, active, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        _income_tuple(body))
    return {"id": iid}


@router.put("/income/{iid}")
def update_income(iid: int, body: IncomeIn, user=Depends(require_user)):
    db.execute(
        "UPDATE income_sources SET earner_id=?, name=?, employer=?, kind=?, amount_cents=?,"
        " frequency=?, anchor_date=?, day1=?, day2=?, month=?, active=?, notes=? WHERE id=?",
        _income_tuple(body) + (iid,))
    return {"ok": True}


@router.delete("/income/{iid}")
def delete_income(iid: int, user=Depends(require_user)):
    db.execute("DELETE FROM income_sources WHERE id=?", (iid,))
    return {"ok": True}


# ---- bills ----
class BillIn(BaseModel):
    name: str
    amount_cents: int = 0
    due_dom: int = 1
    category: str = ""
    autopay: int = 0
    where_to_pay: str = ""
    responsible_earner_id: int | None = None
    funding_mode: str = "auto"
    funding_source_id: int | None = None
    funding_occurrence: int | None = None


def _bill_tuple(b: BillIn):
    return (b.name, b.amount_cents, b.due_dom, b.category, b.autopay, b.where_to_pay,
            b.responsible_earner_id, b.funding_mode, b.funding_source_id, b.funding_occurrence)


@router.post("/bills")
def add_bill(body: BillIn, user=Depends(require_user)):
    bid = db.execute(
        "INSERT INTO bills (name, amount_cents, due_dom, category, autopay, where_to_pay,"
        " responsible_earner_id, funding_mode, funding_source_id, funding_occurrence)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)", _bill_tuple(body))
    return {"id": bid}


@router.put("/bills/{bid}")
def update_bill(bid: int, body: BillIn, user=Depends(require_user)):
    db.execute(
        "UPDATE bills SET name=?, amount_cents=?, due_dom=?, category=?, autopay=?, where_to_pay=?,"
        " responsible_earner_id=?, funding_mode=?, funding_source_id=?, funding_occurrence=? WHERE id=?",
        _bill_tuple(body) + (bid,))
    return {"ok": True}


@router.delete("/bills/{bid}")
def delete_bill(bid: int, user=Depends(require_user)):
    db.execute("DELETE FROM bills WHERE id=?", (bid,))
    return {"ok": True}


# ---- debts ----
class DebtIn(BaseModel):
    name: str
    balance_cents: int = 0
    min_payment_cents: int = 0
    apr: float = 0.0
    roll_order: int = 0


@router.post("/debts")
def add_debt(body: DebtIn, user=Depends(require_user)):
    did = db.execute(
        "INSERT INTO debts (name, balance_cents, min_payment_cents, apr, roll_order) VALUES (?,?,?,?,?)",
        (body.name, body.balance_cents, body.min_payment_cents, body.apr, body.roll_order))
    return {"id": did}


@router.put("/debts/{did}")
def update_debt(did: int, body: DebtIn, user=Depends(require_user)):
    db.execute(
        "UPDATE debts SET name=?, balance_cents=?, min_payment_cents=?, apr=?, roll_order=? WHERE id=?",
        (body.name, body.balance_cents, body.min_payment_cents, body.apr, body.roll_order, did))
    return {"ok": True}


@router.delete("/debts/{did}")
def delete_debt(did: int, user=Depends(require_user)):
    db.execute("DELETE FROM debts WHERE id=?", (did,))
    return {"ok": True}


# ---- settings ----
class SettingsIn(BaseModel):
    timezone: str = "America/Chicago"
    sensors_enabled: int = 1
    notify_service: str = "notify"
    alert_days_ahead: int = 3


@router.put("/settings")
def save_settings(body: SettingsIn, user=Depends(require_user)):
    db.set_setting("timezone", body.timezone.strip() or "America/Chicago")
    db.set_setting("sensors_enabled", "1" if body.sensors_enabled else "0")
    db.set_setting("notify_service", body.notify_service.strip() or "notify")
    db.set_setting("alert_days_ahead", str(body.alert_days_ahead))
    return {"ok": True}


# ======================= budgets / transactions =======================

class BudgetIn(BaseModel):
    category: str
    monthly_limit_cents: int = 0


class SpendIn(BaseModel):
    year: int | None = None
    month: int | None = None
    category: str = ""
    description: str = ""
    amount_cents: int = 0
    txn_date: str = ""


@router.get("/budgets")
def budgets(year: int | None = None, month: int | None = None, user=Depends(require_user)):
    y, m = _period(year, month)
    rows, untracked = budget.budget_status(y, m)
    return {
        "year": y, "month": m, "label": budget.month_label(y, m),
        "rows": rows, "untracked": untracked,
        "transactions": db.query(
            "SELECT * FROM transactions WHERE year=? AND month=? ORDER BY id DESC", (y, m)),
        "categories": [r["category"] for r in db.query(
            "SELECT DISTINCT category FROM bills WHERE category != '' ORDER BY category")],
    }


@router.post("/budgets")
def save_budget(body: BudgetIn, user=Depends(require_user)):
    cat = body.category.strip()
    if cat:
        db.execute(
            "INSERT INTO budgets (category, monthly_limit_cents) VALUES (?,?) "
            "ON CONFLICT(category) DO UPDATE SET monthly_limit_cents=excluded.monthly_limit_cents",
            (cat, body.monthly_limit_cents))
    return {"ok": True}


@router.delete("/budgets/{bid}")
def delete_budget(bid: int, user=Depends(require_user)):
    db.execute("DELETE FROM budgets WHERE id=?", (bid,))
    return {"ok": True}


@router.post("/transactions")
def add_transaction(body: SpendIn, user=Depends(require_user)):
    y, m = _period(body.year, body.month)
    db.execute(
        "INSERT INTO transactions (year, month, category, description, amount_cents, txn_date)"
        " VALUES (?,?,?,?,?,?)",
        (y, m, body.category.strip(), body.description.strip(), body.amount_cents,
         body.txn_date or budget.now_ct().date().isoformat()))
    return {"ok": True}


@router.delete("/transactions/{tid}")
def delete_transaction(tid: int, user=Depends(require_user)):
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    return {"ok": True}


# ======================= period actuals (history) =======================

class PaycheckActualIn(BaseModel):
    year: int
    month: int
    source_id: int
    occurrence: int
    pay_date: str = ""
    amount_cents: int = 0
    motus_cents: int = 0


class BillPaymentIn(BaseModel):
    year: int
    month: int
    bill_id: int
    paid_cents: int = 0
    paid: int = 0
    funding_source_id: int | None = None
    funding_occurrence: int | None = None


@router.post("/period/paycheck")
def save_paycheck(body: PaycheckActualIn, user=Depends(require_user)):
    db.execute(
        "INSERT INTO paycheck_actuals (year, month, source_id, occurrence, pay_date, amount_cents,"
        " motus_cents) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(year, month, source_id, occurrence) DO UPDATE SET "
        "pay_date=excluded.pay_date, amount_cents=excluded.amount_cents, motus_cents=excluded.motus_cents",
        (body.year, body.month, body.source_id, body.occurrence, body.pay_date,
         body.amount_cents, body.motus_cents))
    return {"ok": True}


@router.post("/period/bill")
def save_bill_payment(body: BillPaymentIn, user=Depends(require_user)):
    db.execute(
        "INSERT INTO bill_payments (year, month, bill_id, paid_cents, paid, funding_source_id,"
        " funding_occurrence) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(year, month, bill_id) DO UPDATE SET "
        "paid_cents=excluded.paid_cents, paid=excluded.paid, "
        "funding_source_id=excluded.funding_source_id, funding_occurrence=excluded.funding_occurrence",
        (body.year, body.month, body.bill_id, body.paid_cents, body.paid,
         body.funding_source_id, body.funding_occurrence))
    return {"ok": True}


# ======================= net worth / accounts =======================

class AccountIn(BaseModel):
    name: str
    kind: str = "checking"
    is_liability: int = 0
    institution: str = ""
    owner_earner_id: int | None = None
    active: int = 1
    sort_order: int = 0


class BalanceIn(BaseModel):
    as_of: str
    balance_cents: int = 0


@router.get("/accounts")
def accounts(user=Depends(require_user)):
    return {
        "summary": budget.net_worth_summary(),
        "series": budget.net_worth_series(),
        "earners": db.query("SELECT id, name, color FROM earners"),
        "kinds": ["checking", "savings", "investment", "cash", "property", "loan", "credit", "other"],
    }


@router.post("/accounts")
def add_account(body: AccountIn, user=Depends(require_user)):
    aid = db.execute(
        "INSERT INTO accounts (name, kind, is_liability, institution, owner_earner_id, active, sort_order)"
        " VALUES (?,?,?,?,?,?,?)",
        (body.name, body.kind, body.is_liability, body.institution, body.owner_earner_id,
         body.active, body.sort_order))
    return {"id": aid}


@router.put("/accounts/{aid}")
def update_account(aid: int, body: AccountIn, user=Depends(require_user)):
    db.execute(
        "UPDATE accounts SET name=?, kind=?, is_liability=?, institution=?, owner_earner_id=?,"
        " active=?, sort_order=? WHERE id=?",
        (body.name, body.kind, body.is_liability, body.institution, body.owner_earner_id,
         body.active, body.sort_order, aid))
    return {"ok": True}


@router.delete("/accounts/{aid}")
def delete_account(aid: int, user=Depends(require_user)):
    db.execute("DELETE FROM accounts WHERE id=?", (aid,))
    db.execute("DELETE FROM account_balances WHERE account_id=?", (aid,))
    return {"ok": True}


@router.post("/accounts/{aid}/balance")
def record_balance(aid: int, body: BalanceIn, user=Depends(require_user)):
    db.execute(
        "INSERT INTO account_balances (account_id, as_of, balance_cents) VALUES (?,?,?) "
        "ON CONFLICT(account_id, as_of) DO UPDATE SET balance_cents=excluded.balance_cents",
        (aid, body.as_of or budget.now_ct().date().isoformat(), body.balance_cents))
    return {"ok": True}


# ======================= goals (sinking funds) =======================

class GoalIn(BaseModel):
    name: str
    target_cents: int = 0
    current_cents: int = 0
    target_date: str = ""


@router.get("/goals")
def goals(user=Depends(require_user)):
    rows = db.query("SELECT * FROM goals ORDER BY target_date, name")
    for g in rows:
        g["pct"] = round(g["current_cents"] / g["target_cents"] * 100) if g["target_cents"] else 0
    return {"goals": rows}


@router.post("/goals")
def add_goal(body: GoalIn, user=Depends(require_user)):
    gid = db.execute(
        "INSERT INTO goals (name, target_cents, current_cents, target_date) VALUES (?,?,?,?)",
        (body.name, body.target_cents, body.current_cents, body.target_date))
    return {"id": gid}


@router.put("/goals/{gid}")
def update_goal(gid: int, body: GoalIn, user=Depends(require_user)):
    db.execute(
        "UPDATE goals SET name=?, target_cents=?, current_cents=?, target_date=? WHERE id=?",
        (body.name, body.target_cents, body.current_cents, body.target_date, gid))
    return {"ok": True}


@router.delete("/goals/{gid}")
def delete_goal(gid: int, user=Depends(require_user)):
    db.execute("DELETE FROM goals WHERE id=?", (gid,))
    return {"ok": True}


# ======================= reports =======================

@router.get("/reports")
def reports(months: int = 12, year: int | None = None, month: int | None = None,
            user=Depends(require_user)):
    y, m = _period(year, month)
    return {
        "cashflow": budget.cashflow_series(max(3, min(months, 24))),
        "category": budget.category_breakdown(y, m),
        "net_worth": budget.net_worth_series(),
        "snowball": budget.snowball_projection()[1],
        "budget_status": budget.budget_status(y, m)[0],
        "label": budget.month_label(y, m),
    }


# ======================= web terminal =======================

@router.post("/term/exec")
def term_exec(body: dict = Body(...), user=Depends(require_user)):
    return {"output": tui.run(body.get("line", ""))}


# ======================= alerts test =======================

@router.post("/alerts/test")
def alerts_test(user=Depends(require_user)):
    cy, cm = budget.current_period()
    if db.get_setting("sensors_enabled", "1") == "1":
        ha.push_sensors(budget.sensor_payload(cy, cm))
    al = budget.detect_alerts(cy, cm)
    msg = "Perry Budget test: HA link is working. ✓" if not al else \
        "Perry Budget — " + "; ".join(a["text"] for a in al[:3])
    service = db.get_setting("notify_service", "notify") or "notify"
    ha.notify(msg, service=service)
    return {"ok": True, "sent": msg}
