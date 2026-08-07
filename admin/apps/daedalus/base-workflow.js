"use strict";

(function exposeDaedalusBaseWorkflow(root) {
  const BASE_TYPES = ["sign", "statue", "building", "other"];
  const CORVETTE_STYLES = ["sailing ship", "saucer", "sci-fi", "other"];

  function normalizeName(value) {
    return String(value || "")
      .replace(/\.(nmsbase|nmsprefab|json)$/i, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "");
  }

  function isPlacedObject(item) {
    return Boolean(
      item
      && typeof item === "object"
      && typeof item.ObjectID === "string"
      && item.ObjectID.length
      && Array.isArray(item.Position)
      && item.Position.slice(0, 3).every(Number.isFinite)
    );
  }

  function findPlacedObjects(value, depth = 0) {
    if (depth > 6 || value == null) return null;
    if (Array.isArray(value)) {
      return value.some(isPlacedObject) ? value : null;
    }
    if (typeof value !== "object") return null;

    for (const key of ["Objects", "objects", "Prefab", "PersistentBaseObjects", "PlacedObjects"]) {
      if (Array.isArray(value[key]) && value[key].some(isPlacedObject)) return value[key];
    }
    for (const child of Object.values(value)) {
      const found = findPlacedObjects(child, depth + 1);
      if (found) return found;
    }
    return null;
  }

  function findPrefabInstances(value, depth = 0) {
    if (depth > 6 || value == null || typeof value !== "object") return [];
    if (Array.isArray(value)) {
      if (value.some((item) => item && typeof item.PrefabID === "string")) {
        return value.filter((item) => item && typeof item.PrefabID === "string");
      }
      for (const child of value) {
        const found = findPrefabInstances(child, depth + 1);
        if (found.length) return found;
      }
      return [];
    }
    for (const key of ["Prefabs", "prefabs", "PrefabInstances"]) {
      if (Array.isArray(value[key])) {
        return value[key].filter((item) => item && typeof item.PrefabID === "string");
      }
    }
    for (const child of Object.values(value)) {
      const found = findPrefabInstances(child, depth + 1);
      if (found.length) return found;
    }
    return [];
  }

  function classifyJsonBuild(parsed, sourceName) {
    const objects = findPlacedObjects(parsed) || [];
    const prefabInstances = findPrefabInstances(parsed);
    const referenceOnly = objects.length === 0 && prefabInstances.length > 0;
    return {
      objects,
      prefabInstances,
      sourceName,
      sourceKind: referenceOnly
        ? "prefab-instance-wrapper"
        : Array.isArray(parsed?.Prefab)
          ? "native-prefab-definition"
          : "placed-objects",
      geometryStatus: referenceOnly ? "reference_only" : objects.length ? "direct" : "missing",
      definitionNames: [
        parsed?.Name,
        parsed?.PrefabID,
        parsed?.ID,
        sourceName
      ].filter(Boolean)
    };
  }

  function classifyBuildIntent(text, modeHint = "corvette") {
    const value = String(text || "").toLowerCase();
    const baseSignals = /\b(base|prefab|sign|statue|building|structure|house|cavern)\b/;
    const corvetteSignals = /\b(corvette|ship|starship|saucer|vessel|frigate)\b/;
    const mode = baseSignals.test(value)
      ? "base"
      : corvetteSignals.test(value)
        ? "corvette"
        : modeHint;

    let category = "other";
    if (mode === "base") {
      if (/\b(sign|lettering|letters|billboard|marquee)\b/.test(value)) category = "sign";
      else if (/\b(statue|sculpture|monument|figure)\b/.test(value)) category = "statue";
      else if (/\b(building|house|tower|station|facility|structure)\b/.test(value)) category = "building";
    } else {
      if (/\b(sailing|sailboat|galleon|pirate|clipper|tall ship)\b/.test(value)) category = "sailing ship";
      else if (/\b(saucer|ufo|disc)\b/.test(value)) category = "saucer";
      else if (/\b(sci[ -]?fi|science fiction|futuristic|spacecraft)\b/.test(value)) category = "sci-fi";
    }

    return {
      mode,
      category,
      confidence: category === "other" ? "low" : "high",
      allowedCategories: mode === "base" ? BASE_TYPES : CORVETTE_STYLES
    };
  }

  function definitionMatches(prefabId, definition) {
    const target = normalizeName(prefabId);
    return (definition.definitionNames || []).some((name) => normalizeName(name) === target);
  }

  function resolvePrefabReferences(wrapper, definitions) {
    const instances = wrapper.prefabInstances || [];
    const resolved = [];
    const unresolved = [];
    const usedDefinitions = new Set();

    instances.forEach((instance) => {
      const definition = definitions.find((item) => definitionMatches(instance.PrefabID, item));
      if (!definition || !definition.objects?.length) {
        unresolved.push(instance);
        return;
      }
      usedDefinitions.add(definition);
      resolved.push({ instance, definition });
    });

    const objects = [];
    usedDefinitions.forEach((definition) => {
      definition.objects.filter(isPlacedObject).forEach((object) => objects.push(object));
    });

    return {
      resolved,
      unresolved,
      objects,
      geometryStatus: unresolved.length ? "partially_resolved" : resolved.length ? "resolved_definition_relative" : "reference_only"
    };
  }

  function createSignSpecification(values = {}) {
    return {
      text: String(values.text || "Cavern Below!"),
      buildType: "sign",
      fontGrammar: values.fontGrammar || "pill-light-rounded",
      backdropColor: values.backdropColor || "black",
      letteringColor: values.letteringColor || "red",
      objectIdOnly: true,
      output: "BASE_PREFAB",
      geometryReadiness: values.geometryReadiness || "WAITING_FOR_VERIFIED_PREFAB_DEFINITION"
    };
  }

  const api = {
    BASE_TYPES,
    CORVETTE_STYLES,
    normalizeName,
    findPlacedObjects,
    findPrefabInstances,
    classifyJsonBuild,
    classifyBuildIntent,
    resolvePrefabReferences,
    createSignSpecification
  };

  root.DaedalusBaseWorkflow = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
