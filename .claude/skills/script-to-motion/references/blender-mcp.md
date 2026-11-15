# Blender MCP — preparing and using Blender for 3D assets

Blender makes the 3D assets (models, materials, keyframed animation); the video still plays in the
browser, where three.js renders the exported glTF on the player's clock (threejs-3d.md). Blender is
driven through the **official Blender Lab MCP server** (https://www.blender.org/lab/mcp-server/) —
the same tools a native MCP client gets, wrapped in scripts so they work in any session.

## Contents
1. When to use Blender (and when not)
2. How the pieces connect
3. Preparation — setup_blender.mjs
4. Platforms
5. Using it — the CLI wrapper
6. Using it — as native MCP tools in your agent
7. The tools, and what works headless
8. Writing asset scripts (web-ready rules)
9. The asset workflow inside a video project
10. Troubleshooting
11. Safety

---

## 1. When to use Blender (and when not)

Use Blender when a beat needs a **real 3D object** the viewer should see turn, open, assemble or fly
through: a product, a prop, a stylised character bust, an architectural space, a logo extrusion with
bevels. Keep 2D (DOM/SVG/Canvas) for typography, diagrams, UI and comic-style scenes — they are sharper,
lighter and faster to iterate. For simple 3D shapes (a cube, a sphere, floating cards) three.js
primitives in scenes.js are enough; Blender earns its place when modelling, modifiers (bevel, solidify,
array, boolean), or keyframed parts matter.

## 2. How the pieces connect

```
you (the agent) ──▶ blender_mcp.mjs ──▶ mcp_client.py ──stdio──▶ blender-mcp (official server, venv)
                                                              │ TCP 127.0.0.1:9876
                                                              ▼
                     background Blender ◀── bridge.py loads the official add-on (unmodified, pinned)
                              │ export_glb()
                              ▼
              <project>/assets3d/<name>.glb ──embed_glb.mjs──▶ models/<name>.glb.js ──▶ three.js layer
```

- The add-on runs inside a **background** Blender (no window); it is imported from the pinned repository,
  not installed into Blender's preferences.
- Calls go through the real MCP protocol, so behaviour matches a native MCP client exactly.
- Environment variables understood by the server: `BLENDER_MCP_HOST`, `BLENDER_MCP_PORT` (default 9876),
  `BLENDER_PATH` (used by the `*_for_cli` tools). The wrapper sets them.

## 3. Preparation — setup_blender.mjs

```bash
node <skill>/scripts/setup_blender.mjs --check    # diagnose: platform, x86_64 capability, Blender, venv, git, xz
node <skill>/scripts/setup_blender.mjs            # set up everything, then self-test
```

Tell the user in one line before the first real run: it downloads Blender (~400 MB) and, on ARM Linux,
a few MB of x86_64 runtime libraries, all into `~/.cache/motion-video-deps/blender/` — no sudo.

What it does (idempotent; each step is skipped when already done):

1. **Blender** — downloads the official `blender-<version>-linux-x64.tar.xz` (default **5.1.2**, the
   version this pipeline was proven with; `--version 5.2.2` for another), checks it against the official
   `.sha256` file, extracts it. `--blender /path/to/blender` uses an installed Blender instead.
2. **x86_64 runtime (ARM Linux only)** — Blender publishes Linux builds for x86_64 only. On an ARM host
   that can run x86_64 programs (Docker Desktop's Rosetta on Apple silicon, or QEMU binfmt), the script
   - verifies emulation by running a tiny x86_64 busybox,
   - fetches the x86_64 glibc + the libraries Blender links (X11, xkbcommon, GL dispatch stubs…) from the
     distro's **amd64** archive, SHA256-checked against its Packages index (fetched over HTTP, Release signature
     not verified — catches corrupt downloads), into `x64root/` (lib/debs.mjs; missing ones are resolved
     through the Contents index),
   - copies the x86_64 loader **into the Blender folder** and writes `bin/blender`, which runs
     `ld-linux-x86-64.so.2 --library-path … --argv0 blender blender "$@"`. The loader must sit next to
     the binary because Blender locates its bundled Python and scripts relative to `/proc/self/exe`.
3. **MCP server** — clones `https://projects.blender.org/lab/blender_mcp.git` at a pinned revision
   (default `ff54e4d`, known good; `--mcp-ref` to change), creates `venv/` with the system `python3` (≥3.10 — the
   mcp SDK needs it; checked before anything is downloaded, `--python python3.12` picks another) and installs the
   server (`venv/bin/blender-mcp`).
4. Writes `blender.json` (paths, version, port) and runs `blender_mcp.mjs selftest`: start Blender,
   list the tools, build a sphere with a material, export a GLB, stop.

Layout under `~/.cache/motion-video-deps/blender/`: `blender-5.1.2-linux-x64/`, `x64root/`, `bin/blender`,
`blender_mcp/`, `venv/`, `blender.json`, `logs/` (Blender log, `mcp-calls.jsonl`), `run/` (pid files).

## 4. Platforms

| platform | what happens |
|---|---|
| Docker on Apple silicon (arm64 Linux) | Rosetta runs the x86_64 build through the user-space runtime above. If `--check` says x86_64 can't run: Docker Desktop → Settings → General → *Use Rosetta for x86_64/amd64 emulation on Apple Silicon* (admin/user action), restart |
| x86_64 Linux | the official build runs natively; any missing X11/GL libraries are fetched the same way (or `sudo apt-get install libx11-6 libxi6 libxkbcommon0 libsm6 libgl1 …` with admin rights) |
| other ARM Linux | needs QEMU binfmt (`qemu-user-static`, admin) — otherwise run Blender elsewhere |
| macOS | install Blender 5.1+ (`/Applications/Blender.app`, or `brew install --cask blender`); the script finds it and sets up the MCP venv |
| Windows | install Blender 5.1+; pass `--blender "C:\\…\\blender.exe"`; the wrapper's process management is untested there |

## 5. Using it — the CLI wrapper (works in any session)

```bash
S=<skill>/scripts
node $S/blender_mcp.mjs start [--blend file.blend] [--port 9876]   # ~1–2 s; log in logs/blender-<port>.log
node $S/blender_mcp.mjs status                                       # version, open file, objects
node $S/blender_mcp.mjs tools                                        # the 26 tools
node $S/blender_mcp.mjs run assets3d/mug.py --prelude --log <project>/assets3d/mcp-calls.jsonl
node $S/blender_mcp.mjs call get_objects_summary
node $S/blender_mcp.mjs call get_object_detail_summary '{"name": "Cup"}'
node $S/blender_mcp.mjs call search_api_docs '{"query": "gltf export"}'
node $S/blender_mcp.mjs stop
```

- `run` sends the file through `execute_blender_code`. With `--prelude` it prepends
  `scripts/blender/prelude.py` (helpers below). The script's `result` dict comes back as JSON; Blender's
  stdout is shown; a Python exception inside Blender is reported with its traceback and exit code 1.
- The Blender session **persists between calls** (state stays until `stop`), so you can build in steps and
  inspect in between. Start with `--blend` to continue work on a saved file.
- Always `stop` when done — it's a background process.

## 6. Using it — as native MCP tools in your agent

```bash
node $S/blender_mcp.mjs mcp-json    # prints {"mcpServers": {"blender": {"command": …/venv/bin/blender-mcp, "env": {…}}}}
```

That is the standard MCP server entry (command + env). Add it to the MCP configuration of the agent you use —
for example a project `.mcp.json` in Claude Code — and ask the user first: it changes their agent's setup. In a new
session the agent offers the server's tools (`execute_blender_code`, `get_objects_summary`, … — some agents prefix
them, e.g. `mcp__blender__…`). Without MCP support, the CLI wrapper above does the same job. Blender itself must already be
running: `node $S/blender_mcp.mjs start` before using the tools, `stop` afterwards. The CLI wrapper and the
native tools talk to the same Blender, so they can be mixed.

## 7. The tools, and what works headless

| group | tools | headless (background Blender, no GPU) |
|---|---|---|
| run code | `execute_blender_code`, `execute_blender_code_for_cli` | ✓ — the workhorse; assign a dict to `result` |
| scene | `get_objects_summary`, `get_object_detail_summary` | ✓ |
| file | `get_blendfile_summary_datablocks / _missing_files / _of_linked_libraries / _path_info / _usage_guess` (+ `_for_cli` variants that open a given .blend) | ✓ |
| docs | `search_api_docs`, `search_manual_docs`, `get_python_api_docs` | ✓ — use them instead of guessing operator arguments |
| UI | `get_screenshot_of_window_as_image/_json`, `get_screenshot_of_area_as_image`, `jump_to_*` | ✗ "not available in background mode" |
| render | `render_thumbnail_to_path`, `render_viewport_to_path` | needs a scene camera; EEVEE/Workbench need a GPU — without one they fail. Render with **Cycles (CPU)** via `execute_blender_code` if you need a Blender-side picture |

To *see* an asset, the best check is the real target: embed it and shoot the video with `render.py --screenshot`
(threejs-3d.md). A Cycles still is useful only to judge the model before export:

```python
scene = bpy.context.scene
scene.render.engine = "CYCLES"; scene.cycles.samples = 16
scene.render.resolution_x, scene.render.resolution_y = 640, 480
bpy.ops.object.camera_add(location=(2.5, -2.5, 2), rotation=(1.1, 0, 0.78)); scene.camera = bpy.context.object
bpy.ops.object.light_add(type="SUN", location=(3, -3, 5))
scene.render.filepath = "/abs/path/preview.png"; bpy.ops.render.render(write_still=True)
result = {"preview": scene.render.filepath}
```
(then open the PNG and look at it).

## 8. Writing asset scripts (web-ready rules)

Every model, material and texture is built by your own script from geometry, modifiers and procedural nodes —
never imported from an asset library (Sketchfab, Poly Haven, TurboSquid …), an HDRI download or a generative
3D service, unless the user provided that file (SKILL.md → Originality).

One script per asset in `<project>/assets3d/<name>.py`, idempotent (starts with `reset_scene()`), parameters
and output paths at the top, ends with `result = {...}`. Prelude helpers:

| helper | does |
|---|---|
| `reset_scene(fps=30)` | empty scene, purge orphans, metric units |
| `mat(name, "#hex", roughness, metallic, emission=None)` | Principled BSDF material (sRGB hex → linear) — reused by name |
| `assign(obj, material)` · `smooth(obj, angle_deg=35)` | material; smooth shading keeping sharp edges |
| `apply_transforms(objects=None)` | apply rotation/scale |
| `stats()` | objects, triangles, bounds, materials — put it in `result` and check it |
| `export_glb(path, objects=None, animations=True)` | GLB, Y-up, modifiers applied, **no Draco** (three.js needs no decoder), no cameras/lights |
| `save_blend(path)` | keep the editable source next to the GLB |

Rules that make assets behave in three.js:
- **Scale & orientation**: 1 unit = 1 m; model around the origin, resting on Z=0 (glTF Y-up after export);
  front faces −Y in Blender.
- **Materials**: Principled BSDF only (base colour, roughness, metallic, emission, alpha). Procedural
  textures, node tricks and Blender-only shaders don't survive glTF — bake them or simplify.
- **Modifiers** (bevel, solidify, array, mirror, subdivision) are applied at export (`export_apply=True`).
- **Budget**: ≲100k triangles for everything on screen at once; bevel segments 2–3; subdivision level ≤2.
- **Names** become node names: name every object (`Cup`, `Handle`) so scenes.js can find them
  (`Stage3D.byName(gltf, 'Handle')`). Parent parts to a root object you animate.
- **Animation**: keyframed object transforms, armatures and shape keys export as clips; set
  `scene.frame_start/end` and fps to match the timing you want. In the video the clip is *sampled* at the
  playhead (`mixer.setTime(t)`), so it is seekable. Prefer animating in three.js from the timeline when the
  motion must hit narration cues; use Blender animation for mechanical/looping motion.
- **Stylised look**: flat colours + low roughness read well; a comic look comes from three.js
  `OutlineEffect` (threejs-3d.md), not from Blender Freestyle.
- Put `stats()` and the export result in `result`, and read them: unexpected bounds or triangle counts are
  the quickest sign something went wrong.

Example (tested):

```python
import math, bmesh
OUT = "/abs/project/assets3d/cup.glb"
reset_scene()
coral = mat("CupCoral", "#F2604C", roughness=0.35)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.42, depth=0.9, location=(0, 0, 0.45))
cup = bpy.context.object; cup.name = "Cup"
bm = bmesh.new(); bm.from_mesh(cup.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.z > 0.9], context="FACES")  # open top
bm.to_mesh(cup.data); bm.free()
cup.modifiers.new("thick", "SOLIDIFY").thickness = 0.05
assign(cup, coral); smooth(cup)
bpy.ops.mesh.primitive_torus_add(major_radius=0.2, minor_radius=0.055, location=(0.47, 0, 0.48), rotation=(math.radians(90), 0, 0))
handle = bpy.context.object; handle.name = "Handle"; assign(handle, coral); smooth(handle)
handle.parent = cup; handle.matrix_parent_inverse = cup.matrix_world.inverted()
scene = bpy.context.scene; scene.frame_start, scene.frame_end = 1, 121          # 4 s at 30 fps
cup.rotation_euler = (0, 0, 0); cup.keyframe_insert("rotation_euler", index=2, frame=1)
cup.rotation_euler = (0, 0, math.tau); cup.keyframe_insert("rotation_euler", index=2, frame=121)
result = {"stats": stats(), "glb": export_glb(OUT), "blend": save_blend(OUT.replace(".glb", ".blend"))}
```

## 9. The asset workflow inside a video project

1. Storyboard marks the beats that need a 3D asset and what the camera does there.
2. `node $S/blender_mcp.mjs start`.
3. Write `assets3d/<name>.py`; `run … --prelude --log assets3d/mcp-calls.jsonl`; read `result`
   (`stats`, bounds); inspect with `get_objects_summary`; fix and re-run until right.
   The run records in the project's `generated.json` every file Blender created or changed in `assets3d/` — write
   the script's outputs there (`call` records nothing).
4. `node $S/embed_glb.mjs assets3d/<name>.glb <project>` → `models/<name>.glb.js` (+ script tag). It takes only a
   `.glb` recorded from a Blender run (unchanged since) or declared as the user's in `provenance.json`.
5. Build the 3D layer in scenes.js (threejs-3d.md), verify on render.py sheets — `--screenshot --from a --to b
   --gapframe 3` across the 3D moves.
6. `stop` Blender. Keep `assets3d/*.py`, `*.blend`, `*.glb` and the call log in the project — the asset
   can be regenerated or edited later.

## 10. Troubleshooting

| symptom | cause / fix |
|---|---|
| `--check`: x86_64 NOT available | enable Rosetta in Docker Desktop (or QEMU binfmt), restart the container |
| `needs Python 3.10 or newer` | the system `python3` is older (e.g. macOS's 3.9): install a newer one, rerun with `--python python3.12` |
| `Blender does not start` + `Unable to find the Python binary` / `encodings` | Blender can't see its bundled Python — run it through `bin/blender` (loader inside the Blender folder), not the loader from x64root |
| `error while loading shared libraries: libX.so` | rerun setup (it resolves missing libs); `--check` shows the state |
| `Cannot connect to Blender at …:9876` | not started, or another port: `blender_mcp.mjs status/start` |
| `start` says already serving but nothing responds | a stale Blender holds the port: `stop` (only stops what it started), or use `--port 9877` |
| `Empty response from Blender` | Blender crashed during the call (e.g. an EEVEE render without GPU) — check `logs/blender-<port>.log`, `start` again |
| a script silently did nothing | wrong mode/selection — see the server's instructions: set mode, active object and selection explicitly; use `search_api_docs` |
| exported model is huge / invisible | check `stats()` bounds (units), apply scale, triangle count; Z-up vs Y-up handled by export |

## 11. Safety

`execute_blender_code` runs arbitrary Python inside Blender with full file-system access (the official
docs warn about this). The wrapper binds the add-on to `127.0.0.1` only, runs it in the sandboxed
container, and the scripts come from the project. Don't open untrusted `.blend` files (they can carry
scripts), and don't expose the port. The call log (`--log`) keeps a record of every script that ran.
