"""
Comfy Compositor — Nuke menu registration.
Add this directory to NUKE_PATH or nuke.pluginAddPath() in ~/.nuke/init.py.
"""
import nuke

toolbar = nuke.menu("Nodes")
comfy_menu = toolbar.addMenu("Comfy Compositor", icon="CC.png")
comfy_menu.addCommand("Open Panel", "import comfy_bridge; comfy_bridge.show_panel()")

# (label shown in menu, task token used in filenames/folders)
_TASKS = (("Prep", "prep"), ("RotoPaint", "rotopaint"), ("AI", "ai"), ("Comp", "comp"))

# Scaffold a new shot's folders (no terminal).
comfy_menu.addCommand("New Shot", "import nuke_pipeline; nuke_pipeline.new_shot_dialog()")

# Save the .nk with the enforced name + auto version.
save_menu = comfy_menu.addMenu("Pipeline Save Script")
for _label, _task in _TASKS:
    save_menu.addCommand(
        _label,
        "import nuke_pipeline; nuke_pipeline.save_script('{0}')".format(_task),
    )

# Pipeline-aware Write node. Auto-derives task/type/version/shot from the OPEN
# script, so the render mirrors the .nk exactly. One button, no picking.
comfy_menu.addCommand(
    "Pipeline Write (EXR + MOV)",
    "import nuke_pipeline; nuke_pipeline.create_write()",
)
