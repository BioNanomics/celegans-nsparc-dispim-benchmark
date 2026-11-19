"use strict";

// Run with: node --test tests/test_spot_annotation_viewer.cjs
// These tests execute the viewer's real CSV/validation functions against
// artificial records. They do not open NIS, read ND2 pixels, or create labels.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(
  path.resolve(__dirname, "..", "scripts", "assets", "spot_annotation.html"),
  "utf8",
);
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
const js = scripts.at(-1)[1];

function section(start, end) {
  const a = js.indexOf(start);
  const b = js.indexOf(end, a + start.length);
  assert.ok(a >= 0 && b > a, `Viewer function section not found: ${start}`);
  return js.slice(a, b);
}

const declarations = section("    const ANNOTATION_FIELDS=", "    const QA=");
const helpers = js.split("\n").filter(
  line => /^    const (text=|rowKey=|reviewKey=|sameRow=)/.test(line),
).join("\n");
const pureFunctions = section("    function requiredId(", "    function saveDraft(");
const makeCore = new Function("manifest", "frameByIndex", declarations + helpers +
  pureFunctions + "return {validateManifest,normalizeAnnotation,normalizeReview," +
  "parseCSV,decodeCSV,csvText,rowKey,reviewKey,sameRow,ANNOTATION_FIELDS,REVIEW_FIELDS};");

function fixture() {
  const manifest = {
    schema_version: 1,
    width: 1024,
    height: 1024,
    pixel_um: 0.506691,
    source_sha256: "a".repeat(64),
    plan_sha256: "b".repeat(64),
    channels: ["GFP", "RFP", "TD"].map(name => ({
      name, display_lo: 0, display_hi: 4000,
    })),
    frames: Array.from({ length: 151 }, (_, i) => ({
      frame_index: i,
      time_s: i * 4,
      split: i < 60 ? "development" : i < 90 ? "buffer" : "evaluation",
      secondary_review: false,
      images: { GFP: `frames/${i}_GFP.png`, RFP: `frames/${i}_RFP.png`, TD: `frames/${i}_TD.png` },
    })),
  };
  const api = makeCore(manifest, new Map(manifest.frames.map(f => [f.frame_index, f])));
  const annotation = {
    source_sha256: manifest.source_sha256, plan_sha256: manifest.plan_sha256,
    reviewer_id: "TEST_R1", target_id: "TEST_S01", frame_index: 0, time_s: 0,
    split: "development", channel: "GFP", visibility: "visible",
    x_px: 511.5, y_px: 511.5,
    x_um: 511.5 * manifest.pixel_um, y_um: 511.5 * manifest.pixel_um,
    reason: "", notes: 'Artificial test, with a "quote"\nand a second line.',
    reviewed_at: "2026-11-18T23:10:00.000Z",
  };
  const review = {
    source_sha256: manifest.source_sha256, plan_sha256: manifest.plan_sha256,
    reviewer_id: "", frame_index: 0, time_s: 0, split: "development",
    review_status: "not_reviewed", notes: "", reviewed_at: "",
  };
  return { manifest, api, annotation, review };
}

function file(name, contents) {
  return { name, size: Buffer.byteLength(contents), text: async () => contents };
}

function importer(api, state = { annotations: new Map(), reviews: new Map() }, qa = false) {
  const messages = [];
  const input = { value: "selected.csv" };
  let saves = 0;
  const code = section("    async function importFiles(", "    function provenance(");
  const importFiles = new Function(
    "QA", "state", "decodeCSV", "rowKey", "reviewKey", "ANNOTATION_FIELDS", "REVIEW_FIELDS",
    "sameRow", "saveDraft", "loadTargetRecord", "renderRecords", "draw", "announce", "$",
    code + "return importFiles;",
  )(qa, state, api.decodeCSV, api.rowKey, api.reviewKey, api.ANNOTATION_FIELDS, api.REVIEW_FIELDS,
    api.sameRow, () => saves++, () => {}, () => {}, () => {},
    (message, kind) => messages.push({ message, kind }), () => input);
  return { state, messages, input, importFiles, saves: () => saves };
}

test("template has one manifest placeholder, unique IDs and syntactically valid JavaScript", () => {
  assert.equal(html.split("__ANNOTATION_MANIFEST__").length - 1, 1);
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(x => x[1]);
  assert.equal(new Set(ids).size, ids.length);
  assert.doesNotThrow(() => new Function(js));
});

test("manifest accepts version 1 and rejects unsupported or malformed calibration", () => {
  const { manifest, api } = fixture();
  assert.equal(api.validateManifest(manifest), manifest);
  for (const version of [2, "1", null, undefined]) {
    assert.throws(() => api.validateManifest({ ...manifest, schema_version: version }), /requires version 1/);
  }
  assert.throws(() => api.validateManifest({ ...manifest, pixel_um: 0 }), /pixel_um/);
});

test("manifest rejects remote or escaping image paths", () => {
  const { manifest, api } = fixture();
  for (const image of ["../private.png", "%2e%2e/private.png", "https://example.test/frame.png", "/frame.png"]) {
    const frames = structuredClone(manifest.frames);
    frames[0].images.GFP = image;
    assert.throws(() => api.validateManifest({ ...manifest, frames }), /relative PNG/);
  }
});

test("CSV roundtrip preserves commas, escaped quotes and embedded line breaks", () => {
  const { api, annotation } = fixture();
  const row = api.normalizeAnnotation(annotation, "test");
  assert.deepEqual(api.decodeCSV(api.csvText(api.ANNOTATION_FIELDS, [row]), "roundtrip").rows, [row]);
  assert.deepEqual(api.parseCSV('\uFEFFa,b\r\n1,"two, ""quoted""\nlines"\r\n'),
    [["a", "b"], ["1", 'two, "quoted"\nlines']]);
});

test("header-only annotations mean zero completed labels", () => {
  const { api } = fixture();
  const decoded = api.decodeCSV(api.csvText(api.ANNOTATION_FIELDS, []), "initial");
  assert.equal(decoded.kind, "annotations");
  assert.deepEqual(decoded.rows, []);
});

test("CSV rejects unclosed quotes and text after a closing quote", () => {
  const { api } = fixture();
  assert.throws(() => api.parseCSV('a,b\n1,"unfinished'), /unclosed/);
  assert.throws(() => api.parseCSV('a,b\n1,"closed"junk'), /unexpected/);
});

test("CSV rejects missing, unknown, reordered or inconsistent columns", () => {
  const { api, annotation } = fixture();
  const fields = [...api.ANNOTATION_FIELDS];
  assert.throws(() => api.decodeCSV(api.csvText(fields.slice(1), [annotation]), "missing"), /columns/);
  assert.throws(() => api.decodeCSV(api.csvText([...fields, "unknown"], [annotation]), "extra"), /columns/);
  [fields[0], fields[1]] = [fields[1], fields[0]];
  assert.throws(() => api.decodeCSV(api.csvText(fields, [annotation]), "reordered"), /columns/);
  assert.throws(() => api.decodeCSV(api.ANNOTATION_FIELDS.join(",") + "\nonly,two\n", "short"), /column count/);
});

test("duplicate per-reviewer target/frame annotations are rejected", () => {
  const { api, annotation } = fixture();
  assert.throws(() => api.decodeCSV(api.csvText(api.ANNOTATION_FIELDS, [annotation, annotation]), "duplicate"), /duplicate/);
});

test("annotations require matching source and plan hashes", () => {
  const { api, annotation } = fixture();
  for (const column of ["source_sha256", "plan_sha256"]) {
    assert.throws(() => api.normalizeAnnotation({ ...annotation, [column]: "c".repeat(64) }, "wrong hash"), /hash/);
  }
  assert.equal(api.normalizeAnnotation({ ...annotation, source_sha256: annotation.source_sha256.toUpperCase() }, "case").source_sha256,
    annotation.source_sha256);
});

test("frame indices, times and planned splits cannot be relabeled", () => {
  const { api, annotation } = fixture();
  assert.throws(() => api.normalizeAnnotation({ ...annotation, frame_index: 151 }, "frame"), /outside/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, frame_index: 0.5 }, "frame"), /outside/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, time_s: 1 }, "time"), /time_s/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, split: "evaluation" }, "split"), /split/);
});

test("visible centroids use finite native pixel-centre bounds", () => {
  const { api, annotation, manifest } = fixture();
  for (const position of [0, 511.5, 1023]) {
    assert.equal(api.normalizeAnnotation({ ...annotation, x_px: position, y_px: position,
      x_um: position * manifest.pixel_um, y_um: position * manifest.pixel_um }, "valid").x_px, position);
  }
  for (const position of [-1, 1024, Infinity, NaN]) {
    assert.throws(() => api.normalizeAnnotation({ ...annotation, x_px: position,
      x_um: position * manifest.pixel_um }, "bounds"), /outside|finite/);
  }
  assert.throws(() => api.normalizeAnnotation({ ...annotation, x_px: "", y_px: "", x_um: "", y_um: "" }, "missing"), /centroid/);
});

test("micrometre coordinates must match the recorded calibration", () => {
  const { api, annotation } = fixture();
  assert.throws(() => api.normalizeAnnotation({ ...annotation, x_um: annotation.x_um + 1 }, "units"), /pixel_um/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, y_um: "" }, "partial"), /complete/);
});

test("uncertain records need a reason and allow either complete or absent coordinates", () => {
  const { api, annotation } = fixture();
  assert.throws(() => api.normalizeAnnotation({ ...annotation, visibility: "uncertain" }, "uncertain"), /requires a reason/);
  assert.equal(api.normalizeAnnotation({ ...annotation, visibility: "uncertain", reason: "overlap" }, "candidate").visibility, "uncertain");
  assert.equal(api.normalizeAnnotation({ ...annotation, visibility: "uncertain", reason: "not uniquely localizable",
    x_px: "", y_px: "", x_um: "", y_um: "" }, "absent").x_px, null);
});

test("not_visible requires a reason and prohibits a centroid", () => {
  const { api, annotation } = fixture();
  const absent = { ...annotation, visibility: "not_visible", x_px: "", y_px: "", x_um: "", y_um: "" };
  assert.throws(() => api.normalizeAnnotation(absent, "reason"), /requires a reason/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, visibility: "not_visible", reason: "out of plane" }, "coords"), /blank coordinates/);
  assert.equal(api.normalizeAnnotation({ ...absent, reason: "out of plane" }, "valid").x_px, null);
});

test("completed annotations require GFP, coded reviewer/target IDs and timestamp", () => {
  const { api, annotation } = fixture();
  assert.throws(() => api.normalizeAnnotation({ ...annotation, channel: "RFP" }, "channel"), /GFP/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, reviewer_id: "" }, "reviewer"), /Reviewer ID/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, target_id: "" }, "target"), /Target ID/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, reviewed_at: "" }, "date"), /ISO date/);
  assert.throws(() => api.normalizeAnnotation({ ...annotation, visibility: "not_reviewed" }, "placeholder"), /invalid visibility/);
});

test("151 blank frame-review seeds remain explicitly not reviewed", () => {
  const { api, review, manifest } = fixture();
  const rows = manifest.frames.map(f => ({ ...review, frame_index: f.frame_index, time_s: f.time_s, split: f.split }));
  const decoded = api.decodeCSV(api.csvText(api.REVIEW_FIELDS, rows), "initial frame reviews");
  assert.equal(decoded.rows.length, 151);
  assert.ok(decoded.rows.every(r => r.review_status === "not_reviewed" && r.reviewer_id === "" && r.reviewed_at === ""));
});

test("completed/flagged frame reviews require a reviewer and explicit timestamp", () => {
  const { api, review, annotation } = fixture();
  assert.throws(() => api.normalizeReview({ ...review, review_status: "reviewed" }, "review"), /Reviewer ID/);
  assert.throws(() => api.normalizeReview({ ...review, reviewer_id: "TEST_R1", review_status: "reviewed" }, "date"), /ISO date/);
  assert.throws(() => api.normalizeReview({ ...review, reviewer_id: "TEST_R1", review_status: "needs_review", reviewed_at: annotation.reviewed_at }, "flag"), /requires notes/);
  assert.equal(api.normalizeReview({ ...review, reviewer_id: "TEST_R1", review_status: "reviewed", reviewed_at: annotation.reviewed_at }, "done").review_status, "reviewed");
  assert.throws(() => api.normalizeReview({ ...review, reviewed_at: annotation.reviewed_at }, "not reviewed"), /blank reviewed_at/);
});

test("QA blocks CSV downloads in both the export function and button state", () => {
  const messages = [];
  const download = new Function("QA", "announce", section("    function downloadCSV(", "    function exportAnnotations(") + "return downloadCSV;")(
    true, message => messages.push(message),
  );
  // If the QA guard were removed, browser-only Blob/DOM dependencies would be reached.
  assert.doesNotThrow(() => download([], [], "annotations"));
  assert.match(messages[0], /disabled in QA mode/);
  const nodes = new Map();
  const get = id => { if (!nodes.has(id)) nodes.set(id, { setAttribute() {} }); return nodes.get(id); };
  const update = new Function("QA", "state", "frames", "$", "document",
    section("    function updateButtons(", "    function coordinateText(") + "return updateButtons;")(
    true, { frame: 0, mode: "GFP", loading: false, candidate: null, playing: null },
    Array(151), get, { querySelectorAll: () => [] },
  );
  update();
  assert.equal(get("export-annotations").disabled, true);
  assert.equal(get("export-reviews").disabled, true);
});

test("multi-file import validates every file before changing the draft", async () => {
  const { api, annotation, review } = fixture();
  const imp = importer(api);
  await imp.importFiles([
    file("annotations.csv", api.csvText(api.ANNOTATION_FIELDS, [annotation])),
    file("bad_reviews.csv", api.csvText(api.REVIEW_FIELDS, [{ ...review, source_sha256: "c".repeat(64) }])),
  ]);
  assert.equal(imp.state.annotations.size, 0);
  assert.equal(imp.state.reviews.size, 0);
  assert.equal(imp.saves(), 0);
  assert.match(imp.messages.at(-1).message, /Import rejected; draft unchanged/);
  assert.equal(imp.input.value, "");
});

test("conflicting imports preserve existing rows; identical imports are idempotent", async () => {
  const { api, annotation } = fixture();
  const existing = api.normalizeAnnotation(annotation, "existing");
  const imp = importer(api, { annotations: new Map([[api.rowKey(existing), existing]]), reviews: new Map() });
  await imp.importFiles([file("conflict.csv", api.csvText(api.ANNOTATION_FIELDS, [
    { ...annotation, target_id: "TEST_S02" }, { ...annotation, notes: "conflicting change" },
  ]))]);
  assert.equal(imp.state.annotations.size, 1);
  assert.equal(imp.state.annotations.get(api.rowKey(existing)).notes, annotation.notes);
  assert.equal(imp.saves(), 0);
  await imp.importFiles([file("same.csv", api.csvText(api.ANNOTATION_FIELDS, [annotation]))]);
  assert.equal(imp.state.annotations.size, 1);
  assert.match(imp.messages.at(-1).message, /0 new rows, 1 identical/);
});

test("production rejects QA_ONLY_ inputs and valid imports add only the requested rows", async () => {
  const { api, annotation } = fixture();
  const imp = importer(api);
  let reads = 0;
  await imp.importFiles([{ name: "QA_ONLY_annotations.csv", size: 1, text: async () => { reads++; return ""; } }]);
  assert.equal(reads, 0);
  assert.equal(imp.saves(), 0);
  assert.match(imp.messages.at(-1).message, /QA_ONLY_/);
  await imp.importFiles([file("annotations.csv", api.csvText(api.ANNOTATION_FIELDS, [annotation]))]);
  assert.equal(imp.state.annotations.size, 1);
  assert.equal(imp.state.reviews.size, 0);
  assert.equal(imp.saves(), 1);
  assert.match(imp.messages.at(-1).message, /1 new rows/);
});

function numberNavigationHarness() {
  const { manifest } = fixture();
  const state = { frame: 0 };
  const nodes = new Map();
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, {
      value: "0", listeners: new Map(),
      addEventListener(type, fn) { this.listeners.set(type, fn); },
    });
    return nodes.get(id);
  };
  const navigations = [], messages = [];
  const setFrame = index => {
    navigations.push(index); state.frame = index;
    get("frame-number").value = String(index);
    get("frame-slider").value = String(index);
  };
  const navigate = new Function("$", "state", "frames", "frameByIndex", "setFrame", "announce",
    section("    function navigateFrameNumber(", "    function bind(") + "return navigateFrameNumber;")(
    get, state, manifest.frames, new Map(manifest.frames.map(f => [f.frame_index, f])),
    setFrame, message => messages.push(message),
  );
  const bind = new Function("$", "state", "setFrame", "navigateFrameNumber", "canvas", "window", "document",
    "recordAnnotation", "draw", "exportAnnotations", "exportReviews",
    section("    function bind(", "\n    try{\n") + "return bind;")(
    get, state, setFrame, navigate, { addEventListener() {} },
    { addEventListener() {} }, { querySelectorAll: () => [], addEventListener() {} },
    () => {}, () => {}, () => {}, () => {},
  );
  bind();
  return { state, get, navigations, messages };
}

test("Frame index change and explicit Enter commit navigate to the requested frame", () => {
  const h = numberNavigationHarness(), field = h.get("frame-number");
  field.value = "150";
  field.listeners.get("change")({ target: field });
  assert.equal(h.state.frame, 150);
  assert.equal(h.get("frame-slider").value, "150");
  field.value = "38";
  let prevented = false;
  field.listeners.get("keydown")({ key: "Enter", preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  assert.equal(h.state.frame, 38);
  assert.equal(h.get("frame-slider").value, "38");
  assert.deepEqual(h.navigations, [150, 38]);
});

test("Frame index commits normalize invalid values and preserve unchanged selections", () => {
  const h = numberNavigationHarness(), field = h.get("frame-number");
  field.value = "";
  field.listeners.get("change")({ target: field });
  assert.equal(Number(field.value), 0);
  assert.match(h.messages.at(-1), /integer frame from 0 to 150/);
  field.value = "151";
  field.listeners.get("change")({ target: field });
  assert.equal(Number(field.value), 0);
  field.value = "000";
  field.listeners.get("change")({ target: field });
  assert.equal(Number(field.value), 0);
  assert.deepEqual(h.navigations, []);
});
