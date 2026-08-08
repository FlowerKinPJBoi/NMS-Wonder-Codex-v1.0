(() => {
  "use strict";

  const API = "/api/admin/apps/daedalus";
  const key = sessionStorage.getItem("wc_admin_key") || "";
  const actor = sessionStorage.getItem("wc_admin_actor") || "";
  const state = {permissions: {}, maxUploadBytes: 0, storageReady: false, corpus: {}, generation: {}, items: []};
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const headers = () => ({"X-Admin-Key": key, "X-Admin-Actor": actor, Accept: "application/json"});
  const formatBytes = (bytes) => bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.ceil(bytes / 1024)} KB`;
  const formatDate = (value) => value ? new Date(value).toLocaleString() : "—";

  async function api(path = "", options = {}) {
    const response = await fetch(API + path, {...options, headers: {...headers(), ...(options.headers || {})}});
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function notice(message, error = false) {
    $("#sharedUploadHelp").textContent = message;
    $("#sharedUploadHelp").style.color = error ? "#ff9eaa" : "";
  }

  async function connect() {
    if (!key || !actor) {
      window.location.replace("/admin/apps/");
      return;
    }
    try {
      const data = await api();
      state.permissions = data.permissions || {};
      state.maxUploadBytes = Number(data.max_upload_bytes || 0);
      state.storageReady = Boolean(data.storage_ready);
      state.corpus = data.corpus || {};
      state.generation = data.generation || {};
      $("#sharedStatus").textContent = data.storage_ready ? "Shared storage online" : "Storage setup required";
      $("#sharedOperator").textContent = `${data.operator} · ${state.permissions.review ? "reviewer" : "trainer"}`;
      $("#sharedArchive").disabled = !state.permissions.submit;
      $("#sharedSubmit").disabled = !state.permissions.submit || !state.storageReady;
      $("#sharedUploadHelp").textContent = state.storageReady
        ? `Maximum ${formatBytes(state.maxUploadBytes)}. ${data.production_rule}`
        : "DigitalOcean Spaces must be configured before packages can be shared.";
      renderCounts(data.counts || {});
      renderCorpus(state.corpus);
      await loadQueue();
    } catch (error) {
      $("#sharedStatus").textContent = "Access unavailable";
      notice(error.message, true);
    }
  }

  function renderCounts(counts) {
    $("#queuePending").textContent = Number(counts.pending_review || 0).toLocaleString();
    $("#queueCorrection").textContent = Number(counts.needs_correction || 0).toLocaleString();
    $("#queueApproved").textContent = Number(counts.approved || 0).toLocaleString();
    $("#queueReleased").textContent = Number(counts.released || 0).toLocaleString();
  }

  function renderCorpus(corpus) {
    $("#corpusActive").textContent = Number(corpus.active || 0).toLocaleString();
    $("#corpusVersion").textContent = `v${Number(corpus.version || 0).toLocaleString()}`;
  }

  async function loadQueue() {
    const status = $("#queueFilter").value;
    const data = await api(`/submissions${status ? `?status=${encodeURIComponent(status)}` : ""}`);
    state.items = data.items || [];
    renderQueue();
  }

  function actionButtons(item) {
    if (item.status === "released" && state.permissions.release) {
      if (item.corpus?.status === "not_indexed") {
        return `<textarea class="queue-note" maxlength="4000" placeholder="Required indexing decision"></textarea><button type="button" data-corpus-action="index">Index released lesson</button>`;
      }
      const action = item.corpus?.active ? "disable" : "enable";
      const label = item.corpus?.active ? "Disable lesson" : "Enable lesson";
      return `<textarea class="queue-note" maxlength="4000" placeholder="Required corpus decision reason"></textarea><button type="button" data-corpus-action="${action}">${label}</button>`;
    }
    if (!state.permissions.review || item.status === "rejected") return "";
    const buttons = [];
    if (["pending_review", "needs_correction"].includes(item.status)) buttons.push(`<button type="button" data-action="approve">Approve</button>`);
    if (["pending_review", "approved"].includes(item.status)) buttons.push(`<button type="button" data-action="needs_correction">Needs correction</button>`);
    if (item.status === "approved" && state.permissions.release) buttons.push(`<button type="button" data-action="release">Release to learning</button>`);
    buttons.push(`<button type="button" data-action="reject">Reject</button>`);
    return `<textarea class="queue-note" maxlength="4000" placeholder="Reviewer decision or correction guidance">${escapeHtml(item.reviewer_note || "")}</textarea>${buttons.join("")}`;
  }

  function renderQueue() {
    const container = $("#sharedQueue");
    if (!state.items.length) {
      container.innerHTML = '<div class="queue-empty">No learning packages match this queue state.</div>';
      return;
    }
    container.innerHTML = state.items.map((item) => {
      const domain = item.domain === "NO_MANS_SKY_CORVETTE_BUILDING" ? "Corvette" : "Base / Prefab";
      const intent = item.design_intent?.originalRequest || "No design brief recorded.";
      const corpusTag = item.status === "released"
        ? (item.corpus?.status === "not_indexed"
          ? '<span class="queue-tag">not indexed</span>'
          : `<span class="queue-tag corpus-${item.corpus?.active ? "active" : "disabled"}">${item.corpus?.active ? `retrieval active · v${Number(item.corpus.version).toLocaleString()}` : "retrieval disabled"}</span>`)
        : "";
      return `<article class="queue-card" data-submission="${escapeHtml(item.id)}">
        <div><h4>${escapeHtml(item.build_name || item.original_filename)}</h4><p>${escapeHtml(intent)}</p><div class="queue-tags"><span class="queue-tag ${escapeHtml(item.status)}">${escapeHtml(item.status.replaceAll("_", " "))}</span>${corpusTag}<span class="queue-tag">${escapeHtml(domain)}</span><span class="queue-tag">${Number(item.object_count).toLocaleString()} parts</span><span class="queue-tag">${Number(item.distinct_object_ids).toLocaleString()} Object IDs</span><span class="queue-tag">by ${escapeHtml(item.contributor)}</span><span class="queue-tag">${escapeHtml(formatDate(item.created_at))}</span></div></div>
        <div class="queue-actions"><button type="button" data-download>Download ZIP</button>${actionButtons(item)}</div>
        <div class="queue-message">Server validation: passed · protected ${escapeHtml(item.server_validation?.protectedObjectId || "prefab geometry")} · uniform-scale source check ${item.server_validation?.uniformScaleVerifiedInSource ? "passed" : "not available for wrapper-only geometry"}. ${item.production_training_eligible ? "Released and available to Daedalus retrieval." : "Not active in Daedalus retrieval."}${item.contributor_note ? ` Trainer: ${escapeHtml(item.contributor_note)}` : ""}${item.reviewer_note ? ` Reviewer: ${escapeHtml(item.reviewer_note)}` : ""}</div>
      </article>`;
    }).join("");
    container.querySelectorAll("[data-download]").forEach((button) => button.addEventListener("click", () => download(button.closest("[data-submission]").dataset.submission, button)));
    container.querySelectorAll("[data-action]").forEach((button) => button.addEventListener("click", () => review(button.closest("[data-submission]"), button.dataset.action, button)));
    container.querySelectorAll("[data-corpus-action]").forEach((button) => button.addEventListener("click", () => changeCorpus(button.closest("[data-submission]"), button.dataset.corpusAction, button)));
  }

  async function download(id, button) {
    button.disabled = true;
    try {
      const data = await api(`/submissions/${encodeURIComponent(id)}/download`, {method: "POST"});
      window.location.assign(data.download_url);
    } catch (error) {
      notice(error.message, true);
    } finally {
      button.disabled = false;
    }
  }

  async function review(card, action, button) {
    const labels = {approve: "approve", needs_correction: "request corrections for", release: "release", reject: "reject"};
    if (!window.confirm(`Confirm you want to ${labels[action]} this learning record?`)) return;
    button.disabled = true;
    const note = card.querySelector(".queue-note")?.value || "";
    try {
      await api(`/submissions/${encodeURIComponent(card.dataset.submission)}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action, note}),
      });
      notice(`Queue updated: ${action.replaceAll("_", " ")}.`);
      await connect();
    } catch (error) {
      notice(error.message, true);
      button.disabled = false;
    }
  }

  async function changeCorpus(card, action, button) {
    const note = card.querySelector(".queue-note")?.value.trim() || "";
    if (!note) return notice("Record a reason before changing the production corpus.", true);
    if (!window.confirm(`Confirm you want to ${action} this Daedalus lesson?`)) return;
    button.disabled = true;
    try {
      await api(`/corpus/${encodeURIComponent(card.dataset.submission)}`, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({action, note}),
      });
      const completed = {index: "indexed", disable: "disabled", enable: "enabled"};
      notice(`Corpus updated: lesson ${completed[action]}.`);
      await connect();
    } catch (error) {
      notice(error.message, true);
      button.disabled = false;
    }
  }

  async function retrieveLessons(request) {
    return api("/corpus/retrieve", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(request),
    });
  }

  function newClientIncidentId() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    return `client-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function buildRequestError(message, context) {
    const error = new Error(message);
    error.diagnostic = context;
    return error;
  }

  async function reportBuildError(error) {
    const context = error?.diagnostic || {};
    const clientIncidentId = context.clientIncidentId || newClientIncidentId();
    const payload = {
      client_incident_id: clientIncidentId,
      api_incident_id: context.apiIncidentId || "",
      phase: context.phase || "generation_request",
      http_status: Number.isFinite(context.httpStatus) ? context.httpStatus : null,
      elapsed_ms: Math.max(0, Math.round(context.elapsedMs || 0)),
      message: String(error?.message || "Daedalus build request failed.").slice(0, 1200),
      session_id: context.sessionId || "",
      pass_version: Number(context.passVersion || 0),
      source_kind: context.sourceKind || "prompt_only",
      reference_count: Number(context.referenceCount || 0),
      instruction_length: Number(context.instructionLength || 0),
    };
    let stored = false;
    let incidentId = payload.api_incident_id || clientIncidentId;
    let occurredAt = new Date().toISOString();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`${API}/errors`, {
        method: "POST",
        headers: {...headers(), "Content-Type": "application/json"},
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        stored = true;
        incidentId = data.incident_id || incidentId;
        occurredAt = data.incident?.occurred_at || occurredAt;
      }
    } catch {}
    finally { window.clearTimeout(timeout); }
    return {
      schema: "wonder-codex.daedalus-client-diagnostic.v1",
      incidentId,
      apiIncidentId: payload.api_incident_id || null,
      clientIncidentId,
      occurredAt,
      storedInOwnerLedger: stored,
      area: "daedalus",
      phase: payload.phase,
      category: payload.http_status === 504 ? "gateway_timeout" : "build_request_failure",
      httpStatus: payload.http_status,
      elapsedMs: payload.elapsed_ms,
      message: payload.message,
      model: state.generation.model || null,
      session: {
        id: payload.session_id || null,
        passVersion: payload.pass_version,
        sourceKind: payload.source_kind,
        referenceCount: payload.reference_count,
        instructionLength: payload.instruction_length,
      },
      privacy: {
        promptIncluded: false,
        apiKeysIncluded: false,
        operatorKeysIncluded: false,
        filenamesIncluded: false,
        uploadedFileContentsIncluded: false,
        referenceImagesIncluded: false,
        rawUserAgentIncluded: false,
      },
    };
  }

  async function generateBuild({sourceFile = null, instruction, references = [], sessionId = null}) {
    if (!state.permissions.submit) throw new Error("This operator cannot generate Daedalus builds.");
    if (state.generation.ready === false) {
      throw new Error(state.generation.setup_required || "Daedalus generation is not ready on the API service.");
    }
    const form = new FormData();
    form.append("instruction", String(instruction || "").trim());
    if (!sessionId && sourceFile) {
      form.append("source", sourceFile, sourceFile.name);
    }
    references.slice(0, Number(state.generation.maximum_references || 4)).forEach((file) => {
      form.append("references", file, file.name);
    });
    const path = sessionId
      ? `/build-sessions/${encodeURIComponent(sessionId)}/passes`
      : "/build-sessions";
    const startedAt = Date.now();
    const requestContext = {
      clientIncidentId: newClientIncidentId(),
      phase: "generation_request",
      sessionId: sessionId || "",
      passVersion: 0,
      sourceKind: sessionId ? "existing_session" : (sourceFile ? "uploaded_build" : "prompt_only"),
      referenceCount: references.length,
      instructionLength: String(instruction || "").trim().length,
    };
    let response;
    try {
      response = await fetch(API + path, {method: "POST", headers: headers(), body: form});
    } catch (error) {
      throw buildRequestError(error?.message || "Daedalus build request could not reach the API.", {
        ...requestContext,
        httpStatus: 0,
        elapsedMs: Date.now() - startedAt,
      });
    }
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) {
      throw buildRequestError(data.detail || `Build generation failed (${response.status})`, {
        ...requestContext,
        apiIncidentId: data.incident_id || response.headers.get("X-Incident-ID") || "",
        httpStatus: response.status,
        elapsedMs: Date.now() - startedAt,
      });
    }
    return data;
  }

  async function fetchGeneratedFile(filePath, filename) {
    const startedAt = Date.now();
    let response;
    try {
      response = await fetch(filePath, {headers: headers()});
    } catch (error) {
      throw buildRequestError(error?.message || "The generated build file could not reach this browser.", {
        clientIncidentId: newClientIncidentId(),
        phase: "generated_file_download",
        httpStatus: 0,
        elapsedMs: Date.now() - startedAt,
        sourceKind: "existing_session",
      });
    }
    if (!response.ok) {
      let data = {};
      try { data = await response.json(); } catch {}
      throw buildRequestError(data.detail || `Generated file download failed (${response.status})`, {
        clientIncidentId: newClientIncidentId(),
        apiIncidentId: data.incident_id || response.headers.get("X-Incident-ID") || "",
        phase: "generated_file_download",
        httpStatus: response.status,
        elapsedMs: Date.now() - startedAt,
        sourceKind: "existing_session",
      });
    }
    const blob = await response.blob();
    return new File([blob], filename || "daedalus-build.nmsbase", {type: "application/octet-stream"});
  }

  function buildContributorNote(note) {
    const versionDetails = [
      ["BBA", $("#sharedBbaVersion").value.trim()],
      ["Blender", $("#sharedBlenderVersion").value.trim()],
      ["Python", $("#sharedPythonVersion").value.trim()],
    ].filter(([, value]) => value).map(([name, value]) => `${name} ${value}`);
    return [String(note || "").trim(), versionDetails.length ? `Compatibility: ${versionDetails.join(" · ")}` : ""]
      .filter(Boolean).join(" — ").slice(0, 4000);
  }

  async function uploadLearningArchive(archive, filename, note) {
    if (!state.permissions.submit) throw new Error("This operator cannot submit Daedalus learning records.");
    if (!state.storageReady) throw new Error("Shared learning storage is not ready.");
    if (!archive) throw new Error("Choose or create a Daedalus learning ZIP first.");
    if (state.maxUploadBytes && archive.size > state.maxUploadBytes) {
      throw new Error(`That ZIP exceeds ${formatBytes(state.maxUploadBytes)}.`);
    }
    const form = new FormData();
    form.append("note", buildContributorNote(note));
    form.append("archive", archive, filename || archive.name || "daedalus-learning-package.zip");
    const response = await fetch(`${API}/submissions`, {method: "POST", headers: headers(), body: form});
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Upload failed (${response.status})`);
    return data;
  }

  async function submitLearningBlob(blob, filename, note = "") {
    notice("Packaging complete. Uploading and repeating Daedalus safety validation…");
    const data = await uploadLearningArchive(blob, filename, note);
    notice("Learning session added to shared review. Admin approval and release are still required.");
    await connect();
    return data;
  }

  async function submit(event) {
    event.preventDefault();
    const file = $("#sharedArchive").files?.[0];
    if (!file) return notice("Choose the exported Daedalus learning ZIP first.", true);
    $("#sharedSubmit").disabled = true;
    notice("Uploading and repeating Daedalus safety validation…");
    try {
      await uploadLearningArchive(file, file.name, $("#sharedNote").value);
      event.target.reset();
      notice("Learning package added to shared review. It is not production training data.");
      await connect();
    } catch (error) {
      notice(error.message, true);
    } finally {
      $("#sharedSubmit").disabled = false;
    }
  }

  $("#sharedUploadForm").addEventListener("submit", submit);
  $("#sharedRefresh").addEventListener("click", connect);
  $("#queueFilter").addEventListener("change", loadQueue);
  window.DaedalusShared = {
    submitLearningBlob,
    retrieveLessons,
    generateBuild,
    reportBuildError,
    fetchGeneratedFile,
    generationStatus: () => ({...state.generation}),
    refreshQueue: connect
  };
  connect();
})();
