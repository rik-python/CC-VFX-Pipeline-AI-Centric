"""
Comfy Compositor — Nuke menu registration.
Add this directory to NUKE_PATH or nuke.pluginAddPath() in ~/.nuke/init.py.
"""
import nuke

toolbar = nuke.menu("Nodes")
comfy_menu = toolbar.addMenu("Comfy Compositor", icon="")
comfy_menu.addCommand("Open Panel", "import comfy_bridge; comfy_bridge.show_panel()")
