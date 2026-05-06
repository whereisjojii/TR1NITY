import { useEffect } from "react";

export interface VimHandler {
  /** Single-char binding, e.g. "j", "k", "o" */
  key: string;
  /** Optional second char for two-char sequences like "gg", "gG" */
  follow?: string;
  /** True if Shift must be held (e.g. "G") */
  shift?: boolean;
  description: string;
  handler: () => void;
}

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

function isInTypingContext(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (TYPING_TAGS.has(target.tagName)) return true;
  if (target.isContentEditable) return true;
  return false;
}

export function useVimShortcuts(handlers: VimHandler[]): void {
  useEffect(() => {
    let pending: string | null = null;
    let pendingTimer: number | null = null;

    function clearPending(): void {
      pending = null;
      if (pendingTimer !== null) {
        window.clearTimeout(pendingTimer);
        pendingTimer = null;
      }
    }

    function onKeydown(event: KeyboardEvent): void {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isInTypingContext(event.target)) return;

      const key = event.key;

      // Two-char sequence in flight?
      if (pending) {
        const compoundMatch = handlers.find(
          (h) =>
            h.follow !== undefined &&
            h.key === pending &&
            h.follow === key &&
            !!h.shift === event.shiftKey,
        );
        clearPending();
        if (compoundMatch) {
          event.preventDefault();
          compoundMatch.handler();
          return;
        }
      }

      // Anything that introduces a two-char sequence?
      const compoundIntro = handlers.find(
        (h) =>
          h.follow !== undefined &&
          h.key === key &&
          !!h.shift === event.shiftKey,
      );
      if (compoundIntro) {
        pending = key;
        pendingTimer = window.setTimeout(clearPending, 800);
        event.preventDefault();
        return;
      }

      const single = handlers.find(
        (h) =>
          h.follow === undefined &&
          h.key === key &&
          !!h.shift === event.shiftKey,
      );
      if (single) {
        event.preventDefault();
        single.handler();
      }
    }

    window.addEventListener("keydown", onKeydown);
    return () => {
      window.removeEventListener("keydown", onKeydown);
      clearPending();
    };
  }, [handlers]);
}
