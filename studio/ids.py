"""모든 프로젝트 폴더가 한 곳(projects/) 아래에 "날짜시분초_프로젝트명"으로 만들어지게 하는 공통 규칙.

홍보 영상, AI 영상, 캐릭터, 콘텐츠 생성 결과가 모두 projects/<20261115101135_프로젝트명>/ 폴더 하나씩이고,
어떤 종류인지는 폴더 안의 표지 파일(meta.json, project.json, character.json, batch.json)로 구분한다.
예전 12자리 16진수 ID(jobs/ 아래)도 읽을 수 있게 VALID가 받아 준다.
"""
import re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
SYSTEM = ROOT / "jobs"  # 설정·로그·사용량 기록처럼 프로젝트가 아닌 파일
_BAD = r'\\/:*?"<>|\x00-\x1f'
VALID = re.compile(rf"^(?:\d{{14}}_[^{_BAD}\s]{{1,60}}|[0-9a-f]{{12}})$")


def slug(name, default="프로젝트"):
    """폴더 이름에 쓸 수 있게: 금지 문자를 빼고 공백은 _로, 앞뒤 점·밑줄 정리, 40자까지."""
    s = re.sub(rf"[{_BAD}]", "", str(name or ""))
    s = re.sub(r"\s+", "_", s.strip()).strip("._-")
    return s[:40].rstrip("._-") or default


def new_id(name, default="프로젝트", root=None, now=None):
    """'20261115101135_이름'. 같은 초에 같은 이름이 이미 있으면 _2, _3을 붙여 덮어쓰지 않는다."""
    root = Path(root) if root else PROJECTS
    base = f"{time.strftime('%Y%m%d%H%M%S', time.localtime(now))}_{slug(name, default)}"
    pid, n = base, 1
    while (root / pid).exists():
        n += 1
        pid = f"{base}_{n}"
    return pid


def name_of(pid):
    """폴더 이름에서 프로젝트명만 (예전 ID면 빈 문자열)."""
    m = re.match(r"^\d{14}_(.+)$", pid or "")
    return m.group(1) if m else ""


if __name__ == "__main__":  # python -m studio.ids : 규칙 자체 검사
    import tempfile
    assert slug('가족 캠프: "홍보" 영상?') == "가족_캠프_홍보_영상" and slug("   ") == "프로젝트" and slug("a" * 80) == "a" * 40
    with tempfile.TemporaryDirectory() as t:
        a = new_id("가족 캠프", root=t, now=1760000000)
        assert VALID.match(a) and name_of(a) == "가족_캠프", a
        (Path(t) / a).mkdir()
        b = new_id("가족 캠프", root=t, now=1760000000)
        assert b == a + "_2" and VALID.match(b), b
    assert VALID.match("0123456789ab") and not VALID.match("../x") and not VALID.match("20261115101135_a/b") and not VALID.match("c20261115_095637")
    print("OK")
