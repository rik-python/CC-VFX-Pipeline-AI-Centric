# CC Pipeline (AI Centric) - Folder Structure (Template)

Canonical layout. Hierarchy: `<root>/<show>/<part>/<seq>/<shot>/<task folders>`.
`root` = your work drive (holds many shows), `show` = show code. Folders are created by the
scaffolder, never by hand.

Naming: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}`
e.g. `shwx_101_010_0010_ai_FirstPass_rikinp_v01.exr`

| token | meaning | example |
|-------|---------|---------|
| show  | show code | `shwx` |
| part  | part / episode | `101` |
| seq   | sequence | `010` |
| shot  | shot | `0010` |
| task  | rotopaint / track / layout / anim / fx / lighting / render / ai / comp | `ai` |
| type  | SlapComp / FirstPassSingle / FirstPassVideo / WIP / CF / TF | `FirstPass` |
| artist| your name | `rikinp` |
| version | 2-digit, per shot+task | `v01` |

## Setup

One-time, per machine:
```bash
python pipeline_core.py config root D:/Work/projects   # folder holding all shows
python pipeline_core.py config show shwx               # show code
python pipeline_core.py config artist rikinp           # your artist name
```

Let Nuke find the tools (adds this repo to Nuke). Put this line in `~/.nuke/init.py`:
```
nuke.pluginAddPath(r"<path to this repo>")
```

Verify setup:
```bash
python pipeline_core.py doctor
```

Build folders:
```bash
python pipeline_core.py init_show                 # show-level folders, once
python pipeline_core.py new_shot 101 010 0010     # a shot: new_shot <PART> <SEQ> <SHOT>
python pipeline_core.py sync                       # after a config change: add new folders to all existing shots
python pipeline_core.py sync --prune               # also remove dropped folders (empty only, never deletes data)
```

Settings live in `~/.comfyx_local.json` (env `COMFYX_ROOT` / `COMFYX_SHOW` / `COMFYX_ARTIST`
override). Folder sets are defined in `pipeline.json` (`show_structure` + `shot_structure`),
type list in `types`.

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
    color/
      luts/   cdl/   ocio/              show color management (ACES OCIO)
    ai/
      datasets/
        images/   { raw/  processed/ }
        videos/   { raw/  processed/ }
        audio/    { raw/  processed/ }
        captions/                       labels / tags for training sets
      prompts/                          reusable prompt library
      loras/                            trained + downloaded LoRAs
      models/   { checkpoints/  controlnet/  vae/  upscale/ }
      training/ { configs/  runs/ }
    <part>/                             part / episode, e.g. 101
      <seq>/                            sequence, e.g. 010
        <shot>/                         shot, e.g. 0010
          plates/                       localized client source EXR (ACEScg)
          nuke/                         .nk work scripts (Nuke tasks)
            precomp/                    precomp .nk / renders (working subfolder, not a task)
          rotopaint/                    roto mattes + paint cleanup               [task: RotoPaint, Nuke]
          track/                        matchmove / camera solve                  [task: track, 3DE/Nuke]
          layout/                       layout / blocking                         [task: layout, 3D]
          anim/                         animation                                 [task: anim, 3D]
          fx/                           FX / sims                                 [task: fx, Houdini]
          lighting/                     CG lighting setups                        [task: lighting, 3D]
          render/                       CG renders coming in (beauty / AOVs)      [task: render, 3D out]
          ai_input/                     frames exported from Nuke to feed AI
          ai_output/                    AI results back (ComfyUI / Kling / Runway)   [task: AI]
          comp/                         final Nuke comp renders                   [task: Comp, Nuke]
          elements/                     CG / stock / matte elements
          comfyui/                      ComfyUI working files
          workflow/                     workflow.json used (reproducibility)
          cache/                        Nuke scratch
          review/                       shot proxy / mov for client review
          delivery/                     final EXR going back to client
```

## Rules
- Everything under `ai/` and the show-level folders are show-shared. Do not duplicate per shot.
- A part holds sequences; a sequence holds shots.
- Version is per shot+task (shared across types). The Nuke script version drives the render
  version, so a `comp_v03` script produces `comp_v03` renders.
- `raw` = as-received, never edit in place. `processed` = your treated result.
- The 3D discipline tasks (track / layout / anim / fx / lighting / render) get their folders +
  enforced names from the engine/CLI; the Nuke **Save Script / Write** buttons only cover the
  Nuke tasks (RotoPaint / AI / Comp). `precomp` is a working subfolder inside `nuke/`, not a task.
