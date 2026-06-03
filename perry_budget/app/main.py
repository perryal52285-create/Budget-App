"""Perry Budget — FastAPI app served via Home Assistant ingress."""
import os

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import db, budget

BASE = os.path.dirname(__file__)
app = FastAPI(title="Perry Budget")
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))


@app.on_event("startup")
def _startup():
    db.init_db()


def ctx(request: Request, **extra):
    base = request.headers.get("X-Ingress-Path", "")
    now = budget.now_ct()
    data = {
        "request": request, "base": base, "fmt": budget.fmt,
        "now_str": now.strftime("%a %b %-d, %Y · %-I:%M %p"),
        "tz_name": db.get_setting("timezone", "America/Chicago"),
        "month_names": budget.MONTH_NAMES,
    }
    data.update(extra)
    return data


def _cents(value) -> int:
    try:
        return round(float(str(value).replace(",", "").replace("$", "").strip()) * 100)
    except (ValueError, AttributeError):
        return 0


def _int(value, default=0) -> int:
    try:
        return int(str(value).strip())
    except (ValueError, AttributeError):
        return default


def _float(value, default=0.0) -> float:
    try:
        return float(str(value).strip())
    except (ValueError, AttributeError):
        return default


def back(request: Request, anchor: str = "") -> RedirectResponse:
    base = request.headers.get("X-Ingress-Path", "")
    return RedirectResponse(url=f"{base}/manage{anchor}", status_code=303)


def back_dash(request: Request, year: int, month: int) -> RedirectResponse:
    base = request.headers.get("X-Ingress-Path", "")
    return RedirectResponse(url=f"{base}/?year={year}&month={month}", status_code=303)


# ---- dashboard -----------------------------------------------------------

@app.get("/")
def dashboard(request: Request, year: int = None, month: int = None):
    cy, cm = budget.current_period()
    year = year or cy
    month = month or cm
    if month < 1 or month > 12:
        year, month = cy, cm

    if (year, month) == (cy, cm):
        budget.snapshot_debts(year, month)  # keep current-month debt history fresh

    view = budget.month_view(year, month)
    py, pm = budget.shift_month(year, month, -1)
    ny, nm = budget.shift_month(year, month, 1)
    months_, points = budget.snowball_projection()
    chart = budget.svg_area_chart(points)

    return templates.TemplateResponse("dashboard.html", ctx(
        request,
        view=view,
        prev={"year": py, "month": pm},
        next={"year": ny, "month": nm},
        is_current=(year, month) == (cy, cm),
        three_check=budget.three_check_months(year),
        total_debt=budget.total_debt(),
        next_target=budget.next_target(),
        payoff_months=months_,
        chart=chart,
    ))


# ---- manage --------------------------------------------------------------

@app.get("/manage")
def manage(request: Request):
    sources = db.query("SELECT * FROM income_sources ORDER BY earner_id, name")
    for s in sources:
        s["preview"] = budget.source_preview(s)
    return templates.TemplateResponse("manage.html", ctx(
        request,
        earners=db.query("SELECT * FROM earners ORDER BY is_primary DESC, name"),
        sources=sources,
        bills=db.query("SELECT * FROM bills ORDER BY name"),
        debts=db.query("SELECT * FROM debts ORDER BY roll_order, balance_cents"),
        frequencies=["weekly", "biweekly", "semimonthly", "monthly", "annual", "one_time"],
        kinds=["payroll", "reimbursement", "bonus_annual", "one_time", "other"],
    ))


# ---- earners -------------------------------------------------------------

@app.post("/manage/earners/add")
def add_earner(request: Request, name: str = Form(...), color: str = Form("#46d970")):
    db.execute("INSERT INTO earners (name, color, is_primary) VALUES (?,?,0)", (name, color))
    return back(request, "#earners")


@app.post("/manage/earners/{earner_id}/update")
def update_earner(request: Request, earner_id: int, name: str = Form(...), color: str = Form("#46d970")):
    db.execute("UPDATE earners SET name=?, color=? WHERE id=?", (name, color, earner_id))
    return back(request, "#earners")


@app.post("/manage/earners/{earner_id}/delete")
def delete_earner(request: Request, earner_id: int):
    db.execute("DELETE FROM earners WHERE id=?", (earner_id,))
    return back(request, "#earners")


# ---- income sources ------------------------------------------------------

def _income_fields(form):
    return (
        _int(form.get("earner_id")), form.get("name", ""), form.get("kind", "payroll"),
        _cents(form.get("amount", 0)), form.get("frequency", "biweekly"),
        form.get("anchor_date", ""), _int(form.get("day1"), 1), _int(form.get("day2"), 0),
        _int(form.get("month"), 1), 1 if form.get("active", "1") else 0, form.get("notes", ""),
    )


@app.post("/manage/income/add")
async def add_income(request: Request):
    f = await request.form()
    db.execute(
        "INSERT INTO income_sources (earner_id, name, kind, amount_cents, frequency, anchor_date,"
        " day1, day2, month, active, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", _income_fields(f))
    return back(request, "#income")


@app.post("/manage/income/{source_id}/update")
async def update_income(request: Request, source_id: int):
    f = await request.form()
    vals = _income_fields(f) + (source_id,)
    db.execute(
        "UPDATE income_sources SET earner_id=?, name=?, kind=?, amount_cents=?, frequency=?,"
        " anchor_date=?, day1=?, day2=?, month=?, active=?, notes=? WHERE id=?", vals)
    return back(request, "#income")


@app.post("/manage/income/{source_id}/delete")
def delete_income(request: Request, source_id: int):
    db.execute("DELETE FROM income_sources WHERE id=?", (source_id,))
    return back(request, "#income")


# ---- bills ---------------------------------------------------------------

@app.post("/manage/bills/add")
async def add_bill(request: Request):
    f = await request.form()
    resp = _int(f.get("responsible_earner_id")) or None
    fsrc = _int(f.get("funding_source_id")) or None
    focc = _int(f.get("funding_occurrence")) or None
    db.execute(
        "INSERT INTO bills (name, amount_cents, due_dom, category, autopay, where_to_pay,"
        " responsible_earner_id, funding_mode, funding_source_id, funding_occurrence)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (f.get("name", ""), _cents(f.get("amount", 0)), _int(f.get("due_dom"), 1),
         f.get("category", ""), 1 if f.get("autopay") else 0, f.get("where_to_pay", ""),
         resp, f.get("funding_mode", "auto"), fsrc, focc))
    return back(request, "#bills")


@app.post("/manage/bills/{bill_id}/delete")
def delete_bill(request: Request, bill_id: int):
    db.execute("DELETE FROM bills WHERE id=?", (bill_id,))
    return back(request, "#bills")


# ---- debts ---------------------------------------------------------------

@app.post("/manage/debts/add")
def add_debt(request: Request, name: str = Form(...), balance: str = Form("0"),
             min_payment: str = Form("0"), apr: str = Form("0"), roll_order: str = Form("0")):
    db.execute(
        "INSERT INTO debts (name, balance_cents, min_payment_cents, apr, roll_order) VALUES (?,?,?,?,?)",
        (name, _cents(balance), _cents(min_payment), _float(apr), _int(roll_order)))
    return back(request, "#debts")


@app.post("/manage/debts/{debt_id}/delete")
def delete_debt(request: Request, debt_id: int):
    db.execute("DELETE FROM debts WHERE id=?", (debt_id,))
    return back(request, "#debts")


# ---- settings ------------------------------------------------------------

@app.post("/manage/settings/save")
def save_settings(request: Request, timezone: str = Form("America/Chicago")):
    db.set_setting("timezone", timezone.strip() or "America/Chicago")
    return back(request, "#settings")


# ---- per-month actuals (history) -----------------------------------------

@app.post("/period/paycheck/save")
def save_paycheck_actual(request: Request, year: int = Form(...), month: int = Form(...),
                         source_id: int = Form(...), occurrence: int = Form(...),
                         pay_date: str = Form(""), amount: str = Form("0"), motus: str = Form("0")):
    db.execute(
        "INSERT INTO paycheck_actuals (year, month, source_id, occurrence, pay_date, amount_cents,"
        " motus_cents) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(year, month, source_id, occurrence) DO UPDATE SET "
        "pay_date=excluded.pay_date, amount_cents=excluded.amount_cents, motus_cents=excluded.motus_cents",
        (year, month, source_id, occurrence, pay_date, _cents(amount), _cents(motus)))
    return back_dash(request, year, month)


@app.post("/period/bill/save")
async def save_bill_payment(request: Request):
    f = await request.form()
    year, month = _int(f.get("year")), _int(f.get("month"))
    fsrc = _int(f.get("funding_source_id")) or None
    focc = _int(f.get("funding_occurrence")) or None
    db.execute(
        "INSERT INTO bill_payments (year, month, bill_id, paid_cents, paid, funding_source_id,"
        " funding_occurrence) VALUES (?,?,?,?,?,?,?) "
        "ON CONFLICT(year, month, bill_id) DO UPDATE SET "
        "paid_cents=excluded.paid_cents, paid=excluded.paid, "
        "funding_source_id=excluded.funding_source_id, funding_occurrence=excluded.funding_occurrence",
        (year, month, _int(f.get("bill_id")), _cents(f.get("paid_cents", 0)),
         1 if f.get("paid") else 0, fsrc, focc))
    return back_dash(request, year, month)
