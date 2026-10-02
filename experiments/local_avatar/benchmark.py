"""Synthetic device probe. No personal data, pretrained weights or avatar quality claims."""

import argparse
import copy
import json
import math
import os
import platform
import resource
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F


class MotionProbe(nn.Module):
    """Causal convolution and recurrent state, with arbitrary probe outputs."""

    def __init__(self):
        super().__init__()
        self.conv = nn.Conv1d(80, 128, 5)
        self.recurrent = nn.GRU(128, 256, num_layers=2, batch_first=True)
        self.output = nn.Linear(256, 12)

    def forward(self, features, state=None):
        encoded = F.gelu(self.conv(F.pad(features.transpose(1, 2), (4, 0)))).transpose(1, 2)
        sequence, state = self.recurrent(encoded, state)
        return torch.sigmoid(self.output(sequence)), state


def summary(values):
    ordered = sorted(values)
    if not ordered or not all(math.isfinite(v) and v >= 0 for v in ordered):
        raise ValueError("Need finite, nonnegative timing samples")
    return {
        "samples": len(ordered), "p50_ms": statistics.median(ordered),
        "p95_ms": ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)], "max_ms": ordered[-1],
    }


def memory(device):
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    out = {"process_peak_rss_bytes": peak if platform.system() == "Darwin" else peak * 1024}
    if device == "mps":
        out.update(mps_tensor_bytes=torch.mps.current_allocated_memory(), mps_driver_bytes=torch.mps.driver_allocated_memory())
    return out


def system_snapshot():
    """Aggregate observations only: no process arguments, users or source content."""
    result = {"load_average": list(os.getloadavg())}
    if platform.system() == "Darwin":
        vm = subprocess.run(["/usr/bin/vm_stat"], capture_output=True, text=True, check=True).stdout
        import re
        size = int(re.search(r"page size of (\d+) bytes", vm).group(1))
        pages = {k.strip(): int(v.strip().rstrip(".")) for k, v in (line.split(":", 1) for line in vm.splitlines()[1:] if ":" in line)}
        keys = ("Pages free", "Pages active", "Pages wired down", "Pages occupied by compressor")
        result["vm_bytes"] = {k: pages.get(k, 0) * size for k in keys}
    return result


def probe(device, iterations, train_steps, contention=False):
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable; run on the Mac outside the tool sandbox. No silent CPU fallback.")
    torch.manual_seed(20261002)
    prototype = MotionProbe()
    state_dict = copy.deepcopy(prototype.state_dict())
    model = MotionProbe()
    model.load_state_dict(state_dict)
    before = memory(device)
    transfer_start = time.perf_counter()
    model.to(device)
    train_x = torch.randn(8, 32, 80).to(device)
    # This algebraic target verifies optimization, not speech or facial realism.
    target = torch.sigmoid(train_x[:, :, :12] * 0.5)
    infer_x = train_x[:1, :16].contiguous()
    rival = torch.randn(512, 512, device=device) if contention else None

    def sync():
        if device == "mps":
            torch.mps.synchronize()

    sync()
    transfer_ms = (time.perf_counter() - transfer_start) * 1000

    def infer():
        with torch.inference_mode():
            model(infer_x)
            if rival is not None:
                # Sequential queued compute proxy; does not simulate Higgs or Tibi.
                torch.mm(rival, rival)

    start = time.perf_counter()
    infer()
    sync()
    cold_ms = (time.perf_counter() - start) * 1000
    for _ in range(10):
        infer()
    sync()
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        infer()
        sync()
        times.append((time.perf_counter() - start) * 1000)

    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
    training_ms, losses = [], []
    initial_weight = model.output.weight.detach().clone()
    gradient_finite = True
    for _ in range(train_steps):
        start = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        predicted, _ = model(train_x)
        loss = F.mse_loss(predicted, target)
        loss.backward()
        gradient_finite &= all(p.grad is None or torch.isfinite(p.grad).all().item() for p in model.parameters())
        optimizer.step()
        sync()
        training_ms.append((time.perf_counter() - start) * 1000)
        losses.append(loss.item())
    changed = not torch.equal(initial_weight, model.output.weight.detach())
    assert gradient_finite and changed and all(math.isfinite(v) for v in losses)
    return {
        "device": device, "scenario": "queued_matrix_compute_proxy" if contention else "avatar_probe_only_ambient_machine_load",
        "parameters": sum(p.numel() for p in model.parameters()), "dtype": "float32", "cpu_threads": torch.get_num_threads(),
        "inference_shape": [1, 16, 80], "training_shape": [8, 32, 80],
        "allocation_transfer_ms": transfer_ms, "first_inference_ms": cold_ms, "warm_inference": summary(times),
        "training_step": summary(training_ms), "first_training_step_ms": training_ms[0],
        "initial_synthetic_loss": losses[0], "final_synthetic_loss": losses[-1],
        "finite_gradients": gradient_finite, "parameters_updated": changed,
        "before": before, "after": memory(device),
        "limits": ("Synchronized complete 16-frame input block; no feature extraction, playback, transport or renderer. "
                   "Synthetic fitting is not an avatar quality evaluation."),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", default="cpu,mps")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--train-steps", type=int, default=20)
    parser.add_argument("--contention-proxy", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(".runtime/local-avatar/device-benchmark.json"))
    args = parser.parse_args()
    if not 5 <= args.iterations <= 10000 or not 2 <= args.train_steps <= 1000:
        parser.error("iterations must be 5..10000 and train-steps 2..1000")
    if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
        parser.error("Disable PYTORCH_ENABLE_MPS_FALLBACK to verify native MPS operations")
    devices = args.devices.split(",")
    if any(d not in ("cpu", "mps") for d in devices):
        parser.error("Only CPU and MPS probes are supported")
    torch.set_num_threads(4)
    started = time.perf_counter()
    report = {
        "schema_version": 1, "recorded_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "torch": torch.__version__, "numpy": __import__("numpy").__version__,
        "seed": 20261002, "mps_built": torch.backends.mps.is_built(), "mps_available": torch.backends.mps.is_available(),
        "weights": "random_initialization_no_pretrained_model", "data": "synthetic_random_tensors_only",
        "baseline_system": system_snapshot(), "results": [],
    }
    for device in devices:
        result = probe(device, args.iterations, args.train_steps, args.contention_proxy)
        report["results"].append(result)
        fields = ("device", "parameters", "warm_inference", "training_step")
        print(json.dumps({k: result[k] for k in fields}), flush=True)
    report["after_system"] = system_snapshot()
    report["elapsed_seconds_excluding_import"] = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
