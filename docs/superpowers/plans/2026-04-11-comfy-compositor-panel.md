# Comfy Compositor Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the v0.1 single-workflow `comfy_bridge.py` with a manifest-driven panel that dynamically supports any number of workflows.

**Architecture:** Single-file panel (`comfy_bridge.py`) scans `Workflows/` subfolders for `manifest.json` + `workflow.json` pairs. The manifest declares which parameters and image inputs to expose. The panel builds a collapsible tree of categories/workflows and dynamically creates UI widgets from the manifest when a workflow is selected. All ComfyUI communication uses HTTP (no WebSocket). A `menu.py` registers the panel in Nuke's menu.

**Tech Stack:** Python 3.x, PySide2/PySide6 (Nuke's Qt), stdlib only (urllib, json, threading, uuid, tempfile, copy, time, os, random)

**Testing note:** This code runs inside Nuke's embedded Python. There is no external test framework available — all verification is manual inside Nuke, or syntax-only checks outside Nuke.

---

### Task 1: Restructure workflow files into subfolders with manifests

**Files:**
- Create: `Workflows/z_image_turbo/manifest.json`
- Move: `Workflows/API-image_z_image_turbo.json` → `Workflows/z_image_turbo/workflow.json`
- Move: `Workflows/API-image_qwen_image_edit_2511.json` → `Workflows/qwen_image_edit/workflow.json`
- Create: `Workflows/qwen_image_edit/manifest.json`

- [ ] **Step 1: Create z_image_turbo subfolder and move workflow**

```bash
mkdir -p D:/ComfyXNuke/Workflows/z_image_turbo
cp D:/ComfyXNuke/Workflows/API-image_z_image_turbo.json D:/ComfyXNuke/Workflows/z_image_turbo/workflow.json
```

- [ ] **Step 2: Write z_image_turbo manifest**

Create `Workflows/z_image_turbo/manifest.json`:

```json
{
  "name": "Z-Image Turbo",
  "category": "Text to Image",
  "description": "Fast text-to-image using Z-Image Turbo model. 8 steps.",
  "inputs": [],
  "parameters": [
    {"label": "Prompt",  "node": "57:27", "field": "text",   "type": "text"},
    {"label": "Width",   "node": "57:13", "field": "width",  "type": "int",   "default": 1024, "min": 64,  "max": 4096, "step": 64},
    {"label": "Height",  "node": "57:13", "field": "height", "type": "int",   "default": 1024, "min": 64,  "max": 4096, "step": 64},
    {"label": "Shift",   "node": "57:11", "field": "shift",  "type": "float", "default": 3.0,  "min": 0.0, "max": 10.0, "step": 0.5},
    {"label": "Steps",   "node": "57:3",  "field": "steps",  "type": "int",   "default": 8,    "min": 1,   "max": 50},
    {"label": "CFG",     "node": "57:3",  "field": "cfg",    "type": "float", "default": 1.0,  "min": 0.0, "max": 20.0, "step": 0.1},
    {"label": "Seed",    "node": "57:3",  "field": "seed",   "type": "seed",  "default": 0}
  ],
  "output_node": "9"
}
```

- [ ] **Step 3: Create qwen_image_edit subfolder and move workflow**

```bash
mkdir -p D:/ComfyXNuke/Workflows/qwen_image_edit
cp D:/ComfyXNuke/Workflows/API-image_qwen_image_edit_2511.json D:/ComfyXNuke/Workflows/qwen_image_edit/workflow.json
```

- [ ] **Step 4: Write qwen_image_edit manifest**

Create `Workflows/qwen_image_edit/manifest.json`:

```json
{
  "name": "Qwen Image Edit",
  "category": "Image to Image",
  "description": "Edit an image using a text prompt with optional reference image.",
  "inputs": [
    {"label": "Source Image", "node": "41", "field": "image"},
    {"label": "Reference",   "node": "83", "field": "image"}
  ],
  "parameters": [
    {"label": "Prompt", "node": "170:151", "field": "prompt", "type": "text"},
    {"label": "Shift",  "node": "170:145", "field": "shift",  "type": "float", "default": 3.1,  "min": 0.0, "max": 10.0, "step": 0.1},
    {"label": "Seed",   "node": "170:169", "field": "seed",   "type": "seed",  "default": 0}
  ],
  "output_node": "9"
}
```

- [ ] **Step 5: Verify folder structure**

```bash
ls -R D:/ComfyXNuke/Workflows/z_image_turbo/ D:/ComfyXNuke/Workflows/qwen_image_edit/
```

Expected: each folder has `manifest.json` and `workflow.json`.

- [ ] **Step 6: Commit**

```bash
git add Workflows/z_image_turbo/ Workflows/qwen_image_edit/
git commit -m "feat: restructure workflows into subfolders with manifests"
```

---

### Task 2: Write the manifest-driven comfy_bridge.py

**Files:**
- Rewrite: `comfy_bridge.py`

This replaces the entire v0.1 file with the manifest-driven panel. The file has these sections: imports/constants, manifest discovery, ComfyUI communication, workflow patching, Nuke integration, panel class, registration.

- [ ] **Step 1: Write the complete comfy_bridge.py**

Create `comfy_bridge.py` with this content (replaces existing file):

```python
"""
Comfy Compositor — Manifest-driven ComfyUI Bridge for Nuke
"""

import copy
import json
import os
import random
import tempfile
import threading
import time
import uuid
import urllib.error
import urllib.request

import nuke
import nukescripts

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui


# ── Constants ────────────────────────────────────────────────────────────────
COMFY_URL = "http://127.0.0.1:8188"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS_DIR = os.path.join(SCRIPT_DIR, "Workflows")
OUTPUT_DIR = r"C:\Users\rikin\Local_AI\ComfyUI\output"


# ── Manifest Discovery ──────────────────────────────────────────────────────
def discover_workflows(workflows_dir):
    """Scan Workflows/ for subfolders with manifest.json + workflow.json.
    Returns dict: {category: [manifest_dict, ...]}
    Each manifest_dict gets an extra '_dir' key pointing to its subfolder.
    """
    categories = {}
    if not os.path.isdir(workflows_dir):
        return categories
    for entry in sorted(os.listdir(workflows_dir)):
        subdir = os.path.join(workflows_dir, entry)
        if not os.path.isdir(subdir):
            continue
        manifest_path = os.path.join(subdir, "manifest.json")
        workflow_path = os.path.join(subdir, "workflow.json")
        if not os.path.isfile(manifest_path) or not os.path.isfile(workflow_path):
            continue
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        required = ["name", "category", "parameters", "output_node"]
        if not all(k in manifest for k in required):
            continue
        manifest["_dir"] = subdir
        cat = manifest.get("category", "Uncategorized")
        categories.setdefault(cat, []).append(manifest)
    return categories


# ── ComfyUI Communication ───────────────────────────────────────────────────
def check_comfy_connection():
    """Return True if ComfyUI is reachable."""
    try:
        urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def upload_image(filepath):
    """Upload an image file to ComfyUI via /upload/image. Returns uploaded filename."""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(filepath)
    with open(filepath, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{COMFY_URL}/upload/image",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    return resp["name"]


def submit_workflow(workflow):
    """POST workflow to /prompt. Returns prompt_id."""
    client_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    response = json.loads(urllib.request.urlopen(req).read())
    return response["prompt_id"]


def poll_result(prompt_id, output_node, timeout=300):
    """Poll /history until the job finishes. Returns output image filename."""
    for _ in range(timeout * 2):
        try:
            resp = urllib.request.urlopen(
                f"{COMFY_URL}/history/{prompt_id}", timeout=5
            )
            history = json.loads(resp.read())
            if prompt_id in history:
                outputs = history[prompt_id]["outputs"]
                # Try the declared output node first
                if output_node in outputs and "images" in outputs[output_node]:
                    return outputs[output_node]["images"][0]["filename"]
                # Fallback: search all output nodes
                for node_out in outputs.values():
                    if "images" in node_out:
                        return node_out["images"][0]["filename"]
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("ComfyUI job timed out after 5 minutes")


# ── Workflow Patching ────────────────────────────────────────────────────────
def patch_workflow(workflow, manifest, param_values, input_images):
    """Deep-copy workflow and patch values using manifest mappings.
    param_values: {label: value}
    input_images: {label: uploaded_filename}
    """
    wf = copy.deepcopy(workflow)

    for param in manifest.get("parameters", []):
        node_id = param["node"]
        field = param["field"]
        label = param["label"]
        if label not in param_values:
            continue
        value = param_values[label]
        ptype = param["type"]
        if ptype in ("int", "seed"):
            value = int(value)
        elif ptype == "float":
            value = float(value)
        if node_id in wf and "inputs" in wf[node_id]:
            wf[node_id]["inputs"][field] = value

    for inp in manifest.get("inputs", []):
        node_id = inp["node"]
        field = inp["field"]
        label = inp["label"]
        if label in input_images:
            if node_id in wf and "inputs" in wf[node_id]:
                wf[node_id]["inputs"][field] = input_images[label]

    return wf


# ── Nuke Integration ────────────────────────────────────────────────────────
def create_read_node(image_path):
    """Create a Read node in the DAG pointing at the output image."""
    def _create():
        n = nuke.createNode("Read", inpanel=False)
        n["file"].setValue(image_path.replace("\\", "/"))
        basename = os.path.splitext(os.path.basename(image_path))[0]
        n["name"].setValue("ComfyAI_" + basename)
    nuke.executeInMainThread(_create)


def render_node_to_temp(node_name):
    """Render a Read node's current frame to a temp PNG. Returns the file path."""
    temp_path = os.path.join(
        tempfile.gettempdir(), f"comfy_input_{uuid.uuid4().hex}.png"
    )
    node = nuke.toNode(node_name)
    if node is None:
        raise ValueError(f"Node '{node_name}' not found in DAG")
    write = nuke.createNode("Write", inpanel=False)
    write["file"].setValue(temp_path.replace("\\", "/"))
    write["file_type"].setValue("png")
    write.setInput(0, node)
    frame = nuke.frame()
    nuke.execute(write, frame, frame)
    nuke.delete(write)
    return temp_path


# ── Stylesheet ───────────────────────────────────────────────────────────────
PANEL_STYLE = """
QWidget {
    font-size: 12px;
}
QTreeWidget {
    background-color: #282828;
    border: 1px solid #3a3a3a;
    outline: none;
}
QTreeWidget::item {
    padding: 4px 2px;
}
QTreeWidget::item:selected {
    background-color: #00d4ff22;
    color: #00d4ff;
}
QTreeWidget::branch:has-children:closed {
    image: none;
}
QTreeWidget::branch:has-children:open {
    image: none;
}
QPlainTextEdit {
    background-color: #282828;
    border: 1px solid #3a3a3a;
    color: #ddd;
    padding: 4px;
}
QSpinBox, QDoubleSpinBox {
    background-color: #282828;
    border: 1px solid #3a3a3a;
    color: #ddd;
    padding: 2px 4px;
}
QComboBox {
    background-color: #282828;
    border: 1px solid #3a3a3a;
    color: #ddd;
    padding: 2px 4px;
}
QPushButton#generateBtn {
    background-color: #ff2d9b;
    color: white;
    font-weight: bold;
    font-size: 13px;
    border-radius: 4px;
    border: none;
}
QPushButton#generateBtn:disabled {
    background-color: #555;
    color: #999;
}
QPushButton#generateBtn:hover {
    background-color: #ff50b0;
}
"""


# ── Panel ────────────────────────────────────────────────────────────────────
class ComfyCompositorPanel(QtWidgets.QWidget):

    status_signal = QtCore.Signal(str)
    result_signal = QtCore.Signal(str)
    error_signal = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comfy Compositor")
        self.setMinimumWidth(340)
        self.setStyleSheet(PANEL_STYLE)

        self._workflows = {}          # {category: [manifest, ...]}
        self._current_manifest = None
        self._param_widgets = []      # [(param_dict, widget), ...]
        self._seed_modes = {}         # {label: QComboBox}
        self._input_nodes = {}        # {label: node_name}
        self._input_labels = {}       # {label: QLabel showing node name}

        self._build_ui()
        self._connect_signals()
        self._refresh_workflows()
        QtCore.QTimer.singleShot(500, self._check_connection)

    # ── Build UI ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Comfy Compositor")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #00d4ff;")
        header.addWidget(title)
        header.addStretch()
        self._status_dot = QtWidgets.QLabel("\u25cf")
        self._status_dot.setStyleSheet("color: #888; font-size: 16px;")
        header.addWidget(self._status_dot)
        root.addLayout(header)

        root.addWidget(self._divider())

        # Workflow tree
        tree_label = QtWidgets.QLabel("Workflows")
        tree_label.setStyleSheet("color: #888; font-size: 10px; text-transform: uppercase;")
        root.addWidget(tree_label)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True)
        self._tree.setFixedHeight(160)
        root.addWidget(self._tree)

        # Refresh button
        refresh_btn = QtWidgets.QPushButton("Refresh Workflows")
        refresh_btn.setFixedHeight(24)
        refresh_btn.setStyleSheet("font-size: 10px; color: #888; background: #2a2a2a; border: 1px solid #3a3a3a;")
        refresh_btn.clicked.connect(self._refresh_workflows)
        root.addWidget(refresh_btn)

        root.addWidget(self._divider())

        # Workflow info
        self._wf_info = QtWidgets.QLabel("Select a workflow to begin.")
        self._wf_info.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        self._wf_info.setWordWrap(True)
        root.addWidget(self._wf_info)

        # Dynamic area — rebuilt when workflow is selected
        self._dynamic_widget = QtWidgets.QWidget()
        self._dynamic_layout = QtWidgets.QVBoxLayout(self._dynamic_widget)
        self._dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self._dynamic_layout.setSpacing(6)
        root.addWidget(self._dynamic_widget)

        root.addWidget(self._divider())

        # Generate button
        self._generate_btn = QtWidgets.QPushButton("\u25b6  Generate")
        self._generate_btn.setObjectName("generateBtn")
        self._generate_btn.setFixedHeight(36)
        self._generate_btn.setEnabled(False)
        root.addWidget(self._generate_btn)

        # Status
        self._status_label = QtWidgets.QLabel("Ready")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        self._status_label.setWordWrap(True)
        root.addWidget(self._status_label)

        root.addStretch()

    def _divider(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("color: #3a3a3a;")
        return line

    # ── Signals ──────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self._generate_btn.clicked.connect(self._on_generate)
        self._tree.itemClicked.connect(self._on_tree_click)
        self.status_signal.connect(self._on_status)
        self.result_signal.connect(self._on_result)
        self.error_signal.connect(self._on_error)

    # ── Connection ───────────────────────────────────────────────────────────
    def _check_connection(self):
        if check_comfy_connection():
            self._status_dot.setStyleSheet("color: #00d4ff; font-size: 16px;")
            self._status_dot.setToolTip("Connected to ComfyUI")
        else:
            self._status_dot.setStyleSheet("color: #ff4444; font-size: 16px;")
            self._status_dot.setToolTip("Cannot reach ComfyUI at " + COMFY_URL)

    # ── Workflow Discovery ───────────────────────────────────────────────────
    def _refresh_workflows(self):
        self._workflows = discover_workflows(WORKFLOWS_DIR)
        self._build_tree()

    def _build_tree(self):
        self._tree.clear()
        for category, manifests in sorted(self._workflows.items()):
            cat_item = QtWidgets.QTreeWidgetItem(["\u25bc " + category])
            cat_item.setFlags(cat_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            cat_item.setExpanded(True)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            cat_item.setForeground(0, QtGui.QColor("#00d4ff"))
            self._tree.addTopLevelItem(cat_item)
            for manifest in manifests:
                wf_item = QtWidgets.QTreeWidgetItem(["  " + manifest["name"]])
                wf_item.setData(0, QtCore.Qt.UserRole, manifest)
                cat_item.addChild(wf_item)

    def _on_tree_click(self, item, column):
        manifest = item.data(0, QtCore.Qt.UserRole)
        if manifest is None:
            # Clicked a category header — toggle expand/collapse
            item.setExpanded(not item.isExpanded())
            prefix = "\u25bc " if item.isExpanded() else "\u25b6 "
            text = item.text(0)
            # Strip old prefix and apply new one
            clean = text.lstrip("\u25bc \u25b6 ").strip()
            item.setText(0, prefix + clean)
            return
        self._current_manifest = manifest
        desc = manifest.get("description", "")
        self._wf_info.setText(f"<b>{manifest['name']}</b> — {desc}")
        self._wf_info.setStyleSheet("color: #ccc; font-size: 11px; font-style: normal;")
        self._rebuild_dynamic_ui(manifest)
        self._generate_btn.setEnabled(True)

    # ── Dynamic UI ───────────────────────────────────────────────────────────
    def _rebuild_dynamic_ui(self, manifest):
        # Clear old widgets
        self._param_widgets = []
        self._seed_modes = {}
        self._input_nodes = {}
        self._input_labels = {}
        while self._dynamic_layout.count():
            item = self._dynamic_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Build input slots
        inputs = manifest.get("inputs", [])
        if inputs:
            inp_header = QtWidgets.QLabel("Image Inputs")
            inp_header.setStyleSheet(
                "color: #ff2d9b; font-size: 10px; text-transform: uppercase; font-weight: bold;"
            )
            self._dynamic_layout.addWidget(inp_header)
            for inp in inputs:
                self._build_input_row(inp["label"])
            self._dynamic_layout.addWidget(self._divider())

        # Build parameters
        params = manifest.get("parameters", [])
        if params:
            param_header = QtWidgets.QLabel("Parameters")
            param_header.setStyleSheet(
                "color: #ff2d9b; font-size: 10px; text-transform: uppercase; font-weight: bold;"
            )
            self._dynamic_layout.addWidget(param_header)
            for param in params:
                self._build_param_row(param)

    def _build_input_row(self, label):
        row = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel(label + ":")
        name_label.setStyleSheet("color: #ccc;")
        name_label.setFixedWidth(100)
        row.addWidget(name_label)

        node_label = QtWidgets.QLabel("(none)")
        node_label.setStyleSheet("color: #888; font-style: italic;")
        self._input_labels[label] = node_label
        row.addWidget(node_label, 1)

        add_btn = QtWidgets.QPushButton("+ Add")
        add_btn.setFixedWidth(50)
        add_btn.setFixedHeight(22)
        add_btn.setStyleSheet("font-size: 10px; background: #2a2a2a; border: 1px solid #3a3a3a; color: #ccc;")
        add_btn.clicked.connect(lambda checked, lbl=label: self._on_add_input(lbl))
        row.addWidget(add_btn)

        clear_btn = QtWidgets.QPushButton("X")
        clear_btn.setFixedWidth(22)
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet("font-size: 10px; background: #2a2a2a; border: 1px solid #3a3a3a; color: #888;")
        clear_btn.clicked.connect(lambda checked, lbl=label: self._on_clear_input(lbl))
        row.addWidget(clear_btn)

        container = QtWidgets.QWidget()
        container.setLayout(row)
        self._dynamic_layout.addWidget(container)

    def _on_add_input(self, label):
        try:
            sel = nuke.selectedNode()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a Read node in the DAG first.")
            return
        if sel.Class() != "Read":
            QtWidgets.QMessageBox.warning(self, "Wrong Node", f"'{sel.name()}' is not a Read node.")
            return
        self._input_nodes[label] = sel.name()
        self._input_labels[label].setText(sel.name())
        self._input_labels[label].setStyleSheet("color: #00d4ff; font-style: normal;")

    def _on_clear_input(self, label):
        self._input_nodes.pop(label, None)
        self._input_labels[label].setText("(none)")
        self._input_labels[label].setStyleSheet("color: #888; font-style: italic;")

    def _build_param_row(self, param):
        ptype = param["type"]

        if ptype == "text":
            lbl = QtWidgets.QLabel(param["label"])
            lbl.setStyleSheet("color: #ccc;")
            self._dynamic_layout.addWidget(lbl)
            widget = QtWidgets.QPlainTextEdit()
            widget.setPlaceholderText(f"Enter {param['label'].lower()}...")
            widget.setFixedHeight(80)
            self._dynamic_layout.addWidget(widget)
            self._param_widgets.append((param, widget))
            return

        row = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel(param["label"] + ":")
        name_label.setStyleSheet("color: #ccc;")
        name_label.setFixedWidth(60)
        row.addWidget(name_label)

        if ptype == "int":
            widget = QtWidgets.QSpinBox()
            widget.setRange(param.get("min", 0), param.get("max", 999999))
            widget.setSingleStep(param.get("step", 1))
            widget.setValue(param.get("default", 0))
            row.addWidget(widget)
            self._param_widgets.append((param, widget))

        elif ptype == "float":
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(param.get("min", 0.0), param.get("max", 999.0))
            widget.setSingleStep(param.get("step", 0.1))
            widget.setValue(param.get("default", 0.0))
            row.addWidget(widget)
            self._param_widgets.append((param, widget))

        elif ptype == "seed":
            widget = QtWidgets.QSpinBox()
            widget.setRange(0, 2147483647)
            widget.setValue(param.get("default", 0))
            row.addWidget(widget)
            mode = QtWidgets.QComboBox()
            mode.addItems(["Fixed", "Random"])
            mode.setCurrentIndex(1)
            row.addWidget(mode)
            self._seed_modes[param["label"]] = mode
            self._param_widgets.append((param, widget))

        row.addStretch()
        container = QtWidgets.QWidget()
        container.setLayout(row)
        self._dynamic_layout.addWidget(container)

    # ── Collect Parameters ───────────────────────────────────────────────────
    def _collect_params(self):
        values = {}
        for param, widget in self._param_widgets:
            label = param["label"]
            ptype = param["type"]
            if ptype == "text":
                values[label] = widget.toPlainText().strip()
            elif ptype == "seed":
                mode = self._seed_modes.get(label)
                if mode and mode.currentText() == "Random":
                    val = random.randint(0, 2147483647)
                    widget.setValue(val)
                    values[label] = val
                else:
                    values[label] = widget.value()
            else:
                values[label] = widget.value()
        return values

    # ── Generate ─────────────────────────────────────────────────────────────
    def _on_generate(self):
        if self._current_manifest is None:
            return

        # Validate: check required text params are filled
        for param, widget in self._param_widgets:
            if param["type"] == "text" and not widget.toPlainText().strip():
                QtWidgets.QMessageBox.warning(
                    self, "Missing Input", f"Please enter {param['label']}."
                )
                return

        # Validate: check required image inputs are assigned
        for inp in self._current_manifest.get("inputs", []):
            if inp["label"] not in self._input_nodes:
                QtWidgets.QMessageBox.warning(
                    self, "Missing Input",
                    f"Please assign a Read node for '{inp['label']}'."
                )
                return

        # Collect params
        param_values = self._collect_params()

        # Render input images to temp files (main thread — fast, one frame)
        input_temp_paths = {}
        for label, node_name in self._input_nodes.items():
            try:
                temp_path = render_node_to_temp(node_name)
                input_temp_paths[label] = temp_path
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Render Error", f"Failed to render '{node_name}': {e}"
                )
                return

        self._generate_btn.setEnabled(False)
        self._status_label.setText("Submitting...")
        self._status_label.setStyleSheet("color: #00d4ff; font-size: 11px;")

        threading.Thread(
            target=self._run_job,
            args=(param_values, input_temp_paths),
            daemon=True,
        ).start()

    def _run_job(self, param_values, input_temp_paths):
        try:
            manifest = self._current_manifest

            # Upload input images
            uploaded = {}
            for label, path in input_temp_paths.items():
                self.status_signal.emit(f"Uploading {label}...")
                uploaded_name = upload_image(path)
                uploaded[label] = uploaded_name

            # Load and patch workflow
            wf_path = os.path.join(manifest["_dir"], "workflow.json")
            with open(wf_path, "r") as f:
                workflow = json.load(f)

            patched = patch_workflow(workflow, manifest, param_values, uploaded)

            # Submit
            self.status_signal.emit("Job submitted — waiting for result...")
            prompt_id = submit_workflow(patched)

            # Poll
            output_node = manifest.get("output_node", "9")
            filename = poll_result(prompt_id, output_node)

            # Build output path
            output_path = os.path.join(OUTPUT_DIR, filename)
            self.result_signal.emit(output_path)

        except Exception as e:
            self.error_signal.emit(str(e))

    # ── Callbacks (main thread) ──────────────────────────────────────────────
    def _on_status(self, msg):
        self._status_label.setText(msg)

    def _on_result(self, path):
        self._status_label.setText(f"Done \u2192 {os.path.basename(path)}")
        self._status_label.setStyleSheet("color: #44ff44; font-size: 11px;")
        self._generate_btn.setEnabled(True)
        create_read_node(path)

    def _on_error(self, msg):
        self._status_label.setText(f"Error: {msg}")
        self._status_label.setStyleSheet("color: #ff4444; font-size: 11px;")
        self._generate_btn.setEnabled(True)


# ── Nuke Registration ───────────────────────────────────────────────────────
_widget_instance = None


def get_widget():
    global _widget_instance
    if _widget_instance is None:
        _widget_instance = ComfyCompositorPanel()
    return _widget_instance


def show_panel():
    pane = nuke.getPaneFor("Properties.1")
    panel = nukescripts.registerWidgetAsPanel(
        "comfy_bridge.get_widget",
        "Comfy Compositor",
        "uk.co.comfycompositor.panel",
        create=True,
    )
    panel.addToPane(pane)
```

- [ ] **Step 2: Verify syntax is valid**

```bash
python -c "import ast; ast.parse(open('D:/ComfyXNuke/comfy_bridge.py').read()); print('Syntax OK')"
```

Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add comfy_bridge.py
git commit -m "feat: rewrite comfy_bridge.py as manifest-driven Comfy Compositor panel"
```

---

### Task 3: Write menu.py for Nuke auto-registration

**Files:**
- Create: `menu.py`

- [ ] **Step 1: Write menu.py**

Create `menu.py`:

```python
"""
Comfy Compositor — Nuke menu registration.
Add this directory to NUKE_PATH or nuke.pluginAddPath() in ~/.nuke/init.py.
"""
import nuke

toolbar = nuke.menu("Nodes")
comfy_menu = toolbar.addMenu("Comfy Compositor", icon="")
comfy_menu.addCommand("Open Panel", "import comfy_bridge; comfy_bridge.show_panel()")
```

- [ ] **Step 2: Commit**

```bash
git add menu.py
git commit -m "feat: add menu.py for Nuke menu registration"
```

---

### Task 4: Clean up old workflow files

**Files:**
- Remove: `Workflows/API-image_z_image_turbo.json`
- Remove: `Workflows/API-image_qwen_image_edit_2511.json`

- [ ] **Step 1: Remove the old flat workflow files**

The workflows have been copied to subfolders in Task 1. Remove the originals:

```bash
rm D:/ComfyXNuke/Workflows/API-image_z_image_turbo.json
rm D:/ComfyXNuke/Workflows/API-image_qwen_image_edit_2511.json
```

- [ ] **Step 2: Verify only subfolders remain**

```bash
ls D:/ComfyXNuke/Workflows/
```

Expected: `qwen_image_edit/  z_image_turbo/`

- [ ] **Step 3: Commit**

```bash
git add -A Workflows/
git commit -m "chore: remove old flat workflow files (now in subfolders)"
```

---

### Task 5: End-to-end verification in Nuke

**Files:** None (manual testing)

- [ ] **Step 1: Verify Nuke can load the panel**

In Nuke's Script Editor, run:

```python
import comfy_bridge
comfy_bridge.show_panel()
```

Expected: The "Comfy Compositor" panel appears docked with:
- Cyan title "Comfy Compositor" + status dot
- Workflow tree with "Text to Image" and "Image to Image" categories
- "Z-Image Turbo" and "Qwen Image Edit" nested under their categories
- "Select a workflow to begin." info text
- Disabled Generate button
- "Ready" status

- [ ] **Step 2: Test workflow selection**

Click "Z-Image Turbo" in the tree.

Expected:
- Info text updates to show name and description
- Parameters appear: Prompt (text area), Width, Height, Shift, Steps, CFG, Seed
- No input slots (text-to-image has no image inputs)
- Generate button becomes enabled

- [ ] **Step 3: Test text-to-image generation**

1. Enter a prompt (e.g., "A sunset over mountains")
2. Click Generate
3. Wait for completion

Expected:
- Status shows "Submitting..." → "Job submitted — waiting for result..." → "Done → filename.png"
- A Read node named "ComfyAI_..." appears in the DAG pointing to the output image

- [ ] **Step 4: Test workflow switching**

Click "Qwen Image Edit" in the tree.

Expected:
- Parameters change to: Prompt, Shift, Seed
- Input slots appear: "Source Image" and "Reference" with "Add" and "X" buttons
- Previous Z-Image Turbo parameters are gone

- [ ] **Step 5: Test image input assignment**

1. Create a Read node in the DAG pointing to any image
2. Select it
3. Click "+ Add" next to "Source Image"

Expected:
- The Read node's name appears next to "Source Image" in cyan
- Clicking "X" clears it back to "(none)"
