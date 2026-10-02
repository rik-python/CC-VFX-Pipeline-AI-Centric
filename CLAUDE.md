# CC Pipeline (AI Centric) - Version 1

Project name: **CC Pipeline (AI Centric)** (Comfy Compositing). Repo: `CC-VFX-Pipeline-AI-Centric`. Local folder: `ComfyXNuke`.
Freelance VFX pipeline for an all-Nuke team: config-driven folders + naming + Nuke save/write.

## What it is
- **Pipeline (the deliverable)**: config-driven path/naming/version engine so saves + renders land in correct shot folders with enforced naming, identical for every freelancer. No ComfyUI dependency.
- **comfy_bridge.py + Workflows/ (DORMANT)**: the old manifest-driven Nuke<->ComfyUI panel. Kept in the repo but NOT wired into the menus (unlinked per Rikin 2026-10-02). Do not reference it from the pipeline. Spec: `docs/superpowers/specs/2026-04-11-comfy-compositor-panel-design.md`.

## Pipeline scope (decided)
- Automate ONLY: folder scaffold, naming convention, auto-versioning, correct save/render paths across all collaborators. Everything else manual/documented.
- Standards: 4K, ACEScg, EXR. Team is all-Nuke (nuke/roto, AI artist, compositor). Hierarchy `ROOT/SHOW/PART/SEQ/SHOT/<task>` - **task-centric**: common folders `plates/review/delivery/elements` at shot level; each task (prep/rotopaint/ai/comp) owns a folder with `nk/ render/ precomp/ cache/` (ai also `input/ output/ workflow/`). Scripts in `<task>/nk`; renders in `<task>/render/<stem>/{exr,mov}`. Naming: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}`. version 2-digit, per shot+task from the nk folder (script version drives render version). type from `pipeline.json` `types`. Config keys: `shot_common`, `tasks`, `task_subfolders`, `task_extras`, `show_structure`, `render_folder`/`render_exr_dir`/`render_mov_dir`, `mov_format`, `write_colorspace`/`review_colorspace`. Structure template: `FOLDER_STRUCTURE.md`. Engine: `pipeline_core.py` (CLI: `config root|show|artist <v>`, `doctor`, `init_show`, `new_shot <PART> <SEQ> <SHOT>`, `sync [--prune]`, `path`). `sync` reconciles existing show+shots to the current config (add-only; `--prune` removes empty-only dropped folders, never data). Updater scripts run `sync` after `git pull`. Per-machine settings in `~/.cc_pipeline.json` (env `CC_ROOT/CC_SHOW/CC_ARTIST`; legacy `~/.comfyx_local.json` + `COMFYX_*` still read as fallback). First-time setup: `install.py` (double-click `install.bat`/`install.command`) prompts artist / root / show code / Nuke folder, writes the local config, appends `pluginAddPath` to `<nuke>/init.py` (idempotent), checks deps (python/git/shared drive), offers `init_show`, runs doctor.
- Nuke side: `nuke_pipeline.py` (`save_script(task)` -> `<task>/nk`; `create_write()` reads the open script and makes TWO Write nodes, EXR -> `<task>/render/<stem>/exr`, MOV -> `.../mov`, via `pc.render_outputs`; PART/SEQ/SHOT from the open script path else a `pc.list_shots` dropdown; type picked on save), registered in `menu.py` as a top-bar **CC VFX Menu** > New Shot / Pipeline Save Script (Prep/RotoPaint/AI/Comp) / Pipeline Write (EXR + MOV). `menu.py` also sets OCIO/aces_1.3 as the default color.
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
