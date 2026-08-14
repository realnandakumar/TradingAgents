import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook } from "./swing-types";
import { parseBookJson } from "./parse-book-json";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "swing", "positions.json");

export function swingBookPath(): string {
  return process.env.SWING_BOOK_PATH ?? process.env.TRADINGAGENTS_SWING_BOOK_PATH ?? DEFAULT_BOOK;
}

export function readSwingBook(): SwingBook | null {
  const bookPath = swingBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return parseBookJson<SwingBook>(raw);
  } catch {
    return null;
  }
}
