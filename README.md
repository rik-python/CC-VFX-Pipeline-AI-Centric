# CC Pipeline (AI Centric)

**Version 1**

A **free, AI-centric VFX pipeline for freelancers**, built around Nuke and ComfyUI.
(Comfy Compositing pipeline. Repo: `CC-VFX-Pipeline-AI-Centric`.)

Two parts in one repo:
1. **Pipeline automation** - one shared config builds an identical folder structure and enforces
   naming + versioning for every artist on a show. No more files saved in the wrong place or
   named inconsistently.
2. **Comfy Compositor panel** - a manifest-driven Nuke side panel that runs ComfyUI workflows
   from inside Nuke and drops results back as Read nodes.

Designed so a non-technical artist can clone it and be running in about 5 minutes.

---

## What you get

- Standard folder tree per `show / part / seq / shot`, created with one command.
- Enforced naming: `shwx_101_010_0010_comp_WIP_rikinp_v01` (`show_part_seq_shot_task_type_artist_version`).
- Auto-versioning per shot+task. The Nuke **script** version drives the **render** version, so a
  `comp_v03` script always produces `comp_v03` renders.
- Nuke menu with **New Shot**, **Pipeline Save Script**, and **Pipeline Write**, per task
  (RotoPaint / AI / Comp), with **dropdown pickers** for show/part/seq/shot and type (no typing).
- Everyone who points at the same shared drive sees the same shots and names.

---

## Requirements

- **Nuke** (13+ recommended).
- **Python 3** on your PATH (for the command-line setup; Nuke uses its own embedded Python).
- **ComfyUI** running locally (`127.0.0.1:8188`) if you want the Comfy panel.
- A **shared drive** for team work (Dropbox / Google Drive / LucidLink). Everyone mounts the same
  one.

No pip installs. The pipeline code is pure standard library.

---

## Install (about 5 minutes)

**1. Clone the repo**
```bash
git clone https://github.com/rik-python/CC-VFX-Pipeline-AI-Centric.git
```

**2. Tell Nuke where it is.** Add this line to `~/.nuke/init.py` (create the file if it does not
exist), using the path where you cloned it:
```python
nuke.pluginAddPath(r"C:\path\to\CC-VFX-Pipeline-AI-Centric")
```

**3. Set your config (once per machine).** In the repo folder:
```bash
python pipeline_core.py config root D:/Work/projects   # the folder that holds all your shows
python pipeline_core.py config show shwx               # current show code
python pipeline_core.py config artist rikinp           # your artist name
```

**4. Check it:**
```bash
python pipeline_core.py doctor
```
All `[OK]` means you are good. `[WARN] OCIO` is expected unless you use ACES (see Color below).

**5. Restart Nuke.** Open **Nodes > [CC] Comfy Compositor**.

---

## Updating

When the pipeline changes, get the latest in one click:
- **Windows:** double-click **`update.bat`**
- **mac:** double-click **`update.command`** (first time only, run `chmod +x update.command` so macOS lets you double-click it)

It runs `git pull`, then **`sync`** (adds any new folders the update introduced into your
existing shots, so you never delete and rebuild the show), and reminds you to **restart Nuke** so
the new code loads. Never edit files inside this folder, that is what keeps updates one click
forever (local edits cause pull conflicts).

### Changing the folder structure for everyone
Edit `pipeline.json`, push. When teammates update, `sync` adds the new folders to every existing
shot automatically. Adds are always safe. To remove folders you dropped from the config, run it
manually:
```bash
python pipeline_core.py sync --prune
```
`--prune` only deletes folders that are **empty**; anything still holding files is kept and
reported, never deleted.

---

## Daily use

**Make a shot** (from the menu: Comfy Compositor > New Shot, or the CLI):
```bash
python pipeline_core.py new_shot 101 010 0010   # new_shot <PART> <SEQ> <SHOT>
```

**Save your Nuke script** with the correct name + version:
- Comfy Compositor > **Pipeline Save Script > Comp** (or RotoPaint / AI)
- Pick the shot from the dropdown, pick a **type** (WIP / CF / TF / SlapComp / ...).
- Saves e.g. `...\shwx\101\010\0010\nuke\shwx_101_010_0010_comp_WIP_rikinp_v01.nk`.
- Run it again later to bump the version automatically.

**Add a render Write node:**
- Select the node to output, then Comfy Compositor > **Pipeline Write (from script)**.
- No picking. The Write mirrors your **open script** exactly - same task, type, version and shot -
  so a `..._comp_WIP_..._v03.nk` script writes `..._comp_WIP_..._v03.%04d.exr` into the `comp`
  folder. Press **Render** (F7).
- (If the script isn't saved with a pipeline name yet, it just tells you to Pipeline Save Script
  first - it never asks you to pick a shot.)

**Run an AI workflow** (Comfy panel): Comfy Compositor > Open Panel, pick a workflow, set
parameters, Generate. Results come back as Read nodes.

### Going from WIP v08 to Creative Final v09
Just Save Script again and pick type **CF**. The version auto-bumps to v09 (next after the highest
existing). Type is a free label; the version always climbs per shot+task.

---

## Folder structure and naming

Full tree and every folder's purpose: see [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md).

Hierarchy: `<root>/<show>/<part>/<seq>/<shot>/<task folders>`

Name: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}`

| token | meaning | example |
|-------|---------|---------|
| show | show code | `shwx` |
| part | part / episode | `101` |
| seq | sequence | `010` |
| shot | shot | `0010` |
| task | RotoPaint / AI / Comp | `comp` |
| type | SlapComp / FirstPassSingle / FirstPassVideo / WIP / CF / TF | `WIP` |
| artist | your name | `rikinp` |
| version | 2-digit, per shot+task | `v01` |

---

## Configuration

- **`~/.comfyx_local.json`** (per machine): your `root`, `show`, `artist`. Set via the `config`
  command. Switch shows with `python pipeline_core.py config show <code>`.
- **`pipeline.json`** (shared, versioned): the folder sets (`show_structure`, `shot_structure`),
  `task_folders`, the `types` list, and `write_colorspace`. Edit here to change the structure for
  everyone.

Environment overrides (optional): `COMFYX_ROOT`, `COMFYX_SHOW`, `COMFYX_ARTIST`.

---

## Collaboration

Everyone sets `root` to the **same mounted shared drive**. Each person sets their own `artist`.
After that, the same shot resolves to the same folder and the same name on every machine. A local
`root` means a private copy, not shared work.

---

## Color (ACEScg)

The pipeline standard is 4K / ACEScg / EXR. The Write node will set colorspace to
`ACES - ACEScg` **only if your Nuke is on an ACES OCIO config**; otherwise it leaves Nuke's
default and does not error. To get true ACEScg, set Nuke's OCIO config to `aces_1.3` (Project
Settings > Color) or set the `OCIO` environment variable to an ACES `config.ocio`.

> The full ACEScg <-> 8-bit AI color roundtrip (converting plates for AI tools and back) is the
> known hard problem and is on the roadmap, not done yet.

---

## Troubleshooting

- **Menu not showing** - the repo is not on `NUKE_PATH`. Redo install step 2 and restart Nuke.
- **`python` not found** - install Python 3 and tick "Add to PATH".
- **`invalid lut selected: ACES - ACEScg`** - your Nuke is not on an ACES config. Already handled
  (the Write skips it); see Color above to enable ACEScg.
- **Shot not in the dropdown** - create it first (New Shot / `new_shot`). The dropdown lists shots
  that exist on disk.

---

## Development

Pure stdlib. Run the tests:
```bash
python -m unittest -v
```

Core modules:
- `pipeline_core.py` - config, folder scaffolding, naming, versioning, shot listing.
- `nuke_pipeline.py` - Nuke Save Script / Write + the pickers.
- `menu.py` - Nuke menu registration.
- `comfy_bridge.py` - the Comfy Compositor panel.
- `pipeline.json` - the shared config. `test_pipeline_core.py` - tests.

---

## Roadmap

- ACES OCIO config shipped in-repo so ACEScg works out of the box.
- AI color roundtrip (ACEScg plates to 8-bit for AI tools and back).
- More tasks / types as the show needs them.
