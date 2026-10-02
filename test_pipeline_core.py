"""Tests for pipeline_core. Stdlib unittest, no deps. Run: python -m unittest -v"""
import json
import os
import shutil
import tempfile
import unittest

import pipeline_core as pc


def _cfg(root):
    return {
        "root": root,
        "show": "shwx",
        "artist": "rikinp",
        "format": "exr",
        "naming": "{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}",
        "types": ["SlapComp", "FirstPassSingle", "WIP", "CF", "TF"],
        "script_folder": "nuke",
        "task_folders": {"rotopaint": "rotopaint", "track": "track", "layout": "layout",
                         "anim": "anim", "fx": "fx", "lighting": "lighting",
                         "render": "render", "ai": "ai_output", "comp": "comp"},
        "show_structure": ["assets", "reference", "edit", "ai/datasets/images/raw",
                           "ai/models/checkpoints", "color/ocio"],
        "shot_structure": ["plates", "nuke", "nuke/precomp", "rotopaint",
                           "track", "layout", "anim", "fx", "lighting", "render",
                           "ai_input", "ai_output", "comp", "elements", "comfyui",
                           "workflow", "cache", "review", "delivery"],
    }


class PipelineCore(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cfg = _cfg(self.root)
        self.sroot = os.path.join(self.root, "shwx")          # <root>/<show>
        self.P, self.S, self.H = "101", "010", "0010"         # part, seq, shot

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # --- show / shot trees ---
    def test_show_root_includes_show(self):
        self.assertEqual(pc.show_root(self.cfg), self.sroot)

    def test_ensure_show_builds_folders(self):
        pc.ensure_show(self.cfg)
        for sub in self.cfg["show_structure"]:
            self.assertTrue(os.path.isdir(os.path.join(self.sroot, sub)), sub)

    def test_ensure_shot_builds_tree(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        for sub in self.cfg["shot_structure"]:
            self.assertTrue(os.path.isdir(os.path.join(self.sroot, self.P, self.S, self.H, sub)), sub)

    def test_ensure_shot_creates_part_and_seq(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        self.assertTrue(os.path.isdir(os.path.join(self.sroot, self.P, self.S)))

    def test_ensure_shot_idempotent(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)

    # --- naming ---
    def test_filename_matches_convention(self):
        self.assertEqual(
            pc.make_filename(self.cfg, self.P, self.S, self.H, "ai", "FirstPass", 1),
            "shwx_101_010_0010_ai_FirstPass_rikinp_v01.exr",
        )

    def test_filename_sequence_padding_two_digit_version(self):
        self.assertEqual(
            pc.make_filename(self.cfg, self.P, self.S, self.H, "comp", "WIP", 7,
                             ext="exr", frame_pad="%04d"),
            "shwx_101_010_0010_comp_WIP_rikinp_v07.%04d.exr",
        )

    def test_task_folder_mapping(self):
        self.assertEqual(os.path.basename(pc.task_dir(self.cfg, self.P, self.S, self.H, "rotopaint")), "rotopaint")
        self.assertEqual(os.path.basename(pc.task_dir(self.cfg, self.P, self.S, self.H, "ai")), "ai_output")
        # unknown task falls back to a folder named after the task
        self.assertEqual(os.path.basename(pc.task_dir(self.cfg, self.P, self.S, self.H, "weird")), "weird")

    def test_cg_tasks_map_to_own_folders(self):
        for task in ("track", "layout", "anim", "fx", "lighting", "render"):
            self.assertEqual(os.path.basename(pc.task_dir(self.cfg, self.P, self.S, self.H, task)), task)

    def test_precomp_is_nested_under_nuke(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        self.assertTrue(os.path.isdir(os.path.join(self.sroot, self.P, self.S, self.H, "nuke", "precomp")))

    def test_real_pipeline_json_has_cg_set_and_precomp(self):
        cfg = pc.load_config()  # the shipped pipeline.json next to the module
        for task in ("track", "layout", "anim", "fx", "lighting", "render"):
            self.assertIn(task, cfg["task_folders"])
        self.assertIn("nuke/precomp", cfg["shot_structure"])

    def test_paths_are_forward_slashed(self):
        self.assertNotIn("\\", pc.task_dir(self.cfg, self.P, self.S, self.H, "comp"))
        self.assertNotIn("\\", pc.script_dir(self.cfg, self.P, self.S, self.H))
        self.assertNotIn("\\", pc.output_path(self.cfg, self.P, self.S, self.H, "comp", "WIP"))

    # --- render versioning (per shot+task, across types) ---
    def test_next_version_empty_is_one(self):
        self.assertEqual(pc.next_version(self.cfg, self.P, self.S, self.H, "comp"), 1)

    def test_next_version_shared_across_types(self):
        comp = pc.task_dir(self.cfg, self.P, self.S, self.H, "comp")
        os.makedirs(comp)
        open(os.path.join(comp, "shwx_101_010_0010_comp_FirstPass_rikinp_v01.exr"), "w").close()
        open(os.path.join(comp, "shwx_101_010_0010_comp_WIP_rikinp_v02.0001.exr"), "w").close()
        self.assertEqual(pc.next_version(self.cfg, self.P, self.S, self.H, "comp"), 3)

    def test_next_version_ignores_other_shot_task_artist_show(self):
        comp = pc.task_dir(self.cfg, self.P, self.S, self.H, "comp")
        os.makedirs(comp)
        open(os.path.join(comp, "shwx_101_010_9999_comp_WIP_rikinp_v50.exr"), "w").close()  # other shot
        open(os.path.join(comp, "shwx_101_010_0010_roto_WIP_rikinp_v50.exr"), "w").close()  # other task
        open(os.path.join(comp, "shwx_101_010_0010_comp_WIP_zz_v50.exr"), "w").close()      # other artist
        open(os.path.join(comp, "zzzz_101_010_0010_comp_WIP_rikinp_v50.exr"), "w").close()  # other show
        self.assertEqual(pc.next_version(self.cfg, self.P, self.S, self.H, "comp"), 1)

    def test_output_path_autoversions_and_makes_dirs(self):
        p1 = pc.output_path(self.cfg, self.P, self.S, self.H, "comp", "WIP", make_dirs=True)
        self.assertTrue(p1.endswith("shwx_101_010_0010_comp_WIP_rikinp_v01.exr"))
        self.assertTrue(os.path.isdir(os.path.dirname(p1)))
        open(p1, "w").close()
        p2 = pc.output_path(self.cfg, self.P, self.S, self.H, "comp", "CF")
        self.assertTrue(p2.endswith("shwx_101_010_0010_comp_CF_rikinp_v02.exr"))  # shared counter

    # --- script naming ---
    def test_parse_version(self):
        self.assertEqual(pc.parse_version("shwx_101_010_0010_comp_WIP_rikinp_v07.nk"), 7)
        self.assertIsNone(pc.parse_version("random.nk"))
        self.assertIsNone(pc.parse_version(""))

    def test_script_path_name_and_location(self):
        p = pc.script_path(self.cfg, self.P, self.S, self.H, "comp", "WIP", version=1)
        self.assertTrue(p.endswith("101/010/0010/nuke/shwx_101_010_0010_comp_WIP_rikinp_v01.nk"))

    def test_next_script_version_increments_across_types(self):
        nuke_dir = pc.script_dir(self.cfg, self.P, self.S, self.H)
        os.makedirs(nuke_dir)
        open(os.path.join(nuke_dir, "shwx_101_010_0010_comp_WIP_rikinp_v01.nk"), "w").close()
        open(os.path.join(nuke_dir, "shwx_101_010_0010_comp_CF_rikinp_v02.nk"), "w").close()
        self.assertEqual(pc.next_script_version(self.cfg, self.P, self.S, self.H, "comp"), 3)

    # --- shot listing (picker source) ---
    def test_list_shots_finds_shots_and_skips_show_folders(self):
        pc.ensure_show(self.cfg)                        # makes assets, ai, color, ...
        pc.ensure_shot(self.cfg, "101", "010", "0010")
        pc.ensure_shot(self.cfg, "101", "010", "0020")
        pc.ensure_shot(self.cfg, "102", "020", "0010")
        shots = pc.list_shots(self.cfg)
        self.assertEqual(shots, [("101", "010", "0010"), ("101", "010", "0020"),
                                 ("102", "020", "0010")])

    def test_list_shots_empty_when_no_show(self):
        self.assertEqual(pc.list_shots(self.cfg), [])

    def test_list_shows(self):
        pc.ensure_show(self.cfg)                         # creates <root>/shwx
        os.makedirs(os.path.join(self.root, "other_show"))
        self.assertEqual(pc.list_shows(self.cfg), ["other_show", "shwx"])

    def test_list_shots_for_named_show(self):
        cfg2 = dict(self.cfg)
        cfg2["show"] = "other"
        pc.ensure_shot(cfg2, "900", "090", "0900")
        self.assertEqual(pc.list_shots(self.cfg, show="other"), [("900", "090", "0900")])

    # --- sync / migrate existing shots to a changed config ---
    def test_sync_adds_new_folders_to_existing_shots(self):
        # build a shot with an OLD (smaller) structure
        old = dict(self.cfg)
        old["shot_structure"] = ["plates", "nuke", "comp"]
        pc.ensure_shot(old, self.P, self.S, self.H)
        shot = os.path.join(self.sroot, self.P, self.S, self.H)
        self.assertFalse(os.path.isdir(os.path.join(shot, "fx")))
        # now sync with the current (full) config
        rep = pc.sync_structure(self.cfg)
        self.assertTrue(os.path.isdir(os.path.join(shot, "fx")))
        self.assertTrue(os.path.isdir(os.path.join(shot, "nuke", "precomp")))
        self.assertEqual(rep["shots"], 1)
        self.assertTrue(any(p.endswith("/fx") for p in rep["added"]))

    def test_sync_is_additive_and_keeps_files(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        comp = pc.task_dir(self.cfg, self.P, self.S, self.H, "comp")
        marker = os.path.join(comp, "keep.txt")
        open(marker, "w").close()
        pc.sync_structure(self.cfg)
        self.assertTrue(os.path.isfile(marker))  # untouched

    def test_sync_prune_removes_empty_only(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        shot = os.path.join(self.sroot, self.P, self.S, self.H)
        os.makedirs(os.path.join(shot, "oldempty"))
        os.makedirs(os.path.join(shot, "oldfull"))
        open(os.path.join(shot, "oldfull", "work.nk"), "w").close()
        rep = pc.sync_structure(self.cfg, prune=True)
        self.assertFalse(os.path.isdir(os.path.join(shot, "oldempty")))   # empty -> gone
        self.assertTrue(os.path.isdir(os.path.join(shot, "oldfull")))     # has file -> kept
        self.assertTrue(any(p.endswith("/oldempty") for p in rep["removed"]))
        self.assertTrue(any(p.endswith("/oldfull") for p in rep["kept_nonempty"]))

    def test_sync_without_prune_keeps_extras(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        shot = os.path.join(self.sroot, self.P, self.S, self.H)
        os.makedirs(os.path.join(shot, "oldempty"))
        pc.sync_structure(self.cfg)  # no prune
        self.assertTrue(os.path.isdir(os.path.join(shot, "oldempty")))

    def test_sync_prune_keeps_nuke_parent(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        shot = os.path.join(self.sroot, self.P, self.S, self.H)
        pc.sync_structure(self.cfg, prune=True)
        self.assertTrue(os.path.isdir(os.path.join(shot, "nuke")))        # parent of nuke/precomp survives

    # --- context inference ---
    def test_context_from_script_in_nuke_subfolder(self):
        p = os.path.join(self.sroot, self.P, self.S, self.H, "nuke", "shwx_101_010_0010_comp_WIP_rikinp_v03.nk")
        self.assertEqual(pc.context_from_path(self.cfg, p), ("101", "010", "0010"))

    def test_context_outside_show_is_none(self):
        self.assertIsNone(pc.context_from_path(self.cfg, os.path.join(tempfile.gettempdir(), "x.nk")))

    def test_context_other_show_is_none(self):
        p = os.path.join(self.root, "OTHER", self.P, self.S, self.H, "nuke", "x.nk")
        self.assertIsNone(pc.context_from_path(self.cfg, p))

    def test_context_too_shallow_is_none(self):
        self.assertIsNone(pc.context_from_path(self.cfg, os.path.join(self.sroot, self.P, "loose.nk")))

    # --- local config writer ---
    def test_set_local_writes_and_merges(self):
        p = os.path.join(self.root, "local.json")
        pc.set_local("root", "D:/Work/projects", p)
        pc.set_local("show", "shwx", p)
        pc.set_local("artist", "rikinp", p)
        with open(p) as fh:
            data = json.load(fh)
        self.assertEqual(data, {"root": "D:/Work/projects", "show": "shwx", "artist": "rikinp"})

    # --- doctor ---
    def test_doctor_passes_core_config(self):
        rows = pc.doctor(self.cfg, repo_dir=self.root)
        self.assertTrue(any(s == "ok" and l == "root configured" for s, l, _ in rows))
        self.assertTrue(any(s == "ok" and l.startswith("show set") for s, l, _ in rows))
        self.assertTrue(any(s == "ok" and l.startswith("artist set") for s, l, _ in rows))

    def test_doctor_fails_placeholder_root(self):
        cfg = dict(self.cfg)
        cfg["root"] = "P:/SHOW_X"
        st = {l: s for s, l, _ in pc.doctor(cfg, repo_dir=self.root)}
        self.assertEqual(st["root configured"], "fail")

    # --- env override ---
    def test_env_overrides(self):
        os.environ["COMFYX_ROOT"] = self.root
        os.environ["COMFYX_SHOW"] = "zzz"
        os.environ["COMFYX_ARTIST"] = "ab"
        cfg_path = os.path.join(self.root, "pipeline.json")
        with open(cfg_path, "w") as fh:
            json.dump({"root": "P:/WRONG", "show": "shwx", "artist": "rikinp",
                       "naming": "{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}",
                       "task_folders": {}, "show_structure": [], "shot_structure": []}, fh)
        try:
            cfg = pc.load_config(cfg_path)
            self.assertEqual(cfg["root"], self.root)
            self.assertEqual(cfg["show"], "zzz")
            self.assertEqual(cfg["artist"], "ab")
        finally:
            for e in ("COMFYX_ROOT", "COMFYX_SHOW", "COMFYX_ARTIST"):
                del os.environ[e]


if __name__ == "__main__":
    unittest.main(verbosity=2)
