"use strict";

const LEARNING_MEMORY_KEY = "daedalus.learning.memory.v0.1";
const LEARNING_SESSION_KEY = "daedalus.learning.sessions.v0.1";

const learningState = {
  recordId: null,
  attemptFile: null,
  attemptData: null,
  comparison: null,
  inspectionFile: null,
  inspectionSummary: null,
  selectedPart: null,
  partFeedback: [],
  generatedSign: null,
  conversation: [],
  revisions: [],
  groundTruthStatus: "unverified",
  groundTruthVerifiedAt: null,
  attemptStatus: "not_reviewed",
  attemptReviewedAt: null,
  teacherNote: ""
};

let modelInspector = null;

const learningEls = {
  lab: document.querySelector("#learningLab"),
  groundTruthStatus: document.querySelector("#groundTruthStatus"),
  attemptStatus: document.querySelector("#attemptStatus"),
  memoryMetric: document.querySelector("#learningMemoryMetric"),
  truthMetric: document.querySelector("#learningTruthMetric"),
  referenceMetric: document.querySelector("#learningReferenceMetric"),
  comparisonMetric: document.querySelector("#learningComparisonMetric"),
  prompt: document.querySelector("#learningPrompt"),
  tags: document.querySelector("#learningTags"),
  attemptInput: document.querySelector("#attemptInput"),
  attemptDropZone: document.querySelector("#attemptDropZone"),
  selectedAttempt: document.querySelector("#selectedAttempt"),
  comparisonGrid: document.querySelector("#comparisonGrid"),
  inspectionInput: document.querySelector("#inspectionInput"),
  inspectionDropZone: document.querySelector("#inspectionDropZone"),
  inspectorCanvas: document.querySelector("#inspectorCanvas"),
  inspectorEmpty: document.querySelector("#inspectorEmpty"),
  inspectorStatus: document.querySelector("#inspectorStatus"),
  inspectorViewButtons: [...document.querySelectorAll(".inspector-view-button")],
  inspectorResetButton: document.querySelector("#inspectorResetButton"),
  inspectorWireframeButton: document.querySelector("#inspectorWireframeButton"),
  inspectorCaptureButton: document.querySelector("#inspectorCaptureButton"),
  selectedPartName: document.querySelector("#selectedPartName"),
  selectedPartDetails: document.querySelector("#selectedPartDetails"),
  selectedPartFeedback: document.querySelector("#selectedPartFeedback"),
  selectedPartCorrectButton: document.querySelector("#selectedPartCorrectButton"),
  selectedPartWrongButton: document.querySelector("#selectedPartWrongButton"),
  reviseSelectedPartButton: document.querySelector("#reviseSelectedPartButton"),
  conversationLog: document.querySelector("#conversationLog"),
  revisionInput: document.querySelector("#revisionInput"),
  recordRevisionButton: document.querySelector("#recordRevisionButton"),
  teacherNote: document.querySelector("#teacherNote"),
  attemptCorrectButton: document.querySelector("#attemptCorrectButton"),
  needsCorrectionButton: document.querySelector("#needsCorrectionButton"),
  exportButton: document.querySelector("#exportLearningButton"),
  submitReviewButton: document.querySelector("#submitLearningReviewButton"),
  approveButton: document.querySelector("#approveLearningButton")
};

function initLearningLab() {
  if (!learningEls.lab) return;

  learningEls.attemptInput.addEventListener("change", (event) => {
    if (event.target.files[0]) loadAttempt(event.target.files[0]);
  });
  setupDropZone(learningEls.attemptDropZone, (files) => {
    const file = files.find(isBuildFile);
    if (file) loadAttempt(file);
    else showToast("Choose an attempted .nmsship, .nmsprefab, or JSON file.");
  });
  learningEls.inspectionInput.addEventListener("change", (event) => {
    if (event.target.files[0]) loadInspectionFile(event.target.files[0]);
  });
  setupDropZone(learningEls.inspectionDropZone, (files) => {
    const file = files.find((item) => /\.glb$/i.test(item.name));
    if (file) loadInspectionFile(file);
    else showToast("Choose a self-contained Daedalus .glb inspection model.");
  });
  learningEls.inspectorViewButtons.forEach((button) => {
    button.addEventListener("click", () => modelInspector?.setView(button.dataset.inspectorView));
  });
  learningEls.inspectorResetButton.addEventListener("click", () => modelInspector?.resetView());
  learningEls.inspectorWireframeButton.addEventListener("click", toggleInspectorWireframe);
  learningEls.inspectorCaptureButton.addEventListener("click", captureInspectorImage);
  learningEls.selectedPartCorrectButton.addEventListener("click", () => recordPartFeedback("correct"));
  learningEls.selectedPartWrongButton.addEventListener("click", () => recordPartFeedback("incorrect"));
  learningEls.reviseSelectedPartButton.addEventListener("click", reviseSelectedPart);
  learningEls.recordRevisionButton.addEventListener("click", recordRevision);
  learningEls.revisionInput.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      recordRevision();
    }
  });
  learningEls.approveButton.addEventListener("click", approveGroundTruth);
  learningEls.attemptCorrectButton.addEventListener("click", markAttemptCorrect);
  learningEls.needsCorrectionButton.addEventListener("click", markNeedsCorrection);
  learningEls.exportButton.addEventListener("click", exportLearningPackage);
  learningEls.submitReviewButton.addEventListener("click", submitLearningForReview);
  learningEls.teacherNote.addEventListener("input", () => {
    learningState.teacherNote = learningEls.teacherNote.value.trim();
  });

  if (window.DaedalusModelInspector) {
    modelInspector = new window.DaedalusModelInspector({
      canvas: learningEls.inspectorCanvas,
      onSelect: renderSelectedInspectionPart,
      onStatus: renderInspectorStatus
    });
  } else {
    renderInspectorStatus({
      status: "error",
      message: "The bundled 3D inspector could not start."
    });
  }

  renderLearningState();
}

function onLearningSourceChanged() {
  learningState.recordId = null;
  learningState.attemptFile = null;
  learningState.attemptData = null;
  learningState.comparison = null;
  learningState.inspectionFile = null;
  learningState.inspectionSummary = null;
  learningState.selectedPart = null;
  learningState.partFeedback = [];
  learningState.generatedSign = null;
  learningState.conversation = [];
  learningState.revisions = [];
  learningState.groundTruthStatus = "unverified";
  learningState.groundTruthVerifiedAt = null;
  learningState.attemptStatus = "not_reviewed";
  learningState.attemptReviewedAt = null;
  learningState.teacherNote = "";
  learningEls.attemptInput.value = "";
  learningEls.inspectionInput.value = "";
  learningEls.prompt.value = "";
  learningEls.tags.value = "";
  learningEls.teacherNote.value = "";
  learningEls.selectedAttempt.hidden = true;
  learningEls.comparisonGrid.hidden = true;
  modelInspector?.clearModel();
  learningEls.inspectorEmpty.hidden = false;
  renderSelectedInspectionPart(null);
  renderInspectorStatus({ status: "empty", message: "No 3D model loaded" });
  renderLearningState();
}

function onLearningAnalysisReady() {
  if (!state.report || !state.packageData) return;
  learningState.recordId = learningState.recordId || makeRecordId();

  if (!learningState.conversation.length) {
    const build = state.report.build;
    appendConversation(
      "assistant",
      `I analyzed ${build.name}: ${build.objectCount.toLocaleString()} placed records across ${build.distinctObjectIds.toLocaleString()} Object IDs. Tell me what you would like to change, and I will capture a scoped revision for the next build pass.`
    );
  }

  if (/crimson valkyrie/i.test(state.report.build.name) && !learningEls.prompt.value.trim()) {
    learningEls.prompt.value = "Reconstruct this sailing ship-style Corvette from the supplied views, including its long open deck, raised stern, dark-red structure, and multi-mast sail arrangement.";
    learningEls.tags.value = "sailing ship, dark red, multi-mast, open deck, raised stern";
  }

  renderLearningState();
}

function onLearningEvidenceChanged() {
  renderLearningState();
}

function onDesignIntentChanged(intent) {
  if (!intent) return;
  if (intent.originalRequest) learningEls.prompt.value = intent.originalRequest;
  const automaticTags = [intent.category];
  if (intent.signSpecification) {
    automaticTags.push(
      "ObjectID-only",
      intent.signSpecification.fontGrammar,
      `${intent.signSpecification.backdropColor} backdrop`,
      `${intent.signSpecification.letteringColor} lettering`
    );
  }
  const existing = parseTags(learningEls.tags.value);
  learningEls.tags.value = [...new Set([...existing, ...automaticTags].filter(Boolean))].join(", ");
}

function onGeneratedSign(result) {
  learningState.generatedSign = result;
  appendConversation(
    "assistant",
    `Generated an ObjectID-only sign attempt for “${result.manifest.text}” with ${result.manifest.placedObjectCount.toLocaleString()} records. Test the prefab in Base Builder or NMS, then mark the attempt correct or needing correction.`
  );
  saveSessionDraft();
  renderLearningState();
}

async function loadInspectionFile(file) {
  if (!state.report) {
    showToast("Analyze the verified build before loading its Blender inspection model.");
    return;
  }
  if (!/\.glb$/i.test(file.name)) {
    showToast("The interactive inspector requires one self-contained .glb file.");
    return;
  }
  if (!modelInspector) {
    showToast("The bundled 3D inspector is unavailable in this browser.");
    return;
  }

  try {
    learningState.inspectionFile = file;
    learningState.inspectionSummary = await modelInspector.load(await file.arrayBuffer(), file.name);
    learningState.selectedPart = null;
    learningState.attemptStatus = "not_reviewed";
    learningState.attemptReviewedAt = null;
    learningEls.inspectorEmpty.hidden = true;
    appendConversation(
      "assistant",
      `Interactive inspection loaded: ${file.name}, with ${learningState.inspectionSummary.meshCount.toLocaleString()} clickable meshes. Rotate the model and select questionable parts before writing the teacher note.`
    );
    saveSessionDraft();
    renderLearningState();
    showToast("Interactive Blender inspection model loaded.");
  } catch (error) {
    learningState.inspectionFile = null;
    learningState.inspectionSummary = null;
    learningEls.inspectorEmpty.hidden = false;
    renderInspectorStatus({
      status: "error",
      message: error.message || "The GLB could not be opened."
    });
    showToast(error.message || "The GLB could not be opened.");
  }
}

function renderInspectorStatus(event) {
  if (!learningEls.inspectorStatus) return;
  const status = event?.status || "empty";
  learningEls.inspectorStatus.className = `inspector-status ${status}`;
  learningEls.inspectorStatus.textContent = event?.message || "No 3D model loaded";
}

function renderSelectedInspectionPart(part) {
  learningState.selectedPart = part;
  const selected = Boolean(part);
  learningEls.selectedPartCorrectButton.disabled = !selected;
  learningEls.selectedPartWrongButton.disabled = !selected;
  learningEls.reviseSelectedPartButton.disabled = !selected;
  learningEls.selectedPartFeedback.value = "";

  if (!part) {
    learningEls.selectedPartName.textContent = "Click a part to inspect it";
    learningEls.selectedPartDetails.innerHTML = [
      ["Object ID", "—"],
      ["Role", "—"],
      ["Geometry", "—"],
      ["Source index", "—"]
    ].map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("");
    return;
  }

  learningEls.selectedPartName.textContent = part.objectId || part.name;
  learningEls.selectedPartDetails.innerHTML = [
    ["Object ID", part.objectId || "Guide / unavailable"],
    ["Role", part.role || "Unclassified"],
    ["Geometry", part.geometry || (part.guideOnly ? "Guide-only mesh" : "Mesh")],
    ["Source index", part.sourceIndex ?? "Not assigned"]
  ].map(([label, value]) => `
    <div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>
  `).join("");
}

function recordPartFeedback(verdict) {
  const part = learningState.selectedPart;
  if (!part) {
    showToast("Click a mesh in the inspector first.");
    return;
  }
  const explanation = learningEls.selectedPartFeedback.value.trim();
  const feedback = {
    feedbackId: makeRecordId("part-feedback"),
    createdAt: new Date().toISOString(),
    verdict,
    explanation: explanation || null,
    inspectionFileName: learningState.inspectionFile?.name || null,
    part: {
      name: part.name,
      objectId: part.objectId,
      role: part.role,
      geometry: part.geometry,
      sourceIndex: part.sourceIndex,
      modelPath: part.modelPath,
      confidence: part.confidence,
      guideOnly: part.guideOnly
    }
  };
  learningState.partFeedback.push(feedback);

  const identity = part.objectId || part.name;
  const note = `Inspector part ${identity} marked ${verdict}${explanation ? `: ${explanation}` : "."}`;
  appendTeacherNote(note);
  if (verdict === "incorrect") {
    learningState.attemptStatus = "needs_correction";
    learningState.attemptReviewedAt = new Date().toISOString();
  }
  appendConversation(
    "assistant",
    `${identity} was recorded as ${verdict}. ${verdict === "incorrect" ? "The generated attempt is now marked Needs correction." : "This part-level approval does not automatically approve the entire attempt."}`
  );
  learningEls.selectedPartFeedback.value = "";
  saveSessionDraft();
  renderLearningState();
  showToast(`Selected part marked ${verdict}.`);
}

function reviseSelectedPart() {
  const part = learningState.selectedPart;
  if (!part) return;
  const identity = part.objectId || part.name;
  const explanation = learningEls.selectedPartFeedback.value.trim();
  learningEls.revisionInput.value = `Change ${identity}${part.role ? ` (${part.role})` : ""}${explanation ? `: ${explanation}` : ". "}`;
  learningEls.revisionInput.focus();
  learningEls.revisionInput.scrollIntoView({ behavior: "smooth", block: "center" });
  showToast("Part-specific revision prepared.");
}

function appendTeacherNote(note) {
  const existing = learningEls.teacherNote.value.trim();
  learningEls.teacherNote.value = existing ? `${existing} ${note}` : note;
  learningState.teacherNote = learningEls.teacherNote.value.trim();
}

function toggleInspectorWireframe() {
  if (!modelInspector) return;
  const enabled = learningEls.inspectorWireframeButton.getAttribute("aria-pressed") !== "true";
  learningEls.inspectorWireframeButton.setAttribute("aria-pressed", String(enabled));
  modelInspector.setWireframe(enabled);
}

function captureInspectorImage() {
  if (!learningState.inspectionFile || !modelInspector) {
    showToast("Load a Blender inspection GLB first.");
    return;
  }
  const name = safeFileName(state.report?.build?.name || "daedalus");
  modelInspector.capturePng(`${name}-inspection.png`);
  showToast("Inspection view captured as PNG.");
}

async function loadAttempt(file) {
  if (!state.packageData?.objects) {
    showToast("Analyze the verified ground-truth build first.");
    return;
  }
  if (!isBuildFile(file)) {
    showToast("That attempted build is not a supported package.");
    return;
  }

  const priorText = learningEls.comparisonMetric.textContent;
  learningEls.comparisonMetric.textContent = "Reading…";
  try {
    const data = await parseBuildFile(file);
    learningState.attemptFile = file;
    learningState.attemptData = data;
    learningState.comparison = comparePlacedObjects(state.packageData.objects, data.objects);
    learningState.attemptStatus = "not_reviewed";
    learningState.attemptReviewedAt = null;
    renderSelectedAttempt();
    renderComparison();
    appendConversation(
      "assistant",
      buildComparisonMessage(learningState.comparison)
    );
    saveSessionDraft();
    showToast("Attempt compared with verified ground truth.");
  } catch (error) {
    learningState.attemptFile = null;
    learningState.attemptData = null;
    learningState.comparison = null;
    learningEls.comparisonMetric.textContent = priorText;
    showToast(error.message || "Daedalus could not read that attempted build.");
  }
}

function clearAttempt() {
  learningState.attemptFile = null;
  learningState.attemptData = null;
  learningState.comparison = null;
  learningEls.attemptInput.value = "";
  learningEls.selectedAttempt.hidden = true;
  learningEls.comparisonGrid.hidden = true;
  renderLearningState();
}

function renderSelectedAttempt() {
  const data = learningState.attemptData;
  if (!data) return;
  learningEls.selectedAttempt.hidden = false;
  learningEls.selectedAttempt.innerHTML = "";

  const label = document.createElement("strong");
  label.textContent = `${data.sourceName} · ${data.objects.length.toLocaleString()} records`;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "Remove";
  remove.addEventListener("click", clearAttempt);
  learningEls.selectedAttempt.append(label, remove);
}

function comparePlacedObjects(truthSource, attemptSource) {
  const truth = truthSource.filter(isPlacedObject);
  const attempt = attemptSource.filter(isPlacedObject);
  const truthInventory = inventoryMap(truth);
  const attemptInventory = inventoryMap(attempt);
  const truthIds = new Set(truthInventory.keys());
  const attemptIds = new Set(attemptInventory.keys());
  const sharedIds = [...truthIds].filter((id) => attemptIds.has(id));
  const inventoryMatches = sharedIds.reduce(
    (total, id) => total + Math.min(truthInventory.get(id), attemptInventory.get(id)),
    0
  );

  const truthPlacements = multiset(truth.map(placementSignature));
  const attemptPlacements = multiset(attempt.map(placementSignature));
  let exactPlacements = 0;
  truthPlacements.forEach((count, signature) => {
    exactPlacements += Math.min(count, attemptPlacements.get(signature) || 0);
  });

  const truthAnchors = truth.filter((object) => object.ObjectID === "^U_PARAGON");
  const attemptAnchors = attempt.filter((object) => object.ObjectID === "^U_PARAGON");
  const anchorExact = truthAnchors.length === 1
    && attemptAnchors.length === 1
    && stableStringify(truthAnchors[0]) === stableStringify(attemptAnchors[0]);

  const missingParts = [...truthIds]
    .filter((id) => !attemptIds.has(id))
    .sort();
  const unexpectedParts = [...attemptIds]
    .filter((id) => !truthIds.has(id))
    .sort();

  return {
    truthObjectCount: truth.length,
    attemptObjectCount: attempt.length,
    truthDistinctObjectIds: truthIds.size,
    attemptDistinctObjectIds: attemptIds.size,
    sharedObjectIds: sharedIds.length,
    objectIdRecall: ratio(sharedIds.length, truthIds.size),
    partCountRecall: ratio(inventoryMatches, truth.length),
    partCountPrecision: ratio(inventoryMatches, attempt.length),
    exactTransformMatches: exactPlacements,
    exactTransformRecall: ratio(exactPlacements, truth.length),
    missingObjectIds: missingParts,
    unexpectedObjectIds: unexpectedParts,
    protectedAnchor: {
      groundTruthCount: truthAnchors.length,
      attemptCount: attemptAnchors.length,
      exactRecordMatch: anchorExact
    },
    comparisonPolicy: {
      timestampsIgnoredForPlacementMatch: true,
      transformPrecisionDecimals: 5,
      inventoryMatchUsesMinimumCountPerObjectId: true,
      protectedAnchorRequiresExactFullRecord: true
    }
  };
}

function inventoryMap(objects) {
  const map = new Map();
  objects.forEach((object) => map.set(object.ObjectID, (map.get(object.ObjectID) || 0) + 1));
  return map;
}

function multiset(values) {
  const map = new Map();
  values.forEach((value) => map.set(value, (map.get(value) || 0) + 1));
  return map;
}

function placementSignature(object) {
  return JSON.stringify([
    object.ObjectID,
    normalizeScalar(object.UserData),
    normalizeVector(object.Position),
    normalizeVector(object.Up),
    normalizeVector(object.At)
  ]);
}

function normalizeScalar(value) {
  if (typeof value === "number" && Number.isFinite(value)) return round(value, 5);
  return value ?? null;
}

function normalizeVector(vector) {
  if (!Array.isArray(vector)) return null;
  return vector.slice(0, 3).map((value) => Number.isFinite(value) ? round(value, 5) : null);
}

function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableStringify(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function ratio(numerator, denominator) {
  return denominator ? round(numerator / denominator, 6) : 0;
}

function buildComparisonMessage(comparison) {
  const partRecall = formatPercent(comparison.partCountRecall);
  const transformRecall = formatPercent(comparison.exactTransformRecall);
  const anchor = comparison.protectedAnchor.exactRecordMatch
    ? "The protected ^U_PARAGON record matches exactly."
    : "The protected ^U_PARAGON record does not match exactly, so this attempt cannot enter the trusted collection unchanged.";
  return `Comparison complete: ${partRecall} of the verified part inventory is represented and ${transformRecall} of placements match exactly at five-decimal transform precision. ${anchor}`;
}

function renderComparison() {
  const comparison = learningState.comparison;
  if (!comparison) {
    learningEls.comparisonGrid.hidden = true;
    return;
  }

  learningEls.comparisonGrid.hidden = false;
  learningEls.comparisonGrid.innerHTML = [
    comparisonCard("Part inventory recall", formatPercent(comparison.partCountRecall), `${comparison.sharedObjectIds}/${comparison.truthDistinctObjectIds} Object IDs shared`),
    comparisonCard("Placement match", formatPercent(comparison.exactTransformRecall), `${comparison.exactTransformMatches}/${comparison.truthObjectCount} exact transforms`),
    comparisonCard("Attempt precision", formatPercent(comparison.partCountPrecision), `${comparison.attemptObjectCount} attempted records`),
    comparisonCard(
      "Protected anchor",
      comparison.protectedAnchor.exactRecordMatch ? "Exact" : "Blocked",
      `${comparison.protectedAnchor.attemptCount} attempt anchor record${comparison.protectedAnchor.attemptCount === 1 ? "" : "s"}`,
      comparison.protectedAnchor.exactRecordMatch ? "pass" : "fail"
    )
  ].join("");
}

function comparisonCard(label, value, detail, status = "") {
  return `
    <article class="comparison-card ${status}">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <small>${escapeHtml(detail)}</small>
    </article>
  `;
}

function recordRevision(providedInstruction = null) {
  if (!state.report) {
    showToast("Analyze a build before recording revisions.");
    return null;
  }
  const instruction = String(providedInstruction ?? learningEls.revisionInput.value).trim();
  if (!instruction) {
    showToast("Tell Daedalus what you would like to change.");
    return null;
  }

  const plan = buildRevisionPlan(instruction);
  learningState.revisions.push(plan);
  appendConversation("user", instruction, plan.scopes);
  appendConversation("assistant", revisionAcknowledgement(plan), plan.scopes);
  learningEls.revisionInput.value = "";
  saveSessionDraft();
  renderLearningState();
  showToast("Revision recorded for the next build pass.");
  return plan;
}

function buildRevisionPlan(instruction) {
  const scopes = classifyRevision(instruction);
  const preserveRequested = /\b(preserve|keep|leave|do not change|don't change|unchanged)\b/i.test(instruction);
  return {
    revisionId: makeRecordId("revision"),
    createdAt: new Date().toISOString(),
    instruction,
    scopes,
    preserveRequested,
    mutationPolicy: "CHANGE_IDENTIFIED_SCOPES_ONLY",
    defaultRemainderPolicy: "PRESERVE_UNMENTIONED_GEOMETRY",
    status: "PLANNED_NOT_APPLIED",
    nextPassActions: scopes.map((scope) => revisionAction(scope))
  };
}

function classifyRevision(text) {
  const rules = [
    ["masts and rigging", /\b(mast|rigging|boom|rope|cable|spar)\b/i],
    ["sails", /\b(sails?|canvas|pennants?|flags?)\b/i],
    ["hull", /\b(hull|bow|keel|belly|fuselage)\b/i],
    ["deck and stairs", /\b(deck|stair|walkway|platform|rail)\b/i],
    ["stern and propulsion", /\b(stern|engine|thruster|propulsion|exhaust|pod)\b/i],
    ["interior", /\b(interior|room|cabin|bridge|cockpit|quarters)\b/i],
    ["color and materials", /\b(colou?r|paint|palette|material|metal|wood|red|blue|black|white|cream|orange)\b/i],
    ["lighting", /\b(light|lighting|lamp|glow|emissive|brightness)\b/i],
    ["scale and proportions", /\b(scale|size|taller|shorter|longer|wider|narrower|larger|smaller)\b/i],
    ["symmetry and repetition", /\b(symmetr|mirror|repeat|spacing|pattern|paired)\b/i],
    ["decoration", /\b(decor|ornament|banner|trim|detail)\b/i]
  ];
  const scopes = rules.filter(([, pattern]) => pattern.test(text)).map(([name]) => name);
  return scopes.length ? scopes : ["general construction"];
}

function revisionAction(scope) {
  const actions = {
    "masts and rigging": "Identify mast, boom, rope, cable, and support records before proposing scoped transform or part changes.",
    "sails": "Isolate sail and pennant candidates; preserve mast stations unless the request explicitly changes them.",
    "hull": "Re-evaluate silhouette and structural continuity before changing hull records.",
    "deck and stairs": "Preserve traversable deck relationships while revising platforms, rails, walkways, or stairs.",
    "stern and propulsion": "Maintain bilateral propulsion relationships and verify stern clearance.",
    "interior": "Separate interior-only changes from exterior silhouette and protected ship identity data.",
    "color and materials": "Map requested palette changes to UserData variants without altering geometry.",
    "lighting": "Map lighting requests to light Object IDs, color variants, and repeated placements.",
    "scale and proportions": "Compare requested proportions against the verified build envelope and reference views.",
    "symmetry and repetition": "Apply changes through detected mirrored pairs or repeated motifs when verified.",
    "decoration": "Keep decorative edits independent from load-bearing or silhouette-defining records.",
    "general construction": "Retain the complete request for model-assisted decomposition before any build mutation."
  };
  return actions[scope] || actions["general construction"];
}

function revisionAcknowledgement(plan) {
  const scopeText = plan.scopes.join(", ");
  const preserveText = plan.preserveRequested
    ? "I also recorded your explicit preserve instruction."
    : "Everything you did not mention remains preserved by default.";
  return `Revision captured for ${scopeText}. ${preserveText} This is a structured plan for the next guided build pass; no ship record has been changed yet.`;
}

function appendConversation(role, text, scopes = []) {
  learningState.conversation.push({
    turnId: makeRecordId("turn"),
    createdAt: new Date().toISOString(),
    role,
    text,
    scopes
  });
  renderConversation();
}

function renderConversation() {
  learningEls.conversationLog.innerHTML = "";
  learningState.conversation.forEach((turn) => {
    const message = document.createElement("article");
    message.className = `conversation-message ${turn.role}`;

    const label = document.createElement("span");
    label.textContent = turn.role === "user" ? "Builder" : "Daedalus";
    const body = document.createElement("p");
    body.textContent = turn.text;
    message.append(label, body);

    if (turn.scopes?.length) {
      const tags = document.createElement("div");
      tags.className = "conversation-scopes";
      turn.scopes.forEach((scope) => {
        const tag = document.createElement("span");
        tag.textContent = scope;
        tags.appendChild(tag);
      });
      message.appendChild(tags);
    }
    learningEls.conversationLog.appendChild(message);
  });
  learningEls.conversationLog.scrollTop = learningEls.conversationLog.scrollHeight;
}

function approveGroundTruth() {
  const failures = validateLearningGroundTruth();
  if (failures.length) {
    learningState.teacherNote = learningEls.teacherNote.value.trim() || failures.join(" ");
    renderLearningState();
    showToast(failures[0]);
    return false;
  }

  learningState.groundTruthStatus = "verified";
  learningState.groundTruthVerifiedAt = new Date().toISOString();
  learningState.teacherNote = learningEls.teacherNote.value.trim();
  saveMemorySummary();
  appendConversation(
    "assistant",
    `Ground truth verified independently. ${learningState.attemptStatus === "needs_correction" ? "The generated attempt remains marked Needs correction and will be retained as a labeled error example." : "The generated attempt still has its own separate review status."}`
  );
  renderLearningState();
  showToast("Genuine ground truth verified.");
  return true;
}

function markAttemptCorrect() {
  if (!state.report) {
    showToast("Analyze a build before reviewing the generated attempt.");
    return false;
  }
  learningState.attemptStatus = "correct";
  learningState.attemptReviewedAt = new Date().toISOString();
  learningState.teacherNote = learningEls.teacherNote.value.trim();
  const grounded = Boolean(learningState.attemptFile || learningState.inspectionFile);
  saveMemorySummary();
  appendConversation(
    "assistant",
    `The generated attempt was marked correct. This does not verify the ground-truth source; use Verify ground truth as a separate decision.${grounded ? "" : " Add the attempted build or inspection GLB to ground this assessment in a reviewable artifact."}`
  );
  renderLearningState();
  showToast("Generated attempt marked correct.");
  return true;
}

function markNeedsCorrection() {
  if (!state.report) {
    showToast("Analyze a build before recording feedback.");
    return false;
  }
  learningState.attemptStatus = "needs_correction";
  learningState.attemptReviewedAt = new Date().toISOString();
  learningState.teacherNote = learningEls.teacherNote.value.trim() || "Builder marked the generated attempt as needing correction.";
  const grounded = Boolean(learningState.attemptFile || learningState.inspectionFile);
  saveMemorySummary();
  appendConversation(
    "assistant",
    `The generated attempt was marked Needs correction. The genuine ground truth remains a separate decision and can still be verified.${grounded ? "" : " Add the attempted build or inspection GLB to make the correction directly trainable."}`
  );
  renderLearningState();
  showToast("Generated attempt marked Needs correction.");
  return true;
}

function validateLearningGroundTruth() {
  const failures = [];
  if (!state.report || !state.packageData?.objects?.length) {
    failures.push("A verified analyzed build is required.");
    return failures;
  }
  if (state.report.build.checks.some((check) => check.status === "fail")) {
    failures.push("Resolve failed reverse-blueprint safety checks before approval.");
  }
  if (state.mode === "corvette") {
    const anchors = state.packageData.objects.filter((object) => object?.ObjectID === "^U_PARAGON");
    if (anchors.length !== 1) failures.push("A Corvette ground truth must contain exactly one ^U_PARAGON anchor.");
    if (state.packageData.format === "nmsship") {
      const entries = state.packageData.entries.map((name) => name.toLowerCase());
      if (!entries.some((name) => /(^|\/)objects\.json$/.test(name))) failures.push("objects.json is missing.");
      if (!entries.some((name) => /(^|\/)so\.json$/.test(name))) failures.push("so.json is missing.");
      if (!entries.some((name) => /(^|\/)ccd\.json$/.test(name))) failures.push("ccd.json is missing.");
    }
  } else if (state.packageData.format === "nmsbase") {
    const flags = state.packageData.directObjects.filter((object) => object?.ObjectID === "^BASE_FLAG");
    if (flags.length !== 1) failures.push("An NMSBASE ground truth must contain exactly one ^BASE_FLAG record.");
  }
  if (state.mode === "base" && state.packageData.prefabInstances?.length) {
    if (!state.prefabDefinitionFiles?.length) {
      failures.push("A named prefab wrapper requires its matching .nmsprefab definition before it can become verified geometry.");
    }
    if (state.packageData.prefabResolution?.unresolved?.length) {
      failures.push("Every named prefab instance must resolve to an explicitly supplied .nmsprefab definition.");
    }
  }
  return failures;
}

async function buildLearningRecord() {
  if (!state.report || !state.packageFile) throw new Error("Analyze a verified build first.");
  const groundTruthHash = await sha256File(state.packageFile);
  const prefabDefinitionEvidence = await Promise.all((state.prefabDefinitionFiles || []).map(async (file) => {
    const definition = state.prefabDefinitions.find((item) => item.sourceName === file.name);
    return {
      fileName: file.name,
      format: definition?.format || "nmsprefab",
      sizeBytes: file.size,
      sha256: await sha256File(file),
      objectCount: definition?.objects?.length || 0,
      definitionNames: definition?.definitionNames || [file.name]
    };
  }));
  const referenceEvidence = await Promise.all(state.images.map(async (item, index) => ({
    ordinal: index + 1,
    fileName: item.file.name,
    sizeBytes: item.file.size,
    mimeType: item.file.type || null,
    sha256: await sha256File(item.file),
    primary: index === state.primaryImageIndex
  })));
  const attempt = learningState.attemptFile
    ? {
        fileName: learningState.attemptFile.name,
        format: learningState.attemptData.format,
        sizeBytes: learningState.attemptFile.size,
        sha256: await sha256File(learningState.attemptFile),
        comparison: learningState.comparison
      }
    : null;
  const inspection = learningState.inspectionFile
    ? {
        fileName: learningState.inspectionFile.name,
        format: "glb",
        sizeBytes: learningState.inspectionFile.size,
        sha256: await sha256File(learningState.inspectionFile),
        modelSummary: learningState.inspectionSummary,
        partFeedback: learningState.partFeedback,
        viewerCapabilities: [
          "ORBIT_ROTATION",
          "WHEEL_AND_PINCH_ZOOM",
          "PAN",
          "CLICK_MESH_IDENTIFICATION",
          "WIREFRAME",
          "PNG_CAPTURE"
        ]
      }
    : null;
  const validation = validateLearningGroundTruth();
  const attemptEvidencePresent = Boolean(attempt || inspection || learningState.generatedSign);
  const notePresent = Boolean(learningEls.teacherNote.value.trim() || learningState.teacherNote);
  const trust = deriveTrainingTrust({
    groundTruthStatus: learningState.groundTruthStatus,
    attemptStatus: learningState.attemptStatus,
    validationFailures: validation,
    attemptEvidencePresent,
    notePresent,
    partFeedbackCount: learningState.partFeedback.length
  });

  return {
    schema: "wonder-codex.daedalus.learning-record.v0.3",
    recordId: learningState.recordId || makeRecordId(),
    createdAt: new Date().toISOString(),
    domain: {
      allowed: ["NO_MANS_SKY_CORVETTE_BUILDING", "NO_MANS_SKY_BASE_BUILDING"],
      current: state.mode === "corvette" ? "NO_MANS_SKY_CORVETTE_BUILDING" : "NO_MANS_SKY_BASE_BUILDING",
      rejectOutsideDomainExamples: true
    },
    designIntent: {
      originalRequest: learningEls.prompt.value.trim() || null,
      styleTags: parseTags(learningEls.tags.value),
      recognizedCategory: state.buildCategory,
      signSpecification: state.report.designIntent?.signSpecification || null
    },
    groundTruth: {
      fileName: state.packageFile.name,
      format: state.packageData.format,
      sizeBytes: state.packageFile.size,
      sha256: groundTruthHash,
      packageEntries: state.packageData.entries,
      sourceKind: state.packageData.sourceKind,
      geometryStatus: state.packageData.geometryStatus,
      prefabInstances: state.packageData.prefabInstances || [],
      prefabDefinitions: prefabDefinitionEvidence,
      objectCount: state.report.build.objectCount,
      sourceRecordCount: state.report.build.sourceRecordCount,
      distinctObjectIds: state.report.build.distinctObjectIds,
      bounds: state.report.build.bounds,
      partInventory: state.report.build.parts.map((part) => ({
        objectId: part.objectId,
        count: part.count,
        userData: part.userData
      })),
      protectedAnchor: state.mode === "corvette" ? summarizeProtectedAnchor(state.packageData.objects) : null,
      reverseBlueprint: state.report
    },
    referenceEvidence,
    attemptedBuild: attempt,
    generatedSign: learningState.generatedSign?.manifest || null,
    interactiveInspection: inspection,
    conversationalRevisions: learningState.revisions,
    conversation: learningState.conversation,
    teacherFeedback: {
      groundTruth: {
        status: learningState.groundTruthStatus,
        verifiedAt: learningState.groundTruthVerifiedAt
      },
      generatedAttempt: {
        status: learningState.attemptStatus,
        reviewedAt: learningState.attemptReviewedAt,
        evidencePresent: attemptEvidencePresent
      },
      note: learningEls.teacherNote.value.trim() || learningState.teacherNote || null,
      partFeedback: learningState.partFeedback
    },
    trust,
    safety: {
      readOnlyAnalysis: true,
      sourceModified: false,
      saveAccessed: false,
      packageMutationPerformed: false,
      protectedObjectIds: state.mode === "corvette"
        ? ["^U_PARAGON"]
        : (state.packageData.format === "nmsbase" ? ["^BASE_FLAG"] : []),
      protectedObjectPolicy: state.mode === "corvette"
        ? "COPY_SOURCE_RECORD_UNCHANGED_NEVER_INFER_FROM_IMAGES"
        : (state.packageData.format === "nmsbase"
          ? "COPY_BASE_FLAG_SOURCE_RECORD_UNCHANGED_AND_USE_OBJECTID_ONLY_GEOMETRY"
          : "OBJECTID_ONLY_BASE_GEOMETRY_REQUIRE_VERIFIED_PREFAB_DEFINITION")
    }
  };
}

function deriveTrainingTrust({
  groundTruthStatus,
  attemptStatus,
  validationFailures,
  attemptEvidencePresent,
  notePresent,
  partFeedbackCount
}) {
  const groundTruthEligible = groundTruthStatus === "verified" && validationFailures.length === 0;
  const attemptAssessmentEligible = groundTruthEligible
    && attemptEvidencePresent
    && (
      attemptStatus === "correct"
      || (attemptStatus === "needs_correction" && notePresent)
    );
  let collection = "QUARANTINED_UNVERIFIED_GROUND_TRUTH";
  if (groundTruthEligible && attemptStatus === "needs_correction" && attemptAssessmentEligible) {
    collection = "TRUSTED_SUPERVISED_CORRECTION";
  } else if (groundTruthEligible && attemptStatus === "correct" && attemptAssessmentEligible) {
    collection = "TRUSTED_MATCHED_PAIR";
  } else if (groundTruthEligible && attemptStatus === "needs_correction") {
    collection = "TRUSTED_GROUND_TRUTH_ATTEMPT_FEEDBACK_QUARANTINED";
  } else if (groundTruthEligible) {
    collection = "TRUSTED_GROUND_TRUTH";
  }
  return {
    eligibleForTraining: groundTruthEligible,
    approvalRequired: groundTruthStatus !== "verified",
    validationFailures,
    collection,
    trainingComponents: {
      groundTruth: groundTruthEligible,
      generatedAttemptAssessment: attemptAssessmentEligible,
      partLevelInspectionFeedback: groundTruthEligible && attemptEvidencePresent && partFeedbackCount > 0
    },
    policy: "VERIFY_GROUND_TRUTH_AND_LABEL_GENERATED_ATTEMPT_INDEPENDENTLY"
  };
}

function summarizeProtectedAnchor(objects) {
  const anchors = objects.filter((object) => object?.ObjectID === "^U_PARAGON");
  return {
    objectId: "^U_PARAGON",
    count: anchors.length,
    exactSourceRecordRequired: true,
    inferredFromImages: false
  };
}

async function createLearningPackage() {
  if (!state.report || !state.packageFile) {
    throw new Error("Analyze a verified build before creating a learning package.");
  }
  if (!window.JSZip) throw new Error("The local ZIP writer did not load.");

  const record = await buildLearningRecord();
  const zip = new JSZip();
  const sourceName = safeArchiveName(state.packageFile.name);
  zip.file("learning-record.json", JSON.stringify(record, null, 2));
  zip.file("ground-truth/reverse-blueprint.json", JSON.stringify(state.report, null, 2));
  zip.file(`ground-truth/${sourceName}`, await state.packageFile.arrayBuffer());
  for (const file of state.prefabDefinitionFiles || []) {
    zip.file(`ground-truth/prefab-definitions/${safeArchiveName(file.name)}`, await file.arrayBuffer());
  }
  if (learningState.generatedSign) {
    zip.file("generated/sign-attempt.nmsprefab", JSON.stringify(learningState.generatedSign.prefab, null, 4));
    zip.file("generated/sign-generation-manifest.json", JSON.stringify(learningState.generatedSign.manifest, null, 2));
  }

  for (let index = 0; index < state.images.length; index += 1) {
    const item = state.images[index];
    const fileName = `${String(index + 1).padStart(2, "0")}-${safeArchiveName(item.file.name)}`;
    zip.file(`references/${fileName}`, await item.file.arrayBuffer());
  }

  if (learningState.attemptFile) {
    zip.file(
      `attempt/${safeArchiveName(learningState.attemptFile.name)}`,
      await learningState.attemptFile.arrayBuffer()
    );
    zip.file("attempt/comparison.json", JSON.stringify(learningState.comparison, null, 2));
  }
  if (learningState.inspectionFile) {
    zip.file(
      `inspection/${safeArchiveName(learningState.inspectionFile.name)}`,
      await learningState.inspectionFile.arrayBuffer()
    );
    zip.file("inspection/part-feedback.json", JSON.stringify({
      modelSummary: learningState.inspectionSummary,
      selections: learningState.partFeedback
    }, null, 2));
  }

  zip.file("START-HERE.txt", learningPackageReadme(record));
  const blob = await zip.generateAsync({
    type: "blob",
    compression: "DEFLATE",
    compressionOptions: { level: 6 }
  });
  const buildName = safeFileName(state.report.build.name || "daedalus-build");
  return {blob, record, fileName: `${buildName}-daedalus-learning-v0.3.zip`};
}

async function exportLearningPackage() {
  const priorText = learningEls.exportButton.textContent;
  learningEls.exportButton.disabled = true;
  learningEls.exportButton.textContent = "Packaging learning record…";

  try {
    const packageData = await createLearningPackage();
    downloadBlob(packageData.blob, packageData.fileName);
    if (packageData.record.trust.eligibleForTraining) saveMemorySummary();
    showToast(packageData.record.trust.eligibleForTraining
      ? "Trusted learning package exported."
      : "Candidate package exported; approval is still required.");
  } catch (error) {
    showToast(error.message || "The learning package could not be created.");
  } finally {
    learningEls.exportButton.disabled = !state.report;
    learningEls.exportButton.textContent = priorText;
  }
}

async function submitLearningForReview() {
  if (learningState.groundTruthStatus !== "verified") {
    showToast("Verify the ground truth first, then save the session for independent admin review.");
    return null;
  }
  if (!window.DaedalusShared?.submitLearningBlob) {
    showToast("The shared review queue is not connected. Export the learning ZIP as a fallback.");
    return null;
  }

  const priorText = learningEls.submitReviewButton.textContent;
  learningEls.submitReviewButton.disabled = true;
  learningEls.submitReviewButton.textContent = "Saving to review queue…";
  try {
    const packageData = await createLearningPackage();
    const note = learningEls.teacherNote.value.trim()
      || learningState.teacherNote
      || "Submitted directly from a verified Daedalus learning session.";
    const response = await window.DaedalusShared.submitLearningBlob(packageData.blob, packageData.fileName, note);
    saveMemorySummary();
    showToast("Learning session saved for admin review. It cannot teach Daedalus until it is approved and released.");
    return response;
  } catch (error) {
    showToast(error.message || "The learning session could not be submitted for review.");
  } finally {
    learningEls.submitReviewButton.disabled = !state.report;
    learningEls.submitReviewButton.textContent = priorText;
  }
}

function learningPackageReadme(record) {
  return [
    "DAEDALUS LEARNING PACKAGE v0.3",
    "",
    `Record: ${record.recordId}`,
    `Build: ${state.report.build.name}`,
    `Domain: ${record.domain.current}`,
    `Ground truth: ${record.groundTruth.fileName}`,
    `Prefab definitions: ${record.groundTruth.prefabDefinitions.length}`,
    `References: ${record.referenceEvidence.length}`,
    `Attempt included: ${record.attemptedBuild ? "yes" : "no"}`,
    `Interactive inspection included: ${record.interactiveInspection ? "yes" : "no"}`,
    `Ground truth status: ${record.teacherFeedback.groundTruth.status}`,
    `Generated attempt status: ${record.teacherFeedback.generatedAttempt.status}`,
    `Eligible for trusted training: ${record.trust.eligibleForTraining ? "yes" : "no"}`,
    "",
    "POLICY",
    "Ground-truth verification and generated-attempt quality are independent.",
    "Verified ground truth may enter the trusted collection while an incorrect",
    "attempt remains explicitly labeled as a supervised correction example.",
    "",
    "SAFETY",
    "This package was produced in browser memory. No NMS save was accessed.",
    "The original source was not modified. Named base prefabs require matching definitions.",
    "^U_PARAGON protection applies only to Corvette records and is never inferred from images."
  ].join("\r\n");
}

async function sha256File(file) {
  if (!globalThis.crypto?.subtle) return "unavailable-in-this-browser";
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function parseTags(value) {
  return [...new Set(value.split(",").map((tag) => tag.trim()).filter(Boolean))];
}

function saveSessionDraft() {
  if (!state.report) return;
  const sessions = readLocalArray(LEARNING_SESSION_KEY);
  const draft = {
    recordId: learningState.recordId,
    buildName: state.report.build.name,
    sourceFileName: state.packageData?.sourceName,
    updatedAt: new Date().toISOString(),
    groundTruthStatus: learningState.groundTruthStatus,
    attemptStatus: learningState.attemptStatus,
    attemptFileName: learningState.attemptFile?.name || null,
    inspectionFileName: learningState.inspectionFile?.name || null,
    partFeedback: learningState.partFeedback,
    revisionCount: learningState.revisions.length,
    conversation: learningState.conversation,
    revisions: learningState.revisions
  };
  upsertLocalArray(LEARNING_SESSION_KEY, sessions, draft, 50);
}

function saveMemorySummary() {
  if (!state.report) return;
  const records = readLocalArray(LEARNING_MEMORY_KEY);
  const summary = {
    recordId: learningState.recordId,
    buildName: state.report.build.name,
    domain: state.mode,
    sourceFileName: state.packageData?.sourceName,
    groundTruthStatus: learningState.groundTruthStatus,
    attemptStatus: learningState.attemptStatus,
    eligibleForTraining: learningState.groundTruthStatus === "verified" && validateLearningGroundTruth().length === 0,
    groundTruthVerifiedAt: learningState.groundTruthVerifiedAt,
    attemptReviewedAt: learningState.attemptReviewedAt,
    updatedAt: new Date().toISOString(),
    referenceCount: state.images.length,
    attemptFileName: learningState.attemptFile?.name || null,
    inspectionFileName: learningState.inspectionFile?.name || null,
    partFeedbackCount: learningState.partFeedback.length,
    styleTags: parseTags(learningEls.tags.value),
    topParts: state.report.build.parts.slice(0, 12).map((part) => ({
      objectId: part.objectId,
      count: part.count
    })),
    teacherNote: learningEls.teacherNote.value.trim() || learningState.teacherNote || null
  };
  upsertLocalArray(LEARNING_MEMORY_KEY, records, summary, 250);
}

function readLocalArray(key) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function upsertLocalArray(key, records, next, limit) {
  try {
    const updated = [next, ...records.filter((record) => record.recordId !== next.recordId)].slice(0, limit);
    localStorage.setItem(key, JSON.stringify(updated));
  } catch {
    showToast("Browser memory is unavailable; export the learning package to keep this record.");
  }
}

function renderLearningState() {
  const memories = readLocalArray(LEARNING_MEMORY_KEY);
  const approvedCount = memories.filter((record) => record.eligibleForTraining).length;
  learningEls.memoryMetric.textContent = `${approvedCount.toLocaleString()} verified`;
  learningEls.truthMetric.textContent = state.report
    ? `${state.report.build.objectCount.toLocaleString()} records`
    : "Analyze first";
  learningEls.referenceMetric.textContent = `${state.images.length.toLocaleString()} view${state.images.length === 1 ? "" : "s"}`;
  learningEls.comparisonMetric.textContent = learningState.comparison
    ? `${formatPercent(learningState.comparison.partCountRecall)} recall`
    : learningState.inspectionSummary
      ? `${learningState.inspectionSummary.meshCount.toLocaleString()} meshes`
      : "Optional";

  const groundTruthLabels = {
    unverified: "Ground truth · unverified",
    verified: "Ground truth · verified"
  };
  const attemptLabels = {
    not_reviewed: "Attempt · not reviewed",
    correct: "Attempt · looks correct",
    needs_correction: "Attempt · needs correction"
  };
  learningEls.groundTruthStatus.textContent = groundTruthLabels[learningState.groundTruthStatus];
  learningEls.groundTruthStatus.className = `learning-status ${learningState.groundTruthStatus}`;
  learningEls.attemptStatus.textContent = attemptLabels[learningState.attemptStatus];
  learningEls.attemptStatus.className = `learning-status ${learningState.attemptStatus}`;
  learningEls.approveButton.disabled = !state.report;
  learningEls.attemptCorrectButton.disabled = !state.report;
  learningEls.needsCorrectionButton.disabled = !state.report;
  learningEls.exportButton.disabled = !state.report;
  learningEls.submitReviewButton.disabled = !state.report;
  renderConversation();
  renderComparison();
}

function formatPercent(value) {
  return `${(value * 100).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
}

function makeRecordId(prefix = "record") {
  const token = globalThis.crypto?.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `daedalus-${prefix}-${token}`;
}

window.DaedalusLearning = {
  onAnalysisReady: onLearningAnalysisReady,
  onSourceChanged: onLearningSourceChanged,
  onEvidenceChanged: onLearningEvidenceChanged,
  onDesignIntentChanged,
  onGeneratedSign,
  comparePlacedObjects,
  classifyRevision,
  buildRevisionPlan,
  deriveTrainingTrust,
  addRevision: recordRevision,
  approveGroundTruth,
  loadAttempt,
  markAttemptCorrect,
  markNeedsCorrection,
  submitForReview: submitLearningForReview,
  setTeacherNote(note) {
    learningEls.teacherNote.value = String(note || "");
    learningState.teacherNote = learningEls.teacherNote.value.trim();
  },
  getSnapshot() {
    return {
      recordId: learningState.recordId,
      groundTruthStatus: learningState.groundTruthStatus,
      attemptStatus: learningState.attemptStatus,
      revisions: [...learningState.revisions],
      attemptFile: learningState.attemptFile,
      attemptGeometry: learningState.attemptData
        ? {sourceName: learningState.attemptData.sourceName, objects: learningState.attemptData.objects}
        : null
    };
  }
};

initLearningLab();
