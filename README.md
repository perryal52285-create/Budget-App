# Perry Budget

A Home Assistant add-on: a per-paycheck **envelope budget** with a **debt snowball**, in two looks —
a **terminal** dark mode and a **bubbly** light mode (toggle in the header).

## Install on Home Assistant

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add: `https://github.com/perryal52285-create/Budget-App`
3. Install **Perry Budget**, then **Start**. Open it from the sidebar (ingress).

> **Updating:** HA rebuilds the add-on from this repo. After any change, **commit + push to GitHub**,
> then in HA hit **Update** / **Rebuild**. HA cannot build from local/unpushed changes.

## Features (Phase 1)

- **Dashboard** — per-check available/remaining, total debt, projected payoff, debt-paydown chart, bills per check.
- **Manage** — edit all inputs in one place: paychecks (net + variable **Motus** reimbursement), bills (with 14th/28th assignment), and debts (with snowball roll order).
- **Themes** — dark = terminal (phosphor green/mono), light = bubbly (pastel/rounded). Preference saved per browser.

Data is stored in SQLite under the add-on's `/data` (persists across restarts/updates).

## Roadmap

- Phase 2: full snowball controls + payoff projections
- Phase 3: budgets + HA notification alerts + HA sensor export
- Phase 4: forecasting / savings goals (incl. lump sums)
- Phase 5: paystub PDF upload + parse, CSV import

## Local development

```bash
cd perry_budget
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=./data python3 -m uvicorn app.main:app --reload --port 8099
# open http://localhost:8099
```
