"use strict";

const state = {
  mode: "corvette",
  buildCategory: "other",
  images: [],
  primaryImageIndex: 0,
  paletteCrop: { x: 0.08, y: 0.12, width: 0.84, height: 0.8 },
  packageFile: null,
  packageData: null,
  prefabDefinitions: [],
  prefabDefinitionFiles: [],
  report: null,
  palette: []
};

const cropState = {
  image: null,
  selection: null,
  dragging: false,
  start: null
};

const els = {
  steps: [...document.querySelectorAll(".step")],
  modeCards: [...document.querySelectorAll(".mode-card")],
  imageInput: document.querySelector("#imageInput"),
  blueprintInput: document.querySelector("#blueprintInput"),
  buildBrief: document.querySelector("#buildBrief"),
  buildCategory: document.querySelector("#buildCategory"),
  recognizedIntent: document.querySelector("#recognizedIntent"),
  signStudio: document.querySelector("#signStudio"),
  signText: document.querySelector("#signText"),
  signFont: document.querySelector("#signFont"),
  signBackdropColor: document.querySelector("#signBackdropColor"),
  signLetterColor: document.querySelector("#signLetterColor"),
  signReadiness: document.querySelector("#signReadiness"),
  generateSignButton: document.querySelector("#generateSignButton"),
  prefabResolver: document.querySelector("#prefabResolver"),
  prefabResolverMessage: document.querySelector("#prefabResolverMessage"),
  prefabDefinitionInput: document.querySelector("#prefabDefinitionInput"),
  prefabResolutionList: document.querySelector("#prefabResolutionList"),
  imageDropZone: document.querySelector("#imageDropZone"),
  blueprintDropZone: document.querySelector("#blueprintDropZone"),
  imageGallery: document.querySelector("#imageGallery"),
  imageCounter: document.querySelector("#imageCounter"),
  previewStage: document.querySelector("#previewStage"),
  primaryPreview: document.querySelector("#primaryPreview"),
  paletteSection: document.querySelector("#paletteSection"),
  paletteRow: document.querySelector("#paletteRow"),
  paletteCropButton: document.querySelector("#paletteCropButton"),
  paletteDialog: document.querySelector("#paletteDialog"),
  paletteCanvas: document.querySelector("#paletteCanvas"),
  fullImagePaletteButton: document.querySelector("#fullImagePaletteButton"),
  savePaletteCropButton: document.querySelector("#savePaletteCropButton"),
  selectedPackage: document.querySelector("#selectedPackage"),
  analyzeButton: document.querySelector("#analyzeButton"),
  buttonGuidance: document.querySelector("#buttonGuidance"),
  results: document.querySelector("#results"),
  resultTitle: document.querySelector("#resultTitle"),
  resultSubtitle: document.querySelector("#resultSubtitle"),
  objectMetric: document.querySelector("#objectMetric"),
  partMetric: document.querySelector("#partMetric"),
  motifMetric: document.querySelector("#motifMetric"),
  checkMetric: document.querySelector("#checkMetric"),
  insightList: document.querySelector("#insightList"),
  envelopeCard: document.querySelector("#envelopeCard"),
  miniParts: document.querySelector("#miniParts"),
  recipeList: document.querySelector("#recipeList"),
  partsTableBody: document.querySelector("#partsTableBody"),
  partSearch: document.querySelector("#partSearch"),
  checkList: document.querySelector("#checkList"),
  exportButton: document.querySelector("#exportButton"),
  bridgeJobButton: document.querySelector("#bridgeJobButton"),
  copySummaryButton: document.querySelector("#copySummaryButton"),
  helpButton: document.querySelector("#helpButton"),
  helpDialog: document.querySelector("#helpDialog"),
  toast: document.querySelector("#toast"),
  tabs: [...document.querySelectorAll(".tab")],
  tabPanels: [...document.querySelectorAll(".tab-panel")]
};

function init() {
  els.modeCards.forEach((card) => {
    card.addEventListener("click", () => setMode(card.dataset.mode));
  });

  els.imageInput.addEventListener("change", (event) => addImages([...event.target.files]));
  els.blueprintInput.addEventListener("change", (event) => {
    if (event.target.files[0]) loadPackage(event.target.files[0]);
  });
  els.buildBrief.addEventListener("input", handleBuildBrief);
  els.buildCategory.addEventListener("change", () => {
    state.buildCategory = els.buildCategory.value;
    renderIntentControls();
  });
  [els.signText, els.signFont, els.signBackdropColor, els.signLetterColor].forEach((element) => {
    element.addEventListener("input", syncDesignIntentToLearning);
  });
  els.generateSignButton.addEventListener("click", generateSignPrefabDownload);
  els.prefabDefinitionInput.addEventListener("change", (event) => {
    if (event.target.files.length) loadPrefabDefinitions([...event.target.files]);
  });

  setupDropZone(els.imageDropZone, (files) => addImages(files));
  setupDropZone(els.blueprintDropZone, (files) => {
    const file = files.find(isBuildFile);
    if (file) loadPackage(file);
    else showToast("Choose a .nmsship, .nmsprefab, .NMSBASE, or JSON file.");
  });

  els.analyzeButton.addEventListener("click", runAnalysis);
  els.exportButton.addEventListener("click", exportReport);
  els.bridgeJobButton.addEventListener("click", exportBridgeJob);
  els.copySummaryButton.addEventListener("click", copySummary);
  els.partSearch.addEventListener("input", () => renderPartsTable(els.partSearch.value));
  els.helpButton.addEventListener("click", () => els.helpDialog.showModal());
  els.paletteCropButton.addEventListener("click", openPaletteDialog);
  els.fullImagePaletteButton.addEventListener("click", useFullImagePalette);
  els.savePaletteCropButton.addEventListener("click", savePaletteCrop);
  els.paletteCanvas.addEventListener("pointerdown", startCropSelection);
  els.paletteCanvas.addEventListener("pointermove", updateCropSelection);
  els.paletteCanvas.addEventListener("pointerup", endCropSelection);
  els.paletteCanvas.addEventListener("pointercancel", endCropSelection);

  els.tabs.forEach((tab) => tab.addEventListener("click", () => selectTab(tab.dataset.tab)));
  renderIntentControls();
  setStepper(1);
}

function setMode(mode) {
  state.mode = mode;
  els.modeCards.forEach((card) => {
    const selected = card.dataset.mode === mode;
    card.classList.toggle("selected", selected);
    card.setAttribute("aria-checked", String(selected));
  });
  document.querySelector("#packageHint").textContent = mode === "corvette"
    ? "The ship package is read in memory; identity and inventory data remain untouched."
    : "The .NMSBASE, prefab, or base JSON is read in memory and left untouched.";
  const allowed = mode === "base"
    ? window.DaedalusBaseWorkflow.BASE_TYPES
    : window.DaedalusBaseWorkflow.CORVETTE_STYLES;
  if (!allowed.includes(state.buildCategory)) state.buildCategory = "other";
  renderIntentControls();
  if (state.packageData) updateReadyState();
}

function handleBuildBrief() {
  const recognized = window.DaedalusBaseWorkflow.classifyBuildIntent(els.buildBrief.value, state.mode);
  if (recognized.mode !== state.mode) setMode(recognized.mode);
  state.buildCategory = recognized.category;
  renderIntentControls(recognized.confidence);
  syncDesignIntentToLearning();
}

function renderIntentControls(confidence = null) {
  const options = state.mode === "base"
    ? window.DaedalusBaseWorkflow.BASE_TYPES
    : window.DaedalusBaseWorkflow.CORVETTE_STYLES;
  const current = options.includes(state.buildCategory) ? state.buildCategory : "other";
  els.buildCategory.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = titleCase(value);
    option.selected = value === current;
    els.buildCategory.appendChild(option);
  });
  state.buildCategory = current;
  const modeLabel = state.mode === "base" ? "Base" : "Corvette";
  els.recognizedIntent.textContent = `${modeLabel} · ${titleCase(current)}${confidence === "low" ? " · review" : ""}`;
  els.signStudio.hidden = !(state.mode === "base" && current === "sign");
  syncSignReadiness();
}

function titleCase(value) {
  return String(value).replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getSignSpecification() {
  if (state.mode !== "base" || state.buildCategory !== "sign") return null;
  return window.DaedalusBaseWorkflow.createSignSpecification({
    text: els.signText.value,
    fontGrammar: els.signFont.value,
    backdropColor: els.signBackdropColor.value,
    letteringColor: els.signLetterColor.value,
    geometryReadiness: "VERIFIED_FFC_CALIBRATION_GENERATION_READY"
  });
}

function generateSignPrefabDownload() {
  const text = els.signText.value.trim();
  if (!text) {
    showToast("Enter the lettering for the sign first.");
    return;
  }
  const result = window.DaedalusSignGenerator.generateSignPrefab({
    text,
    fontGrammar: els.signFont.value,
    backdropUserData: 1,
    letterUserData: 8
  });
  const blob = new Blob([JSON.stringify(result.prefab, null, 4)], { type: "application/json" });
  downloadBlob(blob, `${safeDisplayFileName(text)}.nmsprefab`);
  els.signReadiness.textContent = `${result.manifest.placedObjectCount.toLocaleString()} ObjectID records generated: ${result.manifest.backdropCount} black wall parts and ${result.manifest.letteringCount} red lettering parts · in-game review required.`;
  els.signReadiness.classList.add("ready");
  window.DaedalusLearning?.onGeneratedSign?.(result);
  showToast(`${text} sign prefab generated.`);
}

function safeDisplayFileName(value) {
  return String(value)
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    || "Daedalus Sign";
}

function syncDesignIntentToLearning() {
  window.DaedalusLearning?.onDesignIntentChanged?.({
    originalRequest: els.buildBrief.value.trim(),
    category: state.buildCategory,
    signSpecification: getSignSpecification()
  });
}

function syncSignReadiness() {
  if (!els.signReadiness) return;
  els.signReadiness.textContent = state.packageData?.objects?.length
    ? `Verified source loaded · ${state.packageData.objects.length.toLocaleString()} ObjectID records available alongside the built-in FFC calibration.`
    : "Verified FFC calibration loaded · generated geometry will be labeled for in-game review.";
  els.signReadiness.classList.add("ready");
}

function setStepper(activeStep) {
  els.steps.forEach((step, index) => {
    const stepNumber = index + 1;
    step.classList.toggle("active", stepNumber === activeStep);
    step.classList.toggle("completed", stepNumber < activeStep);
  });
}

function setupDropZone(element, callback) {
  ["dragenter", "dragover"].forEach((name) => {
    element.addEventListener(name, (event) => {
      event.preventDefault();
      element.classList.add("dragging");
    });
  });
  ["dragleave", "drop"].forEach((name) => {
    element.addEventListener(name, (event) => {
      event.preventDefault();
      element.classList.remove("dragging");
    });
  });
  element.addEventListener("drop", (event) => callback([...event.dataTransfer.files]));
}

function isBuildFile(file) {
  return /\.(nmsship|nmsprefab|nmsbase|json)$/i.test(file.name);
}

function isPreviewableImage(file) {
  return /\.(png|jpe?g|webp)$/i.test(file.name);
}

function addImages(files) {
  const supported = files.filter((file) => /\.(png|jpe?g|webp|jxr)$/i.test(file.name));
  if (!supported.length) {
    showToast("No supported reference images were found.");
    return;
  }

  const remaining = Math.max(0, 12 - state.images.length);
  supported.slice(0, remaining).forEach((file) => {
    state.images.push({
      file,
      url: isPreviewableImage(file) ? URL.createObjectURL(file) : null
    });
  });

  if (supported.length > remaining) showToast("Daedalus keeps up to 12 reference images per analysis.");
  renderImages();
  analyzePrimaryPalette();
  setStepper(state.packageData ? 3 : 2);
  window.DaedalusLearning?.onEvidenceChanged?.();
}

function removeImage(index) {
  const removed = state.images.splice(index, 1)[0];
  if (removed?.url) URL.revokeObjectURL(removed.url);
  state.primaryImageIndex = Math.min(state.primaryImageIndex, Math.max(0, state.images.length - 1));
  renderImages();
  setStepper(state.packageData ? 3 : state.images.length ? 2 : 1);
  window.DaedalusLearning?.onEvidenceChanged?.();
}

function renderImages() {
  els.imageGallery.innerHTML = "";
  state.images.forEach((image, index) => {
    const thumb = document.createElement("div");
    thumb.className = "file-thumb";
    thumb.title = image.file.name;

    if (image.url) {
      const img = document.createElement("img");
      img.src = image.url;
      img.alt = image.file.name;
      thumb.appendChild(img);
      thumb.addEventListener("click", () => setPrimaryImage(index));
    } else {
      const placeholder = document.createElement("div");
      placeholder.className = "jxr-placeholder";
      placeholder.textContent = "JXR · recorded";
      thumb.appendChild(placeholder);
    }

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${image.file.name}`);
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      removeImage(index);
    });
    thumb.appendChild(remove);
    els.imageGallery.appendChild(thumb);
  });

  els.imageCounter.textContent = `${state.images.length} image${state.images.length === 1 ? "" : "s"}`;
  const firstPreviewable = state.images.findIndex((item) => item.url);
  setPrimaryImage(firstPreviewable >= 0 ? firstPreviewable : 0, false);
}

function setPrimaryImage(index, resetCrop = true) {
  const image = state.images[index];
  if (!image?.url) {
    const firstPreviewableIndex = state.images.findIndex((item) => item.url);
    const firstPreviewable = state.images[firstPreviewableIndex];
    if (!firstPreviewable) {
      els.primaryPreview.hidden = true;
      els.previewStage.classList.add("empty");
      document.querySelector(".empty-preview").hidden = false;
      return;
    }
    state.primaryImageIndex = firstPreviewableIndex;
    els.primaryPreview.src = firstPreviewable.url;
  } else {
    state.primaryImageIndex = index;
    els.primaryPreview.src = image.url;
  }

  if (resetCrop) state.paletteCrop = { x: 0.08, y: 0.12, width: 0.84, height: 0.8 };
  els.primaryPreview.hidden = false;
  els.previewStage.classList.remove("empty");
  document.querySelector(".empty-preview").hidden = true;
  analyzePrimaryPalette();
}

async function analyzePrimaryPalette() {
  const primary = state.images[state.primaryImageIndex]?.url
    ? state.images[state.primaryImageIndex]
    : state.images.find((item) => item.url);
  if (!primary) {
    state.palette = [];
    els.paletteSection.hidden = true;
    return;
  }

  try {
    state.palette = await extractPalette(primary.url, state.paletteCrop);
    els.paletteRow.innerHTML = "";
    state.palette.forEach((color) => {
      const chip = document.createElement("div");
      chip.className = "palette-chip";
      chip.style.background = color.hex;
      chip.title = `${color.hex} · ${color.percent}% sampled pixels`;
      const label = document.createElement("span");
      label.textContent = color.hex;
      chip.appendChild(label);
      els.paletteRow.appendChild(chip);
    });
    els.paletteSection.hidden = !state.palette.length;
  } catch {
    state.palette = [];
    els.paletteSection.hidden = true;
  }
}

function extractPalette(url, crop = null) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const maxSide = 220;
      const source = crop || { x: 0, y: 0, width: 1, height: 1 };
      const sourceWidth = Math.max(1, img.naturalWidth * source.width);
      const sourceHeight = Math.max(1, img.naturalHeight * source.height);
      const scale = Math.min(1, maxSide / Math.max(sourceWidth, sourceHeight));
      canvas.width = Math.max(1, Math.round(sourceWidth * scale));
      canvas.height = Math.max(1, Math.round(sourceHeight * scale));
      const context = canvas.getContext("2d", { willReadFrequently: true });
      context.drawImage(
        img,
        img.naturalWidth * source.x,
        img.naturalHeight * source.y,
        sourceWidth,
        sourceHeight,
        0,
        0,
        canvas.width,
        canvas.height
      );
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      const buckets = new Map();
      let total = 0;

      for (let index = 0; index < pixels.length; index += 16) {
        if (pixels[index + 3] < 200) continue;
        const r = Math.min(255, Math.round(pixels[index] / 32) * 32);
        const g = Math.min(255, Math.round(pixels[index + 1] / 32) * 32);
        const b = Math.min(255, Math.round(pixels[index + 2] / 32) * 32);
        const key = `${r},${g},${b}`;
        buckets.set(key, (buckets.get(key) || 0) + 1);
        total += 1;
      }

      const palette = [...buckets.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 6)
        .map(([key, count]) => {
          const [r, g, b] = key.split(",").map(Number);
          return {
            hex: `#${[r, g, b].map((value) => value.toString(16).padStart(2, "0")).join("")}`,
            percent: Math.round((count / total) * 100)
          };
        });
      resolve(palette);
    };
    img.onerror = reject;
    img.src = url;
  });
}

function openPaletteDialog() {
  const primary = state.images[state.primaryImageIndex]?.url
    ? state.images[state.primaryImageIndex]
    : state.images.find((item) => item.url);
  if (!primary) {
    showToast("Add a previewable screenshot before setting the palette area.");
    return;
  }

  const image = new Image();
  image.onload = () => {
    cropState.image = image;
    cropState.selection = { ...state.paletteCrop };
    sizePaletteCanvas(image);
    drawPaletteCrop();
    els.paletteDialog.showModal();
  };
  image.onerror = () => showToast("That image could not be opened for palette selection.");
  image.src = primary.url;
}

function sizePaletteCanvas(image) {
  const maxWidth = 900;
  const maxHeight = 540;
  const scale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight, 1);
  els.paletteCanvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  els.paletteCanvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
}

function drawPaletteCrop() {
  if (!cropState.image) return;
  const canvas = els.paletteCanvas;
  const context = canvas.getContext("2d");
  const selection = cropState.selection || { x: 0, y: 0, width: 1, height: 1 };
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.drawImage(cropState.image, 0, 0, canvas.width, canvas.height);
  context.fillStyle = "rgba(1, 8, 13, 0.64)";
  context.fillRect(0, 0, canvas.width, canvas.height);

  const x = selection.x * canvas.width;
  const y = selection.y * canvas.height;
  const width = selection.width * canvas.width;
  const height = selection.height * canvas.height;
  context.save();
  context.beginPath();
  context.rect(x, y, width, height);
  context.clip();
  context.drawImage(cropState.image, 0, 0, canvas.width, canvas.height);
  context.restore();
  context.strokeStyle = "#62e6ec";
  context.lineWidth = 3;
  context.strokeRect(x, y, width, height);
  context.fillStyle = "rgba(98, 230, 236, 0.9)";
  [[x, y], [x + width, y], [x, y + height], [x + width, y + height]].forEach(([cx, cy]) => {
    context.fillRect(cx - 4, cy - 4, 8, 8);
  });
}

function canvasPoint(event) {
  const bounds = els.paletteCanvas.getBoundingClientRect();
  return {
    x: clamp((event.clientX - bounds.left) / bounds.width, 0, 1),
    y: clamp((event.clientY - bounds.top) / bounds.height, 0, 1)
  };
}

function startCropSelection(event) {
  if (!cropState.image) return;
  cropState.dragging = true;
  cropState.start = canvasPoint(event);
  cropState.selection = { x: cropState.start.x, y: cropState.start.y, width: 0, height: 0 };
  els.paletteCanvas.setPointerCapture?.(event.pointerId);
  drawPaletteCrop();
}

function updateCropSelection(event) {
  if (!cropState.dragging || !cropState.start) return;
  const point = canvasPoint(event);
  cropState.selection = {
    x: Math.min(cropState.start.x, point.x),
    y: Math.min(cropState.start.y, point.y),
    width: Math.abs(point.x - cropState.start.x),
    height: Math.abs(point.y - cropState.start.y)
  };
  drawPaletteCrop();
}

function endCropSelection(event) {
  if (!cropState.dragging) return;
  updateCropSelection(event);
  cropState.dragging = false;
  if (cropState.selection.width < 0.03 || cropState.selection.height < 0.03) {
    cropState.selection = { ...state.paletteCrop };
  }
  drawPaletteCrop();
}

function savePaletteCrop() {
  if (!cropState.selection) return;
  state.paletteCrop = {
    x: round(cropState.selection.x, 5),
    y: round(cropState.selection.y, 5),
    width: round(cropState.selection.width, 5),
    height: round(cropState.selection.height, 5)
  };
  els.paletteDialog.close();
  analyzePrimaryPalette();
  showToast("Palette area updated.");
}

function useFullImagePalette() {
  state.paletteCrop = { x: 0, y: 0, width: 1, height: 1 };
  cropState.selection = { ...state.paletteCrop };
  drawPaletteCrop();
  els.paletteDialog.close();
  analyzePrimaryPalette();
  showToast("Palette now uses the full image.");
}

async function loadPackage(file) {
  if (!isBuildFile(file)) {
    showToast("That file is not a supported build export.");
    return;
  }

  els.analyzeButton.disabled = true;
  els.buttonGuidance.textContent = "Reading the build package…";

  try {
    const packageData = await parseBuildFile(file);
    state.packageFile = file;
    state.packageData = packageData;
    state.prefabDefinitions = [];
    state.prefabDefinitionFiles = [];
    if (packageData.prefabInstances?.length) setMode("base");
    renderSelectedPackage();
    renderPrefabResolver();
    updateReadyState();
    setStepper(3);
    window.DaedalusLearning?.onSourceChanged?.();
    syncDesignIntentToLearning();
  } catch (error) {
    state.packageFile = null;
    state.packageData = null;
    state.prefabDefinitions = [];
    state.prefabDefinitionFiles = [];
    els.selectedPackage.hidden = true;
    els.prefabResolver.hidden = true;
    els.buttonGuidance.textContent = "The build file could not be read.";
    showToast(error.message || "Daedalus could not read that package.");
  }
}

async function parseBuildFile(file) {
  const extension = file.name.split(".").pop().toLowerCase();
  if (["json", "nmsbase", "nmsprefab"].includes(extension)) {
    try {
      const text = stripBom(await file.text());
      const parsed = JSON.parse(text);
      const classified = window.DaedalusBaseWorkflow.classifyJsonBuild(parsed, file.name);
      if (!classified.objects.length && !classified.prefabInstances.length) {
        throw new Error("No placed objects or named prefab instances were found in that file.");
      }
      return {
        format: extension,
        entries: [file.name],
        objects: classified.objects,
        directObjects: classified.objects,
        prefabInstances: classified.prefabInstances,
        sourceKind: classified.sourceKind,
        geometryStatus: classified.geometryStatus,
        definitionNames: classified.definitionNames,
        ship: null,
        customData: null,
        sourceName: file.name
      };
    } catch (error) {
      if (extension !== "nmsprefab" || !(error instanceof SyntaxError)) throw error;
      // Modern .nmsprefab files can be JSON, while earlier Daedalus packages are ZIP containers.
    }
  }

  if (!window.JSZip) throw new Error("The local ZIP reader did not load.");
  const zip = await JSZip.loadAsync(await file.arrayBuffer());
  const names = Object.keys(zip.files).filter((name) => !zip.files[name].dir);
  const objectsName = names.find((name) => /(^|\/)objects\.json$/i.test(name))
    || names.find((name) => /objects.*\.json$/i.test(name));
  if (!objectsName) throw new Error("This package does not contain objects.json.");

  const objects = JSON.parse(stripBom(await zip.file(objectsName).async("string")));
  if (!Array.isArray(objects)) throw new Error("objects.json is not a placed-object array.");

  const soName = names.find((name) => /(^|\/)so\.json$/i.test(name));
  const ccdName = names.find((name) => /(^|\/)ccd\.json$/i.test(name));
  const ship = soName ? JSON.parse(stripBom(await zip.file(soName).async("string"))) : null;
  const customData = ccdName ? JSON.parse(stripBom(await zip.file(ccdName).async("string"))) : null;

  return {
    format: extension,
    entries: names,
    objects,
    directObjects: objects,
    prefabInstances: [],
    sourceKind: "placed-objects",
    geometryStatus: "direct",
    definitionNames: [file.name],
    ship,
    customData,
    sourceName: file.name
  };
}

function stripBom(text) {
  return text.replace(/^\uFEFF/, "");
}

function findObjectsArray(value, depth = 0) {
  if (window.DaedalusBaseWorkflow) return window.DaedalusBaseWorkflow.findPlacedObjects(value, depth);
  if (depth > 5 || value == null) return null;
  if (Array.isArray(value)) {
    if (value.some((item) => item && typeof item === "object" && ("ObjectID" in item || "Position" in item))) {
      return value;
    }
    return null;
  }
  if (typeof value !== "object") return null;

  for (const key of ["Objects", "objects", "Prefab", "PersistentBaseObjects", "PlacedObjects"]) {
    if (Array.isArray(value[key])) return value[key];
  }
  for (const child of Object.values(value)) {
    const found = findObjectsArray(child, depth + 1);
    if (found) return found;
  }
  return null;
}

async function loadPrefabDefinitions(files) {
  const supported = files.filter((file) => /\.(nmsprefab|json)$/i.test(file.name));
  if (!supported.length) {
    showToast("Choose one or more .nmsprefab definition files.");
    return;
  }

  const failures = [];
  for (const file of supported) {
    try {
      const definition = await parseBuildFile(file);
      if (!definition.objects.length) throw new Error("No ObjectID geometry found");
      state.prefabDefinitions = state.prefabDefinitions.filter((item) => item.sourceName !== definition.sourceName);
      state.prefabDefinitionFiles = state.prefabDefinitionFiles.filter((item) => item.name !== file.name);
      state.prefabDefinitions.push(definition);
      state.prefabDefinitionFiles.push(file);
    } catch (error) {
      failures.push(`${file.name}: ${error.message}`);
    }
  }

  applyPrefabResolution();
  renderSelectedPackage();
  renderPrefabResolver();
  updateReadyState();
  window.DaedalusLearning?.onSourceChanged?.();
  syncDesignIntentToLearning();
  if (failures.length) showToast(failures[0]);
  else showToast("Prefab definition checked and linked by name.");
}

function applyPrefabResolution() {
  if (!state.packageData?.prefabInstances?.length) return;
  const resolution = window.DaedalusBaseWorkflow.resolvePrefabReferences(
    state.packageData,
    state.prefabDefinitions
  );
  state.packageData.prefabResolution = resolution;
  state.packageData.objects = resolution.objects;
  state.packageData.geometryStatus = resolution.geometryStatus;
}

function renderPrefabResolver() {
  const instances = state.packageData?.prefabInstances || [];
  els.prefabResolver.hidden = !instances.length;
  if (!instances.length) return;

  const resolution = state.packageData.prefabResolution || {
    resolved: [],
    unresolved: instances
  };
  const uniqueIds = [...new Set(instances.map((item) => item.PrefabID))];
  els.prefabResolverMessage.innerHTML = resolution.unresolved.length
    ? `This base places ${uniqueIds.map((id) => `<code>${escapeHtml(id)}</code>`).join(", ")}. Add the matching <code>.nmsprefab</code> file${uniqueIds.length === 1 ? "" : "s"} to learn its individual ObjectIDs.`
    : `All named prefab references are linked. Daedalus will analyze the verified prefab-relative ObjectID geometry and retain the base placement separately.`;
  els.prefabResolutionList.innerHTML = "";
  uniqueIds.forEach((id) => {
    const matched = resolution.resolved.some((item) => item.instance.PrefabID === id);
    const row = document.createElement("div");
    row.className = `prefab-resolution-row ${matched ? "resolved" : "waiting"}`;
    row.innerHTML = `<span>${matched ? "✓" : "…"}</span><strong>${escapeHtml(id)}</strong><small>${matched ? "definition linked" : "waiting for .nmsprefab"}</small>`;
    els.prefabResolutionList.appendChild(row);
  });
}

function renderSelectedPackage() {
  const { sourceName, objects, entries, prefabInstances, geometryStatus } = state.packageData;
  els.selectedPackage.hidden = false;
  els.selectedPackage.innerHTML = "";
  const label = document.createElement("strong");
  label.textContent = prefabInstances?.length
    ? `${sourceName} · ${prefabInstances.length} prefab instance${prefabInstances.length === 1 ? "" : "s"} · ${objects.length.toLocaleString()} resolved ObjectID records · ${titleCase(geometryStatus.replaceAll("_", " "))}`
    : `${sourceName} · ${objects.length.toLocaleString()} records · ${entries.length} package file${entries.length === 1 ? "" : "s"}`;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "Remove";
  remove.addEventListener("click", clearPackage);
  els.selectedPackage.append(label, remove);
}

function clearPackage() {
  state.packageFile = null;
  state.packageData = null;
  state.prefabDefinitions = [];
  state.prefabDefinitionFiles = [];
  state.report = null;
  els.blueprintInput.value = "";
  els.selectedPackage.hidden = true;
  els.prefabResolver.hidden = true;
  els.prefabDefinitionInput.value = "";
  els.results.hidden = true;
  updateReadyState();
  setStepper(state.images.length ? 2 : 1);
  window.DaedalusLearning?.onSourceChanged?.();
}

function updateReadyState() {
  const ready = Boolean(state.packageData?.objects?.length);
  els.analyzeButton.disabled = !ready;
  if (!ready) {
    els.buttonGuidance.textContent = state.packageData?.prefabInstances?.length
      ? "Add the referenced .nmsprefab definition to analyze its ObjectID geometry. Your prefab placement is retained."
      : "Add an exported build file to begin.";
  } else if (!state.images.length) {
    els.buttonGuidance.textContent = "Ready. Add images for visual context, or analyze the build file now.";
  } else {
    els.buttonGuidance.textContent = `Ready with ${state.images.length} reference image${state.images.length === 1 ? "" : "s"}.`;
  }
  syncSignReadiness();
}

function runAnalysis() {
  if (!state.packageData) return;
  els.analyzeButton.disabled = true;
  els.analyzeButton.querySelector("span:first-child").textContent = "Analyzing transforms…";

  window.setTimeout(() => {
    try {
      state.report = buildReport();
      renderReport();
      els.results.hidden = false;
      setStepper(4);
      selectTab("overview");
      els.results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      showToast(error.message || "Analysis failed.");
    } finally {
      els.analyzeButton.disabled = false;
      els.analyzeButton.querySelector("span:first-child").textContent = "Analyze Reverse Blueprint";
    }
  }, 80);
}

function buildReport() {
  const objects = state.packageData.objects;
  const validObjects = objects.filter(isPlacedObject);
  const partsMap = groupParts(validObjects);
  const parts = [...partsMap.values()].sort((a, b) => b.count - a.count || a.objectId.localeCompare(b.objectId));
  const bounds = getBounds(validObjects);
  const grids = detectGrids(partsMap);
  const motifs = detectOrientationMotifs(partsMap);
  const checks = buildChecks(objects, validObjects, parts);
  const insights = buildInsights(validObjects, parts, grids, motifs);
  const recipe = buildRecipe(validObjects, parts, grids, motifs);
  const reportParts = parts.map(({ objects: groupedObjects, ...part }) => ({
    ...part,
    bounds: normalizeBounds(part.bounds)
  }));
  const ship = state.packageData.ship;

  return {
    schema: "wonder-codex.daedalus.reverse-blueprint.v0.3",
    generatedAt: new Date().toISOString(),
    mode: state.mode,
    source: {
      fileName: state.packageData.sourceName,
      format: state.packageData.format,
      packageEntries: state.packageData.entries,
      sourceKind: state.packageData.sourceKind,
      geometryStatus: state.packageData.geometryStatus,
      prefabInstances: state.packageData.prefabInstances || [],
      prefabDefinitions: state.prefabDefinitions.map((item) => ({
        sourceName: item.sourceName,
        format: item.format,
        objectCount: item.objects.length,
        definitionNames: item.definitionNames
      })),
      imageFiles: state.images.map((item) => ({
        name: item.file.name,
        type: item.file.type || fileExtension(item.file.name).toUpperCase(),
        sizeBytes: item.file.size,
        browserPreviewAvailable: Boolean(item.url)
      })),
      paletteCrop: state.paletteCrop
    },
    build: {
      name: ship?.Name || state.packageData.prefabInstances?.[0]?.PrefabID || baseName(state.packageData.sourceName),
      resource: ship?.Resource?.Filename || null,
      objectCount: validObjects.length,
      sourceRecordCount: objects.length,
      distinctObjectIds: parts.length,
      bounds,
      palette: state.palette,
      parts: reportParts,
      patterns: { grids, motifs },
      insights,
      recipe,
      checks
    },
    designIntent: {
      originalRequest: els.buildBrief.value.trim() || null,
      category: state.buildCategory,
      signSpecification: getSignSpecification()
    },
    safety: {
      readOnly: true,
      saveAccessed: false,
      sourceModified: false,
      exportContainsPlacedObjects: false,
      note: "v0.9.1 resolves Base Builder prefab instances only through explicitly supplied .nmsprefab definitions, reads native Prefab geometry arrays, rejects empty wrapper geometry as training ground truth, and records generated sign attempts for human review. Interactive GLB inspection and guarded learning remain available. ^U_PARAGON protection applies only to Corvette workflows and is never inferred from images."
    }
  };
}

function isPlacedObject(item) {
  return item
    && typeof item === "object"
    && typeof item.ObjectID === "string"
    && item.ObjectID.length > 0
    && isVector(item.Position);
}

function isVector(value) {
  return Array.isArray(value) && value.length >= 3 && value.slice(0, 3).every(Number.isFinite);
}

function vectorLength(value) {
  if (!isVector(value)) return null;
  return Math.sqrt(value.slice(0, 3).reduce((sum, item) => sum + (Number(item) ** 2), 0));
}

function hasUniformScale(object) {
  const up = vectorLength(object?.Up);
  const at = vectorLength(object?.At);
  if (!up || !at) return false;
  return Math.abs(up - at) <= Math.max(0.005, Math.max(up, at) * 0.01);
}

function groupParts(objects) {
  const map = new Map();
  objects.forEach((object) => {
    const id = object.ObjectID;
    if (!map.has(id)) {
      map.set(id, {
        objectId: id,
        count: 0,
        userData: {},
        bounds: emptyBounds(),
        objects: []
      });
    }
    const part = map.get(id);
    part.count += 1;
    const userData = String(object.UserData ?? "missing");
    part.userData[userData] = (part.userData[userData] || 0) + 1;
    part.objects.push(object);
    extendBounds(part.bounds, object.Position);
  });
  return map;
}

function emptyBounds() {
  return {
    min: [Infinity, Infinity, Infinity],
    max: [-Infinity, -Infinity, -Infinity],
    size: [0, 0, 0]
  };
}

function extendBounds(bounds, position) {
  for (let axis = 0; axis < 3; axis += 1) {
    bounds.min[axis] = Math.min(bounds.min[axis], position[axis]);
    bounds.max[axis] = Math.max(bounds.max[axis], position[axis]);
    bounds.size[axis] = bounds.max[axis] - bounds.min[axis];
  }
}

function getBounds(objects) {
  const bounds = emptyBounds();
  objects.forEach((object) => extendBounds(bounds, object.Position));
  return normalizeBounds(bounds);
}

function normalizeBounds(bounds) {
  return {
    min: bounds.min.map((value) => round(value, 4)),
    max: bounds.max.map((value) => round(value, 4)),
    size: bounds.size.map((value) => round(value, 4))
  };
}

function detectGrids(partsMap) {
  const candidates = [];
  partsMap.forEach((part) => {
    if (part.count < 9) return;
    const yGroups = new Map();
    part.objects.forEach((object) => {
      const y = round(object.Position[1], 2);
      if (!yGroups.has(y)) yGroups.set(y, []);
      yGroups.get(y).push(object);
    });

    yGroups.forEach((objects, y) => {
      if (objects.length < 9) return;
      const xs = uniqueSorted(objects.map((object) => round(object.Position[0], 2)));
      const zs = uniqueSorted(objects.map((object) => round(object.Position[2], 2)));
      if (xs.length < 3 || zs.length < 3) return;
      const expected = xs.length * zs.length;
      const coverage = objects.length / expected;
      if (coverage < 0.7 || coverage > 1.03) return;

      candidates.push({
        objectId: part.objectId,
        planeY: y,
        columns: xs.length,
        rows: zs.length,
        placed: objects.length,
        expected,
        gaps: Math.max(0, expected - objects.length),
        coverage: round(coverage * 100, 1),
        spacing: {
          x: medianSpacing(xs),
          z: medianSpacing(zs)
        },
        userData: countUserData(objects)
      });
    });
  });
  return candidates.sort((a, b) => b.placed - a.placed);
}

function detectOrientationMotifs(partsMap) {
  const motifs = [];
  partsMap.forEach((part) => {
    if (part.count < 10) return;
    const signatures = new Map();
    part.objects.forEach((object) => {
      if (!isVector(object.At) || !isVector(object.Up)) return;
      const signature = [...object.At.slice(0, 3), ...object.Up.slice(0, 3)]
        .map((value) => round(value, 3))
        .join("|");
      signatures.set(signature, (signatures.get(signature) || 0) + 1);
    });
    const counts = [...signatures.values()];
    if (counts.length < 2 || counts.length > 16) return;
    const min = Math.min(...counts);
    const max = Math.max(...counts);
    if (min < 2 || max - min > 1) return;
    const copies = min;
    const pieces = counts.length;
    const explained = copies * pieces;
    if (explained / part.count < 0.9) return;

    motifs.push({
      objectId: part.objectId,
      piecesPerMotif: pieces,
      copies,
      explainedObjects: explained,
      confidence: round((explained / part.count) * 100, 1)
    });
  });
  return motifs.sort((a, b) => b.explainedObjects - a.explainedObjects);
}

function buildInsights(objects, parts, grids, motifs) {
  const insights = [];
  if (grids[0]) {
    const grid = grids[0];
    insights.push({
      type: "grid",
      title: `${grid.columns} × ${grid.rows} construction grid`,
      detail: `${grid.placed} ${grid.objectId} records occupy ${grid.coverage}% of the detected grid${grid.gaps ? `, leaving ${grid.gaps} deliberate gap${grid.gaps === 1 ? "" : "s"}` : ""}.`
    });
  }
  if (motifs[0]) {
    const motif = motifs[0];
    insights.push({
      type: "motif",
      title: `${motif.copies} repeated ${motif.piecesPerMotif}-piece motifs`,
      detail: `${motif.objectId} uses ${motif.piecesPerMotif} recurring orientations, explaining ${motif.explainedObjects} placed objects.`
    });
  }

  const colored = parts
    .map((part) => ({ part, variants: Object.keys(part.userData).filter((value) => value !== "0" && value !== "missing") }))
    .filter((item) => item.variants.length > 1)
    .sort((a, b) => b.part.count - a.part.count)[0];
  if (colored) {
    insights.push({
      type: "palette",
      title: `${colored.variants.length} encoded variants on ${colored.part.objectId}`,
      detail: Object.entries(colored.part.userData)
        .map(([value, count]) => `UserData ${value}: ${count}`)
        .join(" · ")
    });
  }

  const top = parts[0];
  if (top) {
    insights.push({
      type: "parts",
      title: `${parts.length} distinct Object IDs`,
      detail: `${top.objectId} is the most-used part at ${top.count} placements; ${objects.length - top.count} placements provide supporting structure and detail.`
    });
  }
  return insights;
}

function buildRecipe(objects, parts, grids, motifs) {
  const recipe = [];
  const grid = grids[0];
  const motif = motifs[0];

  if (grid) {
    recipe.push({
      title: `Lay out the ${grid.columns} × ${grid.rows} foundation grid`,
      detail: `Place ${grid.objectId} at approximately ${formatNumber(grid.spacing.x)} units across X and ${formatNumber(grid.spacing.z)} units across Z. Fill ${grid.placed} of ${grid.expected} detected positions.`
    });
    const variants = Object.entries(grid.userData).sort((a, b) => b[1] - a[1]);
    if (variants.length > 1) {
      recipe.push({
        title: "Apply the encoded color and material pattern",
        detail: variants.map(([value, count]) => `${count} pieces use UserData ${value}`).join("; ") + "."
      });
    }
  }

  if (motif) {
    recipe.push({
      title: `Assemble one ${motif.piecesPerMotif}-piece reusable motif`,
      detail: `Use ${motif.objectId} with the detected orientation set, then repeat the motif ${motif.copies} times instead of placing ${motif.explainedObjects} objects individually.`
    });
  }

  const sign = getSignSpecification();
  if (sign) {
    recipe.push({
      title: `Typeset “${sign.text}” with ${titleCase(sign.fontGrammar.replaceAll("-", " "))}`,
      detail: "Construct every glyph from verified build-part ObjectIDs. Letter spacing, line height, and punctuation remain reusable font-grammar parameters."
    });
    recipe.push({
      title: "Build the black backdrop and apply red lettering",
      detail: "Use verified backdrop ObjectIDs with black UserData and verified glyph ObjectIDs with red UserData learned from an approved sign prefab. No decorative mesh without an ObjectID is permitted."
    });
  }

  const explained = (grid?.placed || 0) + (motif?.explainedObjects || 0);
  const remaining = Math.max(0, objects.length - explained);
  recipe.push({
    title: "Add structural edges, access, and unique details",
    detail: `${remaining} remaining placements across ${Math.max(0, parts.length - new Set([grid?.objectId, motif?.objectId].filter(Boolean)).size)} other Object IDs form the non-repeating structure and decoration.`
  });

  if (state.mode === "corvette") {
    recipe.push({
      title: "Preserve the Corvette wrapper",
      detail: "Future export must replace only the placed Objects list while keeping the existing ship identity, resource, UserData binding, inventories, and CustomData."
    });
  } else {
    recipe.push({
      title: "Prepare a reusable prefab boundary",
      detail: "Normalize the finished placement group around a clear origin before a future .nmsprefab export."
    });
  }

  recipe.push({
    title: "Render and compare before export",
    detail: "The next Daedalus phase will assemble a Blender draft and compare its silhouette, proportions, colors, and repeated details with the reference images."
  });
  return recipe;
}

function buildChecks(sourceObjects, validObjects, parts) {
  const data = state.packageData;
  const checks = [
    {
      status: validObjects.length === sourceObjects.length ? "pass" : "warn",
      title: "Placed-object records",
      detail: validObjects.length === sourceObjects.length
        ? `All ${validObjects.length} records contain an ObjectID and finite Position vector.`
        : `${sourceObjects.length - validObjects.length} records were skipped because required placement fields were missing.`
    },
    {
      status: parts.every((part) => part.objectId.startsWith("^")) ? "pass" : "warn",
      title: "Object ID formatting",
      detail: parts.every((part) => part.objectId.startsWith("^"))
        ? `All ${parts.length} distinct Object IDs use the expected caret-prefixed form.`
        : "Some Object IDs use an unfamiliar format and should be reviewed."
    },
    {
      status: data.entries.some((name) => /objects\.json$/i.test(name)) || data.objects.length ? "pass" : "warn",
      title: "Objects source located",
      detail: data.prefabInstances?.length
        ? "Placed-object records were resolved from explicitly supplied .nmsprefab definitions; the .NMSBASE instance records remain separate."
        : ["json", "nmsbase", "nmsprefab"].includes(data.format)
          ? "A placed-object array was located in the supplied JSON-based build file."
          : "objects.json was located and decoded, including UTF-8 BOM handling."
    }
  ];

  const badVectors = validObjects.filter((object) => !isVector(object.Up) || !isVector(object.At)).length;
  checks.push({
    status: badVectors === 0 ? "pass" : "warn",
    title: "Orientation vectors",
    detail: badVectors === 0
      ? "Every placed object includes finite Up and At vectors."
      : `${badVectors} objects lack a complete Up or At vector; their orientation may be ambiguous.`
  });

  const stretchedObjects = validObjects.filter((object) => !hasUniformScale(object)).length;
  checks.push({
    status: stretchedObjects === 0 ? "pass" : "fail",
    title: "Normal Object ID shape",
    detail: stretchedObjects === 0
      ? "Every placed part uses uniform scale; rotation and size changes retain the part's normal shape."
      : `${stretchedObjects} objects use missing or non-uniform scale. NMS will not reliably recognize stretched Object ID parts.`
  });

  checks.push({
    status: validObjects.length <= 3000 ? "pass" : "fail",
    title: "3,000-part game limit",
    detail: validObjects.length <= 3000
      ? `${validObjects.length.toLocaleString()} placed parts remain within the base and Corvette limit.`
      : `${validObjects.length.toLocaleString()} placed parts exceed the hard 3,000-part limit.`
  });

  if (state.mode === "corvette") {
    const anchors = validObjects.filter((object) => object.ObjectID === "^U_PARAGON");
    checks.push({
      status: anchors.length === 1 ? "pass" : "fail",
      title: "Protected Corvette anchor",
      detail: anchors.length === 1
        ? "Exactly one ^U_PARAGON source record is present and must remain unchanged."
        : `Expected exactly one ^U_PARAGON source record; found ${anchors.length}.`
    });
    checks.push({
      status: data.ship ? "pass" : "warn",
      title: "Corvette identity wrapper",
      detail: data.ship
        ? `so.json is present for “${data.ship.Name || "Unnamed Corvette"}” and will be treated as protected data.`
        : "No so.json wrapper was found. Analysis works, but a safe Corvette export would require an existing target ship."
    });
    checks.push({
      status: data.customData ? "pass" : "warn",
      title: "CustomData package",
      detail: data.customData
        ? "ccd.json is present and will remain outside the generated Objects-only blueprint."
        : "No ccd.json was found; confirm whether the source format requires it."
    });
  } else {
    if (data.format === "nmsbase") {
      const flags = validObjects.filter((object) => object.ObjectID === "^BASE_FLAG");
      checks.push({
        status: flags.length === 1 ? "pass" : "fail",
        title: "Protected base flag",
        detail: flags.length === 1
          ? "Exactly one ^BASE_FLAG source record is present and must remain unchanged."
          : `Expected exactly one ^BASE_FLAG source record in this NMSBASE; found ${flags.length}.`
      });
    }
    const instances = data.prefabInstances || [];
    if (instances.length) {
      const resolution = data.prefabResolution;
      checks.push({
        status: resolution?.unresolved?.length ? "fail" : "pass",
        title: "Named prefab resolution",
        detail: resolution?.unresolved?.length
          ? `${resolution.unresolved.length} named prefab reference${resolution.unresolved.length === 1 ? " is" : "s are"} missing a matching .nmsprefab definition.`
          : `${resolution?.resolved?.length || 0} prefab instance${resolution?.resolved?.length === 1 ? "" : "s"} linked to verified ObjectID definitions. Placement transforms are retained separately from prefab-relative geometry.`
      });
    }
    checks.push({
      status: "pass",
      title: "Base/prefab read-only boundary",
      detail: "The analyzer has not attempted to locate or modify PersistentPlayerBases."
    });
  }

  checks.push({
    status: "pass",
    title: "Save isolation",
    detail: "Analysis occurred entirely in browser memory. No save folder, WGS container, or paired Manual/Auto slot was accessed."
  });
  return checks;
}

function renderReport() {
  const report = state.report;
  const build = report.build;
  const passed = build.checks.filter((check) => check.status === "pass").length;

  els.resultTitle.textContent = build.name || "Reverse Blueprint";
  els.resultSubtitle.textContent = `${state.mode === "corvette" ? "Corvette" : "Base / Prefab"} · ${report.source.fileName} · ${report.source.imageFiles.length} reference image${report.source.imageFiles.length === 1 ? "" : "s"}`;
  els.objectMetric.textContent = build.objectCount.toLocaleString();
  els.partMetric.textContent = build.distinctObjectIds.toLocaleString();
  els.motifMetric.textContent = build.patterns.motifs.length.toLocaleString();
  els.checkMetric.textContent = `${passed}/${build.checks.length}`;

  renderInsights(build.insights);
  renderEnvelope(build.bounds);
  renderMiniParts(build.parts);
  renderRecipe(build.recipe);
  renderPartsTable();
  renderChecks(build.checks);
  window.DaedalusLearning?.onAnalysisReady?.();
}

function renderInsights(insights) {
  const icons = { grid: "▦", motif: "✦", palette: "◒", parts: "⌁" };
  els.insightList.innerHTML = "";
  insights.forEach((insight) => {
    const item = document.createElement("article");
    item.className = "insight";
    item.innerHTML = `
      <span class="insight-icon">${icons[insight.type] || "◆"}</span>
      <div><strong>${escapeHtml(insight.title)}</strong><p>${escapeHtml(insight.detail)}</p></div>
    `;
    els.insightList.appendChild(item);
  });
}

function renderEnvelope(bounds) {
  const axes = ["X", "Y", "Z"];
  els.envelopeCard.innerHTML = bounds.size.map((value, index) => `
    <div class="axis-stat">
      <span>${axes[index]} span</span>
      <strong>${formatNumber(value)}</strong>
      <small>${formatNumber(bounds.min[index])} → ${formatNumber(bounds.max[index])}</small>
    </div>
  `).join("");
}

function renderMiniParts(parts) {
  els.miniParts.innerHTML = parts.slice(0, 6).map((part) => `
    <div class="mini-part"><code>${escapeHtml(part.objectId)}</code><span>${part.count.toLocaleString()}×</span></div>
  `).join("");
}

function renderRecipe(recipe) {
  els.recipeList.innerHTML = recipe.map((step) => `
    <li><strong>${escapeHtml(step.title)}</strong><p>${escapeHtml(step.detail)}</p></li>
  `).join("");
}

function renderPartsTable(filter = "") {
  if (!state.report) return;
  const needle = filter.trim().toLowerCase();
  const gridIds = new Set(state.report.build.patterns.grids.map((grid) => grid.objectId));
  const motifIds = new Set(state.report.build.patterns.motifs.map((motif) => motif.objectId));
  const rows = state.report.build.parts.filter((part) => part.objectId.toLowerCase().includes(needle));

  els.partsTableBody.innerHTML = rows.map((part) => {
    const variants = Object.entries(part.userData)
      .sort((a, b) => b[1] - a[1])
      .map(([value, count]) => `${value}: ${count}`)
      .join(" · ");
    let role = "Unique / structural";
    if (gridIds.has(part.objectId)) role = "Grid foundation";
    if (motifIds.has(part.objectId)) role = "Repeated motif";
    return `
      <tr>
        <td><code>${escapeHtml(part.objectId)}</code></td>
        <td>${part.count.toLocaleString()}</td>
        <td>${escapeHtml(variants)}</td>
        <td><span class="role-badge">${role}</span></td>
      </tr>
    `;
  }).join("");
}

function renderChecks(checks) {
  els.checkList.innerHTML = checks.map((check) => {
    const icon = check.status === "pass" ? "✓" : check.status === "warn" ? "!" : "×";
    return `
      <article class="check-item ${check.status}">
        <span class="check-icon">${icon}</span>
        <div><strong>${escapeHtml(check.title)}</strong><p>${escapeHtml(check.detail)}</p></div>
      </article>
    `;
  }).join("");
}

function selectTab(name) {
  els.tabs.forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  els.tabPanels.forEach((panel) => {
    const active = panel.id === `tab-${name}`;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

function exportReport() {
  if (!state.report) return;
  const content = JSON.stringify(state.report, null, 2);
  const blob = new Blob([content], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${safeFileName(state.report.build.name || "daedalus-blueprint")}-reverse-blueprint.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  showToast("Blueprint report exported.");
}

async function copySummary() {
  if (!state.report) return;
  const build = state.report.build;
  const grid = build.patterns.grids[0];
  const motif = build.patterns.motifs[0];
  const summary = [
    `Daedalus Reverse Blueprint: ${build.name}`,
    `${build.objectCount} placed objects · ${build.distinctObjectIds} Object IDs`,
    grid ? `Grid: ${grid.columns}×${grid.rows}, ${grid.placed}/${grid.expected} positions, ${grid.objectId}` : "Grid: none detected",
    motif ? `Primary motif: ${motif.copies} copies × ${motif.piecesPerMotif} pieces, ${motif.objectId}` : "Repeated motif: none detected",
    "Mode: read-only analysis; no save accessed or modified."
  ].join("\n");

  try {
    await navigator.clipboard.writeText(summary);
    showToast("Summary copied.");
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = summary;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand("copy");
    textarea.remove();
    showToast("Summary copied.");
  }
}

async function exportBridgeJob() {
  if (!state.report || !state.packageFile) {
    showToast("Analyze a known build file before exporting a Blender job.");
    return;
  }
  if (!window.JSZip) {
    showToast("The local ZIP writer did not load.");
    return;
  }

  const buttonText = els.bridgeJobButton.textContent;
  els.bridgeJobButton.disabled = true;
  els.bridgeJobButton.textContent = "Packaging Blender job…";
  try {
    const zip = new JSZip();
    const sourceName = safeArchiveName(state.packageFile.name);
    const referenceFiles = [];
    const usesResolvedPrefabGeometry = Boolean(state.packageData.prefabInstances?.length);
    const sourcePath = usesResolvedPrefabGeometry
      ? "input/source/resolved-prefab-objects.json"
      : `input/source/${sourceName}`;

    if (usesResolvedPrefabGeometry) {
      zip.file("input/source-reference/placement.nmsbase", await state.packageFile.arrayBuffer());
      zip.file(sourcePath, JSON.stringify(state.packageData.objects, null, 2));
      for (const file of state.prefabDefinitionFiles) {
        zip.file(`input/source-reference/prefab-definitions/${safeArchiveName(file.name)}`, await file.arrayBuffer());
      }
    } else {
      zip.file(sourcePath, await state.packageFile.arrayBuffer());
    }
    zip.file("input/blueprint.json", JSON.stringify(state.report, null, 2));

    for (let index = 0; index < state.images.length; index += 1) {
      const item = state.images[index];
      const fileName = `${String(index + 1).padStart(2, "0")}-${safeArchiveName(item.file.name)}`;
      const archivePath = `input/references/${fileName}`;
      zip.file(archivePath, await item.file.arrayBuffer());
      referenceFiles.push({
        path: archivePath,
        originalName: item.file.name,
        primary: index === state.primaryImageIndex,
        browserPreviewAvailable: Boolean(item.url)
      });
    }

    const job = {
      schema: "wonder-codex.daedalus.blender-job.v0.3",
      createdAt: new Date().toISOString(),
      mode: state.mode,
      targetName: state.report.build.name,
      source: {
        path: sourcePath,
        originalName: state.packageFile.name,
        format: usesResolvedPrefabGeometry ? "resolved-prefab-objects-json" : state.packageData.format,
        placementReference: usesResolvedPrefabGeometry ? "input/source-reference/placement.nmsbase" : null,
        prefabDefinitionCount: state.prefabDefinitionFiles.length
      },
      blueprint: { path: "input/blueprint.json" },
      references: referenceFiles,
      requestedOutputs: [
        "real-model-draft.blend",
        "real-top.png",
        "real-front.png",
        "real-side.png",
        "real-model-inspection.glb",
        "bridge-manifest.json",
        "part-inventory.csv",
        "base-builder-addon-inventory.json",
        "Daedalus-Return-to-Nova.zip"
      ],
      safety: {
        saveAccessAllowed: false,
        sourceMutationAllowed: false,
        outputDirectoryOnly: true,
        protectedObjectIds: state.mode === "corvette"
          ? ["^U_PARAGON"]
          : (state.packageData.format === "nmsbase" ? ["^BASE_FLAG"] : []),
        protectedObjectPolicy: state.mode === "corvette"
          ? "COPY_SOURCE_RECORD_UNCHANGED"
          : (state.packageData.format === "nmsbase"
            ? "COPY_BASE_FLAG_SOURCE_RECORD_UNCHANGED_AND_USE_OBJECTID_ONLY_GEOMETRY"
            : "OBJECTID_ONLY_RESOLVED_PREFAB_GEOMETRY")
      }
    };
    zip.file("job.json", JSON.stringify(job, null, 2));
    zip.file("START-HERE.txt", [
      "DAEDALUS BLENDER BRIDGE JOB v0.3",
      "",
      `Target: ${job.targetName}`,
      `Mode: ${job.mode}`,
      `Source: ${job.source.originalName}`,
      `References: ${job.references.length}`,
      "",
      "Do not unzip or edit this job.",
      "Choose it when Run-Daedalus-Blender-Bridge.bat asks for a Blender job.",
      "The runner writes only to its own output folder and never accesses a No Man's Sky save."
    ].join("\r\n"));

    const blob = await zip.generateAsync({
      type: "blob",
      compression: "DEFLATE",
      compressionOptions: { level: 6 }
    });
    downloadBlob(blob, `${safeFileName(state.report.build.name || "daedalus")}-blender-job-v0.3.zip`);
    showToast("Blender Bridge job exported.");
  } catch (error) {
    showToast(error.message || "The Blender job could not be created.");
  } finally {
    els.bridgeJobButton.disabled = false;
    els.bridgeJobButton.textContent = buttonText;
  }
}

function countUserData(objects) {
  return objects.reduce((counts, object) => {
    const key = String(object.UserData ?? "missing");
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function uniqueSorted(values) {
  return [...new Set(values)].sort((a, b) => a - b);
}

function medianSpacing(values) {
  if (values.length < 2) return 0;
  const differences = values.slice(1)
    .map((value, index) => round(value - values[index], 4))
    .filter((value) => value > 0.01)
    .sort((a, b) => a - b);
  if (!differences.length) return 0;
  const middle = Math.floor(differences.length / 2);
  return differences.length % 2
    ? differences[middle]
    : round((differences[middle - 1] + differences[middle]) / 2, 4);
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function formatNumber(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fileExtension(name) {
  return name.includes(".") ? name.split(".").pop() : "";
}

function baseName(name) {
  return name.replace(/\.(nmsship|nmsprefab|nmsbase|json)$/i, "");
}

function safeFileName(name) {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    || "daedalus-blueprint";
}

function safeArchiveName(name) {
  const extension = fileExtension(name);
  const stem = extension ? name.slice(0, -(extension.length + 1)) : name;
  const safeStem = stem
    .replace(/[<>:"/\\|?*\u0000-\u001F]/g, "-")
    .replace(/\s+/g, " ")
    .trim() || "file";
  return extension ? `${safeStem}.${extension.toLowerCase()}` : safeStem;
}

function downloadBlob(blob, fileName) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

let toastTimer;
function showToast(message) {
  window.clearTimeout(toastTimer);
  els.toast.textContent = message;
  els.toast.classList.add("show");
  toastTimer = window.setTimeout(() => els.toast.classList.remove("show"), 2600);
}

init();
