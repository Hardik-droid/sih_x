// Shared page scaffolding: case guard (no case / loading / error) and eyebrow.
import { state } from "../state.js";
import { pageHeader, panel } from "../components/card.js";
import { emptyState } from "../components/emptyState.js";
import { button } from "../components/button.js";
import { pageSkeleton } from "../components/skeleton.js";

export const caseEyebrow = () => (state.detail ? state.detail.case.name : "Your investigation starts here");

/**
 * Returns replacement HTML when the page cannot render its case content yet,
 * or null when state.detail is ready.
 */
export function caseGuard(title, description) {
  if (!state.caseId) {
    return pageHeader({ eyebrow: "Your investigation starts here", title, description: "Create a case to keep your evidence and processing history together." })
      + panel({
        title: "Investigation workspace",
        body: emptyState({
          icon: "folder",
          title: "Start with a case",
          body: "Give your investigation a name and assign an examiner. Every source, recovery and export will stay with it.",
          action: button({ label: "Create case", variant: "primary", icon: "plus", action: "new-case" }) + button({ label: "Run controlled demo", icon: "play", action: "demo" }),
        }),
      });
  }
  if (state.detailError && !state.detail) {
    return pageHeader({ eyebrow: "Case unavailable", title, description })
      + panel({
        title: "Could not load this case",
        body: emptyState({ icon: "warning", title: "The case record could not be read", body: state.detailError, action: button({ label: "Retry", icon: "refresh", action: "reload-case" }) }),
      });
  }
  if (!state.detail) return pageSkeleton(`Loading ${title}`);
  return null;
}
