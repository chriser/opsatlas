"""Loopback-only lab. Serves named assets only, never a directory or arbitrary path."""

import argparse
import json
import math
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

STATIC = Path(__file__).parent / "web"


def validate_pose(record):
    schema = json.loads((STATIC / "rig-schema.json").read_text())
    expected = {"schema_id", "schema_version", "asset_id", "control_order", "source", "pose", "vector"}
    if not isinstance(record, dict) or set(record) != expected:
        raise ValueError("Unexpected pose fields")
    for key in ("schema_id", "schema_version", "asset_id"):
        if type(record[key]) is not type(schema[key]) or record[key] != schema[key]:
            raise ValueError("Pose schema mismatch")
    names = [control["name"] for control in schema["controls"]]
    sources = ["manual"] + ["preset:" + preset["id"] for preset in schema["presets"]]
    if record["control_order"] != names or record["source"] not in sources:
        raise ValueError("Pose order or source mismatch")
    pose, vector = record["pose"], record["vector"]
    if not isinstance(pose, dict) or set(pose) != set(names) or not isinstance(vector, list) or len(vector) != len(names):
        raise ValueError("Expected complete pose and vector")
    for control, value in zip(schema["controls"], vector):
        named = pose[control["name"]]
        for number in (value, named):
            if type(number) not in (int, float) or not math.isfinite(number) or not control["min"] <= number <= control["max"]:
                raise ValueError("Invalid control value")
        if named != value:
            raise ValueError("Named pose differs from vector")
    return record


def validate_result(result):
    if not isinstance(result, dict) or result.get("schema_version") != 1:
        raise ValueError("Unknown renderer result schema")
    expected = {"schema_version", "duration_ms", "frames", "target_fps", "visibility_interruptions", "interval_p50_ms",
                "interval_p95_ms", "draw_p95_ms", "estimated_missed_frames", "width", "height", "webgl_errors",
                "started_at_unix_ms", "finished_at_unix_ms"}
    if set(result) != expected:
        raise ValueError("Unexpected renderer result fields")
    for value in result.values():
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Metrics must be finite nonnegative numbers")
    if not 1000 <= result["duration_ms"] <= 700000 or not 1 <= result["frames"] <= 100000:
        raise ValueError("Run duration or frame count outside bounds")
    if result["target_fps"] != 30 or (result["width"], result["height"]) != (1280, 720):
        raise ValueError("Unexpected renderer configuration")
    if result["finished_at_unix_ms"] <= result["started_at_unix_ms"]:
        raise ValueError("Invalid time range")
    return result


class LabHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No paths, personal assets or client identifiers in a request log.

    def send_data(self, status, data, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        policy = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'"
        self.send_header("Content-Security-Policy", policy)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            return self.send_data(403, b"Loopback host required", "text/plain")
        route = urlsplit(self.path).path
        appearance = self.server.runtime / "appearance"
        speech = self.server.runtime / "speech-v1"
        reference = self.server.runtime / "reference/avatar_a.png"
        source_reference = speech / "source-reference.mp4"
        for version in ("presentation-v3", "presentation-v2"):
            revision = self.server.runtime / version
            required = [revision / directory / name for directory, names in
                        (("appearance", ("authored.mp4", "heldout.mp4", "comparison.mp4")),
                         ("speech", ("selected.mp4", "neural.mp4", "comparison.mp4"))) for name in names]
            required += [revision / "portrait/reference.png", revision / "manifest.json"]
            if all(path.is_file() for path in required):
                appearance, speech = revision / "appearance", revision / "speech"
                reference = revision / "portrait/reference.png"
                break
        start_page = "index.html"
        if (appearance / "authored.mp4").is_file():
            start_page = "appearance.html"
        if (speech / "selected.mp4").is_file():
            start_page = "speech.html"
        paths = {
            "/": (STATIC / start_page, "text/html; charset=utf-8"),
            "/speech": (STATIC / "speech.html", "text/html; charset=utf-8"),
            "/speech.js": (STATIC / "speech.js", "text/javascript; charset=utf-8"),
            "/speech-selected.mp4": (speech / "selected.mp4", "video/mp4"),
            "/speech-neural.mp4": (speech / "neural.mp4", "video/mp4"),
            "/speech-comparison.mp4": (speech / "comparison.mp4", "video/mp4"),
            "/speech-source-reference.mp4": (source_reference, "video/mp4"),
            "/rig": (STATIC / "index.html", "text/html; charset=utf-8"),
            "/appearance": (STATIC / "appearance.html", "text/html; charset=utf-8"),
            "/appearance.css": (STATIC / "appearance.css", "text/css; charset=utf-8"),
            "/appearance-authored.mp4": (appearance / "authored.mp4", "video/mp4"),
            "/appearance-heldout.mp4": (appearance / "heldout.mp4", "video/mp4"),
            "/appearance-comparison.mp4": (appearance / "comparison.mp4", "video/mp4"),
            "/renderer.js": (STATIC / "renderer.js", "text/javascript; charset=utf-8"),
            "/rig.mjs": (STATIC / "rig.mjs", "text/javascript; charset=utf-8"),
            "/rig-schema.json": (STATIC / "rig-schema.json", "application/json"),
            "/style.css": (STATIC / "style.css", "text/css; charset=utf-8"),
            "/reference.png": (reference, "image/png"),
            "/device-benchmark.json": (self.server.runtime / "device-benchmark.json", "application/json"),
            "/renderer-benchmark.json": (self.server.runtime / "renderer-benchmark.json", "application/json"),
        }
        if route == "/health":
            return self.send_data(200, b'{"service":"local-avatar-lab","schema_version":1}', "application/json")
        if route not in paths or not paths[route][0].is_file():
            return self.send_data(404, b"Not found", "text/plain")
        path, content_type = paths[route]
        self.send_data(200, path.read_bytes(), content_type)

    def do_POST(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            return self.send_data(403, b"Loopback host required", "text/plain")
        if self.path not in ("/renderer-benchmark", "/pose"):
            return self.send_data(404, b"Not found", "text/plain")
        # A foreign web page must not be able to write lab artifacts through the browser.
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Origin") != expected_origin or self.headers.get("Content-Type") != "application/json":
            return self.send_data(403, b"Same-origin JSON required", "text/plain")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096:
                raise ValueError("Invalid length")
            validator = validate_pose if self.path == "/pose" else validate_result
            result = validator(json.loads(self.rfile.read(length)))
        except (ValueError, TypeError):
            return self.send_data(400, b"Invalid lab record", "text/plain")
        filename = "avatar-rig-pose-v1.json" if self.path == "/pose" else "renderer-benchmark.json"
        target = self.server.runtime / filename
        self.server.runtime.mkdir(parents=True, exist_ok=True)
        # Atomic replacement avoids serving partial reports while the browser saves.
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as temp:
            json.dump(result, temp, indent=2)
        os.replace(temp.name, target)
        self.send_data(200, b'{"saved":true}', "application/json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--runtime", type=Path, default=Path(".runtime/local-avatar"))
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), LabHandler)
    server.runtime = args.runtime.resolve()
    print(f"Local avatar lab: http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
