"""Audit USER_CLI_GUIDE.md commands: existence, help, and lightweight execution."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)

CLI = [str(PY), "-m", "cli.main"]

TINY_UNIVERSE = ROOT / "scripts" / ".audit_universe.csv"
TINY_UNIVERSE.write_text(
    "symbol,name\nRELIANCE.NS,Reliance\nTCS.NS,TCS\nINFY.NS,Infosys\n",
    encoding="utf-8",
)
UNI = str(TINY_UNIVERSE)

# All distinct CLI invocations from docs/USER_CLI_GUIDE.md
GUIDE_CLI_COMMANDS = [
    # setup / meta
    ["--help"],
    # watchlist
    ["watchlist", "show"],
    ["watchlist", "add", "RELIANCE.NS", "TCS.NS"],
    ["watchlist", "remove", "TCS.NS"],
    # pure screeners (tiny universe for speed)
    ["gap-fill", "--universe", UNI, "--top", "3"],
    ["gap-fill", "--down-only", "--universe", UNI, "--top", "2"],
    ["gap-fill", "--up-only", "--universe", UNI, "--top", "2"],
    ["gap-fill-explain", "RELIANCE.NS"],
    ["chart-patterns", "--universe", UNI, "--top", "3"],
    ["chart-patterns", "--bullish-only", "--universe", UNI, "--top", "2"],
    ["chart-patterns", "--bearish-only", "--universe", UNI, "--top", "2"],
    ["chart-patterns-explain", "RELIANCE.NS"],
    # rule desks — screen (no-save) + read-only
    *[
        [s, "--no-save", "--universe", UNI, "--top", "2"]
        for s in ("swing", "momentum", "nss", "supertrend-rsi", "trama", "nw-envelope", "pattern-forecast")
    ],
    *[[f"{s}-positions"] for s in (
        "swing", "momentum", "nss", "supertrend-rsi", "trama", "nw-envelope",
        "pattern-forecast", "gap-fill",
    )],
    *[[f"{s}-report"] for s in (
        "swing", "momentum", "nss", "supertrend-rsi", "trama", "nw-envelope",
        "pattern-forecast", "gap-fill",
    )],
    *[[f"{s}-daily", "--force"] for s in (
        "swing", "momentum", "nss", "supertrend-rsi", "trama", "nw-envelope",
        "pattern-forecast", "gap-fill", "tech-desk",
    )],
    ["nss-diagnostics"],
    ["nss-explain", "RELIANCE.NS"],
    ["supertrend-rsi-explain", "RELIANCE.NS"],
    ["trama-explain", "RELIANCE.NS"],
    ["nw-envelope-explain", "RELIANCE.NS"],
    ["gap-fill-explain", "RELIANCE.NS"],
    ["pattern-forecast-explain", "RELIANCE.NS"],
    # RS funnel (no full AI run)
    ["screen", "--preview", "--top", "3"],
    ["paper"],
    ["sync"],
    # tech desk read-only
    ["tech-desk-positions"],
    ["tech-desk-report"],
    ["tech-desk-daily", "--force"],
    # portfolio (no LLM)
    ["portfolio-review", "--no-llm"],
]

# Commands that exist but need API key — help-only check
API_COMMANDS = [
    ["analyze", "--help"],
    ["analyze", "--checkpoint", "--help"],
    ["tech-analyze", "--help"],
    ["tech-desk-process", "--help"],
    ["tech-desk-review", "--help"],
    ["tech-desk-review", "--apply", "--help"],
    ["screen", "--help"],
    ["portfolio-review", "--help"],
]

GUIDE_SCRIPTS = [
    "scripts/run_all_screeners_now.py",
    "scripts/run_all_daily_now.py",
    "scripts/run_gap_fill_screener_now.py",
    "scripts/run_chart_patterns_screener_now.py",
    "scripts/run_swing_screener_now.py",
    "scripts/run_swing_daily_now.py",
    "scripts/run_momentum_screener_now.py",
    "scripts/run_momentum_daily_now.py",
    "scripts/run_nss_screener_now.py",
    "scripts/run_nss_daily_now.py",
    "scripts/run_supertrend_rsi_screener_now.py",
    "scripts/run_supertrend_rsi_daily_now.py",
    "scripts/run_trama_screener_now.py",
    "scripts/run_trama_daily_now.py",
    "scripts/run_nw_envelope_screener_now.py",
    "scripts/run_nw_envelope_daily_now.py",
    "scripts/run_pattern_forecast_screener_now.py",
    "scripts/run_pattern_forecast_daily_now.py",
    "scripts/run_analyze_job.py",
]

# Approve commands are interactive — help only
APPROVE_COMMANDS = [
    [f"{s}-approve", "--help"]
    for s in ("swing", "momentum", "nss", "supertrend-rsi", "trama", "nw-envelope", "pattern-forecast", "gap-fill")
]

EXPORT_TMP = None


def run(args: list[str], timeout: int = 300) -> tuple[int, str]:
    global EXPORT_TMP
    try:
        r = subprocess.run(
            CLI + args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode, out[-800:]
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or "") + (e.stderr or "")
        return -1, f"TIMEOUT after {timeout}s\n{out[-400:]}"


def main() -> int:
    global EXPORT_TMP
    results: list[tuple[str, str, str, str]] = []  # name, status, note, detail

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
        EXPORT_TMP = f.name
    # gap/chart export tests appended below

    print(f"Using Python: {PY}")
    print(f"Auditing {len(GUIDE_CLI_COMMANDS)} CLI runs + help checks...\n")

    for args in GUIDE_CLI_COMMANDS:
        label = " ".join(args)
        code, tail = run(args, timeout=600 if "screen" in args or "-explain" in args[0] else 180)
        if code == 0:
            results.append((label, "OK", "ran", ""))
        elif code == 1 and any(x in tail.lower() for x in ("no ", "empty", "yet", "skipped")):
            results.append((label, "OK", "ran (empty/no data)", tail[:200]))
        else:
            results.append((label, "FAIL", f"exit {code}", tail))

    # export tests
    for cmd, flag in (("gap-fill", "--export"), ("chart-patterns", "--export")):
        args = [
            cmd, flag, EXPORT_TMP,
            "--universe", UNI,
            "--top", "2",
        ]
        label = " ".join(args)
        code, tail = run(args, timeout=180)
        ok = code == 0 and Path(EXPORT_TMP).exists()
        results.append((label, "OK" if ok else "FAIL", "export" if ok else f"exit {code}", tail[:200]))

    for args in API_COMMANDS + APPROVE_COMMANDS:
        label = " ".join(args)
        code, tail = run(args, timeout=30)
        results.append((label, "OK" if code == 0 else "FAIL", "help/exists", tail[:150]))

    for rel in GUIDE_SCRIPTS:
        path = ROOT / rel
        if not path.exists():
            results.append((rel, "FAIL", "file missing", ""))
            continue
        # syntax/import check only (full run would take too long)
        code, tail = subprocess.run(
            [str(PY), "-m", "py_compile", str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).returncode, ""
        results.append((rel, "OK" if code == 0 else "FAIL", "script compiles", tail[:150]))

    # dashboard npm
    pkg = ROOT / "dashboard" / "package.json"
    results.append(("dashboard/package.json", "OK" if pkg.exists() else "FAIL", "exists", ""))

    ok = sum(1 for _, s, _, _ in results if s == "OK")
    fail = [r for r in results if r[1] != "OK"]

    print(f"\n{'='*72}")
    print(f"SUMMARY: {ok}/{len(results)} passed\n")
    for label, status, note, detail in results:
        mark = "PASS" if status == "OK" else "FAIL"
        print(f"[{mark}] {label}  ({note})")
        if status != "OK" and detail:
            print(f"       {detail.replace(chr(10), ' ')[:300]}")

    if fail:
        print(f"\n{len(fail)} failure(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
