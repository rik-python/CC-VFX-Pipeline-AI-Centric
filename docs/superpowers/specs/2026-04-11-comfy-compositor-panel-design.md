# Comfy Compositor — Panel Design Spec

## Overview

A manifest-driven Nuke 17 side panel that connects Nuke to a local ComfyUI instance (127.0.0.1:8188). Users select workflows from a collapsible tree, set parameters, and fire jobs — results appear as Read nodes in the DAG. Adding a new workflow means dropping files in a folder, not editing Python.

**Target users:** Artists who find ComfyUI's node-based frontend intimidating. They use Nuke as their primary workspace and want AI generation accessible without learning ComfyUI.

**Maintainer model:** Solo developer creates and updates workflows. The panel is a skeleton that reads workflow manifests — all workflow-specific logic lives in data files, not code.

## Architecture

### Manifest-Driven Design

Each workflow is a subfolder in `Workflows/` containing two files:

```
Workflows/
  z_image_turbo/
    workflow.json       # ComfyUI API-format export (unchanged from ComfyUI)
    manifest.json       # Curated parameter declarations
  qwen_image_edit/
    workflow.json
    manifest.json
```

The panel scans `Workflows/` on startup, reads each `manifest.json`, and builds the UI dynamically. The `workflow.json` is never modified — it's loaded, deep-copied, and patched at execution time.

### Manifest Format

```json
{
  "name": "Z-Image Turbo",
  "category": "Text to Image",
  "description": "Fast text-to-image using Z-Image Turbo model. 8 steps.",
  "inputs": [],
  "parameters": [
    {"label": "Prompt",  "node": "57:27", "field": "text",   "type": "text"},
    {"label": "Width",   "node": "57:13", "field": "width",  "type": "int",   "default": 1024, "min": 64, "max": 4096, "step": 64},
    {"label": "Height",  "node": "57:13", "field": "height", "type": "int",   "default": 1024, "min": 64, "max": 4096, "step": 64},
    {"label": "Shift",   "node": "57:11", "field": "shift",  "type": "float", "default": 3.0,  "min": 0.0, "max": 10.0, "step": 0.5},
    {"label": "Steps",   "node": "57:3",  "field": "steps",  "type": "int",   "default": 8,    "min": 1, "max": 50},
    {"label": "CFG",     "node": "57:3",  "field": "cfg",    "type": "float", "default": 1.0,  "min": 0.0, "max": 20.0, "step": 0.1},
    {"label": "Seed",    "node": "57:3",  "field": "seed",   "type": "seed",  "default": 0}
  ],
  "output_node": "9"
}
```

For image-to-image workflows, `inputs` declares image slots:

```json
{
  "name": "Qwen Image Edit",
  "category": "Image to Image",
  "description": "Edit an image using a text prompt.",
  "inputs": [
    {"label": "Source Image", "node": "41", "field": "image"},
    {"label": "Reference",    "node": "83", "field": "image"}
  ],
  "parameters": [
    {"label": "Prompt", "node": "170:149", "field": "text", "type": "text"}
  ],
  "output_node": "9"
}
```

### Parameter Types

| Type    | Widget              | Manifest fields                          |
|---------|---------------------|------------------------------------------|
| `text`  | QPlainTextEdit      | (none extra)                             |
| `int`   | QSpinBox            | `default`, `min`, `max`, `step`          |
| `float` | QDoubleSpinBox      | `default`, `min`, `max`, `step`          |
| `seed`  | QSpinBox + QComboBox| `default` (value + Fixed/Random toggle)  |

## Panel Layout

Top-to-bottom, single column, fits in Nuke's narrow side panel:

### 1. Header
- Title: "Comfy Compositor"
- Connection status dot (cyan = connected, red = error)
- Theme: dark background, subtle cyan/magenta accents — professional, not flashy

### 2. Workflow Tree
- Collapsible categories: Text to Image, Image to Image, Image to Video, Utility
- Workflows nested under their category
- Clicking a workflow selects it, loads its manifest, rebuilds sections 3 and 4
- Categories auto-populated from manifest `category` fields
- Expand/collapse with click on category header

### 3. Input Slots
- Only visible when the selected workflow has `inputs` in its manifest
- Each input shows: label ("Source Image") + assigned node name + "Add Selected" button
- "Add Selected" grabs `nuke.selectedNode()` — must be a Read node
- Displays the node name once assigned (e.g., "Read1")
- Clear button (X) to unassign

### 4. Parameters
- Auto-built from manifest `parameters` array
- Each parameter renders as a labeled row with the appropriate widget type
- Seed type renders as: spinbox (value) + combo box (Fixed / Random)
- Text type renders as a multi-line text area with placeholder text
- Int/float types render as spinboxes with the manifest's min/max/step/default

### 5. Generate Button
- Full-width button, styled with accent color
- Disabled during job execution
- Label changes: "Generate" → "Working..." → "Generate"

### 6. Status Bar
- Text label at the bottom
- States: Ready / Submitting... / Working... / Done / Error: {message}

## Execution Flow

1. User selects a workflow from the tree
2. Panel reads `manifest.json`, builds input slots and parameter widgets
3. User fills in parameters, optionally assigns Nuke Read nodes to input slots
4. User clicks Generate
5. Panel loads `workflow.json`, deep-copies it
6. Patches all parameter values into the workflow using `node` + `field` from manifest
7. For image inputs: renders the Read node's current frame to a temp PNG, uploads to ComfyUI via `POST /upload/image`, patches the filename into the LoadImage node
8. Submits patched workflow via `POST /prompt` with a UUID `client_id`
9. Polls `GET /history/{prompt_id}` every 0.5s (timeout: 300s)
10. On success: reads output filename from response, constructs full path in ComfyUI's output directory, creates a Nuke Read node pointing to it
11. On error: displays error message in status bar

## ComfyUI Communication

All HTTP, no WebSocket. Four endpoints used:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/system_stats` | GET | Connection check (2s timeout) |
| `/upload/image` | POST | Upload Nuke frames for image inputs |
| `/prompt` | POST | Submit workflow, returns `prompt_id` |
| `/history/{prompt_id}` | GET | Poll for job completion |

## Code Structure

Single file: `comfy_bridge.py`

Sections within the file:
1. **Constants** — COMFY_URL, WORKFLOWS_DIR, OUTPUT_DIR
2. **Manifest loading** — scan Workflows/ dir, parse manifests, group by category
3. **ComfyUI communication** — connection check, image upload, workflow submit, result polling
4. **Workflow patching** — deep-copy workflow JSON, apply parameter values from UI
5. **Nuke integration** — create Read nodes, get selected node, render frame to temp file
6. **UI widgets** — parameter widget builders (text, int, float, seed)
7. **Panel class** — main QWidget with tree, input slots, parameters, generate button, status
8. **Registration** — Nuke panel registration (singleton, dockable)

## Workflow Discovery

On panel initialization and on manual refresh:
1. List subdirectories in `Workflows/`
2. For each subdir, check for `manifest.json` and `workflow.json`
3. Skip subdirs missing either file
4. Parse `manifest.json`, validate required fields (name, category, parameters, output_node)
5. Group workflows by `category`
6. Build collapsible tree widget

## Constraints

- PySide2 or PySide6 for Qt (handle both — Nuke versions vary)
- Python 3.x (Nuke 17's embedded Python)
- No external dependencies beyond stdlib + PySide2 + nuke module
- Single file for simplicity of distribution
- Must not block Nuke's UI — all network operations in daemon threads with Qt signal callbacks

## Out of Scope (Future)

- WebSocket progress (real-time step progress bar)
- Inline result preview in panel
- Output file organization (copy to Exports/)
- Workflow thumbnails
- Prompt history
- Style presets
- Batch processing
- ComfyUI custom node dependency checking
- GitHub installer script
- Qwen3-VL prompt assistant
