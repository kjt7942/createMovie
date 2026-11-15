"""render.py의 'HTML까지만' 장치 검사: 에이전트 셸(CLAUDECODE)에서는 SUMO_RENDER_OK=1 없이 MP4를 만들지 않고, --screenshot은 막지 않는다.
사용: python test_render_guard.py <프로젝트 폴더>   (렌더링은 하지 않는다: 막히는 것과 막히지 않고 다음 단계로 넘어가는 것만 본다)"""
import os, subprocess, sys
from pathlib import Path

proj = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
render = proj / 'render.py'
fails = 0


def run(env_extra, *args):
    env = {k: v for k, v in os.environ.items() if k not in ('CLAUDECODE', 'SUMO_RENDER_OK')}
    env.update(env_extra, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    return subprocess.run([sys.executable, str(render), str(proj), *args], capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, timeout=120)


def ok(cond, msg):
    global fails
    print(('✓ ' if cond else '✖ ') + msg)
    fails += 0 if cond else 1


before = set(p.name for p in proj.glob('movie_*.mp4'))
r = run({'CLAUDECODE': '1'})
ok(r.returncode != 0 and 'MP4 만들기는 사용자가 요청할 때만' in (r.stdout + r.stderr), '에이전트 셸에서 MP4 실행은 거부된다')
ok(set(p.name for p in proj.glob('movie_*.mp4')) == before, 'MP4 파일이 만들어지지 않는다')
# 허용 표시가 있으면 이 검사를 지나 다음 단계로 간다: 없는 구간(--from 9999)으로 불러 렌더 전에 멈추게 한다
r = run({'CLAUDECODE': '1', 'SUMO_RENDER_OK': '1'}, '--from', '999999')
ok('MP4 만들기는 사용자가 요청할 때만' not in (r.stdout + r.stderr), 'SUMO_RENDER_OK=1이면 이 장치는 막지 않는다')
# 사용자가 직접 터미널에서 실행하는 경우(CLAUDECODE 없음)도 막지 않는다
r = run({}, '--from', '999999')
ok('MP4 만들기는 사용자가 요청할 때만' not in (r.stdout + r.stderr), '사용자의 직접 실행은 막지 않는다')
# 시트는 에이전트 셸에서도 허용(도움말 수준까지 도달하는지만: 잘못된 --at 값으로 렌더 전에 멈춘다)
r = run({'CLAUDECODE': '1'}, '--screenshot', '--at', 'x')
ok('MP4 만들기는 사용자가 요청할 때만' not in (r.stdout + r.stderr), '--screenshot은 에이전트 셸에서도 막지 않는다')
print('OK' if not fails else f'{fails}개 실패')
sys.exit(1 if fails else 0)
