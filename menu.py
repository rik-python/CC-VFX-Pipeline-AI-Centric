"""
CC menus - Nuke menu registration. Adds two menus to Nuke's top menu bar:
  - "CC VFX Menu": pipeline (New Shot, Save Script, Write)
  - "CC AI Menu":  the ComfyUI panel
Add this directory to NUKE_PATH or nuke.pluginAddPath() in ~/.nuke/init.py.
"""
import nuke

import pipeline_core as _pc

# --- Default color management: OCIO + the ACES config (config-driven) -----------
# knobDefault makes this the default for every NEW script (File > New). Change
# color_management / ocio_config in pipeline.json to adjust for the whole team.
try:
    _cfg = _pc.load_config()
    _cm = _cfg.get("color_management", "")
    _oc = _cfg.get("ocio_config", "")
    if _cm:
        nuke.knobDefault("Root.colorManagement", _cm)
    if _oc:
        nuke.knobDefault("Root.OCIO_config", _oc)
    # Also apply to the session's current (fresh) root so the first script matches.
    try:
        _root = nuke.root()
        if _cm and _root.knob("colorManagement"):
            _root["colorManagement"].setValue(_cm)
        if _oc and _root.knob("OCIO_config"):
            _root["OCIO_config"].setValue(_oc)
    except Exception:
        pass
except Exception:
    pass

# Top menu bar (next to File / Edit / ...), not the Nodes tab toolbar.
menubar = nuke.menu("Nuke")

# (label shown in menu, task token used in filenames/folders)
_TASKS = (("Prep", "prep"), ("RotoPaint", "rotopaint"), ("AI", "ai"), ("Comp", "comp"))

# --- CC VFX Menu : the pipeline -------------------------------------------------
cc_vfx = menubar.addMenu("CC VFX Menu")

# Scaffold a new shot's folders (no terminal).
cc_vfx.addCommand("New Shot", "import nuke_pipeline; nuke_pipeline.new_shot_dialog()")

# Save the .nk with the enforced name + auto version, into <task>/nk.
save_menu = cc_vfx.addMenu("Pipeline Save Script")
for _label, _task in _TASKS:
    save_menu.addCommand(
        _label,
        "import nuke_pipeline; nuke_pipeline.save_script('{0}')".format(_task),
    )

# Pipeline-aware Write nodes. Auto-derives task/type/version/shot from the OPEN
# script and makes an EXR + a MOV Write into <task>/render/<stem>/. No picking.
cc_vfx.addCommand(
    "Pipeline Write (EXR + MOV)",
    "import nuke_pipeline; nuke_pipeline.create_write()",
)

# --- CC AI Menu : the ComfyUI panel --------------------------------------------
cc_ai = menubar.addMenu("CC AI Menu")
cc_ai.addCommand("Open Panel", "import comfy_bridge; comfy_bridge.show_panel()")
