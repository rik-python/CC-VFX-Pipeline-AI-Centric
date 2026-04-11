"""
ComfyUI Bridge for Nuke
Prototype v0.1 - ZIT Text to Image
"""

import json
import os
import random
import threading
import time
import urllib.request
import urllib.error
import copy

import nuke

try:
    from PySide2 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui

# ── Config ────────────────────────────────────────────────────────────────────
COMFY_URL      = "http://127.0.0.1:8188"
WORKFLOW_PATH  = r"D:\ComfyXNuke\Workflows\API-image_z_image_turbo.json"
OUTPUT_DIR     = r"C:\Users\rikin\Local_AI\ComfyUI\output"

# ── Node IDs (from API export) ────────────────────────────────────────────────
NODE_PROMPT    = "57:27"   # CLIPTextEncode - text
NODE_LATENT    = "57:13"   # EmptySD3LatentImage - width / height
NODE_SHIFT     = "57:11"   # ModelSamplingAuraFlow - shift
NODE_KSAMPLER  = "57:3"    # KSampler - seed, steps, cfg
NODE_SAVE      = "9"       # SaveImage - filename_prefix


# ── Helpers ───────────────────────────────────────────────────────────────────
def check_comfy_connection():
    try:
        urllib.request.urlopen(f"{COMFY_URL}/system_stats", timeout=2)
        return True
    except Exception:
        return False


def load_workflow():
    with open(WORKFLOW_PATH, "r") as f:
        return json.load(f)


def patch_workflow(workflow, positive, width, height, shift, seed, steps, cfg, filename_prefix):
    wf = copy.deepcopy(workflow)
    wf[NODE_PROMPT]["inputs"]["text"]         = positive
    wf[NODE_LATENT]["inputs"]["width"]        = int(width)
    wf[NODE_LATENT]["inputs"]["height"]       = int(height)
    wf[NODE_SHIFT]["inputs"]["shift"]         = float(shift)
    wf[NODE_KSAMPLER]["inputs"]["seed"]       = int(seed)
    wf[NODE_KSAMPLER]["inputs"]["steps"]      = int(steps)
    wf[NODE_KSAMPLER]["inputs"]["cfg"]        = float(cfg)
    wf[NODE_SAVE]["inputs"]["filename_prefix"] = filename_prefix
    return wf


def submit_workflow(workflow):
    import uuid
    client_id = str(uuid.uuid4())
    payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    response = json.loads(urllib.request.urlopen(req).read())
    return response["prompt_id"]


def poll_result(prompt_id, timeout=300):
    """Poll /history until job is done. Returns output image filename or raises."""
    for _ in range(timeout * 2):
        try:
            resp = urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5)
            history = json.loads(resp.read())
            if prompt_id in history:
                outputs = history[prompt_id]["outputs"]
                for node_out in outputs.values():
                    if "images" in node_out:
                        img = node_out["images"][0]
                        return img["filename"]
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError("ComfyUI job timed out after 5 minutes")


def make_version_prefix():
    """Generate a versioned filename prefix using timestamp."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    return f"zit_{ts}"


def create_read_node(image_path):
    """Create a Read node in the Nuke DAG pointing at the output image."""
    def _create():
        n = nuke.createNode("Read", inpanel=False)
        n["file"].setValue(image_path.replace("\\", "/"))
        n["name"].setValue("ComfyAI_" + os.path.splitext(os.path.basename(path))[0])
    nuke.executeInMainThread(_create)


# ── Panel UI ──────────────────────────────────────────────────────────────────
class ComfyBridgePanel(QtWidgets.QWidget):

    # Signals must be class-level
    status_signal  = QtCore.Signal(str)
    result_signal  = QtCore.Signal(str)
    error_signal   = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ComfyUI Bridge")
        self.setMinimumWidth(340)
        self._build_ui()
        self._connect_signals()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # ── Status bar ───────────────────────────────────────────────────────
        self.status_bar = QtWidgets.QLabel("● Checking connection...")
        self.status_bar.setStyleSheet("color: orange; font-weight: bold;")
        root.addWidget(self.status_bar)

        root.addWidget(self._divider())

        # ── Workflow label ───────────────────────────────────────────────────
        wf_label = QtWidgets.QLabel("Workflow: Z-Image Turbo — Text to Image")
        wf_label.setStyleSheet("color: #aaa; font-size: 11px;")
        root.addWidget(wf_label)

        root.addWidget(self._divider())

        # ── Positive prompt ──────────────────────────────────────────────────
        root.addWidget(QtWidgets.QLabel("Positive Prompt"))
        self.positive = QtWidgets.QPlainTextEdit()
        self.positive.setPlaceholderText("Describe the image...")
        self.positive.setFixedHeight(90)
        root.addWidget(self.positive)

        # ── Resolution ───────────────────────────────────────────────────────
        res_row = QtWidgets.QHBoxLayout()
        res_row.addWidget(QtWidgets.QLabel("Width"))
        self.width = QtWidgets.QSpinBox()
        self.width.setRange(64, 4096)
        self.width.setSingleStep(64)
        self.width.setValue(1024)
        res_row.addWidget(self.width)

        res_row.addSpacing(16)

        res_row.addWidget(QtWidgets.QLabel("Height"))
        self.height = QtWidgets.QSpinBox()
        self.height.setRange(64, 4096)
        self.height.setSingleStep(64)
        self.height.setValue(1024)
        res_row.addWidget(self.height)
        root.addLayout(res_row)

        # ── Shift ────────────────────────────────────────────────────────────
        shift_row = QtWidgets.QHBoxLayout()
        shift_row.addWidget(QtWidgets.QLabel("Shift"))
        self.shift = QtWidgets.QDoubleSpinBox()
        self.shift.setRange(0.0, 10.0)
        self.shift.setSingleStep(0.5)
        self.shift.setValue(3.0)
        shift_row.addWidget(self.shift)
        shift_row.addStretch()
        root.addLayout(shift_row)

        # ── Steps / CFG ──────────────────────────────────────────────────────
        sc_row = QtWidgets.QHBoxLayout()
        sc_row.addWidget(QtWidgets.QLabel("Steps"))
        self.steps = QtWidgets.QSpinBox()
        self.steps.setRange(1, 50)
        self.steps.setValue(8)
        sc_row.addWidget(self.steps)

        sc_row.addSpacing(16)

        sc_row.addWidget(QtWidgets.QLabel("CFG"))
        self.cfg = QtWidgets.QDoubleSpinBox()
        self.cfg.setRange(0.0, 20.0)
        self.cfg.setSingleStep(0.1)
        self.cfg.setValue(1.0)
        sc_row.addWidget(self.cfg)
        root.addLayout(sc_row)

        # ── Seed ─────────────────────────────────────────────────────────────
        seed_row = QtWidgets.QHBoxLayout()
        seed_row.addWidget(QtWidgets.QLabel("Seed"))
        self.seed = QtWidgets.QSpinBox()
        self.seed.setRange(0, 2147483647)
        self.seed.setValue(0)
        seed_row.addWidget(self.seed)

        self.seed_mode = QtWidgets.QComboBox()
        self.seed_mode.addItems(["Fixed", "Randomize"])
        self.seed_mode.setCurrentIndex(1)
        seed_row.addWidget(self.seed_mode)
        root.addLayout(seed_row)

        root.addWidget(self._divider())

        # ── Generate button ──────────────────────────────────────────────────
        self.generate_btn = QtWidgets.QPushButton("▶  Generate")
        self.generate_btn.setFixedHeight(36)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff2d9b;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #999;
            }
        """)
        root.addWidget(self.generate_btn)

        # ── Job status ───────────────────────────────────────────────────────
        self.job_status = QtWidgets.QLabel("")
        self.job_status.setStyleSheet("color: #aaa; font-size: 11px;")
        self.job_status.setWordWrap(True)
        root.addWidget(self.job_status)

        root.addStretch()

        # Check connection on startup
        QtCore.QTimer.singleShot(500, self._check_connection)

    def _divider(self):
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)
        line.setStyleSheet("color: #444;")
        return line

    # ── Signals ───────────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.generate_btn.clicked.connect(self._on_generate)
        self.status_signal.connect(self._on_status)
        self.result_signal.connect(self._on_result)
        self.error_signal.connect(self._on_error)

    # ── Connection check ──────────────────────────────────────────────────────
    def _check_connection(self):
        if check_comfy_connection():
            self.status_bar.setText("● Connected to ComfyUI")
            self.status_bar.setStyleSheet("color: #00e5ff; font-weight: bold;")
        else:
            self.status_bar.setText("● Cannot reach ComfyUI at 127.0.0.1:8188")
            self.status_bar.setStyleSheet("color: red; font-weight: bold;")

    # ── Generate ──────────────────────────────────────────────────────────────
    def _on_generate(self):
        # Validate prompt
        prompt_text = self.positive.toPlainText().strip()
        if not prompt_text:
            QtWidgets.QMessageBox.warning(self, "Missing Prompt", "Please enter a positive prompt.")
            return

        # Resolve seed
        if self.seed_mode.currentText() == "Randomize":
            seed_val = random.randint(0, 2147483647)
            self.seed.setValue(seed_val)
        else:
            seed_val = self.seed.value()

        # Collect params
        params = {
            "positive": prompt_text,
            "width":    self.width.value(),
            "height":   self.height.value(),
            "shift":    self.shift.value(),
            "seed":     seed_val,
            "steps":    self.steps.value(),
            "cfg":      self.cfg.value(),
        }

        self.generate_btn.setEnabled(False)
        self.job_status.setText("Submitting to ComfyUI...")

        threading.Thread(target=self._run_job, args=(params,), daemon=True).start()

    def _run_job(self, params):
        try:
            # Load and patch workflow
            workflow = load_workflow()
            prefix   = make_version_prefix()
            patched  = patch_workflow(
                workflow,
                positive        = params["positive"],
                width           = params["width"],
                height          = params["height"],
                shift           = params["shift"],
                seed            = params["seed"],
                steps           = params["steps"],
                cfg             = params["cfg"],
                filename_prefix = prefix,
            )

            # Submit
            self.status_signal.emit("Job submitted — waiting for result...")
            prompt_id = submit_workflow(patched)

            # Poll
            filename = poll_result(prompt_id)

            # Build full output path
            output_path = os.path.join(OUTPUT_DIR, filename)
            self.result_signal.emit(output_path)

        except Exception as e:
            self.error_signal.emit(str(e))

    # ── Callbacks (main thread) ───────────────────────────────────────────────
    def _on_status(self, msg):
        self.job_status.setText(msg)

    def _on_result(self, path):
        self.job_status.setText(f"Done → {os.path.basename(path)}")
        self.generate_btn.setEnabled(True)
        create_read_node(path)

    def _on_error(self, msg):
        self.job_status.setText(f"Error: {msg}")
        self.generate_btn.setEnabled(True)


# ── Nuke Dockable Panel ───────────────────────────────────────────────────────
import nukescripts

_widget_instance = None

def get_widget():
    global _widget_instance
    if _widget_instance is None:
        _widget_instance = ComfyBridgePanel()
    return _widget_instance

def show_panel():
    """Open as a dockable panel in Nuke."""
    pane = nuke.getPaneFor("Properties.1")
    panel = nukescripts.registerWidgetAsPanel(
        "comfy_bridge.get_widget",
        "ComfyUI Bridge",
        "uk.co.comfybridge.panel",
        create=True
    )
    panel.addToPane(pane)