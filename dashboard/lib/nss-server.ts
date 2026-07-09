import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "nss", "positions.json");

export function nssBookPath(): string {
  return process.env.NSS_BOOK_PATH ?? process.env.TRADINGAGENTS_NSS_BOOK_PATH ?? DEFAULT_BOOK;
}

export function readNssBook(): SwingBook | null {
  const bookPath = nssBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return JSON.parse(raw) as SwingBook;
  } catch {
    return null;
  }
}

export type { SwingPosition as NssPosition, SwingBook as NssBook };
