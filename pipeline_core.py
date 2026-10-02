"""CC Pipeline (AI Centric) core: config-driven paths, naming, versioning.

Stdlib only (runs inside Nuke's embedded Python). The Nuke integration imports
this so every freelancer resolves identical paths and names. Pure functions take
a cfg dict; load_config() is the convenience loader.

Hierarchy:  <root>/<show>/<part>/<seq>/<shot>/<task>/{nk,render,precomp,cache,...}
            Common shot folders (plates/review/delivery/elements) sit at shot level.
            Scripts: <shot>/<task>/nk ; renders: <shot>/<task>/render/<stem>/{exr,mov}.
Naming:     {show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}
            -> shwx_101_010_0010_ai_FirstPass_rikinp_v01
Version is per shot+task (shared across types); the script version drives the
render version. All returned paths use forward slashes (Nuke needs '/').
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_PATH = os.path.join(os.path.expanduser("~"), ".cc_pipeline.json")
# Legacy per-machine config from the old "ComfyXNuke" name - still read as a fallback.
OLD_LOCAL_PATH = os.path.join(os.path.expanduser("~"), ".comfyx_local.json")


def _fwd(path):
    return path.replace(os.sep, "/")


# --- config -----------------------------------------------------------------

def load_config(project_json=None):
    """Load pipeline.json (versioned default), then overlay per-machine overrides.

    Config discovery: arg -> env CC_CONFIG (or legacy COMFYX_CONFIG) -> ./pipeline.json.
    Per-machine overrides (differ per freelancer/machine/job):
      - ~/.cc_pipeline.json  {"root":..., "show":..., "artist":...}
        (legacy ~/.comfyx_local.json is still read, then the new file wins)
      - env CC_ROOT / CC_SHOW / CC_ARTIST  (legacy COMFYX_* still honored)
    """
    path = (project_json or os.environ.get("CC_CONFIG") or os.environ.get("COMFYX_CONFIG")
            or os.path.join(HERE, "pipeline.json"))
    with open(path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    for local in (OLD_LOCAL_PATH, LOCAL_PATH):   # legacy first, new wins
        if os.path.isfile(local):
            with open(local, "r", encoding="utf-8") as fh:
                cfg.update({k: v for k, v in json.load(fh).items() if v})

    for new_env, old_env, key in (("CC_ROOT", "COMFYX_ROOT", "root"),
                                  ("CC_SHOW", "COMFYX_SHOW", "show"),
                                  ("CC_ARTIST", "COMFYX_ARTIST", "artist")):
        val = os.environ.get(new_env) or os.environ.get(old_env)
        if val:
            cfg[key] = val
    return cfg


def set_local(key, value, path=LOCAL_PATH):
    """Write one per-machine setting (root/show/artist) to ~/.cc_pipeline.json. Merges."""
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
    """Create a shot's task-centric tree (part/seq auto-created). Returns shot dir. Idempotent.

    Shot level gets the common folders (shot_common: plates/review/delivery/elements).
    Each task in `tasks` gets its own folder holding task_subfolders (nk/render/precomp/
    cache) plus any task_extras (e.g. ai: input/output/workflow).
    """
    base = shot_base(cfg, part, seq, shot)
    for sub in cfg.get("shot_common", []):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    subs = cfg.get("task_subfolders", [])
    extras = cfg.get("task_extras", {})
    for task in cfg.get("tasks", []):
        for sub in subs + extras.get(task, []):
            os.makedirs(os.path.join(base, task, sub), exist_ok=True)
    return _fwd(base)


def task_root(cfg, part, seq, shot, task):
    """The task's own folder: <shot>/<task> (holds nk/ render/ precomp/ cache/ ...)."""
    return _fwd(os.path.join(shot_base(cfg, part, seq, shot), task))


def script_dir(cfg, part, seq, shot, task):
    """Where a task's .nk scripts live: <shot>/<task>/<script_subfolder> (default nk)."""
    return _fwd(os.path.join(shot_base(cfg, part, seq, shot), task, cfg.get("script_subfolder", "nk")))


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


def parse_name(filename):
    """Parse a pipeline filename into its tokens, or None if it is not one.

    Expects the stem show_part_seq_shot_task_type_artist_vNN (token values contain
    no underscores). Extension and frame pad are ignored. 'version' comes back int.
    """
    stem = os.path.basename(filename or "").split(".")[0]
    m = re.match(
        r"^(?P<show>[^_]+)_(?P<part>[^_]+)_(?P<seq>[^_]+)_(?P<shot>[^_]+)_"
        r"(?P<task>[^_]+)_(?P<type>[^_]+)_(?P<artist>[^_]+)_v(?P<version>\d+)$",
        stem,
    )
    if not m:
        return None
    d = m.groupdict()
    d["version"] = int(d["version"])
    return d


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


def next_script_version(cfg, part, seq, shot, task):
    """Next .nk version for a shot+task (scans the task's nk folder, any type).

    Version is per shot+task and driven by the script; renders inherit the script's
    version, so this is the single source of truth for the counter.
    """
    return _scan_version(script_dir(cfg, part, seq, shot, task), _version_regex(cfg, part, seq, shot, task))


def make_filename(cfg, part, seq, shot, task, type_, version, ext=None, frame_pad=None):
    ext = (ext or cfg.get("format", "exr")).lstrip(".")
    stem = _stem(cfg, part, seq, shot, task, type_, version)
    if frame_pad:
        return "{0}.{1}.{2}".format(stem, frame_pad, ext)
    return "{0}.{1}".format(stem, ext)


def _render_stem_dir(cfg, part, seq, shot, task, stem):
    """<shot>/<task>/<render_folder>/<stem> - the per-render folder that holds exr/ + mov/."""
    return os.path.join(shot_base(cfg, part, seq, shot), task, cfg.get("render_folder", "render"), stem)


def render_outputs(cfg, script_path, frame_pad="%04d", make_dirs=False):
    """Render paths that mirror an open .nk script, split into exr/ and mov/.

    From a `..._comp_WIP_..._v03.nk` script this yields, under the task's render folder:
      <shot>/comp/render/<stem>/exr/<stem>.%04d.exr   (frames)
      <shot>/comp/render/<stem>/mov/<stem>.mov         (review movie)
    task/stem come from the script filename; part/seq/shot from its location (falling
    back to the filename tokens). Returns a dict of forward-slashed paths, or None if
    the script is not pipeline-named.
    """
    info = parse_name(script_path)
    if not info:
        return None
    ctx = context_from_path(cfg, script_path)
    part, seq, shot = ctx if ctx else (info["part"], info["seq"], info["shot"])
    stem = os.path.basename(script_path).split(".")[0]
    rdir = _render_stem_dir(cfg, part, seq, shot, info["task"], stem)
    exr_dir = os.path.join(rdir, cfg.get("render_exr_dir", "exr"))
    mov_dir = os.path.join(rdir, cfg.get("render_mov_dir", "mov"))
    if make_dirs:
        os.makedirs(exr_dir, exist_ok=True)
        os.makedirs(mov_dir, exist_ok=True)
    img_ext = cfg.get("format", "exr").lstrip(".")
    mov_ext = cfg.get("mov_format", "mov").lstrip(".")
    exr_name = "{0}.{1}.{2}".format(stem, frame_pad, img_ext) if frame_pad else "{0}.{1}".format(stem, img_ext)
    return {
        "dir": _fwd(rdir),
        "exr_dir": _fwd(exr_dir),
        "mov_dir": _fwd(mov_dir),
        "exr": _fwd(os.path.join(exr_dir, exr_name)),
        "mov": _fwd(os.path.join(mov_dir, "{0}.{1}".format(stem, mov_ext))),
    }


def write_path_from_script(cfg, script_path, frame_pad="%04d", make_dirs=False):
    """Convenience: just the EXR render path for an open script (see render_outputs)."""
    r = render_outputs(cfg, script_path, frame_pad=frame_pad, make_dirs=make_dirs)
    return r["exr"] if r else None


def output_path(cfg, part, seq, shot, task, type_, ext=None, frame_pad="%04d",
                version=None, make_dirs=False):
    """Render EXR path for a task+type (CLI aid): <shot>/<task>/render/<stem>/exr/<stem>.%04d.ext.

    version=None auto-picks the next version for the shot+task. Forward-slashed.
    """
    if version is None:
        version = next_script_version(cfg, part, seq, shot, task)
    stem = _stem(cfg, part, seq, shot, task, type_, version)
    rdir = os.path.join(_render_stem_dir(cfg, part, seq, shot, task, stem), cfg.get("render_exr_dir", "exr"))
    if make_dirs:
        os.makedirs(rdir, exist_ok=True)
    ext = (ext or cfg.get("format", "exr")).lstrip(".")
    name = "{0}.{1}.{2}".format(stem, frame_pad, ext) if frame_pad else "{0}.{1}".format(stem, ext)
    return _fwd(os.path.join(rdir, name))


def script_path(cfg, part, seq, shot, task, type_, version=None, make_dirs=False):
    """Full .nk path with the enforced name, in the task's nk folder. version=None auto-picks next."""
    if version is None:
        version = next_script_version(cfg, part, seq, shot, task)
    folder = script_dir(cfg, part, seq, shot, task)
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

    Add-only by default (safe): creates any show-level, common, or per-task folder a
    shot is missing, so a config change (new task/subfolder) propagates to shots that
    already exist - no deleting and rebuilding the show.

    prune=True also removes shot-level folders no longer in the config, but ONLY when
    they are empty; a folder that still holds anything is kept and reported, never
    deleted. Prune only looks at the shot's direct children (expected = shot_common +
    tasks); it does not descend into task folders.

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
    common = cfg.get("shot_common", [])
    tasks = cfg.get("tasks", [])
    subs = cfg.get("task_subfolders", [])
    extras = cfg.get("task_extras", {})
    expected_top = set(common) | set(tasks)

    for part, seq, shot in shots:
        sbase = shot_base(cfg, part, seq, shot)
        # add common (shot level)
        for sub in common:
            d = os.path.join(sbase, sub)
            if not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
                report["added"].append(_fwd(d))
        # add each task's subfolders (+ extras)
        for task in tasks:
            for sub in subs + extras.get(task, []):
                d = os.path.join(sbase, task, sub)
                if not os.path.isdir(d):
                    os.makedirs(d, exist_ok=True)
                    report["added"].append(_fwd(d))
        # prune (empty-only) shot-level folders dropped from config
        if prune and os.path.isdir(sbase):
            for name in sorted(os.listdir(sbase)):
                d = os.path.join(sbase, name)
                if not os.path.isdir(d) or name in expected_top:
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
