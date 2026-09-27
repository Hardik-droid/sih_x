// "Create an investigation" dialog → POST /api/cases
import { post } from "../api.js";
import { state } from "../state.js";
import { selectCase } from "../data.js";
import { defineActions } from "../actions.js";
import { openModal } from "../components/modal.js";
import { toastSuccess } from "../components/toast.js";
import { icon } from "../icons.js";

let after = null;

export function openNewCase({ then = null } = {}) {
  after = then;
  openModal({
    title: "Create an investigation",
    description: "Sources, recoveries, notes and exports stay together under one case.",
    size: "md",
    body: `<form class="form" id="case-form" novalidate>
        <div class="field">
          <label class="field__label" for="case-name">Case name</label>
          <input class="input" id="case-name" name="name" required maxlength="160" autocomplete="off" placeholder="e.g. Warehouse incident · September 2026" autofocus>
        </div>
        <div class="field">
          <label class="field__label" for="case-examiner">Examiner</label>
          <input class="input" id="case-examiner" name="examiner" required maxlength="100" autocomplete="name" placeholder="Name of the investigating examiner">
        </div>
        <div class="field">
          <label class="field__label" for="case-notes">Case notes <span class="field__optional">Optional</span></label>
          <textarea class="textarea" id="case-notes" name="notes" maxlength="10000" rows="4" placeholder="Purpose, source context and acquisition notes"></textarea>
        </div>
        <p class="form__error" role="alert" aria-live="assertive"></p>
      </form>`,
    footer: `<button type="button" class="btn btn--ghost" data-modal-close><span class="btn__label">Cancel</span></button>
      <button type="submit" form="case-form" class="btn btn--primary"><span class="btn__label">Create case</span>${icon("arrow", { size: 16 })}<span class="btn__spinner" aria-hidden="true"></span></button>`,
    onMount(dialog, ctrl) {
      const form = dialog.querySelector("#case-form");
      const error = form.querySelector(".form__error");
      const submit = dialog.querySelector('[type="submit"]');
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        error.textContent = "";
        const data = Object.fromEntries(new FormData(form));
        data.name = String(data.name || "").trim();
        data.examiner = String(data.examiner || "").trim();
        if (!data.name || !data.examiner) {
          error.textContent = "Case name and examiner are required.";
          form.elements.namedItem(data.name ? "examiner" : "name").focus();
          return;
        }
        submit.disabled = true;
        submit.dataset.loading = "true";
        try {
          const item = await post("/cases", data);
          await ctrl.close();
          await selectCase(item.id);
          const next = after;
          after = null;
          toastSuccess("Case created. Ready for evidence.", next ? {} : { action: { label: "Import evidence", onClick: () => import("./importEvidence.js").then((m) => m.openImport()) } });
          if (state.route.id === "home") location.hash = "#overview";
          if (typeof next === "function") next(item);
        } catch (err) {
          error.textContent = err.message;
        } finally {
          submit.disabled = false;
          delete submit.dataset.loading;
        }
      });
    },
  });
}

defineActions({ "new-case": () => openNewCase() });
