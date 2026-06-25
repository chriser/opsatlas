"""Runtime wrapper tests for external avatar model integrations."""

from services.avatar_render.benchmark import _render_template
from services.avatar_render.models import OfflineBenchmarkRequest
from services.avatar_render.runtime_wrappers.common import RuntimeWrapperError, configured_path, load_profile
from services.avatar_render.runtime_wrappers.musetalk_render import write_inference_config
from services.avatar_render.runtime_wrappers.openvoice_tts import build_parser as build_openvoice_parser
from services.avatar_render.runtime_wrappers.openvoice_tts import synthesize


def _request() -> OfflineBenchmarkRequest:
    return OfflineBenchmarkRequest.model_validate({
        "speech_id": "runtime-test",
        "text": "Approved speech text only.",
        "style": "natural",
        "voice_profile_id": "local-voice",
        "avatar_profile_id": "local-avatar",
        "render_mode": "offline",
        "run_commands": True,
    })


def test_benchmark_template_exposes_runtime_wrapper_paths(tmp_path):
    run_dir = tmp_path / "benchmarks" / "run-001"
    text_path = run_dir / "approved_text.txt"
    audio_path = run_dir / "speech.wav"
    video_path = run_dir / "avatar.mp4"

    command = (
        "python -m services.avatar_render.runtime_wrappers.openvoice_tts "
        "--text-file {text_path} --voice-profile-id {voice_profile_id} "
        "--data-root {data_root} --output {audio_path}"
    )

    parts = _render_template(command, text_path=text_path, audio_path=audio_path, video_path=video_path, request=_request())

    assert str(text_path) in parts
    assert str(audio_path) in parts
    assert str(tmp_path) in parts
    assert "local-voice" in parts


def test_load_profile_reads_ignored_local_profile_json(tmp_path):
    profile_dir = tmp_path / "voice_profiles"
    profile_dir.mkdir()
    profile = profile_dir / "local-voice.json"
    profile.write_text('{"reference_audio_path": "/tmp/reference.wav"}', encoding="utf-8")

    assert load_profile(tmp_path, "voice", "local-voice")["reference_audio_path"] == "/tmp/reference.wav"


def test_configured_path_requires_explicit_runtime_location():
    try:
        configured_path(None, "", "OPENVOICE_REPO_DIR")
    except RuntimeWrapperError as exc:
        assert "OPENVOICE_REPO_DIR must be configured" in str(exc)
    else:
        raise AssertionError("Expected missing runtime path to fail")


def test_openvoice_wrapper_fails_clearly_without_reference_audio(tmp_path):
    text_file = tmp_path / "approved.txt"
    text_file.write_text("Approved speech text only.", encoding="utf-8")
    profile_dir = tmp_path / "voice_profiles"
    profile_dir.mkdir()
    (profile_dir / "local-voice.json").write_text("{}", encoding="utf-8")
    parser = build_openvoice_parser()
    args = parser.parse_args([
        "--text-file",
        str(text_file),
        "--voice-profile-id",
        "local-voice",
        "--data-root",
        str(tmp_path),
        "--output",
        str(tmp_path / "speech.wav"),
        "--repo-dir",
        str(tmp_path / "missing-openvoice"),
    ])

    try:
        synthesize(args)
    except RuntimeWrapperError as exc:
        assert "reference voice sample" in str(exc)
    else:
        raise AssertionError("Expected missing reference audio to fail before importing OpenVoice")


def test_musetalk_wrapper_writes_single_task_config(tmp_path):
    avatar_source = tmp_path / "avatar.mp4"
    audio_path = tmp_path / "speech.wav"
    avatar_source.write_bytes(b"fake")
    audio_path.write_bytes(b"fake")
    config_path = tmp_path / "musetalk.yaml"

    write_inference_config(config_path, avatar_source=avatar_source, audio_path=audio_path, bbox_shift=-7)

    text = config_path.read_text(encoding="utf-8")
    assert 'video_path: "' in text
    assert str(avatar_source) in text
    assert str(audio_path) in text
    assert "bbox_shift: -7" in text
