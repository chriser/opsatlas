"""OpenVoice V2 wrapper used by the local avatar offline benchmark."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from .common import RuntimeWrapperError, configured_path, load_profile, read_text, require_dir, require_file

DEFAULT_ENCODE_MESSAGE = "@MyShell"


def _profile_value(profile: dict[str, Any], key: str, fallback: str | None = None) -> str | None:
    value = profile.get(key, fallback)
    if value is None:
        return None
    return str(value).strip() or None


def _resolve_reference_audio(args: argparse.Namespace, profile: dict[str, Any]) -> Path:
    configured = args.reference_audio or _profile_value(profile, "reference_audio_path")
    if not configured:
        raise RuntimeWrapperError(
            "OpenVoice needs a local reference voice sample. Pass --reference-audio or set "
            "reference_audio_path in the voice profile JSON."
        )
    return require_file(Path(configured), "Reference voice sample")


def _speaker_lookup(speaker_ids: dict[str, int], requested: str) -> tuple[str, int]:
    items = speaker_ids.items() if hasattr(speaker_ids, "items") else dict(speaker_ids).items()
    aliases = {str(key): str(key).lower().replace("_", "-") for key, _value in items}
    for original, normalized in aliases.items():
        if requested in {original, normalized, original.lower()}:
            return normalized, speaker_ids[original]
    available = ", ".join(sorted(aliases.values()))
    raise RuntimeWrapperError(f"Unknown MeloTTS speaker key {requested!r}. Available speakers: {available}")


def synthesize(args: argparse.Namespace) -> Path:
    data_root = args.data_root.expanduser().resolve()
    profile = load_profile(data_root, "voice", args.voice_profile_id)
    text = read_text(args.text_file)
    reference_audio = _resolve_reference_audio(args, profile)
    output_path = args.output.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    repo_dir = require_dir(configured_path(os.environ.get("OPENVOICE_REPO_DIR"), args.repo_dir, "OPENVOICE_REPO_DIR"), "OPENVOICE_REPO_DIR")
    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))

    checkpoints_dir = Path(
        args.checkpoints_dir
        or os.environ.get("OPENVOICE_CHECKPOINTS_DIR", str(repo_dir / "checkpoints_v2"))
    ).expanduser().resolve()
    converter_dir = require_dir(checkpoints_dir / "converter", "OpenVoice V2 converter checkpoint directory")
    base_speaker_dir = require_dir(checkpoints_dir / "base_speakers" / "ses", "OpenVoice V2 base speaker directory")

    try:
        import torch
        from melo.api import TTS
        from openvoice import se_extractor
        from openvoice.api import ToneColorConverter
    except ImportError as exc:
        raise RuntimeWrapperError(
            "OpenVoice/MeloTTS imports failed. Install OpenVoice V2 and MeloTTS in the runtime environment first."
        ) from exc

    device = args.device or os.environ.get("OPENVOICE_DEVICE") or ("cuda:0" if torch.cuda.is_available() else "cpu")
    language = args.language or _profile_value(profile, "language", "EN_NEWEST")
    speaker_key_requested = args.speaker_key or _profile_value(profile, "speaker_key", "en-newest")
    speed = float(args.speed or profile.get("speed", 1.0))

    converter = ToneColorConverter(str(converter_dir / "config.json"), device=device)
    converter.load_ckpt(str(converter_dir / "checkpoint.pth"))
    target_se, _audio_name = se_extractor.get_se(str(reference_audio), converter, vad=True)

    model = TTS(language=language, device=device)
    speaker_key, speaker_id = _speaker_lookup(model.hps.data.spk2id, speaker_key_requested)
    source_se_path = require_file(base_speaker_dir / f"{speaker_key}.pth", "OpenVoice base speaker tone embedding")
    source_se = torch.load(str(source_se_path), map_location=device)

    with tempfile.TemporaryDirectory(prefix="openvoice-", dir=str(output_path.parent)) as tmp:
        source_path = Path(tmp) / "base_tts.wav"
        model.tts_to_file(text, speaker_id, str(source_path), speed=speed)
        converter.convert(
            audio_src_path=str(source_path),
            src_se=source_se,
            tgt_se=target_se,
            output_path=str(output_path),
            message=args.encode_message or DEFAULT_ENCODE_MESSAGE,
        )
    if not output_path.exists():
        raise RuntimeWrapperError(f"OpenVoice did not create output WAV: {output_path}")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate cloned-voice speech with a local OpenVoice V2 checkout.")
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--voice-profile-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--repo-dir", default="")
    parser.add_argument("--checkpoints-dir", default="")
    parser.add_argument("--reference-audio", default="")
    parser.add_argument("--language", default="")
    parser.add_argument("--speaker-key", default="")
    parser.add_argument("--speed", default="")
    parser.add_argument("--device", default="")
    parser.add_argument("--encode-message", default=DEFAULT_ENCODE_MESSAGE)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        output = synthesize(args)
    except RuntimeWrapperError as exc:
        print(f"openvoice_tts failed: {exc}", file=sys.stderr)
        return 2
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
