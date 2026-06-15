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

## Status

Rebuilt as a **React SPA** (`/ui`) on the same FastAPI/SQLite engine:
two-user auth, per-user theme lock (Alex=terminal, Rae=bubbly), Dashboard,
**Net Worth** (accounts + balance history), **Goals/sinking funds**, Budgets,
Manage (full CRUD), **Reports** (cash flow / category / net-worth trends), the
command **Terminal**, HA sensors + alerts, and an installable **PWA**.

## Roadmap

- Envelope **rollover / month-end true-up** for category budgets
- **Scheduled transactions + rules** (auto-categorize) and **split transactions**
- Paystub PDF upload + parse (portal only), **CSV import**

> Security: this tool only needs transaction/payment data — **never** store bank/portal login
> passwords or API tokens in source. Any future tokens go in the add-on's options store.

## Remote access (Cloudflare Tunnel)

The app is a React SPA at **`/ui`** with a password-protected JSON API at `/api`
(two users: `alex`, `rae`). Inside Home Assistant it's reached via ingress. To
reach it **from anywhere**, expose the add-on's standalone port (`8099`) through a
Cloudflare Tunnel — no port-forwarding, free, and HTTPS end to end.

1. **Install the Cloudflared add-on** (HA community add-on store) **or** run
   `cloudflared` anywhere on the LAN.
2. In **Cloudflare Zero Trust → Networks → Tunnels**, create a tunnel and add a
   **public hostname** (e.g. `budget.yourdomain.com`).
3. Point that hostname at the service:
   `http://<home-assistant-ip>:8099` (the Perry Budget add-on port).
4. Open `https://budget.yourdomain.com` → you'll land on the login screen.

**Security model when tunneled:** the app's own login is the only wall, so:
- Session cookies are automatically marked **`Secure`** behind the tunnel
  (the app honors `X-Forwarded-Proto`; `run.sh` starts uvicorn with
  `--proxy-headers`).
- Change both users off the seeded `Test#1` on first login.
- The legacy ungated Jinja pages have been **removed** — every route is either
  the static SPA shell or an auth-gated API call.
- **Recommended hardening:** put **Cloudflare Access** in front of the hostname
  (email OTP / Google login) for a second factor before the app's own login.

## Local development

```bash
cd perry_budget
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=./data python3 -m uvicorn app.main:app --reload --port 8099
# open http://localhost:8099
```
