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
  }

  function setBusy(busy, label = "") {
    guided.busy = busy;
    ui.buildInput.disabled = busy;
    ui.referenceInput.disabled = busy;
    ui.send.disabled = busy || !guided.sourceFile;
    ui.send.textContent = busy ? (label || "Working…") : "Send to Daedalus";
  }

  function updateFinishState() {
    const analyzed = Boolean(window.DaedalusApp?.getSnapshot?.().report);
    ui.submitLearning.disabled = !analyzed || !ui.truthConfirm.checked || guided.busy;
  }

  function renderFacts(report) {
    const values = report
      ? [report.build.objectCount.toLocaleString(), report.build.distinctObjectIds.toLocaleString(), "3,000"]
      : ["—", "—", "3,000"];
    [...ui.facts.querySelectorAll("strong")].forEach((element, index) => {
      element.textContent = values[index];
    });
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
    guided.outputFile = null;
    ui.outputInput.value = "";
    ui.outputName.textContent = "No returned build attached";
    ui.outputHelp.textContent = "No result file yet. Daedalus can prepare the next build here; automatic NMSBASE or prefab creation is not connected yet.";
    ui.downloadOutput.disabled = true;
    ui.attemptGood.disabled = true;
    ui.attemptFix.disabled = true;
    ui.truthConfirm.checked = false;
    try {
      const source = await window.DaedalusApp.loadBuildFile(file);
      if (!source) throw new Error("Daedalus could not read that build file.");
      guided.sourceFile = file;
      ui.buildName.textContent = file.name;
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
      ui.buildName.textContent = "No build added";
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
    const supported = files.filter((file) => /\.(png|jpe?g|webp|jxr)$/i.test(file.name));
    if (!supported.length) return;
    guided.referenceFiles.push(...supported.slice(0, Math.max(0, 12 - guided.referenceFiles.length)));
    window.DaedalusApp?.addReferenceImages?.(supported);
    renderReferences();
    const previewable = supported.find((file) => /\.(png|jpe?g|webp)$/i.test(file.name));
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

  function compactLesson(item) {
    return {
      score: item.score,
      reasons: item.reasons || [],
      intent: item.lesson?.intent || {},
      corrections: item.lesson?.corrections || {},
      structuralFingerprint: {
        objectCount: item.lesson?.groundTruth?.objectCount || null,
        distinctObjectIds: item.lesson?.groundTruth?.distinctObjectIds || null,
        bounds: item.lesson?.groundTruth?.bounds || null,
        topPartInventory: (item.lesson?.groundTruth?.partInventory || []).slice(0, 40)
      },
      provenance: {
        submissionId: item.provenance?.submissionId || null,
        recordId: item.provenance?.recordId || null,
        sourceSha256: item.provenance?.sourceSha256 || null,
        contributor: item.provenance?.contributor || null,
        reviewer: item.provenance?.reviewer || null,
        releasedAt: item.provenance?.releasedAt || null
      }
    };
  }

  async function retrieveLessons(instruction, snapshot) {
    if (!window.DaedalusShared?.retrieveLessons) return { corpus_version: 0, items: [] };
    const parts = snapshot.report?.build?.parts || [];
    return window.DaedalusShared.retrieveLessons({
      query: instruction,
      domain: snapshot.mode === "corvette" ? "NO_MANS_SKY_CORVETTE_BUILDING" : "NO_MANS_SKY_BASE_BUILDING",
      category: snapshot.category || "other",
      style_tags: [],
      object_ids: parts.slice(0, 120).map((part) => part.objectId).filter((id) => /^\^/.test(id)),
      part_count: snapshot.report?.build?.objectCount || null,
      limit: 6
    });
  }

  async function submitPrompt(event) {
    event?.preventDefault?.();
    const instruction = ui.prompt.value.trim();
    if (!instruction || !guided.sourceFile || guided.busy) return;
    const snapshot = window.DaedalusApp.getSnapshot();
    if (!snapshot.report) return;

    appendMessage("user", instruction);
    ui.prompt.value = "";
    setBusy(true, "Preparing pass…");
    setStatus("Finding approved lessons", "working");
    setStep(2);
    if (!guided.initialRequest) {
      guided.initialRequest = instruction;
      window.DaedalusApp.setBrief(instruction);
    }

    const revision = window.DaedalusLearning?.addRevision?.(instruction) || null;
    let retrieval = { corpus_version: 0, items: [] };
    let retrievalError = null;
    try {
      retrieval = await retrieveLessons(instruction, snapshot);
    } catch (error) {
      retrievalError = error;
    }

    const lessons = (retrieval.items || []).map(compactLesson);
    guided.buildPlan = {
      schema: "wonder-codex.daedalus.guided-build-plan.v1",
      createdAt: new Date().toISOString(),
      status: "PLANNED_NOT_APPLIED",
      source: {
        fileName: snapshot.source?.sourceName || guided.sourceFile.name,
        format: snapshot.source?.format || null,
        objectCount: snapshot.report.build.objectCount,
        distinctObjectIds: snapshot.report.build.distinctObjectIds,
        sourceUnmodified: true
      },
      request: instruction,
      revision,
      retrieval: {
        corpusVersion: retrieval.corpus_version || 0,
        lessonCount: lessons.length,
        lessons,
        error: retrievalError?.message || null
      },
      safety: {
        maximumParts: 3000,
        objectIdsOnly: true,
        protectedAnchorPreserved: true,
        uniformScaleRequired: true,
        preserveUnmentionedGeometry: true
      },
      output: {
        generatedBuildFile: null,
        reason: "Automatic NMSBASE or prefab creation is not connected on this server. This plan is ready for that connection."
      }
    };

    const scopeText = revision?.scopes?.length ? revision.scopes.join(", ") : "the requested areas";
    const lessonText = lessons.length
      ? `I matched ${lessons.length} approved learning lesson${lessons.length === 1 ? "" : "s"} from corpus v${retrieval.corpus_version}.`
      : retrievalError
        ? "The approved lesson library was unavailable, so I kept this pass grounded only in your analyzed build and instructions."
        : "No approved lesson was close enough yet, so I kept this pass grounded in your analyzed build and instructions.";
    appendMessage(
      "assistant",
      `${lessonText} I captured a safe next pass for ${scopeText}, preserving everything you did not mention. The build plan is ready. Automatic NMSBASE and prefab creation is not connected yet, so I have not claimed that a modified file exists.`
    );
    ui.planSummary.textContent = `${lessons.length} released lesson${lessons.length === 1 ? "" : "s"} · ${revision?.scopes?.length || 1} change scope${revision?.scopes?.length === 1 ? "" : "s"}`;
    ui.plan.hidden = false;
    setStep(3);
    setStatus("Build plan ready", "ready");
    setBusy(false);
    updateFinishState();
  }

  async function loadOutput(file) {
    if (!file || !guided.sourceFile) return;
    setStatus("Comparing returned build", "working");
    try {
      await window.DaedalusLearning.loadAttempt(file);
      const attempt = window.DaedalusLearning.getSnapshot().attemptFile;
      if (!attempt) throw new Error("The returned build could not be compared.");
      guided.outputFile = file;
      ui.outputName.textContent = file.name;
      ui.outputHelp.textContent = "Returned build attached and compared with the source. Inspect it in BBA or in game before marking the result.";
      ui.downloadOutput.disabled = false;
      ui.attemptGood.disabled = false;
      ui.attemptFix.disabled = false;
      setStep(3);
      setStatus("Returned build ready to inspect", "ready");
      appendMessage("assistant", `I attached ${file.name} as the latest Daedalus result and compared its placed parts with your source. Please inspect it in BBA or in game, then tell me what is right or what needs another pass.`);
    } catch (error) {
      setStatus("Returned build could not be read");
      appendMessage("assistant", error.message || "I could not read that returned build.");
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
    downloadFile(new File([blob], `${stem}-next-build-plan.json`, { type: "application/json" }));
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
    }
  });
  ui.attemptFix.addEventListener("click", () => {
    if (window.DaedalusLearning.markNeedsCorrection()) {
      appendMessage("assistant", "I marked this attempt as needing correction. Tell me what is wrong in the chat so the next pass and learning package preserve the details.");
      ui.prompt.focus();
    }
  });
  ui.truthConfirm.addEventListener("change", updateFinishState);
  ui.submitLearning.addEventListener("click", finishSession);
  window.addEventListener("beforeunload", () => {
    if (guided.previewUrl) URL.revokeObjectURL(guided.previewUrl);
  });
})();
