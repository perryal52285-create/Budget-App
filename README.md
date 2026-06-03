# Perry Budget

A Home Assistant add-on that runs your household budget the way your spreadsheet does:
**real paychecks → funded bills → debt snowball**, with full history kept month to month.
Two looks, one toggle in the header: a **terminal** dark mode and a **bubbly** light mode.

## Install on Home Assistant

1. **Settings → Add-ons → Add-on Store → ⋮ → Repositories**
2. Add: `https://github.com/perryal52285-create/Budget-App`
3. Install **Perry Budget**, then **Start**. Open it from the sidebar (ingress).

Data lives in SQLite under the add-on's `/data` and **persists across restarts, updates, and
rebuilds**. New columns are added with additive migrations, so updating never wipes your data.

## Updating

HA rebuilds the add-on **only from the pushed GitHub repo** — it cannot build from local or
unpushed changes. So the flow for any change is:

1. **Commit + push to GitHub.**
2. Bump `version` in `perry_budget/config.yaml` (e.g. `0.2.0` → `0.2.1`). **HA only shows
   "Update available" when this number increases.** Without a bump, a push is invisible to HA
   until you manually **Rebuild**.
3. In HA: **Update** (if the version changed) or **Rebuild** (to force-pull the same version).

## How it works

### Income — a real pay schedule, per earner
Income is modeled as **sources** attached to **earners** (you + your wife, each with a color),
not fixed slots. Each source has a frequency and the app computes the actual pay dates:

- **biweekly / weekly** — repeat ±14 / ±7 days from an **anchor date** (e.g. `2026-06-05`). This is
  what produces the **two 3-paycheck months a year**.
- **semimonthly** — two days a month (`day1` / `day2`; `0` = last day).
- **monthly** — one day a month.
- **annual** — a month + day (your **January bonus**).
- **one_time** — a single dated payment.

**Motus** (your variable after-tax vehicle reimbursement) is modeled as a *reimbursement* source
tied to an earner; it rides onto that earner's first payroll check of the month. The **3rd
paycheck** in a 3-check month is flagged as **surplus** and gets **no auto-assigned bills** — it's
shown for you to snowball or save.

Everything is editable on the **Manage** page: name, **employer**, earner, kind, frequency, amount,
pay dates/anchor, and active state — with a live preview of the next ~6 pay dates.

### Bills — hybrid funding
Each bill has a **due day** and a responsible earner (or joint). Funding is:

- **auto** — lands on the latest non-surplus paycheck on or before the due day (restricted to the
  responsible earner when one is set);
- **manual** — pinned to a specific source + check number.

### Debts — snowball
Debts carry balance, min payment, APR, and roll order. The dashboard shows total debt, the next
snowball target, a projected payoff in months, and a server-rendered paydown chart.

### History retention
Definitions (income sources, bills, debts) are the recurring **template**. Each month's **actuals**
— recorded paychecks, bill payments, and debt balances — are stored per `(year, month)`, so
browsing to a past month shows what really happened, and editing the template never rewrites the
past.

### Time & current month
A configurable **timezone** (default **America/Chicago / CT**) drives the current-month default and
the header clock. Change it on **Manage → Settings**.

### Themes
- **Dark = terminal** (phosphor green, monospace, CRT scanlines) — your side.
- **Light = bubbly** (pastel, rounded, emoji throughout) — your wife's side.

Preference is saved per browser and applied before paint (no flash).

## Roadmap

- **Phase 3** — budgets + HA notification alerts + HA sensor export
- **Phase 4** — forecasting / savings goals (incl. the bonus & 3-check surplus)
- **Phase 5** — paystub PDF upload + parse (portal only), CSV import

> Security: this tool only needs transaction/payment data — **never** store bank/portal login
> passwords or API tokens in source. Any future tokens go in the add-on's options store.

## Local development

```bash
cd perry_budget
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=./data python3 -m uvicorn app.main:app --reload --port 8099
# open http://localhost:8099
```
