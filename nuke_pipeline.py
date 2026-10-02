"""ComfyXNuke Nuke integration: pipeline-aware Save Script + Write nodes.

Artist picks Show / Part / Seq / Shot from cascading dropdowns (or the shot is
auto-detected from the open .nk path), picks a type from the preset list, and the
name + version are enforced. Save a script -> correct .nk name. Add a Write ->
render version matches the open script's version. A "New Shot" option scaffolds a
shot without the terminal.

stdlib + nuke + PySide only. Imports pipeline_core. Registered via menu.py.
"""
import os

import nuke

import pipeline_core as pc

try:
    from PySide2 import QtWidgets
except ImportError:
    from PySide6 import QtWidgets


def _ask(label, default=""):
    return (nuke.getInput("ComfyXNuke: " + label, default) or "").strip()


def _run_dialog(dlg):
    return dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()


class ShotPicker(QtWidgets.QDialog):
    """Cascading Show / Part / Seq / Shot dropdowns, plus a New Shot button."""

    def __init__(self, cfg, preselect=None, parent=None):
        super(ShotPicker, self).__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("ComfyXNuke: Pick Shot")
        form = QtWidgets.QFormLayout(self)

        self.show_cb = QtWidgets.QComboBox()
        self.part_cb = QtWidgets.QComboBox()
        self.seq_cb = QtWidgets.QComboBox()
        self.shot_cb = QtWidgets.QComboBox()
        form.addRow("Show", self.show_cb)
        form.addRow("Part", self.part_cb)
        form.addRow("Seq", self.seq_cb)
        form.addRow("Shot", self.shot_cb)

        new_btn = QtWidgets.QPushButton("New Shot...")
        form.addRow(new_btn)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)

        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        new_btn.clicked.connect(self._new_shot)
        self.show_cb.currentIndexChanged.connect(lambda *_: self._reload_parts())
        self.part_cb.currentIndexChanged.connect(lambda *_: self._reload_seqs())
        self.seq_cb.currentIndexChanged.connect(lambda *_: self._reload_shots())

        self._load_shows(preselect or {})

    def _shots(self):
        return pc.list_shots(self.cfg, self.show_cb.currentText())

    @staticmethod
    def _fill(cb, items, pre):
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(items)
        if pre and pre in items:
            cb.setCurrentText(pre)
        cb.blockSignals(False)

    def _load_shows(self, pre):
        shows = pc.list_shows(self.cfg) or [self.cfg.get("show", "")]
        self._fill(self.show_cb, shows, pre.get("show") or self.cfg.get("show"))
        self._reload_parts(pre)

    def _reload_parts(self, pre=None):
        pre = pre or {}
        parts = sorted({p for p, _, _ in self._shots()})
        self._fill(self.part_cb, parts, pre.get("part"))
        self._reload_seqs(pre)

    def _reload_seqs(self, pre=None):
        pre = pre or {}
        part = self.part_cb.currentText()
        seqs = sorted({s for p, s, _ in self._shots() if p == part})
        self._fill(self.seq_cb, seqs, pre.get("seq"))
        self._reload_shots(pre)

    def _reload_shots(self, pre=None):
        pre = pre or {}
        part, seq = self.part_cb.currentText(), self.seq_cb.currentText()
        shots = sorted({h for p, s, h in self._shots() if p == part and s == seq})
        self._fill(self.shot_cb, shots, pre.get("shot"))

    def _new_shot(self):
        part = _ask("Part/Episode (e.g. 101)")
        seq = _ask("Sequence (e.g. 010)") if part else ""
        shot = _ask("Shot (e.g. 0010)") if seq else ""
        if not (part and seq and shot):
            return
        cfg = dict(self.cfg)
        cfg["show"] = self.show_cb.currentText()
        pc.ensure_shot(cfg, part, seq, shot)
        self._reload_parts({"part": part, "seq": seq, "shot": shot})

    def context(self):
        return (self.show_cb.currentText(), self.part_cb.currentText(),
                self.seq_cb.currentText(), self.shot_cb.currentText())


def _resolve(cfg):
    """Return (part, seq, shot) via the picker; persists a changed show. None if cancelled."""
    ctx = pc.context_from_path(cfg, nuke.root().name())
    pre = {"show": cfg.get("show"), "part": ctx[0], "seq": ctx[1], "shot": ctx[2]} if ctx else None
    dlg = ShotPicker(cfg, preselect=pre)
    if not _run_dialog(dlg):
        return None
    show, part, seq, shot = dlg.context()
    if not (part and seq and shot):
        raise RuntimeError("ComfyXNuke: no shot selected. Use 'New Shot...' or the new_shot CLI.")
    if show and show != cfg.get("show"):
        cfg["show"] = show
        pc.set_local("show", show)
    return part, seq, shot


def _choose_type(cfg):
    """Pick a type from the preset list. Returns the code, or None if cancelled."""
    types = cfg.get("types", [])
    if not types:
        return _ask("Type", "WIP") or "WIP"
    panel = nuke.Panel("ComfyXNuke: Type")
    panel.addEnumerationPulldown("type", " ".join(types))
    if not panel.show():
        return None
    return panel.value("type")


def new_shot_dialog():
    """Menu entry: scaffold a new shot's folders without the terminal."""
    cfg = pc.load_config()
    show = _ask("Show code", cfg.get("show", ""))
    part = _ask("Part/Episode (e.g. 101)") if show else ""
    seq = _ask("Sequence (e.g. 010)") if part else ""
    shot = _ask("Shot (e.g. 0010)") if seq else ""
    if not (show and part and seq and shot):
        return None
    cfg["show"] = show
    path = pc.ensure_shot(cfg, part, seq, shot)
    nuke.message("ComfyXNuke created shot:\n{0}".format(path))
    return path


def save_script(task="comp"):
    """Save the current Nuke script with the enforced name + next version."""
    cfg = pc.load_config()
    ctx = _resolve(cfg)
    if not ctx:
        return None
    type_ = _choose_type(cfg)
    if type_ is None:
        return None
    part, seq, shot = ctx
    path = pc.script_path(cfg, part, seq, shot, task, type_, make_dirs=True)
    nuke.scriptSaveAs(path)
    nuke.message("ComfyXNuke saved script:\n{0}".format(path))
    return path


def create_write(task="comp", ext="exr"):
    """Create a pipeline-correct Write node wired to the selected node.

    Auto-derives everything from the OPEN SCRIPT: task, type, version and shot all
    mirror the saved .nk, so the render name matches the script exactly (a
    ..._comp_WIP_..._v03.nk script writes ..._comp_WIP_..._v03.%04d.exr into the comp
    folder). No re-picking. If the script is unsaved or not pipeline-named, falls back
    to the shot + type pickers (using the task passed from the menu).
    """
    cfg = pc.load_config()
    script = nuke.root().name()
    info = pc.parse_name(script)
    if info:                                   # auto: mirror the open script
        task = info["task"]
        ext = cfg.get("format", "exr")
        path = pc.write_path_from_script(cfg, script, ext=ext, frame_pad="%04d", make_dirs=True)
    else:                                      # fallback: unnamed script -> ask
        ctx = _resolve(cfg)
        if not ctx:
            return None
        type_ = _choose_type(cfg)
        if type_ is None:
            return None
        part, seq, shot = ctx
        path = pc.output_path(cfg, part, seq, shot, task, type_, ext=ext, frame_pad="%04d",
                              version=pc.parse_version(script), make_dirs=True)

    sel = nuke.selectedNodes()
    w = nuke.nodes.Write(file=path, name="Write_{0}_1".format(task))
    try:
        w["file_type"].setValue(ext)
    except Exception:
        pass
    try:
        w["create_directories"].setValue(True)
    except Exception:
        pass
    if ext == "exr":
        for knob, val in (("datatype", "16 bit half"), ("compression", "Zip (1 scanline)")):
            try:
                w[knob].setValue(val)
            except Exception:
                pass
        # Only set colorspace if that value exists in this Nuke's config (ACES OCIO or not).
        cs = cfg.get("write_colorspace", "")
        try:
            k = w["colorspace"]
            if cs and hasattr(k, "values") and cs in k.values():
                k.setValue(cs)
        except Exception:
            pass
    if sel:
        w.setInput(0, sel[0])
    nuke.message("ComfyXNuke Write set:\n{0}".format(path))
    return w
