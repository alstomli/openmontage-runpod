"""Independent control-plane reliability checks; media rendering is separately tested.

These checks deliberately inject storage/media failures. Passing them does not
establish real S3 or Runpod availability, GPU capability, or narration quality.
"""

from copy import deepcopy
import asyncio
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from openmontage_worker.errors import WorkerError
from openmontage_worker.runner import Runner, execute
from openmontage_worker.storage import LocalStore, S3Store, canonical


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LocalStore(self.root / "storage")
        self.runner = Runner(self.store, self.root / "scratch")
        self.image, self.audio = b"test image", b"test narration"
        self.store.write("inputs/reliability/image.png", self.image)
        self.store.write("inputs/reliability/audio.wav", self.audio)
        self.board = {
            "title": "Reliability fixture",
            "scenes": [{"text": "One", "duration": 4,
                        "image": {"key": "inputs/reliability/image.png", "sha256": sha256(self.image).hexdigest()}}],
            "narration": {"key": "inputs/reliability/audio.wav", "sha256": sha256(self.audio).hexdigest()},
            "captions": [{"text": "Fixture", "start": 0, "end": 4}],
        }

    def call(self, operation, token, **fields):
        return self.runner.run({"operation": operation, "project_id": "reliability", "idempotency_key": token, **fields})

    def plan(self):
        return self.call("prepare", "prepare", storyboard=self.board)

    def approve_plan(self, plan):
        return self.call("approve", "approve-plan", stage="plan", approved=True, artifact_hash=plan["artifact_hash"])

    def assert_error(self, code, function, *args, **kwargs):
        with self.assertRaises(WorkerError) as caught:
            function(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)

    def test_replacement_worker_replays_durable_receipt(self):
        first = self.plan()
        replacement = Runner(LocalStore(self.root / "storage"), self.root / "replacement")
        result = replacement.run({"operation": "prepare", "project_id": "reliability", "idempotency_key": "prepare", "storyboard": self.board})
        self.assertTrue(result["cached"])
        self.assertEqual(first["artifact_hash"], result["artifact_hash"])

    def test_changed_request_cannot_reuse_idempotency_key(self):
        self.plan()
        changed = deepcopy(self.board)
        changed["title"] = "Changed plan"
        self.assert_error("idempotency_conflict", self.call, "prepare", "prepare", storyboard=changed)

    def test_missing_cached_artifact_is_reconstructed(self):
        first = self.plan()
        self.store.delete(first["artifacts"][0]["key"])
        second = self.plan()
        self.assertFalse(second["cached"])
        self.assertEqual(first["artifact_hash"], second["artifact_hash"])

    def test_corrupt_cached_artifact_is_not_reported_intact(self):
        first = self.plan()
        self.store.write(first["artifacts"][0]["key"], b"corrupted")
        second = self.plan()
        self.assertFalse(second["cached"])
        self.assertEqual(first["artifacts"][0]["sha256"], sha256(self.store.read(first["artifacts"][0]["key"])).hexdigest())

    def test_assets_require_exact_plan_approval(self):
        plan = self.plan()
        self.assert_error("approval_required", self.call, "generate_assets", "assets", artifact_hash=plan["artifact_hash"])

    def test_changed_plan_does_not_inherit_approval(self):
        original = self.plan()
        self.approve_plan(original)
        changed = deepcopy(self.board)
        changed["scenes"][0]["text"] = "Revised visual"
        revision = self.call("prepare", "revision", storyboard=changed)
        self.assert_error("approval_required", self.call, "generate_assets", "revised-assets", artifact_hash=revision["artifact_hash"])

    def test_asset_mutation_after_approval_is_rejected(self):
        plan = self.plan()
        self.approve_plan(plan)
        self.store.write("inputs/reliability/audio.wav", b"different narration")
        self.assert_error("asset_hash_mismatch", self.call, "generate_assets", "assets", artifact_hash=plan["artifact_hash"])

    def test_conflicting_hashes_for_one_input_key_are_rejected(self):
        changed = deepcopy(self.board)
        changed["scenes"][0]["duration"] = 2
        changed["scenes"].append({"text": "Conflicting image", "duration": 2,
                                  "image": {"key": "inputs/reliability/image.png", "sha256": "b" * 64}})
        # Either prepare rejects the contradiction, or staging must reject it.
        try:
            plan = self.call("prepare", "contradictory", storyboard=changed)
        except WorkerError:
            return
        self.approve_plan(plan)
        with patch("openmontage_worker.media.validate_media"):
            with self.assertRaises(WorkerError):
                self.call("generate_assets", "assets", artifact_hash=plan["artifact_hash"])

    def test_failed_media_stage_releases_lock_and_can_retry(self):
        plan = self.plan()
        self.approve_plan(plan)
        with patch("openmontage_worker.media.validate_media", side_effect=WorkerError("invalid_media", "Injected failure")):
            self.assert_error("invalid_media", self.call, "generate_assets", "assets", artifact_hash=plan["artifact_hash"])
        self.assertFalse(self.store.path("projects/reliability/execution.lock").exists())
        with patch("openmontage_worker.media.validate_media"):
            result = self.call("generate_assets", "assets", artifact_hash=plan["artifact_hash"])
        self.assertEqual("awaiting_approval", result["status"])

    def test_concurrent_worker_cannot_enter_locked_project(self):
        with self.store.lock("reliability"):
            self.assert_error("project_busy", self.plan)
        self.assertEqual("awaiting_approval", self.plan()["status"])

    def test_crash_leftover_lock_fails_closed(self):
        self.store.create("projects/reliability/execution.lock", canonical({"token": "crashed-worker"}))
        self.assert_error("project_busy", self.plan)
        self.assertTrue(self.store.path("projects/reliability/execution.lock").exists())

    def test_traversal_and_cross_project_assets_rejected(self):
        for key in ("../outside.wav", "inputs/other/audio.wav", "inputs/reliability/../audio.wav", "C:/private.wav"):
            with self.subTest(key=key):
                changed = deepcopy(self.board)
                changed["narration"]["key"] = key
                with self.assertRaises(WorkerError):
                    self.call("prepare", "traversal", storyboard=changed)

    def test_unexpected_exception_does_not_leak_secret_text(self):
        runner = Mock()
        runner.run.side_effect = RuntimeError("private-token-must-not-leak")
        result = execute({"input": {}}, runner)
        self.assertEqual("internal_error", result["error"]["code"])
        self.assertNotIn("private-token", str(result))

    def test_object_and_array_enum_inputs_are_validation_errors(self):
        for value in ([], {}, ["prepare"]):
            for field in ("operation", "stage", "theme"):
                with self.subTest(value=value, field=field):
                    request = {"operation": "prepare", "project_id": "reliability", "idempotency_key": "bad-enum", "storyboard": deepcopy(self.board)}
                    if field == "theme":
                        request["storyboard"]["theme"] = value
                    elif field == "stage":
                        request.update(operation="approve", stage=value, approved=True, artifact_hash="a" * 64)
                        del request["storyboard"]
                    else:
                        request[field] = value
                    response = execute({"input": request}, self.runner)
                    self.assertEqual("invalid_input", response["error"]["code"])


@unittest.skipUnless(importlib.util.find_spec("botocore"), "S3 contract tests require container botocore dependency")
class S3ContractTests(unittest.TestCase):
    def test_installed_sdk_can_encode_conditional_object_creation(self):
        from botocore.session import Session
        operation = Session().get_service_model("s3").operation_model("PutObject")
        self.assertIn("IfNoneMatch", operation.input_shape.members)

    def test_lock_create_uses_atomic_conditional_put(self):
        client = Mock()
        store = S3Store("test-bucket", "prefix", client=client)
        self.assertTrue(store.create("projects/test/execution.lock", b"owner"))
        client.put_object.assert_called_once_with(Bucket="test-bucket", Key="prefix/projects/test/execution.lock", Body=b"owner", IfNoneMatch="*")

    def test_lock_conflict_does_not_overwrite_existing_owner(self):
        from botocore.exceptions import ClientError
        client = Mock()
        client.put_object.side_effect = ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.assertFalse(S3Store("test-bucket", client=client).create("projects/test/execution.lock", b"owner"))
        client.delete_object.assert_not_called()

    def test_missing_s3_object_has_stable_error(self):
        from botocore.exceptions import ClientError
        client = Mock()
        client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        with self.assertRaises(WorkerError) as caught:
            S3Store("test-bucket", client=client).read("projects/test/missing.json")
        self.assertEqual("not_found", caught.exception.code)

    def test_s3_body_is_closed_after_read(self):
        body = Mock(wraps=io.BytesIO(b"verified"))
        client = Mock()
        client.get_object.return_value = {"Body": body, "ContentLength": 8}
        self.assertEqual(b"verified", S3Store("test-bucket", client=client).read("projects/test/blob"))
        body.close.assert_called_once()

    def test_presigned_urls_are_regenerated_for_each_response(self):
        client = Mock()
        client.generate_presigned_url.side_effect = ("fresh-1", "fresh-2")
        store = S3Store("test-bucket", client=client)
        self.assertNotEqual(store.location("projects/test/video.mp4")["download_url"], store.location("projects/test/video.mp4")["download_url"])


@unittest.skipUnless(importlib.util.find_spec("runpod"), "SDK boundary tests require the pinned Runpod container dependency")
class RunpodSDKTests(unittest.TestCase):
    def test_handler_failure_reaches_sdk_error_channel(self):
        from handler import handler
        from runpod.serverless.modules.rp_job import run_job
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.dict(os.environ, {"STORAGE_BACKEND": "local", "LOCAL_STORAGE_ROOT": str(Path(directory) / "store"), "WORK_ROOT": str(Path(directory) / "scratch")}):
                result = asyncio.run(run_job(handler, {"id": "sdk-failure-contract", "input": {"operation": "not-supported", "project_id": "sdk-check", "idempotency_key": "negative"}}))
        self.assertIn("error", result)
        # A dict here passed our earlier SDK-only assertion but the live service
        # discarded it and marked the job COMPLETED. Wire error must be a string.
        self.assertIsInstance(result["error"], str)
        error = json.loads(result["error"])
        self.assertEqual("invalid_input", error["code"])
        self.assertEqual({"code", "message"}, set(error))

    def test_failure_string_survives_complete_sdk_reporting_serialization(self):
        from handler import handler
        from runpod.serverless.modules import rp_http, rp_job
        session = Mock()
        session.headers = {}
        job = {"id": "sdk-report-contract", "input": {"operation": "not-supported", "project_id": "sdk-check", "idempotency_key": "negative"}}
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            with patch.dict(os.environ, {"STORAGE_BACKEND": "local", "LOCAL_STORAGE_ROOT": str(Path(directory) / "store"), "WORK_ROOT": str(Path(directory) / "scratch")}):
                # Capture at the actual SDK network boundary; no cloud request.
                with patch.object(rp_http, "JOB_DONE_URL", "https://worker.invalid/$ID"), patch.object(rp_http, "_transmit", new_callable=AsyncMock) as transmit:
                    asyncio.run(rp_job.handle_job(session, {"handler": handler}, job))
        transmit.assert_awaited_once()
        args = transmit.await_args.args
        self.assertEqual("https://worker.invalid/sdk-report-contract&isStream=false", args[1])
        wire = json.loads(args[2])
        self.assertIsInstance(wire["error"], str)
        error = json.loads(wire["error"])
        self.assertEqual("invalid_input", error["code"])
        self.assertEqual({"code", "message"}, set(error))
        self.assertNotIn("error_traceback", wire["error"])

    def test_sdk_preserves_success_and_ignores_provider_metadata(self):
        from handler import handler
        from runpod.serverless.modules.rp_job import run_job
        with patch("handler.execute", return_value={"status": "awaiting_approval", "artifact_hash": "a" * 64}) as execution:
            result = asyncio.run(run_job(handler, {"id": "sdk-success-contract", "input": {"operation": "prepare"}, "policy": {"ttl": 123}, "delayTime": 20}))
        execution.assert_called_once_with({"input": {"operation": "prepare"}})
        self.assertNotIn("error", result)
        self.assertEqual("awaiting_approval", result["output"]["status"])


if __name__ == "__main__":
    unittest.main()
