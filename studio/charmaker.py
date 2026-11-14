"""캐릭터 생성 탭. 정면 시안(Qwen-Image) -> 고른 정면으로 다른 시점(Qwen-Image-Edit) -> 고른 이미지로 캐릭터 등록.

시안은 batch 큐에서 만든다(jobs/content/<id>, <id>_v). 초안 정보는 정면 배치의 batch.json "character"에 남는다.
"""
import io, random, time

from . import batch, engine

T2I, EDIT = "qwen_image_2512_20B", "qwen_image_edit_plus2_20B"  # 이 PC에서 시험한 모델, 둘 다 상업 이용 가능
SIZES = {"draft": "480x832", "high": "720x1280"}  # 초안 먼저, 마음에 들면 고화질
FRONT = ("Full-body front view, standing straight and facing the viewer, centered, the whole body visible from head to toe, "
         "plain white background, character design reference sheet, no text, no watermark.")
PORTRAIT = "Upper-body portrait facing the viewer, realistic photo, high detail, no text, no watermark."
SHOTS = {"sheet": FRONT, "portrait": PORTRAIT}  # 전신 캐릭터 시트 / 상반신 초상(배경 포함)
SAME = "The same character as in the reference image, with exactly the same face, design, colors, outfit and proportions. "
VIEWS = {  # engine.CHARACTER_VIEWS 키 -> 편집 프롬프트
    "side": SAME + "Full-body side view in profile, facing left, standing, plain white background, no text.",
    "back": SAME + "Full-body back view, seen from directly behind, standing, plain white background, no text.",
    "pose": SAME + "Full-body dynamic pose in three-quarter view, natural expressive action, plain white background, no text.",
}
SEEDS_PER_VIEW = 2
MAX_REFS = 3  # Qwen-Image-Edit Plus가 한 번에 받는 참고 이미지 수
GUIDE = "Use the reference image(s) as the visual guide for this character's face, look and art style. "


def _draft(cid):
    b = batch.load(cid)
    if not b.get("character"):
        raise engine.StudioError("캐릭터 초안이 아닙니다.")
    return b


def _picked(b, prefix=None):
    """prefix로 시작하는 항목(없으면 배치 전체) 중 사용자가 고른 결과 하나. 없으면 None, 둘 이상이면 오류."""
    got = [i for i in b["items"] if (not prefix or i["name"].startswith(prefix + "_")) and i.get("pick") and i["status"] == "done"]
    if len(got) > 1:
        raise engine.StudioError(f"{prefix or '정면'} 시안을 하나만 고르세요. 지금 {len(got)}개를 골랐습니다.")
    return batch.output_file(b["name"], got[0]["name"]) if got else None


def _ref_image(data):
    """올린 참고 이미지를 PNG로 다시 저장한다(형식 확인, 회전 보정, 너무 크면 줄임)."""
    from PIL import Image, ImageOps
    if len(data) > engine.MAX_CHARACTER_IMAGE_BYTES:
        raise engine.StudioError("참고 이미지가 너무 큽니다(최대 30MB).")
    try:
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise engine.StudioError("참고 이미지를 읽지 못했습니다. PNG나 JPG 파일을 올리세요.")
    im.thumbnail((1536, 1536))
    return im


def front(name, description, description_ko, size, count, shot="sheet", background="", refs=()):
    """정면 시안 배치를 만든다. description은 영어 외형 설명(engine.create_character와 같은 규칙).
    refs: 참고 이미지 bytes 목록. 있으면 Qwen-Image-Edit로 그 생김새·그림체를 따라 만든다."""
    name, description = " ".join(str(name or "").split()), " ".join(str(description or "").split())
    if not 1 <= len(name) <= 40:
        raise engine.StudioError("캐릭터 이름을 40자 안으로 입력하세요.")
    if not engine.MIN_TEXT <= len(description) <= engine.MAX_TEXT or any("가" <= c <= "힣" for c in description):
        raise engine.StudioError(f"영어 외형 설명을 {engine.MIN_TEXT}~{engine.MAX_TEXT}자로 넣으세요. 먼저 '영어로 다듬기'를 누르세요.")
    if size not in SIZES:
        raise engine.StudioError("해상도를 고르세요.")
    if shot not in SHOTS:
        raise engine.StudioError("구도를 고르세요.")
    background = " ".join(str(background or "").split()) if shot == "portrait" else ""
    refs = [r for r in refs if r]
    if len(refs) > MAX_REFS:
        raise engine.StudioError(f"참고 이미지는 {MAX_REFS}장까지 올릴 수 있습니다.")
    pictures = [_ref_image(r) for r in refs]
    count = max(1, min(8, int(count or 4)))
    seed = random.randrange(2 ** 31)
    cid = time.strftime("ch%Y%m%d_%H%M%S") + f"_{random.randrange(16 ** 3):03x}"  # 같은 초에 두 번 만들어도 덮어쓰지 않게
    prompt = " ".join(x for x in (description, background and f"Background: {background}.", SHOTS[shot]) if x)
    job = {"model_type": T2I, "prompt": prompt, "resolution": SIZES[size], "batch_size": 1}
    if pictures:
        inputs = batch._dir(cid, False) / "inputs"
        inputs.mkdir(parents=True, exist_ok=True)
        paths = []
        for k, im in enumerate(pictures):
            im.save(inputs / f"ref_{k}.png")
            paths.append((inputs / f"ref_{k}.png").resolve().as_posix())
        job.update(model_type=EDIT, prompt=GUIDE + prompt, video_prompt_type="I", image_refs=paths)
    items = [{"name": f"front_s{k + 1}", "job": dict(job, seed=seed + k)} for k in range(count)]
    batch.create(cid, f"캐릭터 {name} · 정면", items, contest=False)
    batch._update(cid, character={"name": name, "description": description, "description_ko": str(description_ko or "").strip(),
                                  "size": size, "shot": shot, "refs": len(pictures), "views": cid + "_v", "registered": None})
    return cid


def views(cid):
    """고른 정면 하나로 옆·뒤·포즈 시안 배치를 만든다. 다시 누르면 같은 배치를 새 정면으로 바꾼다."""
    b = _draft(cid)
    picked = _picked(b)
    if not picked:
        raise engine.StudioError("정면 시안을 하나 고르세요.")
    seed = random.randrange(2 ** 31)
    body = "Upper-body" if b["character"].get("shot") == "portrait" else "Full-body"  # 초상이면 시점도 상반신으로
    items = [{"name": f"{v}_s{k + 1}", "job": {"model_type": EDIT, "prompt": f"{prompt.replace('Full-body', body)} {b['character']['description']}",
                                               "video_prompt_type": "I", "image_refs": [picked.as_posix()],
                                               "resolution": SIZES[b["character"]["size"]], "batch_size": 1, "seed": seed + 100 * n + k}}
             for n, (v, prompt) in enumerate(VIEWS.items()) for k in range(SEEDS_PER_VIEW)]
    vb = b["character"]["views"]
    batch.create(vb, f"캐릭터 {b['character']['name']} · 다른 시점", items, contest=False)
    return vb


def register(cid):
    """고른 정면(필수)과 시점별로 고른 이미지 하나씩을 캐릭터로 등록한다."""
    b = _draft(cid)
    c = b["character"]
    images = {"front": _picked(b)}
    if not images["front"]:
        raise engine.StudioError("정면 시안을 하나 고르세요.")
    try:
        vb = batch.load(c["views"])
    except engine.StudioError:
        vb = None
    for v in VIEWS:
        p = _picked(vb, v) if vb else None
        if p:
            images[v] = p
    made = engine.create_character(c["name"], c["description"], {v: p.read_bytes() for v, p in images.items()})
    batch._update(cid, character=dict(c, registered=made["id"]))
    return made


def delete(cid):
    """초안(정면 배치와 시점 배치)을 지운다. 이미 등록한 캐릭터는 남는다(AI 영상 생성 탭에서 따로 지움)."""
    b = _draft(cid)
    vb = b["character"].get("views")
    try:
        v = batch.load(vb) if vb else None
    except engine.StudioError:
        v = None
    if v and v["state"] in ("queued", "running") or b["state"] in ("queued", "running"):
        raise engine.StudioError("대기 중이거나 생성 중인 시안이 있습니다. 대기열에서 빼거나 멈춘 뒤 지우세요.")
    if v:
        batch.delete(vb)
    batch.delete(cid)


if __name__ == "__main__":
    # 자체 점검: python -m studio.charmaker
    import tempfile
    from pathlib import Path
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        batch.CONTEST_ROOT, batch.CONTENT_ROOT, engine.CHARACTERS = Path(tmp) / "a", Path(tmp) / "b", Path(tmp) / "c"
        desc = "A small round cartoon fox with orange fur, a white chest and a blue scarf."
        for bad in (("", desc), ("여우", "여우 설명입니다 아주 길게 써도 한글이면 안 됩니다"), ("여우", "short")):
            try:
                front(*bad, "", "draft", 2)
                raise AssertionError(bad)
            except engine.StudioError:
                pass
        cid = front("여우", desc, "주황 여우", "draft", 2)
        b = batch.load(cid)
        assert [i["name"] for i in b["items"]] == ["front_s1", "front_s2"] and b["character"]["name"] == "여우"
        assert b["items"][0]["job"]["prompt"].startswith(desc) and b["contest"] is False
        try:
            views(cid)
            raise AssertionError("no pick must fail")
        except engine.StudioError:
            pass

        def finish(name, item):  # 생성이 끝난 것처럼 결과 파일을 둔다
            out = batch._dir(name) / item / "out" / "r.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (48, 80), "orange").save(out)
            batch._update_item(name, item, status="done", output=str(out))
        finish(cid, "front_s1"); finish(cid, "front_s2")
        batch.set_pick(cid, "front_s1", True); batch.set_pick(cid, "front_s2", True)
        try:
            views(cid)
            raise AssertionError("two picks must fail")
        except engine.StudioError:
            pass
        batch.set_pick(cid, "front_s2", False)
        vb = views(cid)
        v = batch.load(vb)
        assert len(v["items"]) == 6 and v["items"][0]["job"]["image_refs"][0].endswith("r.png")
        finish(vb, "back_s2"); batch.set_pick(vb, "back_s2", True)
        made = register(cid)
        assert made["views"] == ["front view", "back view"] and batch.load(cid)["character"]["registered"] == made["id"]
        assert engine.list_characters()[0]["name"] == "여우"
        pid = front("비서", desc, "", "draft", 1, "portrait", "blurred server racks")
        pj = batch.load(pid)["items"][0]["job"]["prompt"]
        assert "Background: blurred server racks." in pj and "Upper-body portrait" in pj and "Full-body" not in pj, pj
        import io as _io
        buf = _io.BytesIO(); Image.new("RGB", (40, 60), "red").save(buf, "PNG")
        rid = front("참고", desc, "", "draft", 1, "sheet", "", [buf.getvalue()])
        rj = batch.load(rid)["items"][0]["job"]
        assert rj["model_type"] == EDIT and rj["prompt"].startswith(GUIDE) and Path(rj["image_refs"][0]).is_file(), rj
        for bad in ([b"nope"], [buf.getvalue()] * 4):
            try:
                front("참고", desc, "", "draft", 1, "sheet", "", bad)
                raise AssertionError("bad refs must fail")
            except engine.StudioError:
                pass
        batch.mark_queued(pid)
        try:
            delete(pid)
            raise AssertionError("queued draft must not be deleted")
        except engine.StudioError:
            pass
        delete(cid)
        assert not batch._dir(cid).exists() and not batch._dir(vb).exists(), "draft and its views are gone"
        assert engine.list_characters()[0]["name"] == "여우", "registered character stays"
    print("ok")
