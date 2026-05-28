"""Parse report/*-metrics.txt and plot GPU util / FB used / power / temp curves."""

import re
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "report"

SAMPLE_RE = re.compile(r"^--- sample #(\d+) at (\d{2}:\d{2}:\d{2})")
METRIC_RE = re.compile(r"^\s+(DCGM_FI_DEV_\w+)\s+(\S+)")


def parse(path: Path):
    samples: list[dict] = []
    current: dict | None = None
    with path.open() as f:
        for line in f:
            m = SAMPLE_RE.match(line)
            if m:
                if current is not None:
                    samples.append(current)
                current = {"sample": int(m.group(1)), "t": m.group(2)}
                continue
            m = METRIC_RE.match(line)
            if m and current is not None:
                try:
                    current[m.group(1)] = float(m.group(2))
                except ValueError:
                    pass
    if current is not None:
        samples.append(current)
    return samples


def t_seconds(samples: list[dict]) -> list[float]:
    """Convert HH:MM:SS to seconds-from-first-sample."""
    if not samples:
        return []
    h0, m0, s0 = map(int, samples[0]["t"].split(":"))
    base = h0 * 3600 + m0 * 60 + s0
    out = []
    for s in samples:
        hh, mm, ss = map(int, s["t"].split(":"))
        out.append(hh * 3600 + mm * 60 + ss - base)
    return out


def plot_experiment(name: str, path: Path, color: str, out_path: Path):
    samples = parse(path)
    if not samples:
        print(f"{path}: no samples parsed")
        return
    ts = t_seconds(samples)
    util = [s.get("DCGM_FI_DEV_GPU_UTIL", 0) for s in samples]
    fb = [s.get("DCGM_FI_DEV_FB_USED", 0) for s in samples]
    power = [s.get("DCGM_FI_DEV_POWER_USAGE", 0) for s in samples]
    temp = [s.get("DCGM_FI_DEV_GPU_TEMP", 0) for s in samples]
    memcopy = [s.get("DCGM_FI_DEV_MEM_COPY_UTIL", 0) for s in samples]

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"DCGM metrics — {name}", fontsize=14, fontweight="bold")

    ax1.plot(ts, util, color=color, marker="o", label="GPU util")
    ax1.plot(ts, memcopy, color="tab:orange", marker="x", linestyle="--", label="Mem copy util")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Utilization (%)")
    ax1.set_title("GPU utilization")
    ax1.set_ylim(-5, 110)
    ax1.grid(alpha=0.3)
    ax1.legend()

    ax2.plot(ts, fb, color=color, marker="o")
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("FB used (MiB)")
    ax2.set_title("Frame buffer usage")
    ax2.grid(alpha=0.3)

    ax3.plot(ts, power, color=color, marker="o")
    ax3.set_xlabel("Time (s)")
    ax3.set_ylabel("Power (W)")
    ax3.set_title("Power usage (TDP=70W)")
    ax3.axhline(70, color="red", linestyle=":", alpha=0.5, label="TDP")
    ax3.grid(alpha=0.3)
    ax3.legend()

    ax4.plot(ts, temp, color=color, marker="o")
    ax4.set_xlabel("Time (s)")
    ax4.set_ylabel("Temp (°C)")
    ax4.set_title("GPU temperature")
    ax4.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"saved {out_path}")


def plot_comparison(out_path: Path):
    """Side-by-side comparison of avg_step_sec across modes."""
    modes = ["Exclusive", "Time-slicing", "MPS", "DRA"]
    avg_step = [0.120, 0.513, 0.620, 0.120]
    peak_fb = [712, 2842, 2630, 712]
    pods = [1, 4, 4, 1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    colors = ["tab:green", "tab:blue", "tab:red", "tab:purple"]

    bars1 = ax1.bar(modes, avg_step, color=colors)
    ax1.set_ylabel("avg_step_sec (s)")
    ax1.set_title("Per-step latency (lower is better)")
    for bar, val, p in zip(bars1, avg_step, pods):
        ax1.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                 f"{val:.3f}s\n({p} pod)", ha="center", fontsize=9)
    ax1.grid(axis="y", alpha=0.3)

    bars2 = ax2.bar(modes, peak_fb, color=colors)
    ax2.set_ylabel("Peak FB used (MiB)")
    ax2.set_title("Peak frame buffer usage")
    for bar, val in zip(bars2, peak_fb):
        ax2.text(bar.get_x() + bar.get_width() / 2, val + 50,
                 f"{val} MiB", ha="center", fontsize=9)
    ax2.grid(axis="y", alpha=0.3)

    plt.suptitle("GPU sharing modes — summary", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"saved {out_path}")


def main() -> None:
    experiments = [
        ("Exclusive (1 pod, nvidia.com/gpu)", "11-exclusive-metrics.txt", "tab:green"),
        ("Time-slicing (4 pods, nvidia.com/gpu.shared)", "12-timeslicing-metrics.txt", "tab:blue"),
        ("MPS (4 pods, nvidia.com/gpu.shared)", "13-mps-metrics.txt", "tab:red"),
    ]
    for name, fn, color in experiments:
        plot_experiment(name, REPORT / fn, color, REPORT / fn.replace(".txt", ".png"))
    plot_comparison(REPORT / "summary-comparison.png")


if __name__ == "__main__":
    main()
