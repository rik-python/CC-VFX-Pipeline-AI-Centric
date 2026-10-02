# CC Pipeline (AI Centric)

**Version 1**

A **free VFX pipeline for freelancers**, built around Nuke.
(Comfy Compositing pipeline. Repo: `CC-VFX-Pipeline-AI-Centric`.)

One shared config builds an identical folder structure and enforces naming + versioning for every
artist on a show, and a Nuke menu saves scripts and renders (EXR + MOV) into the right place
automatically. No more files saved in the wrong place or named inconsistently.

Designed so a non-technical artist can clone it and be running in about 5 minutes.

---

## What you get

- Standard folder tree per `show / part / seq / shot`, created with one command.
- Enforced naming: `shwx_101_010_0010_comp_WIP_rikinp_v01` (`show_part_seq_shot_task_type_artist_version`).
- Auto-versioning per shot+task. The Nuke **script** version drives the **render** version, so a
  `comp_v03` script always produces `comp_v03` renders.
- Task-centric shots: shared folders (plates/review/delivery/elements) at shot level, and one
  self-contained folder per task (**Prep / RotoPaint / AI / Comp**) holding its nk/render/precomp/cache.
- Nuke menu with **New Shot**, **Pipeline Save Script** (per task), and **Pipeline Write (EXR + MOV)**,
  with dropdown pickers for show/part/seq/shot and type on save (no typing).
- Everyone who points at the same shared drive sees the same shots and names.

---

## Requirements

- **Nuke** (13+ recommended).
- **Python 3** on your PATH (for the installer / command-line setup; Nuke uses its own embedded Python).
- **git** (for the one-click updater).
- A **shared drive** for team work (Dropbox / Google Drive / LucidLink). Everyone mounts the same
  one.

No pip installs. The pipeline code is pure standard library.

---

## Install (about 5 minutes)

**1. Clone the repo**
```bash
git clone https://github.com/rik-python/CC-VFX-Pipeline-AI-Centric.git
```

**2. Run the installer.** Double-click **`install.bat`** (Windows) or **`install.command`** (mac;
first time run `chmod +x install.command` once). It asks for:
- your **artist / user name** (the name stamped into filenames),
- the **shared-drive folder** that holds all shows, and the **show code**,
- your **Nuke folder** (default `~/.nuke`).

Then it saves your settings, wires Nuke (adds `pluginAddPath` to `init.py`), checks dependencies
(Python, git, the shared drive), offers to create the show folders, and runs the doctor.
Re-running it is safe.

**3. Restart Nuke.** You'll see the **CC VFX Menu** in the top menu bar.

<details>
<summary>Manual setup (if you'd rather not use the installer)</summary>

Add this line to `~/.nuke/init.py`, using your clone path:
```python
nuke.pluginAddPath(r"C:\path\to\CC-VFX-Pipeline-AI-Centric")
```
Then, in the repo folder:
```bash
python pipeline_core.py config root D:/Work/projects   # the folder that holds all your shows
python pipeline_core.py config show shwx               # current show code
python pipeline_core.py config artist rikinp           # your artist name
python pipeline_core.py doctor                         # check it
```
Restart Nuke.
</details>

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

**Make a shot** (from the menu: CC VFX Menu > New Shot, or the CLI):
```bash
python pipeline_core.py new_shot 101 010 0010   # new_shot <PART> <SEQ> <SHOT>
```

**Save your Nuke script** with the correct name + version:
- CC VFX Menu > **Pipeline Save Script > Comp** (or Prep / RotoPaint / AI)
- Pick the shot from the dropdown, pick a **type** (WIP / CF / TF / SlapComp / ...).
- Saves into that task's `nk/` folder, e.g.
  `...\shwx\101\010\0010\comp\nk\shwx_101_010_0010_comp_WIP_rikinp_v01.nk`.
- Run it again later to bump the version automatically.

**Add render Write nodes:**
- Select the node to output, then CC VFX Menu > **Pipeline Write (EXR + MOV)**.
- No picking. It reads your **open script** and makes **two** Write nodes that mirror it exactly -
  an EXR into `<task>/render/<stem>/exr/` and a MOV into `<task>/render/<stem>/mov/`. So a
  `..._comp_WIP_..._v03.nk` script writes into
  `...\comp\render\shwx_101_010_0010_comp_WIP_rikinp_v03\{exr,mov}\`. Press **Render** (F7).
- (If the script isn't saved with a pipeline name yet, it just tells you to Pipeline Save Script
  first - it never asks you to pick a shot.)

### Going from WIP v08 to Creative Final v09
Just Save Script again and pick type **CF**. The version auto-bumps to v09 (next after the highest
existing). Type is a free label; the version always climbs per shot+task.

---

## Folder structure and naming

Full tree and every folder's purpose: see [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md).

Hierarchy: `<root>/<show>/<part>/<seq>/<shot>/<task>/...` (scripts in `<task>/nk`, renders in
`<task>/render/<stem>/{exr,mov}`; shared `plates/review/delivery/elements` at shot level).

Name: `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}`

| token | meaning | example |
|-------|---------|---------|
| show | show code | `shwx` |
| part | part / episode | `101` |
| seq | sequence | `010` |
| shot | shot | `0010` |
| task | Prep / RotoPaint / AI / Comp | `comp` |
| type | SlapComp / FirstPassSingle / FirstPassVideo / WIP / CF / TF | `WIP` |
| artist | your name | `rikinp` |
| version | 2-digit, per shot+task | `v01` |

---

## Configuration

- **`~/.cc_pipeline.json`** (per machine): your `root`, `show`, `artist`. Set by the installer or
  the `config` command. Switch shows with `python pipeline_core.py config show <code>`. (The old
  `~/.comfyx_local.json` is still read as a fallback.)
- **`pipeline.json`** (shared, versioned): the folder sets (`show_structure`, `shot_common`,
  `tasks`, `task_subfolders`, `task_extras`), the `types` list, and the colorspaces
  (`write_colorspace`, `review_colorspace`). Edit here to change the structure for everyone.

Environment overrides (optional): `CC_ROOT`, `CC_SHOW`, `CC_ARTIST` (legacy `COMFYX_*` still honored).

---

## Collaboration

Everyone sets `root` to the **same mounted shared drive**. Each person sets their own `artist`.
After that, the same shot resolves to the same folder and the same name on every machine. A local
`root` means a private copy, not shared work.

---

## Color (ACEScg)

The pipeline standard is 4K / ACEScg / EXR, and it sets this up for you: on launch the menu makes
**OCIO + the ACES config the default color management** for new scripts (`color_management` and
`ocio_config` in `pipeline.json`, default `OCIO` / `aces_1.3`). So File > New is already on ACES and
the Write's `ACES - ACEScg` colorspace just works.

If your Nuke build names its ACES config differently (e.g. `aces_1.2`), change `ocio_config` in
`pipeline.json`. The Write still sets `ACES - ACEScg` only when that colorspace exists, so it never
errors on a non-ACES build.

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
- `menu.py` - Nuke menu registration (CC VFX Menu) + default OCIO color.
- `install.py` - first-time interactive setup.
- `pipeline.json` - the shared config. `test_pipeline_core.py` - tests.

(`comfy_bridge.py` + `Workflows/` are a separate, dormant Nuke<->ComfyUI panel kept in the repo but
not wired into the pipeline menus.)

---

## Roadmap

- ACES OCIO config shipped in-repo so ACEScg works out of the box.
- AI color roundtrip (ACEScg plates to 8-bit for AI tools and back).
- More tasks / types as the show needs them.
