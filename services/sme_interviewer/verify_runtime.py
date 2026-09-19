"""Native cancellation and network-policy smoke checks after provisioning."""

import asyncio
import json
import subprocess
import sys
import time

from .catalog import PROMPTS, VOICES
from .speech import ROOT, SpeechWorker


async def run():
    runtime = ROOT / ".runtime"
    probe = """import socket
for host,port in [('1.1.1.1',443),('127.0.0.1',11434)]:
 try: socket.create_connection((host,port),timeout=2)
 except PermissionError: pass
 else: raise SystemExit('Network was not denied')
print('external and loopback sockets denied')
"""
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(ROOT / "offline.sb"), sys.executable, "-c", probe], check=True, text=True, capture_output=True
    )
    rows = []
    for candidate, config in VOICES.items():
        worker = SpeechWorker(config["engine"], runtime)
        output = runtime / "cancel-probe.wav"
        try:
            await worker.start()
            process = worker.process
            task = asyncio.create_task(worker.synthesize(candidate, (PROMPTS[0]["text"] + " ") * 4, output))
            await asyncio.sleep(0.05)
            start = time.perf_counter()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            elapsed = (time.perf_counter() - start) * 1000
            assert process.returncode is not None and not output.exists()
            rows.append(
                {
                    "candidate": candidate,
                    "cancel_to_process_exit_ms": elapsed,
                    "exit_code": process.returncode,
                    "late_audio_file": output.exists(),
                }
            )
            print(candidate, rows[-1], flush=True)
        finally:
            await worker.close()
    report = {
        "network_policy": result.stdout.strip(),
        "cancellation": rows,
        "limits": "One warm-worker cancellation per candidate; software timing only, not acoustic barge-in latency.",
    }
    (runtime / "audition/runtime-checks.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(run())
