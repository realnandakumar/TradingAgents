export interface ReplacementCandidate {
  id: string;
  closeTicker: string;
  closeName: string;
  newTicker: string;
  newName: string;
  proposedAt?: string;
  closeReason?: string;
  closeScore?: number;
  /** Tech Desk process log date (YYYY-MM-DD). */
  processDate?: string;
}

export function isReplacementApprovalAction(actionId: string): boolean {
  return actionId === "approve" || actionId === "process-apply";
}

export const REPLACEMENT_DESK_IDS = [
  "swing",
  "momentum",
  "nss",
  "supertrend-rsi",
  "trama",
  "gap-fill",
  "nw-envelope",
  "pattern-forecast",
  "tech-desk",
] as const;
