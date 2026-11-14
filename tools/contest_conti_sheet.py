"""storyboard_v5(+v5b) 시안을 컷별로 모아 sheet.html 한 장으로 만든다. 추천 시드(selection_v5.json)를 표시하고 사용자가 고를 수 있다.
사용: python tools/contest_conti_sheet.py
선택 결과는 브라우저에 자동 저장되고, 아래 '선택 결과' 칸을 복사해 Claude에게 붙여넣거나 JSON으로 내려받는다.
"""
import json, html
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "jobs" / "contest"
cuts = json.loads((R / "conti_v3" / "cuts_v3.json").read_text(encoding="utf-8"))
sel = json.loads((R / "selection_v5.json").read_text(encoding="utf-8"))
pick, issues = sel["pick"], sel["issues"]
e = html.escape


def find(c, s):
    for d in ("storyboard_v5b", "storyboard_v5"):  # v5b = 재제출분 우선
        out = R / d / f"{c}_s{s}" / "out"
        p = next(out.glob("*.jpg"), None) if out.exists() else None
        if p:
            return p.relative_to(R).as_posix()


rows, meta = [], {}
for c in cuts:
    imgs = {s: find(c["id"], s) for s in (1, 2)}
    if not any(imgs.values()):
        continue
    cid, rec = c["id"], pick.get(c["id"])
    meta[cid] = {"title": c["title"], "rec": rec}
    warn = [v for k, v in issues.items() if cid in k.split(",")]
    cells = "".join(
        f'<label class="cell{" rec" if rec == s else ""}"><img src="../{p}" style="width:100%;display:block">'
        f'<span><input type="radio" name="{cid}" value="{s}"{" checked" if rec == s else ""}> 시드{s}'
        f'{" <b class=badge>★ 추천</b>" if rec == s else ""}</span></label>' for s, p in imgs.items() if p)
    rows.append(f'<section id="{cid}"><h3>{cid} · {e(c["title"])} <small>{c["t0"]}~{c["t1"]}초</small></h3>{cells}'
                f'<label class="cell redo"><span><input type="radio" name="{cid}" value="redo"> 재생성</span>'
                f'<input type="text" name="{cid}_memo" placeholder="재생성 이유 (예: 성문이 중국식)" size="26"></label>'
                f'<p class="n">{e(c["note"])}</p>' + "".join(f'<p class="w">⚠ {e(w)}</p>' for w in warn) + "</section>")

css = ("body{font-family:'Malgun Gothic';margin:16px 16px 260px}section{border-bottom:1px solid #ccc;padding:8px 0}.cell{display:inline-flex;flex-direction:column;width:408px;box-sizing:border-box;padding:2px;margin:4px;border:3px solid transparent;"
       "border-radius:6px;vertical-align:top;cursor:pointer}.cell.rec{border-color:#f5a623}.cell:has(input:checked){border-color:#2a7ae2;background:#eaf2ff}.badge{color:#c27800}"
       ".redo{width:230px;padding:8px;background:#fff4f4;gap:6px}.n{color:#7a4a00;font-size:13px;margin:2px}.w{color:#c0392b;font-size:13px;margin:2px}"
       "#bar{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:2px solid #2a7ae2;padding:8px 16px;box-shadow:0 -2px 8px #0003}"
       "textarea{width:100%;height:120px;font-size:12px}button{margin:4px 6px 4px 0;padding:6px 12px}")
js = """
const META=%s;
const key='sheet_v5_choice';
const saved=JSON.parse(localStorage.getItem(key)||'{}');
for(const id in saved){const v=saved[id];const r=document.querySelector(`input[name=${id}][value="${v.c}"]`);if(r)r.checked=true;const m=document.querySelector(`input[name=${id}_memo]`);if(m)m.value=v.memo||'';}
function collect(){const o={};for(const id in META){const r=document.querySelector(`input[name=${id}]:checked`);const m=document.querySelector(`input[name=${id}_memo]`);o[id]={c:r?r.value:'',memo:m?m.value:''};}return o;}
function render(){const o=collect();localStorage.setItem(key,JSON.stringify(o));let ok=0,redo=0,diff=0;const lines=[];
 for(const id in o){const c=o[id].c;if(c==='redo'){redo++;lines.push(id+': 재생성'+(o[id].memo?' ('+o[id].memo+')':''));}else{ok++;if(String(META[id].rec)!==c)diff++;lines.push(id+': 시드'+c);}}
 document.getElementById('sum').textContent=`선택 ${ok}컷 · 재생성 ${redo}컷 · 추천과 다른 선택 ${diff}컷`;
 document.getElementById('out').value='[시안 선택 v5]\\n'+lines.join('\\n');return o;}
document.addEventListener('input',render);
function resetRec(){for(const id in META){const r=document.querySelector(`input[name=${id}][value="${META[id].rec}"]`);if(r)r.checked=true;const m=document.querySelector(`input[name=${id}_memo]`);if(m)m.value='';}render();}
function copyOut(){navigator.clipboard.writeText(document.getElementById('out').value);document.getElementById('sum').textContent+=' — 복사됨';}
function save(){const b=new Blob([JSON.stringify(collect(),null,1)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='selection_user_v5.json';a.click();}
render();
""" % json.dumps({k: v for k, v in meta.items()}, ensure_ascii=False)
bar = ('<div id="bar"><b id="sum"></b> <button onclick="resetRec()">추천으로 되돌리기</button><button onclick="copyOut()">선택 결과 복사</button>'
       '<button onclick="save()">JSON으로 저장</button><textarea id="out" readonly></textarea></div>')
(R / "storyboard_v5" / "sheet.html").write_text(
    f"<!doctype html><meta charset=utf-8><title>시안 선택 v5</title><style>{css}</style>"
    f"<h1>시안 시트 v5 (480p) — 마음에 드는 시드를 고르세요</h1>"
    f"<p>주황 테두리 ★ = 제 추천, 파란 테두리 = 현재 선택. 재생성이 필요하면 '재생성'을 고르고 이유를 적으세요. 선택은 이 브라우저에 자동 저장됩니다. "
    f"다 고르면 맨 아래 <b>선택 결과 복사</b>를 눌러 Claude에게 붙여넣어 주세요.</p>" + "".join(rows) + bar + f"<script>{js}</script>", encoding="utf-8")
print("ok", len(rows), "cuts")
