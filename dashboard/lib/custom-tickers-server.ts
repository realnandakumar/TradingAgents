import fs from "fs";
import os from "os";
import path from "path";

const TRADINGAGENTS_HOME =
  process.env.TRADINGAGENTS_HOME ?? path.join(os.homedir(), ".tradingagents");

export function customTickersPath(): string {
  return (
    process.env.TRADINGAGENTS_CUSTOM_TICKERS_PATH ??
    path.join(TRADINGAGENTS_HOME, "custom_tickers.txt")
  );
}

/** Mirror Python `_normalise_symbol`: uppercase NSE yfinance symbol. */
export function normalizeSymbol(sym: string): string {
  const s = sym.trim().toUpperCase();
  if (!s) return "";
  if (s.includes(".")) return s;
  return `${s}.NS`;
}

function parseCustomTickersText(text: string): string[] {
  const symbols: string[] = [];
  const seen = new Set<string>();
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const first = line.split(",")[0]?.trim() ?? "";
    const norm = normalizeSymbol(first);
    if (norm && !seen.has(norm)) {
      seen.add(norm);
      symbols.push(norm);
    }
  }
  return symbols;
}

export function readCustomTickers(): { symbols: string[]; path: string } {
  const p = customTickersPath();
  try {
    if (!fs.existsSync(p)) {
      return { symbols: [], path: p };
    }
    const text = fs.readFileSync(p, "utf-8");
    return { symbols: parseCustomTickersText(text), path: p };
  } catch {
    return { symbols: [], path: p };
  }
}

export function saveCustomTickers(symbols: string[]): { symbols: string[]; path: string } {
  const p = customTickersPath();
  const normalized: string[] = [];
  const seen = new Set<string>();
  for (const sym of symbols) {
    const norm = normalizeSymbol(sym);
    if (norm && !seen.has(norm)) {
      seen.add(norm);
      normalized.push(norm);
    }
  }
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(
    p,
    normalized.length ? `${normalized.join("\n")}\n` : "",
    "utf-8",
  );
  return { symbols: normalized, path: p };
}

export function addCustomTickers(symbols: string[]): { symbols: string[]; path: string } {
  const { symbols: current } = readCustomTickers();
  const seen = new Set(current);
  for (const sym of symbols) {
    const norm = normalizeSymbol(sym);
    if (norm && !seen.has(norm)) {
      seen.add(norm);
      current.push(norm);
    }
  }
  return saveCustomTickers(current);
}

export function removeCustomTickers(symbols: string[]): { symbols: string[]; path: string } {
  const removeSet = new Set(symbols.map(normalizeSymbol).filter(Boolean));
  const { symbols: current } = readCustomTickers();
  return saveCustomTickers(current.filter((s) => !removeSet.has(s)));
}
