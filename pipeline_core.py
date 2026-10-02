"""ComfyXNuke pipeline core: config-driven paths, naming, versioning.

Stdlib only (runs inside Nuke's embedded Python). Both the Nuke panel and the
ComfyUI save side import this so every freelancer resolves identical paths and
names. Pure functions take a cfg dict; load_config() is the convenience loader.

Hierarchy:  <root>/<show>/<part>/<seq>/<shot>/<task folder>
Naming:     {show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}
            -> shwx_101_010_0010_ai_FirstPass_rikinp_v01
Version is per shot+task (shared across types); the script version drives the
render version. All returned paths use forward slashes (Nuke needs '/').
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_PATH = os.path.join(os.path.expanduser("~"), ".comfyx_local.json")


def _fwd(path):
    return path.replace(os.sep, "/")


# --- config -----------------------------------------------------------------

def load_config(project_json=None):
    """Load pipeline.json (versioned default), then overlay per-machine overrides.

    Config discovery: arg -> env COMFYX_CONFIG -> ./pipeline.json next to this file.
    Per-machine overrides (differ per freelancer/machine/job):
      - ~/.comfyx_local.json  {"root":..., "show":..., "artist":...}
      - env COMFYX_ROOT / COMFYX_SHOW / COMFYX_ARTIST
    """
    path = project_json or os.environ.get("COMFYX_CONFIG") or os.path.join(HERE, "pipeline.json")
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    if os.path.isfile(LOCAL_PATH):
        with open(LOCAL_PATH, "r", encoding="utf-8") as fh:
            cfg.update({k: v for k, v in json.load(fh).items() if v})

    for env, key in (("COMFYX_ROOT", "root"), ("COMFYX_SHOW", "show"), ("COMFYX_ARTIST", "artist")):
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg


def set_local(key, value, path=LOCAL_PATH):
    """Write one per-machine setting (root/show/artist) to ~/.comfyx_local.json. Merges."""
    data = {}
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    data[key] = value
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return path


# --- show / part / seq / shot folders ---------------------------------------

def show_root(cfg):
    """A show lives at <root>/<show>. root is the per-machine jobs container."""
    return os.path.join(cfg["root"], cfg.get("show", ""))


def shot_base(cfg, part, seq, shot):
    return os.path.join(show_root(cfg), part, seq, shot)


def ensure_show(cfg):
    """Create show-level folders. Returns show root. Idempotent."""
    base = show_root(cfg)
    for sub in cfg.get("show_structure", []):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return _fwd(base)


def ensure_shot(cfg, part, seq, shot):
    """Create a shot's folder tree (part/seq auto-created). Returns shot dir. Idempotent."""
    base = shot_base(cfg, part, seq, shot)
    for sub in cfg.get("shot_structure", []):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return _fwd(base)


def task_dir(cfg, part, seq, shot, task):
    """Folder a task writes into. Unknown task -> folder named after it."""
    folder = cfg.get("task_folders", {}).get(task, task)
    return _fwd(os.path.join(shot_base(cfg, part, seq, shot), folder))


def script_dir(cfg, part, seq, shot):
    """Where .nk scripts live: the shot's nuke folder."""
    return _fwd(os.path.join(shot_base(cfg, part, seq, shot), cfg.get("script_folder", "nuke")))


# --- naming + versioning ----------------------------------------------------

def _stem(cfg, part, seq, shot, task, type_, version):
    return cfg["naming"].format(
        show=cfg["show"], part=part, seq=seq, shot=shot,
        task=task, type=type_, artist=cfg["artist"], version=version,
    )


def parse_version(filename):
    """Extract the integer version from a pipeline filename (..._v07_... -> 7)."""
    m = re.search(r"_v(\d+)", os.path.basename(filename or ""))
    return int(m.group(1)) if m else None


def _version_regex(cfg, part, seq, shot, task):
    """Match this show+part+seq+shot+task at any type/version: version per shot+task."""
    prefix = "_".join(re.escape(x) for x in (cfg["show"], part, seq, shot, task))
    return re.compile("^" + prefix + r"_[^_]+_" + re.escape(cfg["artist"]) + r"_v(\d+)")


def _scan_version(folder, rex):
    if not os.path.isdir(folder):
        return 1
    highest = 0
    for entry in os.listdir(folder):
        m = rex.match(entry)
        if m:
            highest = max(highest, int(m.group(1)))
    return highest + 1


def next_version(cfg, part, seq, shot, task):
    """Next render version for a shot+task (scans the task folder, any type)."""
    return _scan_version(task_dir(cfg, part, seq, shot, task), _version_regex(cfg, part, seq, shot, task))


def next_script_version(cfg, part, seq, shot, task):
    """Next .nk version for a shot+task (scans the nuke folder, any type)."""
    return _scan_version(script_dir(cfg, part, seq, shot), _version_regex(cfg, part, seq, shot, task))


def make_filename(cfg, part, seq, shot, task, type_, version, ext=None, frame_pad=None):
    ext = (ext or cfg.get("format", "exr")).lstrip(".")
    stem = _stem(cfg, part, seq, shot, task, type_, version)
    if frame_pad:
        return "{0}.{1}.{2}".format(stem, frame_pad, ext)
    return "{0}.{1}".format(stem, ext)


def output_path(cfg, part, seq, shot, task, type_, ext=None, frame_pad=None,
                version=None, make_dirs=False):
    """Full render path. version=None auto-picks next for the shot+task. Forward-slashed."""
    if version is None:
        version = next_version(cfg, part, seq, shot, task)
    folder = task_dir(cfg, part, seq, shot, task)
    if make_dirs:
        os.makedirs(folder, exist_ok=True)
    return _fwd(os.path.join(folder, make_filename(cfg, part, seq, shot, task, type_, version, ext, frame_pad)))


def script_path(cfg, part, seq, shot, task, type_, version=None, make_dirs=False):
    """Full .nk path with the enforced name. version=None auto-picks next. Forward-slashed."""
    if version is None:
        version = next_script_version(cfg, part, seq, shot, task)
    folder = script_dir(cfg, part, seq, shot)
    if make_dirs:
        os.makedirs(folder, exist_ok=True)
    return _fwd(os.path.join(folder, _stem(cfg, part, seq, shot, task, type_, version) + ".nk"))


def list_shows(cfg):
    """Scan the root for existing shows (top-level folders). Returns sorted names."""
    root = cfg.get("root", "")
    if not os.path.isdir(root):
        return []
    return sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))


def list_shots(cfg, show=None):
    """Scan a show for existing shots. Returns sorted [(part, seq, shot), ...].

    show defaults to cfg['show']. Skips the show-level folders (assets, ai,
    color, ...) so only part/seq/shot dirs are walked. Feeds the Nuke pickers.
    """
    base = os.path.join(cfg["root"], show if show is not None else cfg.get("show", ""))
    if not os.path.isdir(base):
        return []
    exclude = {p.split("/")[0] for p in cfg.get("show_structure", [])}
    out = []
    for part in sorted(os.listdir(base)):
        ppath = os.path.join(base, part)
        if part in exclude or not os.path.isdir(ppath):
            continue
        for seq in sorted(os.listdir(ppath)):
            spath = os.path.join(ppath, seq)
            if not os.path.isdir(spath):
                continue
            for shot in sorted(os.listdir(spath)):
                if os.path.isdir(os.path.join(spath, shot)):
                    out.append((part, seq, shot))
    return out


def sync_structure(cfg, prune=False):
    """Reconcile the existing show + every existing shot against the current config.

    Add-only by default (safe): creates any folder in show_structure / shot_structure
    that a shot is missing, so a config change (new task/folder) propagates to shots
    that already exist - no deleting and rebuilding the show.

    prune=True also removes shot folders no longer in the config, but ONLY when they
    are empty; a folder that still holds files is kept and reported, never deleted.
    Prune compares the shot's direct children against the top level of shot_structure
    (so a parent like `nuke` is kept even though its `nuke/precomp` child is nested).

    Returns {"shots": N, "added": [...], "removed": [...], "kept_nonempty": [...]}.
    """
    report = {"shots": 0, "added": [], "removed": [], "kept_nonempty": []}

    # show-level (add-only)
    base = show_root(cfg)
    for sub in cfg.get("show_structure", []):
        d = os.path.join(base, sub)
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            report["added"].append(_fwd(d))

    shots = list_shots(cfg)
    report["shots"] = len(shots)
    keep_top = {s.split("/")[0] for s in cfg.get("shot_structure", [])}
    keep_top.add(cfg.get("script_folder", "nuke"))

    for part, seq, shot in shots:
        sbase = shot_base(cfg, part, seq, shot)
        # add missing
        for sub in cfg.get("shot_structure", []):
            d = os.path.join(sbase, sub)
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
                report["added"].append(_fwd(d))
        # prune (empty-only) folders dropped from config
        if prune and os.path.isdir(sbase):
            for name in sorted(os.listdir(sbase)):
                d = os.path.join(sbase, name)
                if not os.path.isdir(d) or name in keep_top:
                    continue
                if os.listdir(d):
                    report["kept_nonempty"].append(_fwd(d))
                else:
                    os.rmdir(d)
                    report["removed"].append(_fwd(d))
    return report


def context_from_path(cfg, path):
    """Infer (part, seq, shot) from a path under <root>/<show>/<part>/<seq>/<shot>/...

    Returns (part, seq, shot) or None if not under the show, on another drive,
    or too shallow (needs part/seq/shot/<file>).
    """
    if not path:
        return None
    root = os.path.abspath(show_root(cfg))
    target = os.path.abspath(path)
    try:
        rel = os.path.relpath(target, root)
    except ValueError:
        return None
    rel = rel.replace("\\", "/")
    if rel.startswith("../") or rel == "..":
        return None
    parts = rel.split("/")
    if len(parts) < 4:  # part / seq / shot / at least one more
        return None
    return parts[0], parts[1], parts[2]


# --- health check -----------------------------------------------------------

def doctor(cfg, repo_dir=HERE):
    """(status, label, hint) checks. status is ok | warn | fail."""
    out = []
    root = cfg.get("root", "")
    out.append(("ok" if root and root != "P:/SHOW_X" else "fail",
                "root configured", "python pipeline_core.py config root <path>"))
    out.append(("ok" if root and os.path.isdir(root) else "fail",
                "root reachable ({0})".format(root or "unset"),
                "mount the shared drive, or create the folder"))
    out.append(("ok" if cfg.get("show") else "fail",
                "show set ({0})".format(cfg.get("show", "")),
                "python pipeline_core.py config show <code>"))
    out.append(("ok" if cfg.get("artist") else "fail",
                "artist set ({0})".format(cfg.get("artist", "")),
                "python pipeline_core.py config artist <name>"))
    init_py = os.path.join(os.path.expanduser("~"), ".nuke", "init.py")
    nuke_ok = False
    if os.path.isfile(init_py):
        try:
            with open(init_py, "r", encoding="utf-8") as fh:
                nuke_ok = os.path.normcase(repo_dir) in os.path.normcase(fh.read())
        except Exception:
            nuke_ok = False
    out.append(("ok" if nuke_ok else "warn",
                "Nuke knows the repo (~/.nuke/init.py)",
                'add: nuke.pluginAddPath(r"{0}")'.format(repo_dir)))
    out.append(("ok" if os.environ.get("OCIO") else "warn",
                "OCIO env set (ACES color)",
                "set OCIO to your ACES config.ocio for correct ACEScg"))
    return out


# --- cli --------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if args and args[0] == "config" and len(args) == 3:
        key, value = args[1], args[2]
        if key not in ("root", "show", "artist"):
            print("config key must be: root | show | artist")
        else:
            print("set {0} = {1}  ({2})".format(key, value, set_local(key, value)))
        sys.exit(0)

    cfg = load_config()
    if args and args[0] == "doctor":
        mark = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]"}
        rows = doctor(cfg)
        for status, label, hint in rows:
            line = mark[status] + " " + label
            if status != "ok":
                line += "\n        -> " + hint
            print(line)
        fails = [r for r in rows if r[0] == "fail"]
        print("\n{0} required check(s) failing.".format(len(fails)) if fails
              else "\nAll required checks pass.")
    elif args and args[0] == "init_show":
        print(ensure_show(cfg))
    elif args and args[0] == "new_shot" and len(args) == 4:
        print(ensure_shot(cfg, args[1], args[2], args[3]))
    elif args and args[0] == "sync":
        prune = "--prune" in args[1:]
        root = cfg.get("root", "")
        if not root or not os.path.isdir(root):
            print("root not reachable ({0}); mount the shared drive, then run sync."
                  .format(root or "unset"))
            sys.exit(0)
        rep = sync_structure(cfg, prune=prune)
        print("sync: {0} shot(s) checked, {1} folder(s) added".format(rep["shots"], len(rep["added"])))
        for d in rep["added"]:
            print("  + " + d)
        if prune:
            print("  {0} empty folder(s) removed".format(len(rep["removed"])))
            for d in rep["removed"]:
                print("  - " + d)
            if rep["kept_nonempty"]:
                print("  kept (not in config but NOT empty - left alone):")
                for d in rep["kept_nonempty"]:
                    print("  ! " + d)
        elif not rep["added"]:
            print("  everything already up to date.")
    elif args and args[0] == "path" and len(args) >= 6:
        part, seq, shot, task, type_ = args[1:6]
        ext = args[6] if len(args) > 6 else None
        print(output_path(cfg, part, seq, shot, task, type_, ext=ext, frame_pad="%04d"))
    else:
        print("usage: pipeline_core.py config <root|show|artist> <value> | doctor | "
              "init_show | new_shot <PART> <SEQ> <SHOT> | sync [--prune] | "
              "path <PART> <SEQ> <SHOT> <task> <type> [ext]")
