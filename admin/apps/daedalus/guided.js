"use strict";

(() => {
  const $ = (selector) => document.querySelector(selector);
  const guided = {
    sourceFile: null,
    outputFile: null,
    referenceFiles: [],
    previewUrl: null,
    initialRequest: "",
    buildPlan: null,
    sessionId: null,
    sessionVersion: 0,
    busy: false
  };

  const ui = {
    status: $("#guidedStatus"),
    step: $("#guidedSessionStep"),
    conversation: $("#guidedConversation"),
    composer: $("#guidedComposer"),
    prompt: $("#guidedPrompt"),
    send: $("#guidedSend"),
    plan: $("#guidedPlan"),
    planSummary: $("#guidedPlanSummary"),
    downloadPlan: $("#guidedDownloadPlan"),
    buildInput: $("#guidedBuildInput"),
    buildName: $("#guidedBuildName"),
    referenceInput: $("#guidedReferenceInput"),
    referenceList: $("#guidedReferenceList"),
    outputInput: $("#guidedOutputInput"),
    outputName: $("#guidedOutputName"),
    outputHelp: $("#guidedOutputHelp"),
    downloadOutput: $("#guidedDownloadOutput"),
    attemptGood: $("#guidedAttemptGood"),
    attemptFix: $("#guidedAttemptFix"),
    previewImage: $("#guidedPreviewImage"),
    previewEmpty: $("#guidedPreviewEmpty"),
    previewBadge: $("#guidedPreviewBadge"),
    facts: $("#guidedBuildFacts"),
    truthConfirm: $("#guidedTruthConfirm"),
    submitLearning: $("#guidedSubmitLearning")
  };

  function setStatus(message, tone = "") {
    ui.status.className = `guided-status ${tone}`.trim();
    ui.status.lastChild.textContent = message;
  }

  function setStep(number) {
    ui.step.textContent = `Step ${number} of 4`;
  }

  function appendMessage(role, text) {
    const message = document.createElement("article");
    message.className = `guided-message ${role}`;
    const label = document.createElement("span");
    label.textContent = role === "user" ? "Builder" : "Daedalus";
    const body = document.createElement("p");
    body.textContent = text;
    message.append(label, body);
    ui.conversation.appendChild(message);
    ui.conversation.scrollTop = ui.conversation.scrollHeight;
    return message;
  }

  const progressLabels = {
    job_reservation: "Opening a private build workspace",
    request_reserved: "Build workspace reserved",
    build_submission: "Reading the prompt and starting materials",
    source_parse: "Reading the build geometry",
    reference_read: "Studying the reference pictures",
    corpus_retrieval: "Reviewing released Daedalus lessons",
    source_storage: "Saving a private working copy",
    provider_submission: "Starting the design pass",
    model_generation: "Designing the build",
    plan_validation: "Validating the design plan",
    plan_application: "Applying the validated changes",
    artifact_storage: "Writing the portable build file",
    generated_file_download: "Bringing the finished file into your browser",
    preview_render: "Drawing the build schematic",
    completed: "Build pass complete"
  };

  function startThinking() {
    const message = appendMessage("assistant", "Opening a private build workspace");
    message.classList.add("thinking");
    const body = message.querySelector("p");
    const label = document.createElement("span");
    label.className = "guided-thinking-label";
    label.textContent = body.textContent;
    const dots = document.createElement("span");
    dots.className = "guided-thinking-dots";
    dots.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) dots.appendChild(document.createElement("i"));
    body.textContent = "";
    body.append(label, dots);
    return {message, label};
  }

  function updateThinking(thinking, progress = {}) {
    if (!thinking?.label) return;
    const phase = String(progress.phase || "model_generation");
    thinking.label.textContent = progressLabels[phase] || "Daedalus is working on the build";
    ui.conversation.scrollTop = ui.conversation.scrollHeight;
  }

  function stopThinking(thinking) {
    thinking?.message?.remove?.();
  }

  function attachDiagnostic(message, diagnostic) {
    if (!message || !diagnostic) return;
    const footer = document.createElement("div");
    footer.className = "guided-diagnostic";
    const incident = document.createElement("code");
    incident.textContent = `Incident ${diagnostic.incidentId}`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Download diagnostic";
    button.addEventListener("click", () => {
      const body = new Blob([JSON.stringify(diagnostic, null, 2)], {type: "application/json"});
      downloadFile(new File(
        [body],
        `daedalus-error-${diagnostic.incidentId}.json`,
        {type: "application/json"}
      ));
    });
    footer.append(incident, button);
    message.appendChild(footer);
  }

  function setBusy(busy, label = "") {
    guided.busy = busy;
    ui.buildInput.disabled = busy;
    ui.referenceInput.disabled = busy;
    ui.send.disabled = busy;
    ui.send.textContent = busy ? (label || "Working…") : "Send to Daedalus";
  }

  function updateFinishState() {
    const analyzed = Boolean(window.DaedalusApp?.getSnapshot?.().report);
    const attemptApproved = window.DaedalusLearning?.getSnapshot?.().attemptStatus === "correct";
    ui.submitLearning.disabled = !analyzed || !guided.outputFile || !attemptApproved || !ui.truthConfirm.checked || guided.busy;
  }

  function renderFacts(report) {
    const values = report
      ? [report.build.objectCount.toLocaleString(), report.build.distinctObjectIds.toLocaleString(), "3,000"]
      : ["—", "—", "3,000"];
    [...ui.facts.querySelectorAll("strong")].forEach((element, index) => {
      element.textContent = values[index];
    });
  }

  function showBuildPreview(source, label) {
    const preview = window.DaedalusPreview?.buildSchematic?.(source, {label});
    if (!preview) return false;
    if (guided.previewUrl) URL.revokeObjectURL(guided.previewUrl);
    guided.previewUrl = URL.createObjectURL(new Blob([preview.svg], {type: "image/svg+xml"}));
    ui.previewImage.src = guided.previewUrl;
    ui.previewImage.alt = `${label} browser schematic in ${preview.axes.join("/")} view`;
    ui.previewImage.hidden = false;
    ui.previewEmpty.hidden = true;
    return true;
  }

  async function loadSource(file) {
    if (!file || !window.DaedalusApp?.isBuildFile?.(file)) {
      appendMessage("assistant", "That file is not a supported NMSBASE, prefab, Corvette, or JSON export.");
      return;
    }
    setBusy(true, "Reading build…");
    setStatus("Reading your build", "working");
    ui.plan.hidden = true;
    guided.buildPlan = null;
    guided.initialRequest = "";
    guided.sessionId = null;
    guided.sessionVersion = 0;
    guided.outputFile = null;
    ui.outputInput.value = "";
    ui.outputName.textContent = "No returned build attached";
    ui.outputHelp.textContent = "No result file yet. Tell Daedalus what to build and the validated result will appear here.";
    ui.downloadOutput.disabled = true;
    ui.attemptGood.disabled = true;
    ui.attemptFix.disabled = true;
    ui.truthConfirm.checked = false;
    try {
      const source = await window.DaedalusApp.loadBuildFile(file);
      if (!source) throw new Error("Daedalus could not read that build file.");
      guided.sourceFile = file;
      ui.buildName.textContent = file.name;
      showBuildPreview(source, "Source build");
      ui.previewBadge.textContent = `${source.objects.length.toLocaleString()} source records`;
      const report = await window.DaedalusApp.analyze();
      if (!report) throw new Error("Daedalus could not analyze that build file.");
      renderFacts(report);
      setStep(2);
      setStatus("Ready for your instructions", "ready");
      appendMessage(
        "assistant",
        `I loaded ${report.build.name}: ${report.build.objectCount.toLocaleString()} placed parts across ${report.build.distinctObjectIds.toLocaleString()} Object IDs. Tell me what you want to change, create, or decorate.`
      );
      ui.prompt.focus();
    } catch (error) {
      guided.sourceFile = null;
      ui.buildName.textContent = "No source file — prompt-only build";
      renderFacts(null);
      setStep(1);
      setStatus("Build could not be read");
      appendMessage("assistant", error.message || "I could not read that build file.");
    } finally {
      setBusy(false);
      updateFinishState();
    }
  }

  function renderReferences() {
    ui.referenceList.innerHTML = "";
    guided.referenceFiles.forEach((file) => {
      const tag = document.createElement("span");
      tag.textContent = file.name;
      tag.title = file.name;
      ui.referenceList.appendChild(tag);
    });
  }

  async function addReferences(files) {
    const supported = files.filter((file) => /\.(png|jpe?g|webp)$/i.test(file.name));
    if (!supported.length) return;
    const maximum = Number(window.DaedalusShared?.generationStatus?.().maximum_references || 4);
    const accepted = supported.slice(0, Math.max(0, maximum - guided.referenceFiles.length));
    guided.referenceFiles.push(...accepted);
    window.DaedalusApp?.addReferenceImages?.(accepted);
    renderReferences();
    const previewable = accepted.find((file) => /\.(png|jpe?g|webp)$/i.test(file.name));
    if (previewable) {
      if (guided.previewUrl) URL.revokeObjectURL(guided.previewUrl);
      guided.previewUrl = URL.createObjectURL(previewable);
      ui.previewImage.src = guided.previewUrl;
      ui.previewImage.hidden = false;
      ui.previewEmpty.hidden = true;
      ui.previewBadge.textContent = `${guided.referenceFiles.length} reference${guided.referenceFiles.length === 1 ? "" : "s"}`;
    }
    if (guided.sourceFile) {
      try {
        const report = await window.DaedalusApp.analyze();
        renderFacts(report);
      } catch {}
    }
  }

  async function submitPrompt(event) {
    event?.preventDefault?.();
    const instruction = ui.prompt.value.trim();
    if (!instruction || guided.busy) return;

    appendMessage("user", instruction);
    const thinking = startThinking();
    ui.prompt.value = "";
    setBusy(true, "Generating build…");
    setStatus("Daedalus is designing and validating this pass", "working");
    setStep(2);
    if (!guided.initialRequest) {
      guided.initialRequest = instruction;
      window.DaedalusApp.setBrief(instruction);
    }

    if (guided.sourceFile && window.DaedalusApp?.getSnapshot?.().report) {
      window.DaedalusLearning?.addRevision?.(instruction);
    }
    try {
      if (!window.DaedalusShared?.generateBuild || !window.DaedalusShared?.fetchGeneratedFile) {
        throw new Error("The Daedalus generation service did not load. Refresh the page and try again.");
      }
      const result = await window.DaedalusShared.generateBuild({
        sourceFile: guided.sourceFile,
        instruction,
        references: guided.referenceFiles,
        sessionId: guided.sessionId,
        onProgress: (progress) => updateThinking(thinking, progress)
      });
      updateThinking(thinking, {phase: "generated_file_download"});
      const outputFile = await window.DaedalusShared.fetchGeneratedFile(result.file_path, result.pass.filename);
      updateThinking(thinking, {phase: "preview_render"});
      if (!await loadOutput(outputFile, {announce: false})) {
        stopThinking(thinking);
        return;
      }
      guided.sessionId = result.session.id;
      guided.sessionVersion = result.pass.version;
      guided.buildPlan = result.pass.plan;

      const plan = result.pass.plan || {};
      const operationCount = Number(result.pass.operation_count || 0);
      const objectCount = Number(result.pass.object_count || 0);
      const corpusVersion = Number(result.pass.corpus_version || 0);
      stopThinking(thinking);
      appendMessage(
        "assistant",
        plan.assistantMessage || `Build Pass ${result.pass.version} is complete with ${objectCount.toLocaleString()} placed parts and ${operationCount.toLocaleString()} validated refinement${operationCount === 1 ? "" : "s"}. Inspect it in BBA or in game, then tell me what to revise.`
      );
      ui.planSummary.textContent = `Pass ${result.pass.version} · ${objectCount.toLocaleString()} parts · ${operationCount.toLocaleString()} refinement${operationCount === 1 ? "" : "s"} · corpus v${corpusVersion}`;
      ui.plan.hidden = false;
      renderFacts({build: {
        objectCount: Number(result.pass.object_count || 0),
        distinctObjectIds: Number(result.pass.distinct_object_ids || 0)
      }});
      ui.previewBadge.textContent = `Latest: Pass ${result.pass.version}`;
      setStep(3);
      setStatus(`Build Pass ${result.pass.version} ready`, "ready");
    } catch (error) {
      stopThinking(thinking);
      setStatus("Build generation needs attention");
      let diagnostic = null;
      try {
        diagnostic = await window.DaedalusShared?.reportBuildError?.(error);
      } catch {}
      const gatewayTimeout = Number(diagnostic?.httpStatus || error?.diagnostic?.httpStatus) === 504;
      const message = appendMessage(
        "assistant",
        gatewayTimeout
          ? "The gateway timed out before Daedalus returned the build. I recorded a diagnostic so we can trace where the request stopped."
          : (error.message || "I could not generate a validated build pass.")
      );
      attachDiagnostic(message, diagnostic);
    } finally {
      setBusy(false);
      updateFinishState();
    }
  }

  async function loadOutput(file, options = {}) {
    if (!file) return false;
    const promptOnly = !guided.sourceFile;
    setStatus(promptOnly ? "Opening prompt-created build" : "Comparing returned build", "working");
    guided.outputFile = null;
    ui.downloadOutput.disabled = true;
    ui.attemptGood.disabled = true;
    ui.attemptFix.disabled = true;
    try {
      if (promptOnly) {
        const source = await window.DaedalusApp.loadBuildFile(file);
        if (!source) throw new Error("Daedalus could not open the prompt-created build.");
        guided.sourceFile = file;
        ui.buildName.textContent = `Prompt-created canvas · ${file.name}`;
        const report = await window.DaedalusApp.analyze();
        if (!report) throw new Error("Daedalus could not analyze the prompt-created build.");
        window.DaedalusApp.setBrief(guided.initialRequest);
        renderFacts(report);
      }
      await window.DaedalusLearning.loadAttempt(file);
      const attemptSnapshot = window.DaedalusLearning.getSnapshot();
      const attempt = attemptSnapshot.attemptFile;
      if (!attempt) throw new Error("The returned build could not be compared.");
      showBuildPreview(attemptSnapshot.attemptGeometry, "Latest Daedalus result");
      guided.outputFile = file;
      ui.outputName.textContent = file.name;
      ui.outputHelp.textContent = promptOnly
        ? "Created from your prompt as a portable prefab. Inspect it in BBA or in game before marking the result."
        : "Returned build attached and compared with the source. Inspect it in BBA or in game before marking the result.";
      ui.downloadOutput.disabled = false;
      ui.attemptGood.disabled = false;
      ui.attemptFix.disabled = false;
      setStep(3);
      setStatus("Returned build ready to inspect", "ready");
      if (options.announce !== false) {
        appendMessage("assistant", `I attached ${file.name} as the latest Daedalus result and compared its placed parts with your source. Please inspect it in BBA or in game, then tell me what is right or what needs another pass.`);
      }
      return true;
    } catch (error) {
      if (promptOnly) guided.sourceFile = null;
      setStatus("Returned build could not be read");
      appendMessage("assistant", error.message || "I could not read that returned build.");
      return false;
    } finally {
      updateFinishState();
    }
  }

  function downloadFile(file) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file.name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function downloadPlan() {
    if (!guided.buildPlan) return;
    const stem = (guided.sourceFile?.name || "daedalus-build").replace(/\.[^.]+$/, "").replace(/[^a-z0-9_-]+/gi, "-");
    const blob = new Blob([JSON.stringify(guided.buildPlan, null, 2)], { type: "application/json" });
    downloadFile(new File([blob], `${stem}-pass-${guided.sessionVersion || 1}-details.json`, { type: "application/json" }));
  }

  async function finishSession() {
    if (!ui.truthConfirm.checked || guided.busy) return;
    setBusy(true, "Submitting…");
    ui.submitLearning.disabled = true;
    setStatus("Sending to human review", "working");
    try {
      const verified = window.DaedalusLearning.approveGroundTruth();
      if (!verified) throw new Error("The source did not pass every ground-truth safety check. Open Advanced Analyzer & Trainer to see what needs attention.");
      const response = await window.DaedalusLearning.submitForReview();
      if (!response) throw new Error("The shared review queue is not ready. Your browser session is still intact.");
      setStep(4);
      setStatus("Saved for human review", "ready");
      appendMessage("assistant", "Session saved! An admin must inspect, approve, and release it before the lesson can influence future Daedalus builds.");
    } catch (error) {
      setStatus("Review submission needs attention");
      appendMessage("assistant", error.message || "I could not send this session to review.");
    } finally {
      setBusy(false);
      updateFinishState();
    }
  }

  ui.buildInput.addEventListener("change", (event) => loadSource(event.target.files?.[0]));
  ui.referenceInput.addEventListener("change", (event) => addReferences([...event.target.files]));
  ui.outputInput.addEventListener("change", (event) => loadOutput(event.target.files?.[0]));
  ui.composer.addEventListener("submit", submitPrompt);
  ui.prompt.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") submitPrompt(event);
  });
  ui.downloadPlan.addEventListener("click", downloadPlan);
  ui.downloadOutput.addEventListener("click", () => downloadFile(guided.outputFile));
  ui.attemptGood.addEventListener("click", () => {
    if (window.DaedalusLearning.markAttemptCorrect()) {
      appendMessage("assistant", "I recorded that this attempt looks correct. That decision is separate from verifying the original source.");
      updateFinishState();
    }
  });
  ui.attemptFix.addEventListener("click", () => {
    if (window.DaedalusLearning.markNeedsCorrection()) {
      appendMessage("assistant", "I marked this attempt as needing correction. Tell me what is wrong in the chat so the next pass and learning package preserve the details.");
      updateFinishState();
      ui.prompt.focus();
    }
  });
  ui.truthConfirm.addEventListener("change", updateFinishState);
  ui.submitLearning.addEventListener("click", finishSession);
  window.addEventListener("beforeunload", () => {
    if (guided.previewUrl) URL.revokeObjectURL(guided.previewUrl);
  });
  setBusy(false);
  setStatus("Describe a build or add a file", "ready");
  ui.prompt.focus();
})();
