#!/usr/bin/env python3
"""First-time installer for CC Pipeline (AI Centric).

Interactive setup: artist/user name, show location (root + show code), and the
Nuke folder. Writes ~/.cc_pipeline.json, wires Nuke (pluginAddPath in init.py),
checks dependencies, optionally scaffolds the show, and runs the doctor.
Re-running is safe (idempotent). Stdlib only.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pipeline_core as pc  # noqa: E402  (after sys.path tweak so it always resolves)


def ask(label, default=""):
    suffix = " [{0}]".format(default) if default else ""
    return input("  {0}{1}: ".format(label, suffix)).strip() or default


def ask_yes(label, default=True):
    val = input("  {0} ({1}): ".format(label, "Y/n" if default else "y/N")).strip().lower()
    return default if not val else val in ("y", "yes")


def wire_nuke(nuke_dir, repo):
    """Append nuke.pluginAddPath(repo) to <nuke_dir>/init.py, once. Returns (path, added)."""
    os.makedirs(nuke_dir, exist_ok=True)
    init_py = os.path.join(nuke_dir, "init.py")
    existing = ""
    if os.path.isfile(init_py):
        with open(init_py, "r", encoding="utf-8") as fh:
            existing = fh.read()
    if os.path.normcase(repo) in os.path.normcase(existing):
        return init_py, False
    with open(init_py, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write('# CC Pipeline (AI Centric)\nnuke.pluginAddPath(r"{0}")\n'.format(repo))
    return init_py, True


def main():
    print("\n=== CC Pipeline (AI Centric) - first-time setup ===\n")
    cfg = pc.load_config()

    print("Your details (press Enter to keep the [default]):")
    artist = ask("Your artist / user name (e.g. rikinp)", cfg.get("artist", ""))
    root = ask("Shared-drive folder holding ALL shows (e.g. D:/Work/projects)", cfg.get("root", ""))
    show = ask("Show code (e.g. shwx)", cfg.get("show", ""))
    nuke_dir = ask("Your Nuke folder", os.path.join(os.path.expanduser("~"), ".nuke"))

    if artist:
        pc.set_local("artist", artist)
    if root:
        pc.set_local("root", root)
    if show:
        pc.set_local("show", show)
    print("\n  [OK]  settings saved to {0}".format(pc.LOCAL_PATH))

    init_py, added = wire_nuke(nuke_dir, HERE)
    print("  [OK]  Nuke wired ({0}){1}".format(init_py, "" if added else " - already set"))

    print("\nDependency checks:")
    print("  [OK]  Python {0}.{1}".format(*sys.version_info[:2]))
    print("  {0} git on PATH (needed for one-click updates)".format(
        "[OK] " if shutil.which("git") else "[WARN]"))
    print("  {0} shared drive reachable ({1})".format(
        "[OK] " if root and os.path.isdir(root) else "[WARN]", root or "unset"))

    cfg = pc.load_config()
    if root and show and ask_yes("\nCreate the show-level folders now?", default=True):
        try:
            print("  [OK]  show folders at {0}".format(pc.ensure_show(cfg)))
        except Exception as exc:
            print("  [WARN] could not create show folders: {0}".format(exc))

    print("\nDoctor:")
    mark = {"ok": "[OK]  ", "warn": "[WARN]", "fail": "[FAIL]"}
    for status, label, hint in pc.doctor(cfg):
        line = "  " + mark[status] + " " + label
        if status != "ok":
            line += "\n         -> " + hint
        print(line)

    print("\nDone. Restart Nuke, then use the CC VFX Menu up top.\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
