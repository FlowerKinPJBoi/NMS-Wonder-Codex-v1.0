"use strict";

(function exposeDaedalusSignGenerator(root) {
  const P = {
    TL: [0, 2], TR: [1, 2], ML: [0, 1], MR: [1, 1], BL: [0, 0], BR: [1, 0],
    TC: [0.5, 2], MC: [0.5, 1], BC: [0.5, 0]
  };
  const s = (a, b) => [P[a], P[b]];
  const GLYPHS = {
    A: [s("TL", "TR"), s("TL", "ML"), s("TR", "MR"), s("ML", "MR"), s("ML", "BL"), s("MR", "BR")],
    B: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("ML", "MR"), s("BL", "BR"), s("TR", "MR"), s("MR", "BR")],
    C: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("BL", "BR")],
    D: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("BL", "BR")],
    E: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("ML", "MR"), s("BL", "BR")],
    F: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("ML", "MR")],
    G: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("BL", "BR"), s("MR", "BR"), [[0.5, 1], [1, 1]]],
    H: [s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("ML", "MR")],
    I: [s("TL", "TR"), s("TC", "MC"), s("MC", "BC"), s("BL", "BR")],
    J: [s("TL", "TR"), s("TR", "MR"), s("MR", "BR"), s("BL", "BR"), [[0, 0], [0, 0.55]]],
    K: [s("TL", "ML"), s("ML", "BL"), s("ML", "TR"), s("ML", "BR")],
    L: [s("TL", "ML"), s("ML", "BL"), s("BL", "BR")],
    M: [s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("TL", "MC"), s("MC", "TR")],
    N: [s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("TL", "MC"), s("MC", "BR")],
    O: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("BL", "BR")],
    P: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("ML", "MR")],
    Q: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("BL", "BR"), s("MC", "BR")],
    R: [s("TL", "TR"), s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("ML", "MR"), s("MC", "BR")],
    S: [s("TL", "TR"), s("TL", "ML"), s("ML", "MR"), s("MR", "BR"), s("BL", "BR")],
    T: [s("TL", "TR"), s("TC", "MC"), s("MC", "BC")],
    U: [s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("BL", "BR")],
    V: [s("TL", "ML"), s("ML", "BC"), s("TR", "MR"), s("MR", "BC")],
    W: [s("TL", "ML"), s("ML", "BL"), s("TR", "MR"), s("MR", "BR"), s("BL", "MC"), s("MC", "BR")],
    X: [s("TL", "MC"), s("MC", "BR"), s("TR", "MC"), s("MC", "BL")],
    Y: [s("TL", "MC"), s("TR", "MC"), s("MC", "BC")],
    Z: [s("TL", "TR"), s("TR", "MC"), s("MC", "BL"), s("BL", "BR")],
    "!": [s("TC", "MC"), [[0.5, 0.9], [0.5, 0.2]]],
    "?": [s("TL", "TR"), s("TR", "MR"), s("MR", "MC"), [[0.5, 0.9], [0.5, 0.2]]]
  };
  const LEARNED_GLYPHS = new Set("FISHNGARMC T".replaceAll(" ", "").split(""));

  function round(value) {
    return Math.round(value * 1e6) / 1e6;
  }

  function makeRecord(index, objectId, userData, position, up, at, timestampBase) {
    return {
      Timestamp: timestampBase + index,
      ObjectID: objectId,
      UserData: userData,
      Position: position.map(round),
      Up: up.map(round),
      At: at.map(round)
    };
  }

  function textWidth(text, glyphWidth, gap, spaceWidth) {
    const widths = [...text].map((character) => character === " " ? spaceWidth : glyphWidth);
    return widths.reduce((total, width) => total + width, 0) + Math.max(0, widths.length - 1) * gap;
  }

  function generateSignPrefab(options = {}) {
    const text = String(options.text || "Cavern Below!").toUpperCase();
    const fontGrammar = options.fontGrammar || "flat-panel-block";
    const glyphWidth = 1;
    const glyphHeight = 2;
    const gap = fontGrammar === "segment-tech" ? 0.34 : 0.42;
    const spaceWidth = 0.7;
    const width = textWidth(text, glyphWidth, gap, spaceWidth);
    const wallWidth = 5.333333;
    const wallHeight = 3.333333;
    const wallColumns = Math.max(1, Math.ceil((width + 1.4) / wallWidth));
    const timestampBase = Number.isInteger(options.timestampBase)
      ? options.timestampBase
      : Math.floor(Date.now() / 1000);
    const letterObjectId = fontGrammar === "pill-light-rounded" ? "^S_LIGHTSTRIP0" : "^BUILDFLATPANEL";
    const letterUpMagnitude = fontGrammar === "pill-light-rounded" ? 0.4 : fontGrammar === "segment-tech" ? 0.18 : 0.25;
    const letterUserData = Number.isInteger(options.letterUserData) ? options.letterUserData : 8;
    const backdropUserData = Number.isInteger(options.backdropUserData) ? options.backdropUserData : 1;
    const records = [];

    for (let column = 0; column < wallColumns; column += 1) {
      const x = (column - (wallColumns - 1) / 2) * wallWidth;
      records.push(makeRecord(
        records.length,
        "^C_WALL",
        backdropUserData,
        [x, wallHeight / 2, 0],
        [0, 1, 0],
        [0, 0, 1],
        timestampBase
      ));
    }

    let cursor = -width / 2;
    const baseline = 0.66;
    const glyphEvidence = [];
    [...text].forEach((character) => {
      if (character === " ") {
        cursor += spaceWidth + gap;
        return;
      }
      const strokes = GLYPHS[character] || GLYPHS["?"];
      strokes.forEach(([start, end]) => {
        const startX = cursor + start[0];
        const startY = baseline + start[1];
        const endX = cursor + end[0];
        const endY = baseline + end[1];
        records.push(makeRecord(
          records.length,
          letterObjectId,
          letterUserData,
          [(startX + endX) / 2, (startY + endY) / 2, -0.18],
          [0, 0, -letterUpMagnitude],
          [endX - startX, endY - startY, 0],
          timestampBase
        ));
      });
      glyphEvidence.push({
        character,
        source: LEARNED_GLYPHS.has(character) ? "FFC_VERIFIED_GLYPH_FAMILY" : "PROCEDURAL_SEGMENT_GRAMMAR"
      });
      cursor += glyphWidth + gap;
    });

    return {
      prefab: { Prefab: records, Tools: [] },
      manifest: {
        schema: "wonder-codex.daedalus.sign-generation.v0.1",
        text,
        fontGrammar,
        objectIdOnly: true,
        backdrop: {
          objectId: "^C_WALL",
          userData: backdropUserData,
          requestedColour: "black",
          paletteEvidence: "LEGACY2_BLACK_AND_YELLOW_PRIMARY"
        },
        lettering: {
          objectId: letterObjectId,
          userData: letterUserData,
          requestedColour: "red",
          paletteEvidence: "LEGACY9_RED_AND_WHITE_PRIMARY"
        },
        placedObjectCount: records.length,
        backdropCount: wallColumns,
        letteringCount: records.length - wallColumns,
        glyphEvidence,
        calibrationSources: ["FFC Sign.nmsprefab", "FFCSign2.NMSPREFAB"],
        geometryStatus: "GENERATED_REQUIRES_IN_GAME_REVIEW"
      }
    };
  }

  const api = { GLYPHS, LEARNED_GLYPHS, generateSignPrefab };
  root.DaedalusSignGenerator = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
