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
  return false;
}

/** Empty — foreclosure/replacements disabled on all paper desks. */
export const REPLACEMENT_DESK_IDS = [] as const;
