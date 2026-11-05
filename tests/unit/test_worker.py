from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch

from openmontage_worker.errors import WorkerError
from openmontage_worker import media, schema
from openmontage_worker.runner import Runner, execute
from openmontage_worker.storage import LocalStore, safe_key


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.store = LocalStore(self.root / "store")
        self.runner = Runner(self.store, self.root / "work")
        self.audio = b"fixture-audio-bytes"
        self.image = b"fixture-image-bytes"
        self.audio_ref = {"key": "inputs/demo/audio.wav", "sha256": sha256(self.audio).hexdigest()}
        self.image_ref = {"key": "inputs/demo/scene.png", "sha256": sha256(self.image).hexdigest()}
        self.store.write(self.audio_ref["key"], self.audio)
        self.store.write(self.image_ref["key"], self.image)
        self.board = {"title": "Test explainer", "scenes": [{"text": "First scene", "duration": 2, "image": self.image_ref}, {"text": "Second scene", "duration": 2}], "narration": self.audio_ref, "captions": [{"text": "Caption", "start": 0, "end": 4}]}
        self.counter = 0

    def tearDown(self):
        self.directory.cleanup()

    def call(self, op, key=None, **kwargs):
        self.counter += 1
        return execute({"input": {"operation": op, "project_id": "demo", "idempotency_key": key or f"request-{self.counter}", **kwargs}}, self.runner)

    def code(self, result, expected):
        self.assertEqual(result["status"], "failed", result)
        self.assertEqual(result["error"]["code"], expected, result)

    def prepare(self):
        result = self.call("prepare", storyboard=self.board)
        self.assertEqual(result["status"], "awaiting_approval", result)
        return result["artifact_hash"]

    def approve(self, stage, version):
        result = self.call("approve", stage=stage, artifact_hash=version, approved=True)
        self.assertEqual(result["status"], "approved", result)

    def assets(self):
        plan = self.prepare()
        self.approve("plan", plan)
        with patch("openmontage_worker.media.validate_media"):
            result = self.call("generate_assets", artifact_hash=plan)
        self.assertEqual(result["status"], "awaiting_approval", result)
        return result

    def test_plan_requires_explicit_approval(self):
        version = self.prepare()
        self.code(self.call("generate_assets", artifact_hash=version), "approval_required")

    def test_approval_does_not_transfer_to_revised_plan(self):
        original = self.prepare()
        self.approve("plan", original)
        self.board["title"] = "Revised title"
        revised = self.prepare()
        self.assertNotEqual(original, revised)
        self.code(self.call("generate_assets", artifact_hash=revised), "approval_required")

    def test_approval_requires_true_attestation(self):
        version = self.prepare()
        self.code(self.call("approve", stage="plan", artifact_hash=version, approved=False), "invalid_input")

    def test_cannot_approve_nonexistent_artifact(self):
        self.code(self.call("approve", stage="plan", artifact_hash="0" * 64, approved=True), "not_found")

    def test_assets_require_separate_approval(self):
        result = self.assets()
        self.code(self.call("compose", artifact_hash=result["artifact_hash"]), "approval_required")

    def test_modified_stored_plan_is_detected(self):
        version = self.prepare()
        key = f"projects/demo/plans/{version}.json"
        changed = self.store.read_json(key)
        changed["title"] = "Tampered"
        self.store.write_json(key, changed)
        self.code(self.call("approve", stage="plan", artifact_hash=version, approved=True), "corrupt_artifact")

    def test_source_replacement_is_detected(self):
        version = self.prepare()
        self.approve("plan", version)
        self.store.write(self.audio_ref["key"], b"replaced")
        self.code(self.call("generate_assets", artifact_hash=version), "asset_hash_mismatch")

    def test_idempotent_request_returns_verified_cached_result(self):
        a = self.call("prepare", key="same", storyboard=self.board)
        b = self.call("prepare", key="same", storyboard=self.board)
        self.assertFalse(a["cached"])
        self.assertTrue(b["cached"])
        self.assertEqual(a["artifact_hash"], b["artifact_hash"])

    def test_reused_key_with_changed_request_fails(self):
        self.call("prepare", key="same", storyboard=self.board)
        self.board["title"] = "Different"
        self.code(self.call("prepare", key="same", storyboard=self.board), "idempotency_conflict")

    def test_missing_cached_artifact_is_rebuilt(self):
        first = self.call("prepare", key="retry", storyboard=self.board)
        self.store.delete(first["artifacts"][0]["key"])
        second = self.call("prepare", key="retry", storyboard=self.board)
        self.assertFalse(second["cached"])
        self.assertEqual(first["artifact_hash"], second["artifact_hash"])

    def test_replacement_worker_resumes_from_durable_plan(self):
        version = self.prepare()
        self.approve("plan", version)
        self.runner = Runner(LocalStore(self.root / "store"), self.root / "replacement")
        with patch("openmontage_worker.media.validate_media"):
            response = self.call("generate_assets", artifact_hash=version)
        self.assertEqual(response["status"], "awaiting_approval", response)

    def test_failed_stage_releases_lock_and_can_retry(self):
        version = self.prepare()
        self.approve("plan", version)
        with patch("openmontage_worker.media.validate_media", side_effect=WorkerError("invalid_media", "Bad input")):
            self.code(self.call("generate_assets", key="retry-assets", artifact_hash=version), "invalid_media")
        with patch("openmontage_worker.media.validate_media"):
            result = self.call("generate_assets", key="retry-assets", artifact_hash=version)
        self.assertEqual(result["status"], "awaiting_approval", result)

    def test_project_lock_excludes_concurrent_requests(self):
        with self.store.lock("demo"):
            self.code(self.call("prepare", storyboard=self.board), "project_busy")
        self.assertEqual(self.call("prepare", storyboard=self.board)["status"], "awaiting_approval")

    def test_different_projects_have_independent_locks(self):
        with self.store.lock("other"):
            self.assertEqual(self.call("prepare", storyboard=self.board)["status"], "awaiting_approval")

    def test_unknown_fields_and_plain_scripts_are_rejected(self):
        self.code(self.call("prepare", storyboard=self.board, script="make video"), "invalid_input")
        self.code(self.call("prepare", storyboard="make video"), "invalid_input")

    def test_eight_scene_limit(self):
        self.board["scenes"] = [{"text": "Scene", "duration": 2}] * 9
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_ninety_second_limit(self):
        self.board["scenes"] = [{"text": "Scene", "duration": 30}] * 4
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_nan_duration_is_rejected(self):
        self.board["scenes"][0]["duration"] = float("nan")
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_cross_project_source_is_rejected(self):
        self.board["narration"]["key"] = "inputs/another/audio.wav"
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_traversal_absolute_paths_and_urls_are_rejected(self):
        for key in ("../secret", "a/../secret", "C:/secret", "/secret", "https://host/file", "a\\b", "a//b", "a/./b", "a\nfile"):
            with self.subTest(key=key), self.assertRaises(WorkerError):
                safe_key(key)

    def test_overlapping_captions_are_rejected(self):
        self.board["captions"] = [{"text": "A", "start": 0, "end": 3}, {"text": "B", "start": 2, "end": 4}]
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_conflicting_hashes_for_same_key_are_rejected(self):
        self.board["scenes"][1]["image"] = {**self.image_ref, "sha256": "0" * 64}
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_srt_preserves_supplied_timing(self):
        self.assertEqual(media.srt([{"text": "Caption", "start": 1.025, "end": 2.5}]), "1\n00:00:01,025 --> 00:00:02,500\nCaption\n")

    def test_long_phrase_wraps_without_inventing_word_timings(self):
        phrase = "This supplied phrase has a very long filename " + "W" * 80
        output = media.srt([{"text": phrase, "start": 1.025, "end": 8.5}])
        lines = output.splitlines()
        self.assertEqual(lines[1], "00:00:01,025 --> 00:00:08,500")
        self.assertTrue(all(len(line) <= 32 for line in lines[2:]))
        self.assertEqual("".join(lines[2:]).replace(" ", ""), phrase.replace(" ", ""))
        self.assertEqual(output.count(" --> "), 1)

    def test_caption_style_markup_is_rejected_instead_of_rewritten(self):
        for phrase in ("{\\pos(0,0)}Hidden", "<font>Styled</font>", "C:\\private"):
            with self.subTest(phrase=phrase):
                self.board["captions"][0]["text"] = phrase
                self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_subtitle_reveal_must_fit_scene_duration(self):
        self.board["scenes"][0].update(text="A lengthy title that takes time to reveal", subtitle="Visible subtitle", duration=1)
        self.code(self.call("prepare", storyboard=self.board), "invalid_input")

    def test_phrase_captions_use_libass_and_scene_subtitles_use_supported_component(self):
        self.board["scenes"][0].update(text="A title", subtitle="Approved subtitle")
        assets = self.assets()
        manifest = self.runner.load("demo", "assets", assets["artifact_hash"])
        plan = self.runner.load("demo", "plans", manifest["plan_hash"])
        upstream = self.root / "upstream"
        cli = upstream / "remotion-composer" / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("fixture", encoding="utf-8")
        workspace = self.root / "render"
        workspace.mkdir()
        calls = []
        def fake_command(args, **kwargs):
            calls.append(args)
            # Produce placeholders for each command's output so the complete
            # rendering boundary can validate its actual generated contracts.
            Path(args[5] if "render" in args else args[-1]).write_bytes(b"fixture-output")
            return ""
        metadata = {"format": {"duration": "4"}, "streams": [{"codec_type": "video", "width": 1280, "height": 720}, {"codec_type": "audio"}]}
        with patch.dict(os.environ, {"OPENMONTAGE_ROOT": str(upstream)}), patch("openmontage_worker.media.command", side_effect=fake_command), patch("openmontage_worker.media.probe", return_value=metadata):
            outputs = media.render(plan, manifest, self.store, workspace)
        props = json.loads(outputs["props"].read_text())
        self.assertEqual(props["captions"], [], "Phrases must not enter the upstream nowrap WordCaption overlay")
        self.assertEqual(props["cuts"][0]["type"], "hero_title")
        self.assertEqual(props["cuts"][0]["subtitle"], "Approved subtitle")
        self.assertEqual(props["cuts"][1]["type"], "text_card")
        burn_calls = [args for args in calls if "-vf" in args]
        self.assertEqual(len(burn_calls), 1)
        self.assertIn("subtitles=filename=captions.srt", burn_calls[0][burn_calls[0].index("-vf") + 1])
        self.assertIn("FontSize=14", burn_calls[0][burn_calls[0].index("-vf") + 1])

    def test_output_manifest_survives_replacement_worker(self):
        assets = self.assets()
        self.approve("assets", assets["artifact_hash"])
        def fake_render(plan, manifest, store, directory):
            path = directory / "final.mp4"
            path.write_bytes(b"render-fixture")
            return {"video": path}
        with patch("openmontage_worker.media.render", side_effect=fake_render):
            result = self.call("compose", key="compose", artifact_hash=assets["artifact_hash"])
        self.assertEqual(result["status"], "completed", result)
        self.runner = Runner(LocalStore(self.root / "store"), self.root / "replacement")
        with patch("openmontage_worker.media.render", side_effect=AssertionError("Must use durable render")):
            again = self.call("compose", key="compose", artifact_hash=assets["artifact_hash"])
        self.assertTrue(again["cached"], again)
        self.assertTrue(any(a.get("kind") == "manifest" for a in again["artifacts"]))


class HandlerAdapterTests(unittest.TestCase):
    def test_runpod_error_is_a_string_without_mutating_local_error_contract(self):
        from handler import handler
        local_result = {"status": "failed", "error": {"code": "invalid_input", "message": "Unknown operation."}}
        with patch("handler.execute", return_value=local_result):
            remote_result = handler({"input": {"operation": "unsupported"}})
        self.assertIsInstance(remote_result["error"], str)
        self.assertEqual(json.loads(remote_result["error"]), local_result["error"])
        self.assertIsInstance(local_result["error"], dict)

    def test_runpod_internal_error_does_not_expose_original_exception(self):
        from handler import handler
        with patch("openmontage_worker.runner.Runner", side_effect=RuntimeError("private-token-must-not-leak")):
            result = handler({"input": {"operation": "prepare"}})
        self.assertIsInstance(result["error"], str)
        self.assertEqual(json.loads(result["error"])["code"], "internal_error")
        self.assertNotIn("private-token", result["error"])
        self.assertNotIn("traceback", result["error"].lower())

    def test_success_is_preserved_and_provider_metadata_is_ignored(self):
        from handler import handler
        expected = {"status": "awaiting_approval", "artifact_hash": "a" * 64}
        with patch("handler.execute", return_value=expected) as execute_mock:
            result = handler({"id": "provider-job", "input": {"operation": "prepare"}, "policy": {"ttl": 123}})
        self.assertEqual(result, expected)
        execute_mock.assert_called_once_with({"input": {"operation": "prepare"}})


if __name__ == "__main__":
    unittest.main()
