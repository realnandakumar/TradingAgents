import { spawn } from "child_process";
import { NextRequest, NextResponse } from "next/server";

import {
  addCustomTickers,
  readCustomTickers,
  removeCustomTickers,
} from "@/lib/custom-tickers-server";
import { normalizeSymbol } from "@/lib/custom-tickers-server";
import { pythonExecutable, repoRootFromDashboard } from "@/lib/desk-cli-server";

export const dynamic = "force-dynamic";

function ensureSymbolCachedBackground(ticker: string): void {
  const cwd = repoRootFromDashboard();
  const pythonCmd = pythonExecutable();
  const script = "scripts/ensure_symbol_cached.py";
  const child = spawn(pythonCmd, [script, ticker], {
    cwd,
    detached: true,
    stdio: "ignore",
  });
  child.unref();
}

export async function GET() {
  try {
    const { symbols, path: filePath } = readCustomTickers();
    return NextResponse.json({ symbols, path: filePath });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to read custom tickers";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

/** Add tickers. Body: { symbols: string[] } */
export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { symbols?: string[] };
    if (!Array.isArray(body.symbols) || body.symbols.length === 0) {
      return NextResponse.json({ error: "symbols array is required" }, { status: 400 });
    }
    const result = addCustomTickers(body.symbols);
    for (const sym of body.symbols) {
      const norm = normalizeSymbol(sym);
      if (norm) ensureSymbolCachedBackground(norm);
    }
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to add custom tickers";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

/** Remove tickers. Body: { symbols: string[] } */
export async function DELETE(req: NextRequest) {
  try {
    const body = (await req.json()) as { symbols?: string[] };
    if (!Array.isArray(body.symbols) || body.symbols.length === 0) {
      return NextResponse.json({ error: "symbols array is required" }, { status: 400 });
    }
    const result = removeCustomTickers(body.symbols);
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed to remove custom tickers";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
