import { useEffect, useRef, useState } from "react";

// A timed-out HTTP request does not prove the server stopped syncing.
export function useStoreSync({ start, status, onStatus, onComplete, pollMs = 4000, timeoutMs = 120000 }) {
  const [state, setState] = useState({ phase: "idle", elapsed: 0 });
  const active = useRef(null);
  const callbacks = useRef({ start, status, onStatus, onComplete });
  callbacks.current = { start, status, onStatus, onComplete };
  useEffect(() => () => { active.current = null; }, []);

  async function finish(attempt, result) {
    if (active.current !== attempt || attempt.finished) return;
    attempt.finished = true;
    active.current = null;
    setState((s) => ({ ...s, phase: "complete", message: "Store synced. Re-run analysis to replace the briefing below." }));
    try { await callbacks.current.onComplete(result); }
    catch { setState((s) => ({ ...s, message: "Store synced, but the page couldn't reload its data. Reload the page before running analysis." })); }
  }

  async function check() {
    const attempt = active.current;
    if (!attempt || attempt.checking) return;
    attempt.checking = true;
    try {
      const result = await callbacks.current.status();
      if (active.current !== attempt) return;
      callbacks.current.onStatus(result);
      const latest = result?.latest;
      setState((s) => ({ ...s, lastCheck: Date.now(), checkError: null, serverStatus: latest?.status }));
      // Never mistake the previous successful sync for this request finishing.
      const isThisAttempt = latest && latest.syncRunId !== attempt.previousId
        && (attempt.previousId != null || new Date(latest.startedAt).getTime() >= attempt.startedAt);
      if (isThisAttempt && latest.status === "complete") {
        await finish(attempt, result);
      } else if (isThisAttempt && ["failed", "incomplete"].includes(latest.status)) {
        active.current = null;
        setState((s) => ({ ...s, phase: "failed", message: latest.validationFailures?.[0]?.message || result.reasons?.[0]?.message || "The sync did not complete. Your previous briefing is still shown." }));
      }
    } catch {
      if (active.current === attempt) setState((s) => ({ ...s, checkError: "Can't reach the sync status service. The server may still be working." }));
    } finally { attempt.checking = false; }
  }

  useEffect(() => {
    if (!["running", "uncertain"].includes(state.phase)) return;
    const timer = setInterval(() => {
      const attempt = active.current;
      if (attempt) setState((s) => ({ ...s, elapsed: Math.floor((Date.now() - attempt.startedAt) / 1000) }));
      void check();
    }, pollMs);
    return () => clearInterval(timer);
  }, [state.phase, pollMs]);

  async function run(previousId) {
    if (active.current) return null;
    const attempt = { previousId, startedAt: Date.now(), checking: false, finished: false };
    active.current = attempt;
    setState({ phase: "running", elapsed: 0 });
    let timeout;
    try {
      const result = await Promise.race([
        callbacks.current.start(),
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error("The sync request has not completed. The server may still be working.")), timeoutMs); }),
      ]);
      if (active.current !== attempt) return result;
      if (result?.published === false) {
        active.current = null;
        setState((s) => ({ ...s, phase: "failed", message: result.validationFailures?.[0]?.message || "Shopify returned incomplete data. Your previous briefing is still shown." }));
        const latest = await callbacks.current.status();
        callbacks.current.onStatus(latest);
      } else { await finish(attempt, result); }
      return result;
    } catch (error) {
      if (active.current === attempt) {
        if ([400, 401, 403].includes(error.status)) {
          active.current = null;
          setState((s) => ({ ...s, phase: "failed", message: error.message }));
          return null;
        }
        setState((s) => ({ ...s, phase: "uncertain", message: error.message }));
        await check();
      }
      return null;
    } finally { clearTimeout(timeout); }
  }
  return { ...state, busy: ["running", "uncertain"].includes(state.phase), run, check };
}
