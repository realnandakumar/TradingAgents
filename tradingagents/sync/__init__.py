"""Push screening + paper-trading results to a Supabase table so the Next.js
dashboard (deployed on Vercel) can read them.

The heavy compute (screening + multi-agent analysis) runs on the user's
machine; this module is the bridge that publishes the results. It is
best-effort: with no Supabase credentials configured it silently no-ops, so
the CLI keeps working fully offline.
"""

from .supabase_sync import (  # noqa: F401
    SupabaseSync,
    paper_snapshot,
    screen_snapshot,
    sync_results,
)
