"use client";

import type { ReplacementCandidate } from "@/lib/desk-replacements-types";

interface Props {
  open: boolean;
  title: string;
  description?: string;
  items: ReplacementCandidate[];
  loading?: boolean;
  submitting?: boolean;
  selectedIds: Set<string>;
  onToggle: (id: string) => void;
  onToggleAll: (checked: boolean) => void;
  onApprove: () => void;
  onCancel: () => void;
}

export function ReplacementApprovalModal({
  open,
  title,
  description,
  items,
  loading = false,
  submitting = false,
  selectedIds,
  onToggle,
  onToggleAll,
  onApprove,
  onCancel,
}: Props) {
  if (!open) return null;

  const allSelected = items.length > 0 && items.every((item) => selectedIds.has(item.id));
  const someSelected = selectedIds.size > 0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div
        className="card max-w-xl w-full max-h-[85vh] overflow-hidden flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="replacement-modal-title"
      >
        <div className="flex items-start justify-between gap-3 px-4 py-3 border-b border-border">
          <div>
            <h3 id="replacement-modal-title" className="text-sm font-medium">
              {title}
            </h3>
            {description ? (
              <p className="text-xs text-muted mt-1 leading-relaxed">{description}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="text-muted hover:text-foreground text-lg leading-none disabled:opacity-50"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="p-4 overflow-y-auto flex-1 space-y-3">
          {loading ? (
            <p className="text-sm text-muted">Loading pending replacements…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted">No pending replacements.</p>
          ) : (
            <>
              <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={(e) => onToggleAll(e.target.checked)}
                  disabled={submitting}
                  className="rounded border-border"
                />
                Select all ({items.length})
              </label>
              <ul className="space-y-2">
                {items.map((item) => {
                  const checked = selectedIds.has(item.id);
                  return (
                    <li key={item.id}>
                      <label
                        className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors ${
                          checked
                            ? "border-accent/40 bg-accent/5"
                            : "border-border bg-surface-2/30 hover:bg-surface-2/50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => onToggle(item.id)}
                          disabled={submitting}
                          className="mt-0.5 rounded border-border"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm font-medium">
                            <span className="font-mono text-bear/90">{item.closeName}</span>
                            <span className="text-muted mx-1.5">→</span>
                            <span className="font-mono text-bull">{item.newName}</span>
                          </div>
                          <div className="text-[11px] text-muted mt-1 font-mono">
                            {item.closeTicker} → {item.newTicker}
                          </div>
                          {item.closeReason || item.proposedAt ? (
                            <div className="text-[11px] text-muted mt-1">
                              {item.closeReason ? <span>{item.closeReason}</span> : null}
                              {item.closeReason && item.proposedAt ? " · " : null}
                              {item.proposedAt ? <span>{item.proposedAt}</span> : null}
                            </div>
                          ) : null}
                        </div>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 px-4 py-3 border-t border-border">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="px-3 py-1.5 rounded-lg bg-surface-2 border border-border text-xs font-medium disabled:opacity-50 hover:bg-surface-2/80"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onApprove}
            disabled={submitting || loading || !someSelected}
            className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium disabled:opacity-50 hover:opacity-90"
          >
            {submitting
              ? "Approving…"
              : `Approve selected (${selectedIds.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}
