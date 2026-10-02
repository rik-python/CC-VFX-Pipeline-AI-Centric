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
        "mov_format": "mov",
        "write_colorspace": "",
        "review_colorspace": "",
        "naming": "{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}",
        "types": ["SlapComp", "FirstPassSingle", "WIP", "CF", "TF"],
        "script_subfolder": "nk",
        "render_folder": "render",
        "render_exr_dir": "exr",
        "render_mov_dir": "mov",
        "show_structure": ["assets", "reference", "edit", "ai/datasets/images/raw",
                           "ai/models/checkpoints", "color/ocio"],
        "shot_common": ["plates", "review", "delivery", "elements"],
        "tasks": ["prep", "rotopaint", "ai", "comp"],
        "task_subfolders": ["nk", "render", "precomp", "cache"],
        "task_extras": {"ai": ["input", "output", "workflow"]},
    }


class PipelineCore(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cfg = _cfg(self.root)
        self.sroot = os.path.join(self.root, "shwx")          # <root>/<show>
        self.P, self.S, self.H = "101", "010", "0010"         # part, seq, shot

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _shot(self, *parts):
        return os.path.join(self.sroot, self.P, self.S, self.H, *parts)

    # --- show / shot trees ---
    def test_show_root_includes_show(self):
        self.assertEqual(pc.show_root(self.cfg), self.sroot)

    def test_ensure_show_builds_folders(self):
        pc.ensure_show(self.cfg)
        for sub in self.cfg["show_structure"]:
            self.assertTrue(os.path.isdir(os.path.join(self.sroot, sub)), sub)

    def test_ensure_shot_common_at_shot_level(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        for sub in ("plates", "review", "delivery", "elements"):
            self.assertTrue(os.path.isdir(self._shot(sub)), sub)

    def test_ensure_shot_task_subfolders(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        for task in ("prep", "rotopaint", "ai", "comp"):
            for sub in ("nk", "render", "precomp", "cache"):
                self.assertTrue(os.path.isdir(self._shot(task, sub)), task + "/" + sub)

    def test_ensure_shot_ai_extras(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        for sub in ("input", "output", "workflow"):
            self.assertTrue(os.path.isdir(self._shot("ai", sub)), "ai/" + sub)
        # non-ai tasks do NOT get the extras
        self.assertFalse(os.path.isdir(self._shot("comp", "input")))

    def test_precomp_is_per_task(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        self.assertTrue(os.path.isdir(self._shot("comp", "precomp")))
        self.assertTrue(os.path.isdir(self._shot("prep", "precomp")))
        # not a shot-level folder anymore
        self.assertFalse(os.path.isdir(self._shot("precomp")))

    def test_ensure_shot_creates_part_and_seq(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        self.assertTrue(os.path.isdir(os.path.join(self.sroot, self.P, self.S)))

    def test_ensure_shot_idempotent(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)

    def test_task_root_and_script_dir(self):
        self.assertTrue(pc.task_root(self.cfg, self.P, self.S, self.H, "comp").endswith("0010/comp"))
        self.assertTrue(pc.script_dir(self.cfg, self.P, self.S, self.H, "comp").endswith("0010/comp/nk"))

    def test_real_pipeline_json_is_task_centric(self):
        cfg = pc.load_config()  # the shipped pipeline.json next to the module
        self.assertEqual(cfg["tasks"], ["prep", "rotopaint", "ai", "comp"])
        self.assertEqual(cfg["shot_common"], ["plates", "review", "delivery", "elements"])
        self.assertIn("nk", cfg["task_subfolders"])
        self.assertIn("render", cfg["task_subfolders"])
        self.assertIn("ai", cfg["task_extras"])
        # CG discipline tasks are gone
        for gone in ("track", "layout", "anim", "fx", "lighting"):
            self.assertNotIn(gone, cfg["tasks"])

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

    def test_paths_are_forward_slashed(self):
        self.assertNotIn("\\", pc.task_root(self.cfg, self.P, self.S, self.H, "comp"))
        self.assertNotIn("\\", pc.script_dir(self.cfg, self.P, self.S, self.H, "comp"))
        self.assertNotIn("\\", pc.output_path(self.cfg, self.P, self.S, self.H, "comp", "WIP"))

    # --- versioning (per shot+task, from the nk folder, across types) ---
    def test_next_script_version_empty_is_one(self):
        self.assertEqual(pc.next_script_version(self.cfg, self.P, self.S, self.H, "comp"), 1)

    def test_next_script_version_shared_across_types(self):
        nk = pc.script_dir(self.cfg, self.P, self.S, self.H, "comp")
        os.makedirs(nk)
        open(os.path.join(nk, "shwx_101_010_0010_comp_FirstPass_rikinp_v01.nk"), "w").close()
        open(os.path.join(nk, "shwx_101_010_0010_comp_WIP_rikinp_v02.nk"), "w").close()
        self.assertEqual(pc.next_script_version(self.cfg, self.P, self.S, self.H, "comp"), 3)

    def test_next_script_version_ignores_other_shot_task_artist_show(self):
        nk = pc.script_dir(self.cfg, self.P, self.S, self.H, "comp")
        os.makedirs(nk)
        open(os.path.join(nk, "shwx_101_010_9999_comp_WIP_rikinp_v50.nk"), "w").close()  # other shot
        open(os.path.join(nk, "shwx_101_010_0010_prep_WIP_rikinp_v50.nk"), "w").close()  # other task
        open(os.path.join(nk, "shwx_101_010_0010_comp_WIP_zz_v50.nk"), "w").close()      # other artist
        open(os.path.join(nk, "zzzz_101_010_0010_comp_WIP_rikinp_v50.nk"), "w").close()  # other show
        self.assertEqual(pc.next_script_version(self.cfg, self.P, self.S, self.H, "comp"), 1)

    # --- script path ---
    def test_script_path_name_and_location(self):
        p = pc.script_path(self.cfg, self.P, self.S, self.H, "comp", "WIP", version=1)
        self.assertTrue(p.endswith("101/010/0010/comp/nk/shwx_101_010_0010_comp_WIP_rikinp_v01.nk"), p)

    def test_script_path_autoversions(self):
        pc.script_path(self.cfg, self.P, self.S, self.H, "comp", "WIP", make_dirs=True)
        nk = pc.script_dir(self.cfg, self.P, self.S, self.H, "comp")
        open(os.path.join(nk, "shwx_101_010_0010_comp_WIP_rikinp_v01.nk"), "w").close()
        p2 = pc.script_path(self.cfg, self.P, self.S, self.H, "comp", "CF")
        self.assertTrue(p2.endswith("_comp_CF_rikinp_v02.nk"), p2)  # shared counter per shot+task

    # --- render output (task/render/<stem>/{exr,mov}) ---
    def test_output_path_under_task_render_stem(self):
        p = pc.output_path(self.cfg, self.P, self.S, self.H, "comp", "WIP", version=3, make_dirs=True)
        self.assertTrue(p.endswith(
            "101/010/0010/comp/render/shwx_101_010_0010_comp_WIP_rikinp_v03/"
            "exr/shwx_101_010_0010_comp_WIP_rikinp_v03.%04d.exr"), p)
        self.assertTrue(os.path.isdir(os.path.dirname(p)))

    def test_parse_version(self):
        self.assertEqual(pc.parse_version("shwx_101_010_0010_comp_WIP_rikinp_v07.nk"), 7)
        self.assertIsNone(pc.parse_version("random.nk"))
        self.assertIsNone(pc.parse_version(""))

    def test_parse_name_full(self):
        d = pc.parse_name("shwx_101_010_0010_comp_WIP_rikinp_v03.nk")
        self.assertEqual((d["show"], d["part"], d["seq"], d["shot"]), ("shwx", "101", "010", "0010"))
        self.assertEqual((d["task"], d["type"], d["artist"], d["version"]), ("comp", "WIP", "rikinp", 3))

    def test_parse_name_ignores_frame_pad_and_ext(self):
        d = pc.parse_name("shwx_101_010_0010_ai_FirstPass_rikinp_v12.%04d.exr")
        self.assertEqual(d["task"], "ai")
        self.assertEqual(d["version"], 12)

    def test_parse_name_none_for_nonpipeline(self):
        self.assertIsNone(pc.parse_name("random_thing.nk"))
        self.assertIsNone(pc.parse_name(""))

    def test_render_outputs_exr_and_mov(self):
        script = self._shot("comp", "nk", "shwx_101_010_0010_comp_WIP_rikinp_v03.nk")
        r = pc.render_outputs(self.cfg, script, make_dirs=True)
        self.assertTrue(r["exr"].endswith(
            "comp/render/shwx_101_010_0010_comp_WIP_rikinp_v03/exr/"
            "shwx_101_010_0010_comp_WIP_rikinp_v03.%04d.exr"), r["exr"])
        self.assertTrue(r["mov"].endswith(
            "comp/render/shwx_101_010_0010_comp_WIP_rikinp_v03/mov/"
            "shwx_101_010_0010_comp_WIP_rikinp_v03.mov"), r["mov"])
        self.assertTrue(os.path.isdir(r["exr_dir"]))
        self.assertTrue(os.path.isdir(r["mov_dir"]))

    def test_render_outputs_ai_task(self):
        script = self._shot("ai", "nk", "shwx_101_010_0010_ai_FirstPass_rikinp_v05.nk")
        r = pc.render_outputs(self.cfg, script)
        self.assertIn("/ai/render/", r["exr"])
        self.assertTrue(r["exr"].endswith("_ai_FirstPass_rikinp_v05.%04d.exr"), r["exr"])

    def test_render_outputs_none_for_unnamed_script(self):
        self.assertIsNone(pc.render_outputs(self.cfg, "/tmp/untitled.nk"))

    def test_write_path_from_script_is_exr(self):
        script = self._shot("comp", "nk", "shwx_101_010_0010_comp_WIP_rikinp_v03.nk")
        self.assertEqual(pc.write_path_from_script(self.cfg, script),
                         pc.render_outputs(self.cfg, script)["exr"])

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
    def test_sync_adds_new_task_folders_to_existing_shots(self):
        old = dict(self.cfg)
        old["tasks"] = ["comp"]               # a shot made before prep/roto/ai existed
        old["task_extras"] = {}
        pc.ensure_shot(old, self.P, self.S, self.H)
        self.assertFalse(os.path.isdir(self._shot("prep", "nk")))
        rep = pc.sync_structure(self.cfg)      # full config
        self.assertTrue(os.path.isdir(self._shot("prep", "nk")))
        self.assertTrue(os.path.isdir(self._shot("ai", "input")))
        self.assertEqual(rep["shots"], 1)
        self.assertTrue(any(p.endswith("/prep/nk") for p in rep["added"]))

    def test_sync_is_additive_and_keeps_files(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        marker = self._shot("comp", "nk", "keep.nk")
        open(marker, "w").close()
        pc.sync_structure(self.cfg)
        self.assertTrue(os.path.isfile(marker))  # untouched

    def test_sync_prune_removes_empty_only(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        os.makedirs(self._shot("oldempty"))
        os.makedirs(self._shot("oldfull"))
        open(self._shot("oldfull", "work.nk"), "w").close()
        rep = pc.sync_structure(self.cfg, prune=True)
        self.assertFalse(os.path.isdir(self._shot("oldempty")))   # empty -> gone
        self.assertTrue(os.path.isdir(self._shot("oldfull")))     # has file -> kept
        self.assertTrue(any(p.endswith("/oldempty") for p in rep["removed"]))
        self.assertTrue(any(p.endswith("/oldfull") for p in rep["kept_nonempty"]))

    def test_sync_without_prune_keeps_extras(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        os.makedirs(self._shot("oldempty"))
        pc.sync_structure(self.cfg)  # no prune
        self.assertTrue(os.path.isdir(self._shot("oldempty")))

    def test_sync_prune_keeps_task_folders(self):
        pc.ensure_shot(self.cfg, self.P, self.S, self.H)
        pc.sync_structure(self.cfg, prune=True)
        for task in ("prep", "rotopaint", "ai", "comp"):
            self.assertTrue(os.path.isdir(self._shot(task)), task)      # tasks are expected -> survive
        for common in ("plates", "review", "delivery", "elements"):
            self.assertTrue(os.path.isdir(self._shot(common)), common)

    # --- context inference ---
    def test_context_from_script_in_task_nk(self):
        p = self._shot("comp", "nk", "shwx_101_010_0010_comp_WIP_rikinp_v03.nk")
        self.assertEqual(pc.context_from_path(self.cfg, p), ("101", "010", "0010"))

    def test_context_outside_show_is_none(self):
        self.assertIsNone(pc.context_from_path(self.cfg, os.path.join(tempfile.gettempdir(), "x.nk")))

    def test_context_other_show_is_none(self):
        p = os.path.join(self.root, "OTHER", self.P, self.S, self.H, "comp", "nk", "x.nk")
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
    def _min_cfg_file(self):
        cfg_path = os.path.join(self.root, "pipeline.json")
        with open(cfg_path, "w") as fh:
            json.dump({"root": "P:/WRONG", "show": "shwx", "artist": "rikinp",
                       "naming": "{show}_{part}_{seq}_{shot}_{task}_{type}_{artist}_v{version:02d}",
                       "tasks": [], "shot_common": [], "show_structure": []}, fh)
        return cfg_path

    def test_env_overrides_cc(self):
        os.environ["CC_ROOT"] = self.root
        os.environ["CC_SHOW"] = "zzz"
        os.environ["CC_ARTIST"] = "ab"
        try:
            cfg = pc.load_config(self._min_cfg_file())
            self.assertEqual((cfg["root"], cfg["show"], cfg["artist"]), (self.root, "zzz", "ab"))
        finally:
            for e in ("CC_ROOT", "CC_SHOW", "CC_ARTIST"):
                del os.environ[e]

    def test_env_overrides_legacy_comfyx_fallback(self):
        os.environ["COMFYX_ROOT"] = self.root
        os.environ["COMFYX_ARTIST"] = "legacy"
        try:
            cfg = pc.load_config(self._min_cfg_file())
            self.assertEqual(cfg["root"], self.root)
            self.assertEqual(cfg["artist"], "legacy")   # old COMFYX_* still honored
        finally:
            for e in ("COMFYX_ROOT", "COMFYX_ARTIST"):
                del os.environ[e]

    def test_local_file_new_wins_over_legacy(self):
        old = os.path.join(self.root, "old_local.json")
        new = os.path.join(self.root, "new_local.json")
        with open(old, "w") as fh:
            json.dump({"artist": "oldguy", "show": "oldshow"}, fh)
        with open(new, "w") as fh:
            json.dump({"artist": "newguy"}, fh)   # show omitted -> legacy value survives
        saved = (pc.LOCAL_PATH, pc.OLD_LOCAL_PATH)
        pc.LOCAL_PATH, pc.OLD_LOCAL_PATH = new, old
        try:
            cfg = pc.load_config(self._min_cfg_file())
            self.assertEqual(cfg["artist"], "newguy")   # new file wins
            self.assertEqual(cfg["show"], "oldshow")     # legacy fills the gap
        finally:
            pc.LOCAL_PATH, pc.OLD_LOCAL_PATH = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
