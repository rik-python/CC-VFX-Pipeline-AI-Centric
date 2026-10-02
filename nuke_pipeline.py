"""CC VFX Nuke integration: pipeline-aware Save Script + Write nodes.

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
    return (nuke.getInput("CC VFX: " + label, default) or "").strip()


def _run_dialog(dlg):
    return dlg.exec_() if hasattr(dlg, "exec_") else dlg.exec()


class ShotPicker(QtWidgets.QDialog):
    """Cascading Show / Part / Seq / Shot dropdowns, plus a New Shot button."""

    def __init__(self, cfg, preselect=None, parent=None):
        super(ShotPicker, self).__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("CC VFX: Pick Shot")
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
        raise RuntimeError("CC VFX: no shot selected. Use 'New Shot...' or the new_shot CLI.")
    if show and show != cfg.get("show"):
        cfg["show"] = show
        pc.set_local("show", show)
    return part, seq, shot


def _choose_type(cfg):
    """Pick a type from the preset list. Returns the code, or None if cancelled."""
    types = cfg.get("types", [])
    if not types:
        return _ask("Type", "WIP") or "WIP"
    panel = nuke.Panel("CC VFX: Type")
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
    nuke.message("CC VFX created shot:\n{0}".format(path))
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
    nuke.message("CC VFX saved script:\n{0}".format(path))
    return path


def _set(node, knob, value):
    """Set a knob if it exists and accepts the value; silently skip otherwise."""
    try:
        node[knob].setValue(value)
    except Exception:
        pass


def _set_colorspace(node, cs):
    """Set the colorspace knob only if that value exists in this Nuke's config."""
    try:
        k = node["colorspace"]
        if cs and hasattr(k, "values") and cs in k.values():
            k.setValue(cs)
    except Exception:
        pass


def create_write():
    """Create pipeline-correct Write nodes from the OPEN SCRIPT: one EXR + one MOV.

    task/type/version/shot all come from the saved .nk name, so the renders mirror the
    script exactly into <task>/render/<stem>/exr (frames) and /mov (review movie). No
    re-picking, no shot dialog. If the script isn't saved with a pipeline name yet, it
    tells the artist to Pipeline Save Script first and does nothing.
    """
    cfg = pc.load_config()
    script = nuke.root().name()
    info = pc.parse_name(script)
    if not info:
        nuke.message(
            "CC VFX: this script isn't saved with a pipeline name yet.\n\n"
            "Run CC VFX Menu > Pipeline Save Script first, then add the Write.\n"
            "(current script: {0})".format(script or "unsaved"))
        return None

    r = pc.render_outputs(cfg, script, frame_pad="%04d", make_dirs=True)
    task = info["task"]
    sel = nuke.selectedNodes()
    src = sel[0] if sel else None

    # EXR: frames, working colorspace (ACEScg if the config has it)
    exr = nuke.nodes.Write(file=r["exr"], name="Write_{0}_exr".format(task))
    _set(exr, "file_type", "exr")
    _set(exr, "create_directories", True)
    _set(exr, "datatype", "16 bit half")
    _set(exr, "compression", "Zip (1 scanline)")
    _set_colorspace(exr, cfg.get("write_colorspace", ""))

    # MOV: review movie, review colorspace. Codec knob names vary by Nuke version; each
    # _set is a no-op when the knob/value is not present.
    mov = nuke.nodes.Write(file=r["mov"], name="Write_{0}_mov".format(task))
    _set(mov, "file_type", "mov")
    _set(mov, "create_directories", True)
    for knob, val in (("mov64_codec", "h264"), ("codec", "h264"), ("meta_codec", "h264")):
        _set(mov, knob, val)
    _set_colorspace(mov, cfg.get("review_colorspace", ""))

    for i, w in enumerate((exr, mov)):
        if src is not None:
            w.setInput(0, src)
            try:
                w.setXYpos(src.xpos() + i * 100, src.ypos() + 120)
            except Exception:
                pass

    nuke.message("CC VFX Write nodes set:\nEXR: {0}\nMOV: {1}".format(r["exr"], r["mov"]))
    return exr, mov
