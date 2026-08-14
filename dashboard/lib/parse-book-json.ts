import fs from "fs";

/** Parse paper-book JSON, including Python's non-standard NaN/Infinity tokens. */
export function parseBookJson<T>(raw: string): T {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return JSON.parse(
      raw
        .replace(/\bNaN\b/g, "null")
        .replace(/\b-Infinity\b/g, "null")
        .replace(/\bInfinity\b/g, "null"),
    ) as T;
  }
}

export function readJsonFile<T>(filePath: string): T | null {
  try {
    if (!fs.existsSync(filePath)) return null;
    return parseBookJson<T>(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}
