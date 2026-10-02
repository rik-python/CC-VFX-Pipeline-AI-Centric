# CC Pipeline (AI Centric) - Version 1

Project name: **CC Pipeline (AI Centric)** (Comfy Compositing). Repo: `CC-VFX-Pipeline-AI-Centric`. Local folder: `ComfyXNuke`.
Freelance AI-centric VFX pipeline + manifest-driven Nuke<->ComfyUI panel.

## What it is
- **comfy_bridge.py**: Nuke 17 side panel. Reads `Workflows/<name>/{workflow.json,manifest.json}`, builds UI, fires jobs to local ComfyUI (127.0.0.1:8188), drops results as Read nodes. Spec: `docs/superpowers/specs/2026-04-11-comfy-compositor-panel-design.md`.
- **Pipeline layer (in progress)**: config-driven path/naming/version engine so saves + renders land in correct shot folders with enforced naming, identical for every freelancer.

## Pipeline scope (decided)
- Automate ONLY: folder scaffold, naming convention, auto-versioning, correct save/render paths across all collaborators. Everything else manual/documented.
- Standards: 4K, ACEScg, EXR. Hierarchy `ROOT/SHOW/PART/SEQ/SHOT` (root = work drive holding shows, e.g. D:/Work/projects; show = code, e.g. shwx; part = episode). Naming: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}` (e.g. shwx_101_010_0010_ai_FirstPass_rikinp_v01). version 2-digit, per shot+task (script version drives render version). type from preset list in `pipeline.json` `types`. Structure template: `FOLDER_STRUCTURE.md` + `pipeline.json`. Engine: `pipeline_core.py` (CLI: `config root|show|artist <v>`, `doctor`, `init_show`, `new_shot <PART> <SEQ> <SHOT>`, `sync [--prune]`). `sync` reconciles existing show+shots to the current config (add-only; `--prune` removes empty-only dropped folders, never data). Updater scripts run `sync` after `git pull`. Per-machine settings in `~/.comfyx_local.json`.
- Nuke side: `nuke_pipeline.py` (`save_script(task)`, `create_write(task)`: auto name/version; PART/SEQ/SHOT from the open script path, else a dropdown of existing shots via `pc.list_shots`, else typed; type picked from preset), registered in `menu.py` under Comfy Compositor > New Shot / Pipeline Save Script / Pipeline Write. Menu icon `CC.png`. Nuke Save/Write buttons cover Nuke tasks only: RotoPaint/AI/Comp (-> rotopaint/ai_output/comp folders). 3D discipline tasks (track/layout/anim/fx/lighting/render) are folder+naming only via the engine/CLI (artists save from Maya/Houdini). `precomp` is a working subfolder inside `nuke/`, not a task.
- Media logistics: LucidLink (live drive, mounts per-machine so ROOT must be locally overridable), Backblaze B2 + rclone cold backup, Frame.io client-side only.
- Color roundtrip (ACEScg<->8-bit AI) = known highest risk, deferred.
- Dropped from original plan: Strada P2P streaming (Nuke needs local-speed disk), smartLog idle surveillance (contractor trust/legal risk).

## Constraints
- Nuke embedded Python 3.x: **stdlib only** (+ nuke, PySide2/6). No pip deps in panel/pipeline code.
- Config is **JSON** (matches existing manifest.json/config.json convention), not YAML.
- Single-file distribution preferred; GitHub clone + one-click install is the deploy model.

## Conventions
- Author: Rikin (RP). Caveman mode + no em/en dashes (global rules).
- Don't commit/push unless asked.
