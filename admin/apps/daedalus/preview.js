"use strict";

((root) => {
  const WIDTH = 960;
  const HEIGHT = 480;
  const PADDING = {top: 52, right: 48, bottom: 54, left: 48};
  const AXIS_NAMES = ["X", "Y", "Z"];
  const WALL_SIZE = [5.333333, 3.333333];

  function isPlacedObject(object) {
    return object
      && typeof object.ObjectID === "string"
      && Array.isArray(object.Position)
      && object.Position.length >= 3
      && object.Position.slice(0, 3).every(Number.isFinite);
  }

  function colorForObjectId(objectId) {
    const id = String(objectId || "").toUpperCase();
    if (id.includes("YELLOW")) return "#ffd95a";
    if (id.includes("RED")) return "#ff6578";
    if (id.includes("GREEN")) return "#62e7a8";
    if (id.includes("BLUE")) return "#58bfff";
    if (id.includes("PINK")) return "#ff7cce";
    if (id.includes("WHITE") || id.includes("LIGHT")) return "#eefcff";
    if (id === "^BASE_FLAG" || id === "^U_PARAGON") return "#ffb15c";
    if (id.includes("WALL") || id.includes("FLOOR") || id.includes("ROOF")) return "#4ca3bd";
    return "#79dff3";
  }

  function chooseAxes(objects) {
    const minimum = [Infinity, Infinity, Infinity];
    const maximum = [-Infinity, -Infinity, -Infinity];
    objects.forEach(({Position}) => {
      for (let axis = 0; axis < 3; axis += 1) {
        minimum[axis] = Math.min(minimum[axis], Position[axis]);
        maximum[axis] = Math.max(maximum[axis], Position[axis]);
      }
    });
    const spans = minimum.map((value, axis) => maximum[axis] - value);
    const axes = [0, 1, 2]
      .sort((first, second) => spans[second] - spans[first])
      .slice(0, 2)
      .sort((first, second) => first - second);
    if (spans[axes[0]] <= 1e-8 && spans[axes[1]] <= 1e-8) return {axes: [0, 1], minimum, maximum, spans};
    return {axes, minimum, maximum, spans};
  }

  function round(value) {
    return Math.round(value * 100) / 100;
  }

  function buildSchematic(source, options = {}) {
    const objects = (Array.isArray(source) ? source : source?.objects || []).filter(isPlacedObject);
    if (!objects.length) return null;

    const selection = chooseAxes(objects);
    const {axes} = selection;
    const [horizontalAxis, verticalAxis] = axes;
    const isFrontView = horizontalAxis === 0 && verticalAxis === 1;
    const minimum = [...selection.minimum];
    const maximum = [...selection.maximum];
    if (isFrontView) {
      objects.filter((object) => object.ObjectID === "^C_WALL").forEach(({Position}) => {
        minimum[0] = Math.min(minimum[0], Position[0] - WALL_SIZE[0] / 2);
        maximum[0] = Math.max(maximum[0], Position[0] + WALL_SIZE[0] / 2);
        minimum[1] = Math.min(minimum[1], Position[1] - WALL_SIZE[1] / 2);
        maximum[1] = Math.max(maximum[1], Position[1] + WALL_SIZE[1] / 2);
      });
    }
    const rawHorizontalSpan = maximum[horizontalAxis] - minimum[horizontalAxis];
    const rawVerticalSpan = maximum[verticalAxis] - minimum[verticalAxis];
    const horizontalSpan = Math.max(rawHorizontalSpan, 1);
    const verticalSpan = Math.max(rawVerticalSpan, 1);
    const plotWidth = WIDTH - PADDING.left - PADDING.right;
    const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;
    const scale = Math.min(plotWidth / horizontalSpan, plotHeight / verticalSpan) * 0.9;
    const centerHorizontal = (minimum[horizontalAxis] + maximum[horizontalAxis]) / 2;
    const centerVertical = (minimum[verticalAxis] + maximum[verticalAxis]) / 2;
    const centerX = PADDING.left + plotWidth / 2;
    const centerY = PADDING.top + plotHeight / 2;
    const project = (object) => ({
      x: centerX + (object.Position[horizontalAxis] - centerHorizontal) * scale,
      y: centerY - (object.Position[verticalAxis] - centerVertical) * scale,
    });
    const backdrop = [];
    const parts = [];

    objects.forEach((object) => {
      const point = project(object);
      const hidden = object.Visible === false || String(object.Visible).toLowerCase() === "false";
      if (isFrontView && object.ObjectID === "^C_WALL") {
        backdrop.push(`<rect x="${round(point.x - WALL_SIZE[0] * scale / 2)}" y="${round(point.y - WALL_SIZE[1] * scale / 2)}" width="${round(WALL_SIZE[0] * scale)}" height="${round(WALL_SIZE[1] * scale)}" rx="4" fill="#081015" stroke="#315565" stroke-width="2" opacity="${hidden ? 0.22 : 0.94}"/>`);
        return;
      }
      const color = colorForObjectId(object.ObjectID);
      const light = /LIGHT/i.test(object.ObjectID);
      const radius = light ? Math.max(4.2, Math.min(7.5, scale * 0.12)) : 4.5;
      parts.push(`<circle cx="${round(point.x)}" cy="${round(point.y)}" r="${round(radius)}" fill="${color}" stroke="#eaffff" stroke-opacity="${light ? 0.7 : 0.28}" stroke-width="1" opacity="${hidden ? 0.22 : 0.94}"${light ? ' filter="url(#partGlow)"' : ""}/>`);
    });

    const passLabel = options.label ? String(options.label).replace(/[<>&]/g, "") : "Latest build";
    const axesLabel = `${AXIS_NAMES[horizontalAxis]}/${AXIS_NAMES[verticalAxis]} view`;
    const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <pattern id="previewGrid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#244454" stroke-width="1" opacity="0.42"/></pattern>
    <filter id="partGlow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="#061521"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#previewGrid)"/>
  <text x="${PADDING.left}" y="31" fill="#dff8ff" font-family="system-ui, sans-serif" font-size="17" font-weight="700">${passLabel}</text>
  <text x="${WIDTH - PADDING.right}" y="31" fill="#8ec7d5" font-family="system-ui, sans-serif" font-size="14" text-anchor="end">${axesLabel}</text>
  ${backdrop.join("\n  ")}
  ${parts.join("\n  ")}
  <text x="${PADDING.left}" y="${HEIGHT - 20}" fill="#87aeb9" font-family="system-ui, sans-serif" font-size="13">Browser schematic · ${objects.length.toLocaleString()} placed parts · verify exact appearance in BBA or the game</text>
</svg>`;
    return {
      svg,
      axes: [AXIS_NAMES[horizontalAxis], AXIS_NAMES[verticalAxis]],
      objectCount: objects.length,
    };
  }

  root.DaedalusPreview = {buildSchematic, chooseAxes, colorForObjectId};
})(typeof window !== "undefined" ? window : globalThis);
