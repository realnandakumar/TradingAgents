"use client";

import { useCallback, useState } from "react";

import type { ReplacementCandidate } from "@/lib/desk-replacements-types";
import { isReplacementApprovalAction } from "@/lib/desk-replacements-types";

export interface ReplacementApprovalRequest {
  deskId: string;
  actionId: string;
  proposalIds: string[];
  processDate?: string;
}

interface OpenReplacementModalArgs {
  deskId: string;
  actionId: string;
  title: string;
  description?: string;
}

interface UseReplacementApprovalOptions {
  onApprove: (request: ReplacementApprovalRequest) => Promise<void>;
  onEmpty?: (deskId: string, actionId: string) => void;
  onError?: (message: string) => void;
}

export function useReplacementApproval({
  onApprove,
  onEmpty,
  onError,
}: UseReplacementApprovalOptions) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [items, setItems] = useState<ReplacementCandidate[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [modalTitle, setModalTitle] = useState("Approve replacements");
  const [modalDescription, setModalDescription] = useState<string | undefined>();
  const [pendingRequest, setPendingRequest] = useState<OpenReplacementModalArgs | null>(null);
  const [processDate, setProcessDate] = useState<string | undefined>();

  const closeModal = useCallback(() => {
    if (submitting) return;
    setOpen(false);
    setItems([]);
    setSelectedIds(new Set());
    setPendingRequest(null);
    setProcessDate(undefined);
  }, [submitting]);

  const openReplacementModal = useCallback(
    async ({ deskId, actionId, title, description }: OpenReplacementModalArgs) => {
      if (!isReplacementApprovalAction(actionId)) {
        return false;
      }

      setLoading(true);
      setModalTitle(title);
      setModalDescription(description);
      setPendingRequest({ deskId, actionId, title, description });

      try {
        const res = await fetch(
          `/api/desk-replacements?deskId=${encodeURIComponent(deskId)}`,
        );
        const data = (await res.json()) as {
          replacements?: ReplacementCandidate[];
          processDate?: string | null;
          error?: string;
        };
        if (!res.ok) {
          throw new Error(data.error ?? "Failed to load replacements");
        }

        const replacements = data.replacements ?? [];
        if (replacements.length === 0) {
          onEmpty?.(deskId, actionId);
          return true;
        }

        setItems(replacements);
        setSelectedIds(new Set(replacements.map((item) => item.id)));
        setProcessDate(data.processDate ?? replacements[0]?.processDate ?? undefined);
        setOpen(true);
        return true;
      } catch (e) {
        onError?.(e instanceof Error ? e.message : "Failed to load replacements");
        return true;
      } finally {
        setLoading(false);
      }
    },
    [onEmpty, onError],
  );

  const toggleId = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleAll = useCallback(
    (checked: boolean) => {
      setSelectedIds(checked ? new Set(items.map((item) => item.id)) : new Set());
    },
    [items],
  );

  const approveSelected = useCallback(async () => {
    if (!pendingRequest || selectedIds.size === 0) return;
    setSubmitting(true);
    try {
      await onApprove({
        deskId: pendingRequest.deskId,
        actionId: pendingRequest.actionId,
        proposalIds: Array.from(selectedIds),
        processDate,
      });
      closeModal();
    } catch (e) {
      onError?.(e instanceof Error ? e.message : "Failed to approve replacements");
    } finally {
      setSubmitting(false);
    }
  }, [closeModal, onApprove, onError, pendingRequest, processDate, selectedIds]);

  return {
    open,
    loading,
    submitting,
    items,
    selectedIds,
    modalTitle,
    modalDescription,
    openReplacementModal,
    closeModal,
    toggleId,
    toggleAll,
    approveSelected,
    isReplacementAction: isReplacementApprovalAction,
  };
}
