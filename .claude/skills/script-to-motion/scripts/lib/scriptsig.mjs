/**
 * scriptsig.mjs — a fingerprint of everything in script.json that js/cues.js is built from.
 *
 * tts.mjs stores it in window.VIDEO_DATA.scriptSig; check.mjs recomputes it from script.json, so any edit that
 * tts.mjs hasn't turned into cues.js yet (a line, its spoken form, a gap, a cut, leadIn/gap/tail, the voice, narration on/off)
 * is reported as "re-run tts.mjs". Projects made before the field existed have no scriptSig: callers fall back.
 */
import crypto from 'node:crypto';

export function scriptSignature(script = {}) {
  const num = (v) => (v === undefined || v === null || v === '' ? null : Number(v));
  const body = {
    title: script.title ?? '',
    lang: script.lang ?? '',
    narration: script.narration !== false,
    voice: script.voice ?? '',
    model: script.model ?? '',
    temperature: num(script.temperature),
    top_p: num(script.top_p),
    leadIn: num(script.leadIn),
    gap: num(script.gap),
    tail: num(script.tail),
    cues: (Array.isArray(script.cues) ? script.cues : []).map((c) => ({
      id: c.id ?? '',
      say: c.say ?? '',
      text: c.text ?? null,
      gapAfter: num(c.gapAfter),
      captions: Array.isArray(c.captions) ? c.captions.map(String) : null,
      ...(c.cut != null ? { cut: c.cut } : {}),   // (only when set: a project without cuts keeps its signature)
    })),
  };
  return crypto.createHash('sha256').update(JSON.stringify(body)).digest('hex').slice(0, 16);
}
