import copy
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
import torch

from experiments.local_avatar.benchmark import MotionProbe, probe, summary
from experiments.local_avatar.server import STATIC, LabHandler, validate_pose, validate_result


def renderer_result():
    return {
        "schema_version": 1, "duration_ms": 30000, "frames": 900, "target_fps": 30,
        "visibility_interruptions": 0, "interval_p50_ms": 33.3, "interval_p95_ms": 34.0,
        "draw_p95_ms": 1.0, "estimated_missed_frames": 0, "width": 1280, "height": 720, "webgl_errors": 0,
        "started_at_unix_ms": 1790967600000, "finished_at_unix_ms": 1790967630000,
    }


def pose_record():
    schema = json.loads((STATIC / "rig-schema.json").read_text())
    names = [control["name"] for control in schema["controls"]]
    return {"schema_id": schema["schema_id"], "schema_version": 1, "asset_id": schema["asset_id"],
            "control_order": names, "source": "manual", "pose": dict.fromkeys(names, 0), "vector": [0] * 12}


@pytest.mark.parametrize("bad", [
    {"schema_version": 2}, {"schema_version": True}, {"asset_id": "other"}, {"source": "personal text"},
    {"control_order": []}, {"vector": [0] * 11}, {"vector": [True] + [0] * 11},
    {"vector": [float("nan")] + [0] * 11}, {"vector": [2] + [0] * 11},
    {"vector": [.1] + [0] * 11}, {"pose": {"jawOpen": 0}}, {"private_path": "other"},
])
def test_pose_storage_rejects_stale_inconsistent_and_invalid_labels(bad):
    with pytest.raises(ValueError):
        validate_pose({**pose_record(), **bad})


def test_motion_probe_cannot_read_future_audio():
    torch.manual_seed(7)
    model = MotionProbe().eval()
    original = torch.randn(1, 16, 80)
    changed = original.clone()
    changed[:, 8:] += 100
    with torch.inference_mode():
        a, state = model(original)
        b, _ = model(changed)
    torch.testing.assert_close(a[:, :8], b[:, :8])
    assert state.shape == (2, 1, 256)


def test_cpu_probe_really_updates_weights_with_finite_gradients():
    torch.set_num_threads(4)
    result = probe("cpu", iterations=5, train_steps=2)
    assert result["finite_gradients"] and result["parameters_updated"]
    assert result["warm_inference"]["samples"] == 5
    assert result["parameters"] == 745612


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="Native Mac MPS required")
def test_cpu_mps_prediction_agreement():
    torch.manual_seed(9)
    cpu = MotionProbe().eval()
    gpu = copy.deepcopy(cpu).to("mps")
    x = torch.randn(1, 16, 80)
    with torch.inference_mode():
        expected, _ = cpu(x)
        actual, _ = gpu(x.to("mps"))
    torch.testing.assert_close(actual.cpu(), expected, rtol=2e-4, atol=2e-5)


@pytest.mark.parametrize("bad", [[], {}, {"schema_version": 9}, {**renderer_result(), "frames": float("nan")},
                                     {**renderer_result(), "source_path": "private"}, {**renderer_result(), "frames": "900"}])
def test_renderer_report_rejects_unbounded_or_nonmetric_payloads(bad):
    with pytest.raises(ValueError):
        validate_result(bad)


def test_percentile_uses_real_samples_and_rejects_nan():
    assert summary(list(range(1, 101)))["p95_ms"] == 95
    with pytest.raises(ValueError):
        summary([float("nan")])


def test_loopback_server_restricts_files_hosts_and_writes(tmp_path):
    (tmp_path / "secret.txt").write_text("not served")
    (tmp_path / "reference").mkdir()
    (tmp_path / "reference/avatar_a.png").write_bytes(b"synthetic-test-reference")
    server = ThreadingHTTPServer(("127.0.0.1", 0), LabHandler)
    server.runtime = tmp_path
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(base + "/rig-schema.json") as response:
            schema = json.load(response)
        assert schema["schema_id"] == "local-avatar-head-controls"
        assert schema["schema_version"] == 1
        assert len(schema["controls"]) == 12
        for path in ("/rig.mjs", "/renderer.js"):
            with urllib.request.urlopen(base + path) as response:
                assert response.headers.get_content_type() == "text/javascript"
                assert response.read()
        with urllib.request.urlopen(base + "/reference.png") as response:
            assert response.read() == b"synthetic-test-reference"
        for path in ("/secret.txt", "/../secret.txt", "/reference/manifest.json", "/.env", "/avatar-rig-pose-v1.json"):
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(base + path)
            assert error.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base + "/reference.png", headers={"Host": "other.example"}))
        assert error.value.code == 403
        data = json.dumps(renderer_result()).encode()
        for origin in (None, "https://other.example"):
            headers = {"Content-Type": "application/json"}
            if origin:
                headers["Origin"] = origin
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(urllib.request.Request(base + "/renderer-benchmark", data=data, headers=headers))
            assert error.value.code == 403
        request = urllib.request.Request(base + "/renderer-benchmark", data=data,
                                         headers={"Content-Type": "application/json", "Origin": base})
        with urllib.request.urlopen(request) as response:
            assert json.load(response) == {"saved": True}
        assert json.loads((tmp_path / "renderer-benchmark.json").read_text()) == renderer_result()
        pose = pose_record()
        pose["pose"]["jawOpen"] = .85
        pose["vector"][0] = .85
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(urllib.request.Request(base + "/pose", data=json.dumps(pose).encode(),
                                                         headers={"Content-Type": "application/json", "Origin": "https://other.example"}))
        assert error.value.code == 403
        request = urllib.request.Request(base + "/pose", data=json.dumps(pose).encode(),
                                         headers={"Content-Type": "application/json", "Origin": base})
        with urllib.request.urlopen(request) as response:
            assert json.load(response) == {"saved": True}
        assert json.loads((tmp_path / "avatar-rig-pose-v1.json").read_text()) == pose
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
