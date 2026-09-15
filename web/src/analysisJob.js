// How the page follows an analysis that runs in the background.
//
// Starting an analysis returns at once with a job; the page polls the store's
// latest job until it settles, then reads the finished briefing. Kept free of
// React so the rules can be tested directly.

export const ANALYSIS_POLL_MS = 5000;
export const NARRATION_POLL_MS = 10000;
// Longer than the server's own deadlines (engine 10 min + narration 5 min), so
// the server always settles a job before the page gives up on it.
export const ANALYSIS_GIVE_UP_MS = 20 * 60 * 1000;

const FAILED_FALLBACK = "The analysis didn't finish. Run it again; if it keeps failing, contact support.";

// Where a job stands, from the page's point of view. `startedJobId` is the job
// this page started (or null when it joined one already running). A newer job
// than the one started means someone else began another run afterwards — this
// page keeps waiting on the latest rather than reporting a result it never saw.
export function analysisOutcome(job, startedJobId = null) {
  if (!job) return { state: "running" };
  if (startedJobId != null && Number(job.id) < Number(startedJobId)) return { state: "running" };
  if (job.status === "complete") return { state: "complete", runId: job.runId || null };
  if (job.status === "failed") return { state: "failed", message: job.error || FAILED_FALLBACK };
  return { state: "running" };
}

export function isNarrationPending(presentedRun) {
  return presentedRun?.narration_status === "pending";
}

// What the Play thesis tab says while a run's explanations are still being
// written. Null means "show whatever there is" — prose, or the evidence chips.
export function thesisPlaceholder(narrationStatus) {
  return narrationStatus === "pending"
    ? "Writing the explanation for this play. It usually takes about a minute."
    : null;
}

// Waits for the store's analysis job to settle. A failed poll is not a failed
// analysis: on the small hosting instance the proxy can answer with an HTML
// error page while the engine has the CPU, and one such response used to end
// the wait with "Unexpected token '<'" although the run finished fine
// (2026-09-14). Polling failures are ridden out until the give-up deadline;
// only a job the server reports as failed ends the wait early.
// Thrown when the caller stops caring — the merchant switched stores. Never
// retried: the next request would go to a different store.
export function abandonedError() {
  return Object.assign(new Error("This analysis belongs to a store that is no longer open."), { code: "abandoned" });
}

export async function waitForAnalysis({
  getJob,
  startedJobId = null,
  // Checked before every request and after every response.
  isCancelled = () => false,
  pollMs = ANALYSIS_POLL_MS,
  giveUpMs = ANALYSIS_GIVE_UP_MS,
  now = () => Date.now(),
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  const giveUpAt = now() + giveUpMs;
  for (;;) {
    if (isCancelled()) throw abandonedError();
    let outcome = { state: "running" };
    try {
      const response = await getJob();
      outcome = analysisOutcome(response?.job, startedJobId);
    } catch (_) {
      // Transient: keep waiting.
    }
    if (isCancelled()) throw abandonedError();
    if (outcome.state === "failed") throw new Error(outcome.message);
    if (outcome.state === "complete") return outcome;
    if (now() > giveUpAt) {
      throw new Error("The analysis is taking longer than usual. It will keep running; reload this page in a few minutes.");
    }
    await sleep(pollMs);
  }
}

// A read that may meet the same transient failure, retried a few times.
export async function withRetries(fn, { attempts = 4, delayMs = 3000, sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)), isCancelled = () => false } = {}) {
  let lastError;
  for (let i = 0; i < attempts; i += 1) {
    if (isCancelled()) throw abandonedError();
    try {
      const result = await fn();
      if (isCancelled()) throw abandonedError();
      return result;
    } catch (error) {
      if (error?.code === "abandoned") throw error;
      lastError = error;
      if (i < attempts - 1) await sleep(delayMs);
    }
  }
  throw lastError;
}
