# RS Screener Dashboard

A Next.js dashboard for the TradingAgents India relative-strength screener and
This dashboard reads paper books, screens, and strategy desks from local JSON under
`~/.tradingagents/` (no Supabase required for daily use). Run jobs from **Command center**
or each desk's **Desk actions** panel.
`tradingagents screen` and displays them — picks, AI decisions, paper P&L, and
per-signal reliability.

- **Overview** — win rate, avg return, avg alpha vs Nifty, realized P&L, and a
  reliability-by-signal chart.
- **Screens** — history of screen runs with ranked candidates, fired signals,
  and the AI's rating.
- **Positions** — open and closed paper trades, scored on return and alpha.

## Quick start

See **[SETUP.md](./SETUP.md)** for the full walkthrough (Supabase + Vercel,
all free). In short:

```bash
npm install
cp .env.example .env.local   # add NEXT_PUBLIC_SUPABASE_URL + ANON_KEY
npm run dev                  # http://localhost:3000
```

Deploy on Vercel with **Root Directory = `dashboard`** and the two
`NEXT_PUBLIC_SUPABASE_*` env vars.

Stack: Next.js 16 (App Router) · React 19 · Tailwind v4 · Recharts ·
@supabase/supabase-js.
