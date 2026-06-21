# Dashboard setup (free hosting)

A Next.js dashboard for the India RS screener + paper-trading results.

**How it works:** your machine runs `tradingagents screen`, which publishes
results to a free Supabase database. This dashboard (deployed free on Vercel)
reads from Supabase and displays picks, decisions, and paper-trading P&L. It
stays online even when your computer is off.

```
[your Mac]  tradingagents screen  ──writes──▶  Supabase (free DB)  ──reads──▶  [Vercel dashboard]
```

Hosting is 100% free. (The OpenAI API calls during a screen still cost tokens —
that's the analysis, not the hosting.)

---

## 1. Create a free Supabase project

1. Go to https://supabase.com → sign up → **New project** (free tier).
2. Pick a name + database password, choose a region near you, create it.
3. Once ready, open **SQL Editor** → **New query**, paste this, and **Run**:

```sql
create table if not exists snapshots (
  id          bigint generated always as identity primary key,
  kind        text not null check (kind in ('screen','paper')),
  created_at  timestamptz not null default now(),
  data        jsonb not null
);

create index if not exists snapshots_kind_created_idx
  on snapshots (kind, created_at desc);

-- Row-level security: allow public READ only. Writes use the service_role
-- key (which bypasses RLS), so no insert policy is needed.
alter table snapshots enable row level security;

create policy "public read snapshots"
  on snapshots for select
  to anon
  using (true);
```

4. Open **Project Settings → API** and copy three values:
   - **Project URL** (e.g. `https://abcd.supabase.co`)
   - **anon public** key
   - **service_role** key (secret — keep it off the browser)

---

## 2. Point the screener at Supabase (on your machine)

Add to the repo-root `.env` (the same file holding `OPENAI_API_KEY`):

```bash
SUPABASE_URL=https://abcd.supabase.co
SUPABASE_SERVICE_KEY=your-service_role-key
```

Now publish results:

```bash
tradingagents screen --top 10     # runs + auto-publishes screen & paper snapshots
tradingagents sync                # or just re-publish the current paper book
```

(No Supabase vars set → the CLI simply skips syncing and works as before.)

---

## 3. Run the dashboard locally (optional)

```bash
cd dashboard
npm install
cp .env.example .env.local        # then fill in the two NEXT_PUBLIC_* values
npm run dev                        # http://localhost:3000
```

`.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://abcd.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-public-key
```

---

## 4. Deploy free on Vercel (share with your brother)

1. Push this repo to GitHub.
2. Go to https://vercel.com → sign up → **Add New… → Project** → import the repo.
3. **Important:** set **Root Directory** to `dashboard`.
4. Under **Environment Variables**, add:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
5. **Deploy.** You get a public URL like `https://your-app.vercel.app` — send it
   to your brother. It updates automatically whenever you run a screen.

---

## Notes

- **Privacy:** the dashboard is public (anyone with the URL can view the paper
  picks). The data is non-sensitive simulated trades. To lock it down later, add
  Vercel's password protection or a simple auth layer.
- **Keeping it fresh:** results only change when you run `tradingagents screen`
  (or `sync`). Consider a scheduled run (cron / the repo's `/loop` or `/schedule`)
  so the dashboard refreshes on its own.
- **Security:** never put the `service_role` key in the dashboard or any
  `NEXT_PUBLIC_*` var — it bypasses row-level security. It belongs only in the
  Python-side `.env`.
