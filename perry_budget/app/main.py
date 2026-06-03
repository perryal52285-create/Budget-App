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
    """Shared template context. `base` makes links work under the ingress prefix."""
    base = request.headers.get("X-Ingress-Path", "")
    data = {"request": request, "base": base, "fmt": budget.fmt}
    data.update(extra)
    return data


def _cents(value: str) -> int:
    try:
        return round(float(str(value).replace(",", "").replace("$", "").strip()) * 100)
    except (ValueError, AttributeError):
        return 0


def back(request: Request, anchor: str = "") -> RedirectResponse:
    base = request.headers.get("X-Ingress-Path", "")
    return RedirectResponse(url=f"{base}/manage{anchor}", status_code=303)


# ---- pages ---------------------------------------------------------------

@app.get("/")
def dashboard(request: Request):
    env = budget.envelope_summary()
    months, points = budget.snowball_projection()
    chart = budget.svg_area_chart(points)
    return templates.TemplateResponse("dashboard.html", ctx(
        request,
        env=env,
        total_debt=budget.total_debt(),
        next_target=budget.next_target(),
        payoff_months=months,
        chart=chart,
    ))


@app.get("/manage")
def manage(request: Request):
    return templates.TemplateResponse("manage.html", ctx(
        request,
        paychecks=db.query("SELECT * FROM paychecks ORDER BY label"),
        bills=db.query("SELECT * FROM bills ORDER BY assignment, name"),
        debts=db.query("SELECT * FROM debts ORDER BY roll_order, balance_cents"),
        checks=budget.CHECKS,
    ))


# ---- paychecks -----------------------------------------------------------

@app.post("/manage/paychecks/save")
def save_paycheck(request: Request, label: str = Form(...), net: str = Form("0"),
                  motus: str = Form("0"), other: str = Form("0"), notes: str = Form("")):
    existing = db.query("SELECT id FROM paychecks WHERE label = ?", (label,))
    if existing:
        db.execute(
            "UPDATE paychecks SET net_cents=?, motus_cents=?, other_cents=?, notes=? WHERE label=?",
            (_cents(net), _cents(motus), _cents(other), notes, label))
    else:
        db.execute(
            "INSERT INTO paychecks (label, net_cents, motus_cents, other_cents, notes) VALUES (?,?,?,?,?)",
            (label, _cents(net), _cents(motus), _cents(other), notes))
    return back(request, "#income")


# ---- bills ---------------------------------------------------------------

@app.post("/manage/bills/add")
def add_bill(request: Request, name: str = Form(...), amount: str = Form("0"),
             due_day: str = Form(""), category: str = Form(""),
             where_to_pay: str = Form(""), assignment: str = Form("14th"),
             autopay: str = Form("")):
    db.execute(
        "INSERT INTO bills (name, amount_cents, due_day, category, where_to_pay, assignment, autopay)"
        " VALUES (?,?,?,?,?,?,?)",
        (name, _cents(amount), due_day, category, where_to_pay, assignment, 1 if autopay else 0))
    return back(request, "#bills")


@app.post("/manage/bills/{bill_id}/delete")
def delete_bill(request: Request, bill_id: int):
    db.execute("DELETE FROM bills WHERE id=?", (bill_id,))
    return back(request, "#bills")


# ---- debts ---------------------------------------------------------------

@app.post("/manage/debts/add")
def add_debt(request: Request, name: str = Form(...), balance: str = Form("0"),
             min_payment: str = Form("0"), apr: str = Form("0"), roll_order: str = Form("0")):
    try:
        order = int(roll_order)
    except ValueError:
        order = 0
    try:
        apr_v = float(apr)
    except ValueError:
        apr_v = 0.0
    db.execute(
        "INSERT INTO debts (name, balance_cents, min_payment_cents, apr, roll_order) VALUES (?,?,?,?,?)",
        (name, _cents(balance), _cents(min_payment), apr_v, order))
    return back(request, "#debts")


@app.post("/manage/debts/{debt_id}/delete")
def delete_debt(request: Request, debt_id: int):
    db.execute("DELETE FROM debts WHERE id=?", (debt_id,))
    return back(request, "#debts")
