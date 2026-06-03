# Changelog

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
