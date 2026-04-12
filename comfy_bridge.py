"""
Comfy Compositor — Dynamic ComfyUI Bridge for Nuke
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

INFRASTRUCTURE_CLASSES = {
    "CLIPLoader", "VAELoader", "UNETLoader", "DualCLIPLoader",
    "CheckpointLoaderSimple", "LoraLoader", "LoraLoaderModelOnly",
    "VAEDecode", "VAEEncode", "SaveImage", "PreviewImage",
    "ConditioningZeroOut", "ConditioningCombine", "ConditioningConcat",
    "FluxKontextImageScale", "FluxKontextMultiReferenceLatentMethod",
    "CFGNorm", "ComfySwitchNode",
}

GLOBAL_PARAM_FIELDS = {"seed", "steps", "cfg", "denoise", "shift"}

PROMPT_FIELDS = {"text", "prompt"}

FLOAT_FIELD_HINTS = {"denoise", "strength", "shift", "cfg", "strength_model"}


# ── Workflow Discovery ──────────────────────────────────────────────────────
def discover_workflows(workflows_dir):
    """Scan Workflows/ for subfolders with workflow.json.
    manifest.json is optional (provides name, category, description).
    Returns dict: {category: [info_dict, ...]}
    """
    categories = {}
    if not os.path.isdir(workflows_dir):
        return categories
    for entry in sorted(os.listdir(workflows_dir)):
        subdir = os.path.join(workflows_dir, entry)
        if not os.path.isdir(subdir):
            continue
        workflow_path = os.path.join(subdir, "workflow.json")
        if not os.path.isfile(workflow_path):
            continue

        info = {"_dir": subdir}

        manifest_path = os.path.join(subdir, "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                info["name"] = manifest.get("name", entry.replace("_", " ").title())
                info["category"] = manifest.get("category", "Uncategorized")
                info["description"] = manifest.get("description", "")
                info["output_node"] = manifest.get("output_node")
            except (json.JSONDecodeError, IOError):
                info["name"] = entry.replace("_", " ").title()
                info["category"] = "Uncategorized"
                info["description"] = ""
                info["output_node"] = None
        else:
            info["name"] = entry.replace("_", " ").title()
            info["category"] = "Uncategorized"
            info["description"] = ""
            info["output_node"] = None

        cat = info["category"]
        categories.setdefault(cat, []).append(info)
    return categories


# ── Workflow Introspection ─────────────────────────────────────────────────
def auto_detect_workflow(workflow):
    """Analyze workflow.json and return structured parameter data.

    Returns dict with keys:
        load_image_nodes: [(node_id, title, current_filename), ...]
        output_node: node_id or None
        param_nodes: [{node_id, title, class_type, fields: [(name, value, type), ...]}, ...]
        global_params: [(node_id, field_name, value, value_type), ...]
    """
    load_image_nodes = []
    output_node = None
    param_nodes = []
    global_params = []

    for node_id, node_data in workflow.items():
        class_type = node_data.get("class_type", "")
        title = node_data.get("_meta", {}).get("title", class_type)
        inputs = node_data.get("inputs", {})

        if class_type == "LoadImage":
            filename = inputs.get("image", "")
            load_image_nodes.append((node_id, title, filename))
            continue

        if class_type in ("SaveImage", "PreviewImage"):
            output_node = node_id
            continue

        if class_type in INFRASTRUCTURE_CLASSES:
            continue

        fields = []
        for field_name, value in inputs.items():
            if isinstance(value, list):
                continue

            if isinstance(value, bool):
                value_type = "bool"
            elif isinstance(value, int):
                value_type = "seed" if field_name == "seed" else "int"
            elif isinstance(value, float):
                value_type = "float"
            elif isinstance(value, str):
                value_type = "text" if field_name in PROMPT_FIELDS else "string"
            else:
                continue

            if value_type == "int" and field_name in FLOAT_FIELD_HINTS:
                value_type = "float"
                value = float(value)

            fields.append((field_name, value, value_type))

            if field_name in GLOBAL_PARAM_FIELDS or field_name in PROMPT_FIELDS:
                global_params.append((node_id, field_name, value, value_type))

        if fields:
            param_nodes.append({
                "node_id": node_id,
                "title": title,
                "class_type": class_type,
                "fields": fields,
            })

    return {
        "load_image_nodes": load_image_nodes,
        "output_node": output_node,
        "param_nodes": param_nodes,
        "global_params": global_params,
    }


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
                if output_node in outputs and "images" in outputs[output_node]:
                    return outputs[output_node]["images"][0]["filename"]
                for node_out in outputs.values():
                    if "images" in node_out:
                        return node_out["images"][0]["filename"]
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("ComfyUI job timed out after 5 minutes")


# ── Workflow Patching ────────────────────────────────────────────────────────
def patch_workflow(workflow, param_values, input_images, locked_nodes=None):
    """Deep-copy workflow and patch values.
    param_values: {(node_id, field): value}
    input_images: {node_id: uploaded_filename}
    locked_nodes: set of node_ids to skip
    """
    wf = copy.deepcopy(workflow)
    for (node_id, field), value in param_values.items():
        if locked_nodes and node_id in locked_nodes:
            continue
        if node_id in wf and field in wf[node_id].get("inputs", {}):
            wf[node_id]["inputs"][field] = value
    for node_id, filename in input_images.items():
        if node_id in wf and "image" in wf[node_id].get("inputs", {}):
            wf[node_id]["inputs"]["image"] = filename
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
    """Render a node's current frame to a temp PNG. Returns the file path."""
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
    try:
        nuke.execute(write, frame, frame)
    finally:
        nuke.delete(write)
    return temp_path


# ── Collapsible Section Widget ──────────────────────────────────────────────
class CollapsibleSection(QtWidgets.QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_row = QtWidgets.QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self._toggle_btn = QtWidgets.QPushButton("\u25b6 " + title)
        self._toggle_btn.setStyleSheet(
            "text-align: left; background: #2a2a2a; border: 1px solid #3a3a3a; "
            "color: #ccc; padding: 4px 8px; font-size: 11px;"
        )
        self._toggle_btn.clicked.connect(self._toggle)
        header_row.addWidget(self._toggle_btn)

        self._lock_cb = QtWidgets.QCheckBox("Lock")
        self._lock_cb.setStyleSheet("color: #888; font-size: 10px;")
        header_row.addWidget(self._lock_cb)

        layout.addLayout(header_row)

        self._content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 0, 4)
        self._content_layout.setSpacing(4)
        self._content.setVisible(False)
        layout.addWidget(self._content)

        self._expanded = False
        self._title = title

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        prefix = "\u25bc " if self._expanded else "\u25b6 "
        self._toggle_btn.setText(prefix + self._title)

    def content_layout(self):
        return self._content_layout

    def lock_checkbox(self):
        return self._lock_cb


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
QLineEdit {
    background-color: #282828;
    border: 1px solid #3a3a3a;
    color: #ddd;
    padding: 2px 4px;
}
QScrollArea {
    border: none;
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
    connection_signal = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comfy Compositor")
        self.setMinimumWidth(340)
        self.setStyleSheet(PANEL_STYLE)

        self._workflows = {}
        self._current_wf_info = None
        self._current_workflow = None
        self._current_analysis = None
        self._param_widgets = {}       # {(node_id, field): widget}
        self._lock_checkboxes = {}     # {node_id: QCheckBox}
        self._input_nodes = {}         # {node_id: nuke_node_name}
        self._input_labels = {}        # {node_id: QLabel}
        self._seed_modes = {}          # {(node_id, field): QComboBox}

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

        # Dynamic area with scroll
        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._dynamic_widget = QtWidgets.QWidget()
        self._dynamic_layout = QtWidgets.QVBoxLayout(self._dynamic_widget)
        self._dynamic_layout.setContentsMargins(0, 0, 0, 0)
        self._dynamic_layout.setSpacing(6)
        self._dynamic_layout.addStretch()
        self._scroll_area.setWidget(self._dynamic_widget)
        root.addWidget(self._scroll_area, 1)

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
        def _check():
            result = check_comfy_connection()
            self.connection_signal.emit(result)
        self.connection_signal.connect(self._on_connection_result)
        threading.Thread(target=_check, daemon=True).start()

    def _on_connection_result(self, connected):
        if connected:
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
        for category, infos in sorted(self._workflows.items()):
            cat_item = QtWidgets.QTreeWidgetItem(["\u25bc " + category])
            cat_item.setFlags(cat_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            cat_item.setExpanded(True)
            font = cat_item.font(0)
            font.setBold(True)
            cat_item.setFont(0, font)
            cat_item.setForeground(0, QtGui.QColor("#00d4ff"))
            self._tree.addTopLevelItem(cat_item)
            for info in infos:
                wf_item = QtWidgets.QTreeWidgetItem(["  " + info["name"]])
                wf_item.setData(0, QtCore.Qt.UserRole, info)
                cat_item.addChild(wf_item)

    def _on_tree_click(self, item, column):
        data = item.data(0, QtCore.Qt.UserRole)
        if data is None:
            item.setExpanded(not item.isExpanded())
            prefix = "\u25bc " if item.isExpanded() else "\u25b6 "
            clean = item.text(0)[2:].strip()
            item.setText(0, prefix + clean)
            return

        self._current_wf_info = data
        desc = data.get("description", "")
        self._wf_info.setText(f"<b>{data['name']}</b> \u2014 {desc}")
        self._wf_info.setStyleSheet("color: #ccc; font-size: 11px; font-style: normal;")

        # Load and analyze workflow
        wf_path = os.path.join(data["_dir"], "workflow.json")
        with open(wf_path, "r") as f:
            self._current_workflow = json.load(f)

        self._current_analysis = auto_detect_workflow(self._current_workflow)

        # Override output_node from manifest if provided
        if data.get("output_node"):
            self._current_analysis["output_node"] = data["output_node"]

        self._rebuild_dynamic_ui()
        self._generate_btn.setEnabled(True)

    # ── Dynamic UI ───────────────────────────────────────────────────────────
    def _rebuild_dynamic_ui(self):
        # Clear old widgets
        self._param_widgets = {}
        self._lock_checkboxes = {}
        self._input_nodes = {}
        self._input_labels = {}
        self._seed_modes = {}
        while self._dynamic_layout.count():
            item = self._dynamic_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        analysis = self._current_analysis

        # ── Input Mapping ────────────────────────────────────────────────────
        if analysis["load_image_nodes"]:
            header = QtWidgets.QLabel("Input Mapping")
            header.setStyleSheet(
                "color: #ff2d9b; font-size: 10px; text-transform: uppercase; font-weight: bold;"
            )
            self._dynamic_layout.addWidget(header)
            for node_id, title, filename in analysis["load_image_nodes"]:
                self._build_input_row(node_id, title, filename)
            self._dynamic_layout.addWidget(self._divider())

        # ── Global Parameters ────────────────────────────────────────────────
        global_keys = set()
        if analysis["global_params"]:
            header = QtWidgets.QLabel("Global Parameters")
            header.setStyleSheet(
                "color: #ff2d9b; font-size: 10px; text-transform: uppercase; font-weight: bold;"
            )
            self._dynamic_layout.addWidget(header)

            for node_id, field_name, value, value_type in analysis["global_params"]:
                key = (node_id, field_name)
                if key in global_keys:
                    continue
                global_keys.add(key)
                self._build_field_widget(node_id, field_name, value, value_type, self._dynamic_layout)

            self._dynamic_layout.addWidget(self._divider())

        # ── Node Sections (collapsible) ──────────────────────────────────────
        for node_info in analysis["param_nodes"]:
            node_id = node_info["node_id"]
            title = node_info["title"]
            class_type = node_info["class_type"]

            remaining = [
                (f, v, t) for f, v, t in node_info["fields"]
                if (node_id, f) not in global_keys
            ]
            if not remaining:
                continue

            section = CollapsibleSection(f"{title} ({class_type})")
            self._lock_checkboxes[node_id] = section.lock_checkbox()

            for field_name, value, value_type in remaining:
                self._build_field_widget(
                    node_id, field_name, value, value_type, section.content_layout()
                )

            self._dynamic_layout.addWidget(section)

        self._dynamic_layout.addStretch()

    def _build_input_row(self, node_id, title, filename):
        row = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel(title + ":")
        name_label.setStyleSheet("color: #ccc;")
        name_label.setFixedWidth(100)
        row.addWidget(name_label)

        node_label = QtWidgets.QLabel("(none)")
        node_label.setStyleSheet("color: #888; font-style: italic;")
        node_label.setToolTip(f"Comfy default: {filename}")
        self._input_labels[node_id] = node_label
        row.addWidget(node_label, 1)

        add_btn = QtWidgets.QPushButton("+ Add")
        add_btn.setFixedWidth(50)
        add_btn.setFixedHeight(22)
        add_btn.setStyleSheet("font-size: 10px; background: #2a2a2a; border: 1px solid #3a3a3a; color: #ccc;")
        add_btn.clicked.connect(lambda _=False, nid=node_id: self._on_add_input(nid))
        row.addWidget(add_btn)

        clear_btn = QtWidgets.QPushButton("X")
        clear_btn.setFixedWidth(22)
        clear_btn.setFixedHeight(22)
        clear_btn.setStyleSheet("font-size: 10px; background: #2a2a2a; border: 1px solid #3a3a3a; color: #888;")
        clear_btn.clicked.connect(lambda _=False, nid=node_id: self._on_clear_input(nid))
        row.addWidget(clear_btn)

        container = QtWidgets.QWidget()
        container.setLayout(row)
        self._dynamic_layout.addWidget(container)

    def _on_add_input(self, node_id):
        try:
            sel = nuke.selectedNode()
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "No Selection", "Select a node in the DAG first.")
            return
        self._input_nodes[node_id] = sel.name()
        self._input_labels[node_id].setText(sel.name())
        self._input_labels[node_id].setStyleSheet("color: #00d4ff; font-style: normal;")

    def _on_clear_input(self, node_id):
        self._input_nodes.pop(node_id, None)
        self._input_labels[node_id].setText("(none)")
        self._input_labels[node_id].setStyleSheet("color: #888; font-style: italic;")

    def _build_field_widget(self, node_id, field_name, value, value_type, layout):
        key = (node_id, field_name)

        if value_type == "text":
            lbl = QtWidgets.QLabel(field_name.replace("_", " ").title())
            lbl.setStyleSheet("color: #ccc;")
            layout.addWidget(lbl)
            widget = QtWidgets.QPlainTextEdit()
            widget.setPlainText(str(value))
            widget.setPlaceholderText(f"Enter {field_name}...")
            widget.setFixedHeight(80)
            layout.addWidget(widget)
            self._param_widgets[key] = widget
            return

        row = QtWidgets.QHBoxLayout()
        label_text = field_name.replace("_", " ").title() + ":"
        name_label = QtWidgets.QLabel(label_text)
        name_label.setStyleSheet("color: #ccc;")
        name_label.setFixedWidth(80)
        row.addWidget(name_label)

        if value_type == "seed":
            widget = QtWidgets.QSpinBox()
            widget.setRange(0, 2147483647)
            widget.setValue(int(value))
            row.addWidget(widget)
            mode = QtWidgets.QComboBox()
            mode.addItems(["Fixed", "Random"])
            mode.setCurrentIndex(1)
            row.addWidget(mode)
            self._seed_modes[key] = mode
            self._param_widgets[key] = widget
        elif value_type == "int":
            widget = QtWidgets.QSpinBox()
            widget.setRange(0, 999999)
            widget.setValue(int(value))
            row.addWidget(widget)
            self._param_widgets[key] = widget
        elif value_type == "float":
            widget = QtWidgets.QDoubleSpinBox()
            widget.setRange(0.0, 999.0)
            widget.setSingleStep(0.1)
            widget.setDecimals(2)
            widget.setValue(float(value))
            row.addWidget(widget)
            self._param_widgets[key] = widget
        elif value_type == "bool":
            widget = QtWidgets.QCheckBox()
            widget.setChecked(bool(value))
            row.addWidget(widget)
            self._param_widgets[key] = widget
        elif value_type == "string":
            widget = QtWidgets.QLineEdit()
            widget.setText(str(value))
            row.addWidget(widget)
            self._param_widgets[key] = widget

        row.addStretch()
        container = QtWidgets.QWidget()
        container.setLayout(row)
        layout.addWidget(container)

    # ── Collect Parameters ───────────────────────────────────────────────────
    def _extract_widget_value(self, key, widget):
        if isinstance(widget, QtWidgets.QPlainTextEdit):
            return widget.toPlainText().strip()
        elif isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        elif isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            if key in self._seed_modes:
                mode = self._seed_modes[key]
                if mode.currentText() == "Random":
                    val = random.randint(0, 2147483647)
                    widget.setValue(val)
                    return val
            return widget.value()
        return None

    def _collect_dynamic_params(self):
        values = {}
        for key, widget in self._param_widgets.items():
            values[key] = self._extract_widget_value(key, widget)
        return values

    # ── Generate ─────────────────────────────────────────────────────────────
    def _on_generate(self):
        if self._current_workflow is None or self._current_analysis is None:
            return

        # Validate input nodes
        for node_id, title, filename in self._current_analysis["load_image_nodes"]:
            if node_id not in self._input_nodes:
                QtWidgets.QMessageBox.warning(
                    self, "Missing Input",
                    f"Please assign a Nuke node for '{title}'."
                )
                return

        param_values = self._collect_dynamic_params()

        locked_nodes = set()
        for nid, cb in self._lock_checkboxes.items():
            if cb.isChecked():
                locked_nodes.add(nid)

        # Render input images on main thread
        input_temp_paths = {}
        for node_id, nuke_name in self._input_nodes.items():
            try:
                temp_path = render_node_to_temp(nuke_name)
                input_temp_paths[node_id] = temp_path
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Render Error", f"Failed to render '{nuke_name}': {e}"
                )
                return

        self._generate_btn.setEnabled(False)
        self._status_label.setText("Preparing...")
        self._status_label.setStyleSheet("color: #00d4ff; font-size: 11px;")

        threading.Thread(
            target=self._run_job,
            args=(param_values, input_temp_paths, locked_nodes),
            daemon=True,
        ).start()

    def _run_job(self, param_values, input_temp_paths, locked_nodes):
        try:
            # Upload input images
            uploaded = {}
            for node_id, path in input_temp_paths.items():
                self.status_signal.emit(f"Uploading image...")
                uploaded[node_id] = upload_image(path)

            # Patch workflow
            patched = patch_workflow(
                self._current_workflow, param_values, uploaded, locked_nodes
            )

            # Submit
            self.status_signal.emit("Submitting...")
            prompt_id = submit_workflow(patched)

            # Poll
            self.status_signal.emit("Working...")
            output_node = self._current_analysis.get("output_node") or "9"
            filename = poll_result(prompt_id, output_node)

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
