// Import evidence: local path · browser upload (byte-accurate progress) · USB /
// removable drive scan. Copy states exactly what the backend does — no more.
import { get, post, uploadWithProgress } from "../api.js";
import { state } from "../state.js";
import { refresh } from "../data.js";
import { defineActions } from "../actions.js";
import { esc } from "../dom.js";
import { icon } from "../icons.js";
import { bytes } from "../format.js";
import { openModal } from "../components/modal.js";
import { tabs } from "../components/tabs.js";
import { notice } from "../components/card.js";
import { toneBadge } from "../components/badge.js";
import { progressBar } from "../components/progressBar.js";
import { toastSuccess } from "../components/toast.js";

export const ALLOWED = [".img", ".dd", ".raw", ".mp4", ".avi", ".h264", ".264", ".dav", ".jpg", ".jpeg", ".mkv", ".ts", ".dat", ".hevc"];
const E01_MESSAGE = "Import a raw image or supported media file. Convert E01 with ewfexport; acquire physical devices using established write-blocked tools.";
const UPLOAD_LIMIT = 8 * 1024 ** 3;
const TAB_ITEMS = [
  { id: "path", label: "Local path", icon: "folder" },
  { id: "upload", label: "Upload file", icon: "upload" },
  { id: "usb", label: "USB / removable drive", icon: "usb-drive" },
];

const extOf = (name) => { const m = /\.[^.\\/]+$/.exec(String(name).trim().toLowerCase()); return m ? m[0] : ""; };

function checkName(name) {
  const ext = extOf(name);
  if (/\.e0\d$|\.ex0\d$|\.e\d\d$/.test(ext)) return E01_MESSAGE;
  if (!ALLOWED.includes(ext)) return `Unsupported file type${ext ? ` (${ext})` : ""}. ${E01_MESSAGE}`;
  return "";
}

const metaFields = (prefix) => `
  <div class="form__row form__row--3">
    <div class="field"><label class="field__label" for="${prefix}-vendor">Recorder vendor</label><input class="input" id="${prefix}-vendor" name="vendor" maxlength="100" placeholder="UNKNOWN" autocomplete="off"></div>
    <div class="field"><label class="field__label" for="${prefix}-model">Model</label><input class="input" id="${prefix}-model" name="model" maxlength="100" placeholder="UNKNOWN" autocomplete="off"></div>
    <div class="field"><label class="field__label" for="${prefix}-firmware">Firmware</label><input class="input" id="${prefix}-firmware" name="firmware" maxlength="100" placeholder="UNKNOWN" autocomplete="off"></div>
  </div>`;

function pathPanel() {
  return `<form class="form" data-import="path" novalidate>
    ${notice("Recommended for large disk images: no size limit. The source is opened read-only, copied into case storage and verified with a full SHA-256 read-back before analysis.", { tone: "info" })}
    <div class="field">
      <label class="field__label" for="import-path">Absolute file path</label>
      <input class="input mono" id="import-path" name="path" required maxlength="2048" autocomplete="off" spellcheck="false" placeholder="C:\\Evidence\\recorder-image.img">
      <p class="field__hint">Supported: ${ALLOWED.join(" ")}</p>
    </div>
    ${metaFields("path")}
    <p class="field__hint field__hint--warn">${icon("warning", { size: 14 })}<span>${esc(E01_MESSAGE)}</span></p>
    <p class="form__error" role="alert"></p>
    <div class="form__actions"><button type="submit" class="btn btn--primary"><span class="btn__label">Acquire &amp; analyze</span>${icon("arrow", { size: 16 })}<span class="btn__spinner" aria-hidden="true"></span></button></div>
  </form>`;
}

function uploadPanel() {
  return `<form class="form" data-import="upload" novalidate>
    <label class="dropzone" for="import-file">
      <span class="dropzone__icon">${icon("upload", { size: 22 })}</span>
      <strong class="dropzone__title">Drop an image or media file, or browse</strong>
      <span class="dropzone__hint">RAW · IMG · DD · MP4 · AVI · H.264 · DAV · DAT · HEVC · MKV · TS · JPEG</span>
      <input class="dropzone__input" type="file" id="import-file" name="file" accept="${ALLOWED.join(",")}">
    </label>
    <div class="upload-file" hidden></div>
    <div class="upload-progress" hidden></div>
    <p class="field__hint">Browser upload is limited to 8 GiB — use local path acquisition for larger images. Uploaded files are registered with vendor, model and firmware recorded as UNKNOWN.</p>
    <p class="form__error" role="alert"></p>
    <div class="form__actions">
      <button type="button" class="btn btn--ghost" data-upload-cancel hidden><span class="btn__label">Cancel upload</span></button>
      <button type="submit" class="btn btn--primary"><span class="btn__label">Upload &amp; acquire</span>${icon("arrow", { size: 16 })}<span class="btn__spinner" aria-hidden="true"></span></button>
    </div>
  </form>`;
}

function usbPanel() {
  return `<form class="form" data-import="usb" novalidate>
    ${notice("If Windows offers to format the drive, choose Cancel — formatting destroys evidence. Trace scans the selected drive or folder for supported evidence files (up to 20) and acquires each one read-only into case storage. It never writes to the drive; use a hardware write blocker for original media.", { tone: "warning", title: "Before you connect recorder media" })}
    <fieldset class="field">
      <legend class="field__label">Detected storage</legend>
      <div class="drive-list" data-drives aria-live="polite"><p class="subtle">Enumerating drives…</p></div>
    </fieldset>
    <div class="field">
      <label class="field__label" for="usb-path">Drive or folder path</label>
      <input class="input mono" id="usb-path" name="drive_path" required maxlength="2048" autocomplete="off" spellcheck="false" placeholder="E:\\">
    </div>
    <div class="form__row">
      <div class="field">
        <label class="field__label" for="usb-vendor">Recorder vendor profile</label>
        <div class="select-wrap"><select class="select" id="usb-vendor" name="vendor">
          <option value="AUTO_DETECT">Auto-detect (label only)</option>
          <option value="Dahua / DHAV">Dahua · DHAV</option>
          <option value="Heimvision">Heimvision</option>
          <option value="Hikvision (unvalidated)">Hikvision · unvalidated</option>
          <option value="Generic H.264 / H.265">Generic H.264 / H.265</option>
          <option value="UNKNOWN">Unknown</option>
        </select></div>
      </div>
    </div>
    <fieldset class="field">
      <legend class="field__label">Mode</legend>
      <div class="choice-list">
        <label class="choice"><input type="radio" name="recovery_mode" value="raw_stream_carve" checked><span class="choice__body"><strong>Acquire supported files (read-only)</strong><span>Each file found goes through the standard acquisition → hash → recovery pipeline.</span></span></label>
        <label class="choice"><input type="radio" name="recovery_mode" value="demo_usb"><span class="choice__body"><strong>Simulated demonstration drive</strong><span>Registers a simulated 64 GiB CCTV USB source with four pre-built camera artifacts. For demonstration only — not evidence.</span></span></label>
      </div>
    </fieldset>
    <p class="form__error" role="alert"></p>
    <div class="form__actions"><button type="submit" class="btn btn--primary">${icon("usb-drive", { size: 16 })}<span class="btn__label">Scan drive</span><span class="btn__spinner" aria-hidden="true"></span></button></div>
  </form>`;
}

const PANELS = { path: pathPanel, upload: uploadPanel, usb: usbPanel };

export function openImport({ tab = "path" } = {}) {
  if (!state.caseId) {
    import("./newCase.js").then((m) => m.openNewCase({ then: () => openImport({ tab }) }));
    return;
  }
  let active = tab in PANELS ? tab : "path";
  let uploading = null;
  openModal({
    title: "Import evidence",
    description: state.detail ? `Into case “${state.detail.case.name}”` : "",
    size: "lg",
    body: `${tabs({ id: "import", items: TAB_ITEMS, active, action: "import-tab", label: "Import method" })}<div class="tab-panel" role="tabpanel" id="import-panel" aria-labelledby="import-tab-${active}" data-import-panel>${PANELS[active]()}</div>`,
    onMount(dialog, ctrl) {
      const panel = dialog.querySelector("[data-import-panel]");
      const show = (id) => {
        if (uploading) return;
        active = id;
        dialog.querySelectorAll('[role="tab"]').forEach((t) => {
          const on = t.dataset.tab === id;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
          t.tabIndex = on ? 0 : -1;
        });
        panel.setAttribute("aria-labelledby", `import-tab-${id}`);
        panel.innerHTML = PANELS[id]();
        wire();
      };
      dialog.addEventListener("click", (event) => {
        const t = event.target.closest('[role="tab"][data-tabs="import"]');
        if (t) { event.preventDefault(); event.stopPropagation(); show(t.dataset.tab); }
      }, true);

      const done = async (message, route) => {
        await ctrl.close();
        await refresh();
        toastSuccess(message, { action: route === "recovery" ? null : { label: "View recovery engine", onClick: () => { location.hash = "#recovery"; } } });
        location.hash = `#${route}`;
      };

      function wire() {
        const form = panel.querySelector("form");
        const error = form.querySelector(".form__error");
        const submit = form.querySelector('[type="submit"]');
        const busy = (on) => { submit.disabled = on; if (on) submit.dataset.loading = "true"; else delete submit.dataset.loading; };

        if (active === "upload") {
          const input = form.querySelector('input[type="file"]');
          const zone = form.querySelector(".dropzone");
          const info = form.querySelector(".upload-file");
          const describe = () => {
            const file = input.files[0];
            info.hidden = !file;
            if (file) info.innerHTML = `${icon("file", { size: 16 })}<span class="truncate">${esc(file.name)}</span><span class="subtle tabular">${bytes(file.size)}</span>`;
            error.textContent = file ? checkName(file.name) || (file.size > UPLOAD_LIMIT ? "Browser uploads are limited to 8 GiB; use local path acquisition for larger images" : "") : "";
          };
          input.addEventListener("change", describe);
          ["dragenter", "dragover"].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.add("is-drag"); }));
          ["dragleave", "drop"].forEach((type) => zone.addEventListener(type, (e) => { e.preventDefault(); zone.classList.remove("is-drag"); }));
          zone.addEventListener("drop", (e) => {
            if (e.dataTransfer?.files?.length) {
              const dt = new DataTransfer();
              dt.items.add(e.dataTransfer.files[0]);
              input.files = dt.files;
              describe();
            }
          });
          form.querySelector("[data-upload-cancel]").addEventListener("click", () => uploading?.abort());
        }

        if (active === "usb") loadDrives(form);

        form.addEventListener("submit", async (event) => {
          event.preventDefault();
          error.textContent = "";
          const data = new FormData(form);
          try {
            if (active === "path") {
              const path = String(data.get("path") || "").trim();
              if (!path) { error.textContent = "Enter the absolute path of a local image or media file."; form.elements.namedItem("path").focus(); return; }
              const problem = checkName(path);
              if (problem) { error.textContent = problem; return; }
              busy(true);
              await post(`/cases/${encodeURIComponent(state.caseId)}/sources`, {
                path,
                vendor: String(data.get("vendor") || "").trim() || "UNKNOWN",
                model: String(data.get("model") || "").trim() || "UNKNOWN",
                firmware: String(data.get("firmware") || "").trim() || "UNKNOWN",
              });
              await done("Source registered. Read-only acquisition is running.", "recovery");
            } else if (active === "upload") {
              const file = form.querySelector('input[type="file"]').files[0];
              if (!file) { error.textContent = "Choose a file to upload."; return; }
              const problem = checkName(file.name) || (file.size > UPLOAD_LIMIT ? "Browser uploads are limited to 8 GiB; use local path acquisition for larger images" : "");
              if (problem) { error.textContent = problem; return; }
              busy(true);
              const progress = form.querySelector(".upload-progress");
              const cancel = form.querySelector("[data-upload-cancel]");
              progress.hidden = false;
              cancel.hidden = false;
              const controller = new AbortController();
              uploading = controller;
              const draw = (loaded, total) => {
                const pct = total ? (loaded / total) * 100 : 0;
                progress.innerHTML = `${progressBar(pct, { label: "Upload progress" })}<div class="upload-progress__meta"><span class="tabular">${bytes(loaded)} of ${bytes(total)}</span><span class="tabular">${pct.toFixed(1)}%</span></div>`;
              };
              draw(0, file.size);
              try {
                await uploadWithProgress(state.caseId, file, draw, { signal: controller.signal });
              } finally {
                uploading = null;
                cancel.hidden = true;
              }
              await done("Upload verified and registered. Read-only acquisition is running.", "recovery");
            } else {
              const drivePath = String(data.get("drive_path") || "").trim();
              if (!drivePath) { error.textContent = "Select a detected drive or enter a drive or folder path."; return; }
              busy(true);
              const result = await post(`/cases/${encodeURIComponent(state.caseId)}/usb-scan`, {
                drive_path: drivePath,
                vendor: String(data.get("vendor") || "AUTO_DETECT"),
                recovery_mode: String(data.get("recovery_mode") || "raw_stream_carve"),
              });
              await done(result.status || "Drive scanned.", result.artifacts ? "evidence" : "recovery");
            }
          } catch (err) {
            error.textContent = err.message;
          } finally {
            if (submit.isConnected) busy(false);
          }
        });
      }
      wire();
      return () => uploading?.abort();
    },
  });
}

async function loadDrives(form) {
  const list = form.querySelector("[data-drives]");
  const input = form.querySelector("#usb-path");
  try {
    const data = await get("/drives/detect");
    const drives = data.drives || [];
    if (!drives.length) {
      list.innerHTML = '<p class="subtle">No drives were enumerated. Enter the drive or folder path manually.</p>';
      return;
    }
    const preferred = drives.findIndex((d) => d.is_removable);
    list.innerHTML = drives.map((d, i) => {
      const type = d.type === "REMOVABLE_USB" ? toneBadge("blue", "Removable", { icon: "usb-drive", size: "sm" }) : d.type === "FIXED_DISK" ? toneBadge("gray", "Fixed disk", { icon: "disk", size: "sm" }) : toneBadge("gray", "Other", { size: "sm" });
      const sim = d.is_simulated ? toneBadge("violet", "Simulated", { icon: "sparkles", size: "sm", title: "Demonstration entry supplied by the server, not a physical drive" }) : "";
      const capacity = d.capacity_gb ? `${d.capacity_gb} GiB total${d.free_gb !== undefined ? ` · ${d.free_gb} GiB free` : ""}` : "Capacity unknown";
      return `<label class="drive">
        <input type="radio" name="drive_choice" value="${esc(d.path)}" data-simulated="${d.is_simulated ? "1" : ""}" data-fixed="${d.type === "FIXED_DISK" ? "1" : ""}"${i === preferred ? " checked" : ""}>
        <span class="drive__icon">${icon(d.is_removable ? "usb-drive" : "disk", { size: 18 })}</span>
        <span class="drive__body"><strong class="truncate">${esc(d.label || d.path)}</strong><span class="drive__meta">${type}${sim}<span class="subtle">${esc(capacity)}</span></span>${d.forensic_status ? `<span class="drive__status">${esc(d.forensic_status)}</span>` : ""}</span>
      </label>`;
    }).join("") + '<p class="field__hint field__hint--warn" data-fixed-warning hidden></p>';
    const warning = list.querySelector("[data-fixed-warning]");
    const apply = (radio) => {
      input.value = radio.value;
      const demo = form.querySelector('input[name="recovery_mode"][value="demo_usb"]');
      const real = form.querySelector('input[name="recovery_mode"][value="raw_stream_carve"]');
      if (radio.dataset.simulated) demo.checked = true;
      else if (demo.checked) real.checked = true;
      warning.hidden = !radio.dataset.fixed;
      warning.innerHTML = radio.dataset.fixed ? `${icon("warning", { size: 14 })}<span>This is a fixed system disk. Trace would walk the whole volume for supported files — enter a specific evidence folder instead.</span>` : "";
    };
    const initial = list.querySelector('input[name="drive_choice"]:checked');
    if (initial) apply(initial);
    list.addEventListener("change", (event) => {
      const radio = event.target.closest('input[name="drive_choice"]');
      if (radio) apply(radio);
    });
  } catch (err) {
    list.innerHTML = `<p class="form__error">${esc(err.message)}</p>`;
  }
}

defineActions({
  import: ({ tab }) => openImport({ tab: tab || "path" }),
  "usb-ingest": () => openImport({ tab: "usb" }),
  "import-tab": () => {},
});
