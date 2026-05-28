"""Slurm-side benchmark: same matmul workload as the Kubernetes Job."""

import json
import os
import statistics
import time

import torch


def main() -> None:
    matrix_size = int(os.environ.get("MATRIX_SIZE", "6144"))
    steps = int(os.environ.get("STEPS", "120"))
    warmup = int(os.environ.get("WARMUP", "5"))

    assert torch.cuda.is_available()
    device = torch.device("cuda:0")
    name = torch.cuda.get_device_name(0)
    total = torch.cuda.get_device_properties(0).total_memory / 1024**3

    print(f"gpu_name={name}")
    print(f"total_memory_gb={total:.2f}")
    print(f"matrix_size={matrix_size} steps={steps} warmup={warmup}")

    a = torch.randn(matrix_size, matrix_size, device=device)
    b = torch.randn(matrix_size, matrix_size, device=device)
    for _ in range(warmup):
        c = torch.matmul(a, b)
    torch.cuda.synchronize()
    torch.cuda.reset_peak_memory_stats(device)

    durations: list[float] = []
    t0 = time.time()
    for step in range(steps):
        s = time.time()
        c = torch.matmul(a, b)
        torch.cuda.synchronize()
        durations.append(time.time() - s)
        if (step + 1) % 10 == 0:
            print(f"step={step + 1}/{steps} last={durations[-1]:.4f}")
    wall = time.time() - t0
    peak = torch.cuda.max_memory_allocated(device) / 1024**3

    summary = {
        "gpu_name": name,
        "total_memory_gb": round(total, 3),
        "total_wall_sec": round(wall, 4),
        "avg_step_sec": round(statistics.mean(durations), 6),
        "min_step_sec": round(min(durations), 6),
        "max_step_sec": round(max(durations), 6),
        "peak_cuda_mem_gb": round(peak, 4),
    }
    print("RESULT_JSON=" + json.dumps(summary))


if __name__ == "__main__":
    main()
