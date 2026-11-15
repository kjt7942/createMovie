/**
 * phrases.mjs — the phrase times the agent set for a cue (script.json "at"), as seconds from the cue's start in the
 * finished take (after its cut). Nothing is measured here and nothing is decided: the agent read each time off
 * `wave.mjs --cue` (seconds in the take as recorded — the clock a "cut" uses); this only moves it back by the stretches
 * the cut took out before it. Shared by sync.mjs (writes js/sync.js) and check.mjs (compares js/sync.js with it).
 *
 *   "at": { "take": "<the take's id>", "phrases": { "<phrase as written in the cue's text>": <seconds in the take>, … } }
 */

/** sc: the cue in script.json · cue: the same cue in js/cues.js · takeLen: the take's length in seconds (null if unknown)
 *  → { phrases } (seconds from the cue start) · { stale } (set on another take, or no recorded take) · { problems } */
export function phraseTimes(sc, cue, takeLen) {
  const at = sc.at;
  if (at == null) return {};
  const shape = '"at" must be { "take": "<take id>", "phrases": { "<phrase as in the cue\'s text>": <seconds in the take>, … } }';
  if (!at || typeof at !== 'object' || typeof at.take !== 'string' || !at.phrases || typeof at.phrases !== 'object' || Array.isArray(at.phrases)) {
    return { problems: [shape] };
  }
  if (!cue || !cue.take) return { stale: 'the cue has no recorded take' };
  if (at.take !== cue.take) return { stale: `"at" was set on take ${at.take}, the take now is ${cue.take}` };
  const text = cue.text || '';
  const cut = (cue.cut || []).map(([a, b]) => [a, b]).sort((x, y) => x[0] - y[0]);
  const problems = [], phrases = {};
  for (const [p, t] of Object.entries(at.phrases)) {
    if (typeof t !== 'number' || !Number.isFinite(t) || t < 0) { problems.push(`"${p}": ${JSON.stringify(t)} is not a time (seconds in the take, ≥ 0)`); continue; }
    if (takeLen != null && t > takeLen + 0.0005) { problems.push(`"${p}": ${t} s is past the end of the take (${takeLen.toFixed(3)} s)`); continue; }
    if (!p || text.indexOf(p) < 0) { problems.push(`"${p}" is not in the cue's text ("${text}") — write the phrase as when() will look it up`); continue; }
    const inCut = cut.find(([a, b]) => t >= a && t < b);
    if (inCut) { problems.push(`"${p}": ${t} s falls inside the stretch the cut takes out (${inCut[0]}–${inCut[1]} s)`); continue; }
    const gone = cut.reduce((n, [a, b]) => n + (b <= t ? b - a : 0), 0);
    phrases[p] = Math.round((t - gone) * 1000) / 1000;
  }
  return problems.length ? { problems } : { phrases };
}
