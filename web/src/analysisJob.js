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
