<div align="center">

# 🎬 CC Pipeline (AI Centric)

**A free, dead-simple VFX pipeline for freelance Nuke teams.**
One shared config → identical folders, enforced names, and auto-set renders for every artist.

![Nuke](https://img.shields.io/badge/Nuke-13%2B-orange)
![Python](https://img.shields.io/badge/Python-3-blue)
![Color](https://img.shields.io/badge/Color-ACEScg%20%2F%20OCIO-green)
![Deps](https://img.shields.io/badge/deps-stdlib%20only-success)
![Tests](https://img.shields.io/badge/tests-46%20passing-brightgreen)

*Comfy Compositing · Version 1 · Repo `CC-VFX-Pipeline-AI-Centric`*

</div>

---

## ✨ What it does

| | |
|---|---|
| 📁 **Same folders for everyone** | One command builds an identical `show / part / seq / shot` tree on every machine. |
| 🏷️ **Enforced naming** | `shwx_101_010_0010_comp_WIP_rikinp_v03` — automatic, never typed by hand. |
| 🔢 **Auto-versioning** | The Nuke **script** version drives the **render** version. `comp_v03` script → `comp_v03` renders. |
| 💾 **Save + Render from a menu** | Save Script and a one-click **EXR + MOV** Write, named and placed for you. |
| 🎨 **ACEScg by default** | Sets OCIO + the ACES config on launch, so color just works. |
| 🔄 **One-click updates** | Double-click to pull the latest and sync new folders into existing shots. |

No pip installs. Pure standard library. A non-technical artist can be running in ~5 minutes.

---

## 🎞️ The shot workflow

```mermaid
flowchart LR
    PLATE[🎥 Plate in] --> PREP[Prep] --> ROTO[RotoPaint] --> AI[AI] --> COMP[Comp] --> REV[Review] --> DEL[📦 Delivery]
```

Each stage is a **task** with its own folder; renders from any task land in `<task>/render/<name>/{exr,mov}`.

---

## 🚀 Quick start

> **1. Clone**
> ```bash
> git clone https://github.com/rik-python/CC-VFX-Pipeline-AI-Centric.git
> ```
> **2. Run the installer** — double-click **`install.bat`** (Windows) or **`install.command`** (mac).
> It asks for your **name**, the **shared-drive folder + show code**, and your **Nuke folder**, then
> wires everything up and checks your setup.
>
> **3. Restart Nuke** — you'll see the **CC VFX Menu** in the top menu bar. Done. 🎉

<details>
<summary>Prefer to set it up by hand? (manual setup)</summary>

Add this to `~/.nuke/init.py`, using your clone path:
```python
nuke.pluginAddPath(r"C:\path\to\CC-VFX-Pipeline-AI-Centric")
```
Then, in the repo folder:
```bash
python pipeline_core.py config root D:/Work/projects   # folder that holds all your shows
python pipeline_core.py config show shwx               # show code
python pipeline_core.py config artist rikinp           # your name
python pipeline_core.py doctor                         # check it
```
Restart Nuke.
</details>

---

## 🧭 Daily use (from the **CC VFX Menu**)

**🆕 New Shot** — pick/enter part / seq / shot; builds the full folder tree.

**💾 Pipeline Save Script → Prep / RotoPaint / AI / Comp**
Pick a **type** (WIP / CF / TF / …). Saves into that task's `nk/` folder, auto-named + auto-versioned:
```
…\shwx\101\010\0010\comp\nk\shwx_101_010_0010_comp_WIP_rikinp_v01.nk
```

**🎬 Pipeline Write (EXR + MOV)**
No picking. Reads your open script and drops **two** Write nodes that mirror it exactly:
```
…\comp\render\shwx_101_010_0010_comp_WIP_rikinp_v03\
    exr\  …_v03.%04d.exr      ← frames
    mov\  …_v03.mov           ← review movie
```
Press **Render** (F7). *(If the script isn't pipeline-named yet, it just says "Save Script first".)*

> **WIP → Creative Final?** Save Script again, pick type **CF**. The version auto-bumps. Type is a
> free label; the version always climbs per shot+task.

---

## 📂 Folder structure

Full tree and every folder's purpose: **[FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md)**.

```
<root>/<show>/<part>/<seq>/<shot>/
│
├── plates/        review/   delivery/   elements/      ← shared across tasks
│
├── prep/          nk/  render/  precomp/  cache/        ┐
├── rotopaint/     nk/  render/  precomp/  cache/        │  one self-contained
├── ai/            nk/  render/  precomp/  cache/        │  folder per task
│                  input/ output/ workflow/              │
└── comp/          nk/  render/  precomp/  cache/        ┘
```

**Naming:** `{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version}`

| token | example | | token | example |
|---|---|---|---|---|
| show | `shwx` | | task | `comp` |
| part | `101` | | type | `WIP` |
| seq | `010` | | artist | `rikinp` |
| shot | `0010` | | version | `v03` |

---

## 🔄 Updating

When the pipeline changes, get the latest in one click:

- **Windows:** double-click **`update.bat`**
- **mac:** double-click **`update.command`**

It runs `git pull`, then **`sync`** (adds any new folders into your existing shots — never deletes
your work), then reminds you to restart Nuke.

> **Rule for the team:** never edit files inside the repo folder. That keeps updates one-click forever.

<details>
<summary>Changing the folder structure for everyone</summary>

Edit `pipeline.json`, push. Teammates get the new folders automatically on their next update. To
remove folders you dropped from the config:
```bash
python pipeline_core.py sync --prune
```
`--prune` only deletes folders that are **empty** — anything holding files is kept and reported.
</details>

---

## 👥 Collaboration

Everyone points `root` at the **same mounted shared drive** (Dropbox / Google Drive / LucidLink) and
sets their own `artist`. After that, the same shot resolves to the same folder and the same name on
every machine.

---

## 🎨 Color (ACEScg)

Standard is **4K / ACEScg / EXR**, and the menu sets it up for you: on launch it makes **OCIO + the
ACES config** (`aces_1.3`) the default for new scripts, so the Write's `ACES - ACEScg` colorspace just
works. If your Nuke uses a different ACES name, change `ocio_config` in `pipeline.json`.

> The full ACEScg ↔ 8-bit AI color roundtrip (plates to AI tools and back) is on the roadmap, not done yet.

---

## ⚙️ Configuration

- **`~/.cc_pipeline.json`** (per machine) — your `root`, `show`, `artist`. Set by the installer or
  `config` command. *(The old `~/.comfyx_local.json` is still read as a fallback.)*
- **`pipeline.json`** (shared, versioned) — the folder sets (`shot_common`, `tasks`,
  `task_subfolders`, `task_extras`, `show_structure`), the `types` list, and the colorspaces.
- Environment overrides: `CC_ROOT`, `CC_SHOW`, `CC_ARTIST` *(legacy `COMFYX_*` still honored)*.

---

## 🩺 Troubleshooting

| Problem | Fix |
|---|---|
| **No CC VFX Menu** | Repo isn't on `NUKE_PATH`. Re-run the installer (or the manual `init.py` step) and restart Nuke. |
| **`python` not found** | Install Python 3 and tick "Add to PATH", then re-run the installer. |
| **Shot not in the dropdown** | Create it first (New Shot / `new_shot`). The list shows shots that exist on disk. |
| **`invalid lut selected: ACES - ACEScg`** | Your Nuke isn't on an ACES config. Set `ocio_config` in `pipeline.json` to your build's name. |

---

## 🛠️ Development

Pure stdlib. Run the tests:
```bash
python -m unittest -v
```

| File | Role |
|---|---|
| `pipeline_core.py` | config, folder scaffolding, naming, versioning, shot listing, `sync` |
| `nuke_pipeline.py` | Nuke Save Script / Write + the pickers |
| `menu.py` | CC VFX Menu registration + default OCIO color |
| `install.py` | first-time interactive setup |
| `pipeline.json` | the shared config · `test_pipeline_core.py` — tests |

*(`comfy_bridge.py` + `Workflows/` are a separate, dormant Nuke↔ComfyUI panel kept in the repo but not wired into the pipeline menus.)*

---

## 🗺️ Roadmap

- [ ] Ship an ACES OCIO config in-repo so ACEScg works with zero Nuke setup
- [ ] AI color roundtrip (ACEScg plates → 8-bit for AI tools and back)
- [ ] More tasks / types as the show needs them
