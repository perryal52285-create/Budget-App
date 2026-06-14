# Changelog

## 0.4.0
- **React rebuild — Phase 0 (scaffold).** Groundwork for the new password-protected,
  mobile-first React frontend. Nothing user-facing changes yet: the classic UI still
  serves at `/`.
  - New **JSON API** (`/api`) exposing the budget engine — starting with `/api/health`.
    Additive; the existing Jinja routes are untouched.
  - New **React + Vite SPA** served at `/ui`, built in a **multi-stage Docker** image
    (Node builds the bundle → copied into the Python runtime). Same push-to-update flow.
  - **HA ingress base-path handling:** the server injects a runtime `<base href>` and
    API/router base derived from `X-Ingress-Path`, so the SPA works behind ingress and
    standalone on `:8099`.
- Next phases: two-user auth (Alex/Rae) → React dashboard → manage/budgets/debts →
  terminal + dual-theme polish + mobile/PWA → retire Jinja → Cloudflare tunnel.

## 0.3.3
- **Fix:** the allocation donut rendered huge and showed both the 🐱 and the income
  number at once. Cause was the browser serving a stale cached `theme.css` from before
  the redesign. Static CSS/JS are now cache-busted by version (`?v=`), so each update
  forces a fresh stylesheet — the donut sizes correctly (300px) and the dual-theme
  center label shows just one element per theme.

## 0.3.2
- **Earner accordion cards** — Manage page now groups each person's income sources under their
  own collapsible card. Click ▾ to expand/collapse; "Add income for [Name]" pre-selects that
  earner in the pop-out.
- **Dashboard redesign** — removed per-paycheck detail clutter. New layout: big allocation
  donut (full-width) → upcoming bills by due day + income dates side-by-side → debt chart.
  Record-actual moved to clean modal pop-outs (✎ button per paycheck row).
- **Bubbly full-tilt** — animated gradient background, rainbow cycling brand text with 🐱,
  pill-shaped gradient buttons, sparkle floating in topbar, colored card left-borders with
  staggered entrance, rainbow panel-heads, earner card pop-in, pastel alerts.
- **Bubbly donut** — rainbow segment colors, emoji legend (🏠⚡🚗💰…), 🐱 emoji center.
- **Terminal donut** — phosphor green shade segments with oscillating pulse-glow animation.

## 0.3.1
- **Fix:** adding a bill failed with "Internal Server Error" on databases that
  carried over from an earlier install — the `bills` table was missing the
  columns added in Phase 2. Added migrations so old databases self-upgrade
  (existing rows are preserved).
- **Allocation donut** — a themed donut chart on the dashboard shows where each
  month's income goes (bills by category + what's left).
- **Pop-out dialogs** — adding/editing income, bills, debts, earners, budgets,
  and spending now happens in clean modal pop-outs instead of long inline forms.
- **Tidier Manage page** — income/bills/debts shown as compact tables with
  edit/delete actions; the page no longer stacks every field down the screen.

## 0.3.0
- **Category budgets** — set a monthly cap per category; spend = recurring bills +
  ad-hoc logged spending, shown as progress bars that flag when you go over.
- **Spending log** — record one-off transactions per month so budgets reflect reality.
- **Home Assistant alerts** — a "send test alert" button and a configurable notify
  service push nudges for unfunded bills, over-budget categories, and imminent paychecks.
- **Home Assistant sensors** — publishes `sensor.perry_budget_*` (total debt, remaining,
  income, bills, payoff months, next target, days to paycheck, unfunded/over-budget counts)
  for dashboards and automations. Refreshes when the current month is viewed.
- **Web terminal (TUI)** — a command-driven terminal at `/term`: `show`, `bal`, `next`,
  `budget`, `spend`, `add bill`, `add debt`, `alerts`, with command history.
- **Standalone access** — the app is now reachable directly on port 8099 (LAN), in
  addition to Home Assistant ingress.

## 0.2.0
- **Real pay-date engine** — biweekly/weekly (anchor + step), semimonthly, monthly, annual,
  one-time. Produces the two 3-paycheck months a year automatically.
- **Two earners** with their own colors, income sources, and bill responsibilities.
- **Motus** modeled as a reimbursement that rides an earner's first payroll check.
- **Annual January bonus** support; 3rd paycheck shown as **surplus** (no auto-assigned bills).
- **Hybrid bill funding** — auto (latest non-surplus check before due day) or manual (pinned slot).
- **Monthly history retention** — per-month paycheck actuals, bill payments, and debt snapshots,
  kept separately from the editable template.
- **Configurable timezone** (default America/Chicago / CT) drives the current month + header clock.
- **Editable payroll** including pay dates, frequency, and **employer**.
- Manage page rebuilt: earners, income sources (with next-pay-date preview), bills, debts, settings.

## 0.1.0
- Initial release: per-paycheck envelope budget, debt snowball, terminal/bubbly themes.
