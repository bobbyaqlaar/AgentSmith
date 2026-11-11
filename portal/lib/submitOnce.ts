// portal/lib/submitOnce.ts — one click, one request, and an answer either way
// (the 4.1.0 release review, R28). Pure, so a test runs the same logic the buttons do.

export type SubmitResult = { ok: true } | { ok: false; error: string | null };

/** Runs `send` unless one is already in flight or `confirm` declines. A thrown error
 *  (a failed fetch included) comes back as its message; null means nothing was sent. */
export async function submitOnce(
  state: { busy: boolean },
  send: () => Promise<void>,
  confirm: () => boolean = () => true,
): Promise<SubmitResult> {
  if (state.busy || !confirm()) return { ok: false, error: null };
  state.busy = true;
  try {
    await send();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) };
  } finally {
    state.busy = false;
  }
}
