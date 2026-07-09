import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "nw_envelope", "positions.json");

export function nwEnvelopeBookPath(): string {
  return (
    process.env.NWE_BOOK_PATH ??
    process.env.TRADINGAGENTS_NWE_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function readNwEnvelopeBook(): SwingBook | null {
  const bookPath = nwEnvelopeBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return JSON.parse(raw) as SwingBook;
  } catch {
    return null;
  }
}

export type NwEnvelopePosition = SwingPosition & {
  cross_age?: number;
  dist_pct?: number;
  nwe_middle?: number;
  nwe_upper?: number;
  nwe_lower?: number;
  remark?: string;
};

export type { SwingBook as NwEnvelopeBook };
