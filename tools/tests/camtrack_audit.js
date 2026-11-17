#!/usr/bin/env node
/* camtrack_audit.js — JS ground truth for the camera audit.
 *
 * Extracts the PURE playback math (utils, phase01/angleAt, curve/polyline/
 * zigzag LUTs, normalFromTangent, evalTrack, cycleDuration, sanitizeTrack)
 * VERBATIM from the downloaded camtrack.html and runs them over the test
 * camdat, dumping the exact same CSV format as fog_poc --cam-dump.
 *
 * usage: node camtrack_audit.js camtrack.html camtest_tracks.json outPrefix
 * writes: outPrefix_<trackIndex>.csv  (one per track)
 */
'use strict';
const fs = require('fs');

const [, , htmlPath, jsonPath, outPrefix] = process.argv;
if (!htmlPath || !jsonPath || !outPrefix) {
  console.error('usage: node camtrack_audit.js camtrack.html tracks.json outPrefix');
  process.exit(1);
}
const html = fs.readFileSync(htmlPath, 'utf8');
const lines = html.split('\n');

/* --- verbatim extractor: single-line consts + column-0-brace functions --- */
function extractFunction(name) {
  const start = lines.findIndex(l =>
    l.startsWith(`function ${name}(`) || l.startsWith(`function ${name} (`));
  if (start < 0) throw new Error(`function ${name} not found`);
  let depth = 0, end = -1;
  for (let i = start; i < lines.length; i++) {
    const l = lines[i];
    for (const ch of l) {
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
    }
    if (depth === 0 && i > start && l.trim().endsWith('}')) { end = i; break; }
    if (depth === 0 && i === start && l.trim().endsWith('}')) { end = i; break; }
  }
  if (end < 0) throw new Error(`function ${name}: no closing brace`);
  return lines.slice(start, end + 1).join('\n');
}
function extractConst(name) {
  const idx = lines.findIndex(l => l.startsWith(`const ${name} =`) || l.startsWith(`const ${name}=`));
  if (idx < 0) throw new Error(`const ${name} not found`);
  /* single-line const (possibly with trailing comment) */
  const l = lines[idx];
  const m = l.match(/^const\s+\w+\s*=\s*(.*?);/);
  if (m) return l;
  /* multi-line const object — take until a line ending with ';' at depth 0 */
  let depth = 0, end = -1;
  for (let i = idx; i < lines.length; i++) {
    const s = lines[i];
    for (const ch of s) {
      if (ch === '{' || ch === '(' || ch === '[') depth++;
      else if (ch === '}' || ch === ')' || ch === ']') depth--;
    }
    if (depth === 0 && s.trim().endsWith(';')) { end = i; break; }
  }
  return lines.slice(idx, end + 1).join('\n');
}

const parts = [];
/* utils (verbatim) */
parts.push(extractConst('DEG'));
parts.push(extractConst('clamp'));
parts.push(extractConst('dist3'));
parts.push(extractConst('lerp3'));
parts.push(extractConst('sub3'));
parts.push(extractConst('add3'));
parts.push(extractConst('cross3'));
parts.push(extractFunction('normSafe'));
/* playback math (verbatim) */
parts.push(extractFunction('tri01'));
parts.push(extractFunction('phase01'));
parts.push(extractFunction('angleAt'));
parts.push(extractConst('CURVE_SAMPLES'));
parts.push(extractConst('curveCache'));
parts.push(extractFunction('catmullRom'));
parts.push(extractFunction('catmullRomTangent'));
parts.push(extractFunction('curveLUT'));
parts.push(extractFunction('curveParamAt'));
parts.push(extractFunction('curvePosAt'));
parts.push(extractFunction('curveTangentAt'));
parts.push(extractFunction('pointsLUT'));
parts.push(extractConst('polyCache'));
parts.push(extractFunction('polylineLUT'));
parts.push(extractFunction('polyParamAt'));
parts.push(extractFunction('polyPosAt'));
parts.push(extractFunction('polyTangentAt'));
parts.push(extractFunction('zigzagPoints'));
parts.push(extractConst('zigCache'));
parts.push(extractFunction('zigzagLUT'));
parts.push(extractFunction('normalFromTangent'));
parts.push(extractFunction('evalTrack'));
parts.push(extractFunction('cycleDuration'));
/* sanitize (verbatim; newId stubbed — ids do not affect playback) */
parts.push('function newId() { return "audit"; }');
parts.push(extractFunction('num'));
parts.push(extractFunction('vec3'));
parts.push(extractFunction('pick'));
parts.push(extractFunction('sanitizeTrack'));

const libSrc = parts.join('\n');
fs.writeFileSync(outPrefix + '_extracted.js', libSrc);
const lib = new Function(libSrc + '\nreturn { evalTrack, cycleDuration, sanitizeTrack, DEG };')();
const { evalTrack, cycleDuration, sanitizeTrack } = lib;

/* --- run over the test camdat (same traversal as fog_poc camdat_load) --- */
const doc = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
const model = doc.models.find(m => m.file === 'THRF9FD.glb') || doc.models[0];
const tracks = model.tracks.map(raw => sanitizeTrack(raw));
if (tracks.some(t => !t)) throw new Error('a test track failed sanitizeTrack (JS side)');

/* fixed dump parameters — must match the C --cam-dump code exactly */
const STEPS = 400;

tracks.forEach((tr, idx) => {
  let T = cycleDuration(tr);
  if (!isFinite(T) || T <= 0) T = 8;              /* static: 8 s window */
  let out = 'idx,t,px,py,pz,hasLook,lx,ly,lz,yaw,pitch,fov\n';
  for (let k = 0; k <= STEPS; k++) {
    const t = k / STEPS * T;
    const ev = evalTrack(tr, t);
    const yaw = ev.yaw == null ? 0 : ev.yaw;
    const pitch = ev.pitch == null ? 0 : ev.pitch;
    const la = ev.lookAt == null ? [0, 0, 0] : ev.lookAt;
    const has = ev.lookAt != null ? 1 : 0;
    out += `${k},${t.toPrecision(17)},${ev.pos[0].toPrecision(17)},` +
           `${ev.pos[1].toPrecision(17)},${ev.pos[2].toPrecision(17)},` +
           `${has},${la[0].toPrecision(17)},${la[1].toPrecision(17)},` +
           `${la[2].toPrecision(17)},${yaw.toPrecision(17)},` +
           `${pitch.toPrecision(17)},${ev.fovDeg.toPrecision(17)}\n`;
  }
  fs.writeFileSync(`${outPrefix}_${idx}.csv`, out);
  console.log(`track ${idx} (${tr.type}/${tr.lookMode}/${tr.loopMode}) T=${T.toFixed(4)} -> ${outPrefix}_${idx}.csv`);
});
console.log(`JS ground truth: ${tracks.length} tracks x ${STEPS + 1} samples`);
