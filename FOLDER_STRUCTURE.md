# CC Pipeline (AI Centric) - Folder Structure (Template)

Canonical layout for an all-Nuke team. Hierarchy:
`<root>/<show>/<part>/<seq>/<shot>/<task>/...`
`root` = your work drive (holds many shows), `show` = show code. Folders are created by the
scaffolder, never by hand.

The shot is **task-centric**: shared inputs/outputs live at shot level, and each task
(prep / rotopaint / ai / comp) owns a self-contained folder with its scripts, renders, precomp and
cache.

Naming: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}`
e.g. `shwx_101_010_0010_comp_WIP_rikinp_v03`

| token | meaning | example |
|-------|---------|---------|
| show  | show code | `shwx` |
| part  | part / episode | `101` |
| seq   | sequence | `010` |
| shot  | shot | `0010` |
| task  | prep / rotopaint / ai / comp | `comp` |
| type  | SlapComp / FirstPassSingle / FirstPassVideo / WIP / CF / TF | `WIP` |
| artist| your name | `rikinp` |
| version | 2-digit, per shot+task | `v03` |

## Setup

One-time, per machine:
```bash
python pipeline_core.py config root D:/Work/projects   # folder holding all shows
python pipeline_core.py config show shwx               # show code
python pipeline_core.py config artist rikinp           # your artist name
```

Let Nuke find the tools. Put this line in `~/.nuke/init.py`:
```
nuke.pluginAddPath(r"<path to this repo>")
```

Verify / build:
```bash
python pipeline_core.py doctor
python pipeline_core.py init_show                 # show-level folders, once
python pipeline_core.py new_shot 101 010 0010     # a shot: new_shot <PART> <SEQ> <SHOT>
python pipeline_core.py sync                       # after a config change: add new folders everywhere
python pipeline_core.py sync --prune               # also remove dropped folders (empty only, never data)
```

Settings live in `~/.cc_pipeline.json` (env `CC_ROOT` / `CC_SHOW` / `CC_ARTIST` override; the old
`~/.comfyx_local.json` / `COMFYX_*` are still read as a fallback). Folder sets live in `pipeline.json`
(`shot_common`, `tasks`, `task_subfolders`, `task_extras`, `show_structure`), type list in `types`.

## Tree

```
<root>/                                 work drive, e.g. D:/Work/projects
  <show>/                               show code, e.g. shwx
    assets/                             shared elements, HDRI, stock, matte paintings
    reference/                          briefs, boards, look refs
    edit/                               editorial (cuts, EDL/XML)
    incoming/                           raw client drops before sorting into shots
    deliveries/                         packaged final sends back to client
    review/                             dailies / proxies staged for Frame.io
    color/   luts/ cdl/ ocio/           show color management (ACES OCIO)
    ai/
      datasets/ images/ videos/ audio/  { raw/  processed/ }  + captions/
      prompts/  loras/
      models/   checkpoints/ controlnet/ vae/ upscale/
      training/ configs/ runs/
    <part>/                             part / episode, e.g. 101
      <seq>/                            sequence, e.g. 010
        <shot>/                         shot, e.g. 0010
          # --- common, shared across tasks ---
          plates/                       localized client source EXR (ACEScg)
          review/                       shot proxy / mov staged for client review
          delivery/                     final files going back to client
          elements/                     CG / stock / matte elements shared by tasks
          # --- one self-contained folder per task (prep / rotopaint / ai / comp) ---
          <task>/
            nk/                         the task's .nk scripts
            render/                     renders, one subfolder per render (see below)
            precomp/                    precomp working files
            cache/                      Nuke scratch
          ai/                           the AI task also gets:
            input/                      frames exported from Nuke to feed the AI tool
            output/                     AI results back (Kling / Runway / local tools)
            workflow/                   the recipe / settings actually used (reproducibility)
```

### Renders (created at Write time)
Each render gets its own subfolder named exactly like the script, with `exr/` + `mov/` inside:
```
<shot>/<task>/render/
  shwx_101_010_0010_comp_WIP_rikinp_v03/
    exr/   shwx_101_010_0010_comp_WIP_rikinp_v03.%04d.exr
    mov/   shwx_101_010_0010_comp_WIP_rikinp_v03.mov
```
Pipeline Write makes both nodes from the open script (EXR into `exr/`, MOV into `mov/`).

## Rules
- Scripts live in `<task>/nk/`; renders in `<task>/render/<stem>/{exr,mov}`.
- Version is per shot+task (shared across types), driven by the script version in `<task>/nk/`.
  A `comp_v03` script renders `comp_v03`.
- `plates / review / delivery / elements` are shot-level and shared; everything else is per task.
- Everything under `ai/` (show level) and the other show-level folders are show-shared. Do not
  duplicate per shot.
- `raw` = as-received, never edit in place. `processed` = your treated result.
