#!/bin/bash
#SBATCH --job-name=torch-bench
#SBATCH --partition=gpu
#SBATCH --gres=gpu:tesla_t4:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=/home/khra-oksana/slurm-test/job-%j.out

set -e
echo "=== Slurm job $SLURM_JOB_ID on $(hostname) ==="
echo "GPU GRES: $SLURM_JOB_GPUS / CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "Start: $(date)"
echo

# Driver is in /run/nvidia/driver (NVIDIA GPU Operator container path);
# we expose libnvidia-ml.so via LD_LIBRARY_PATH for host-side nvidia-smi.
export LD_LIBRARY_PATH=/run/nvidia/driver/usr/lib/x86_64-linux-gnu
echo "--- nvidia-smi (host) ---"
/run/nvidia/driver/usr/bin/nvidia-smi
echo

# Run the actual PyTorch workload inside a containerd-managed container
# with NVIDIA toolkit injection so libnvidia-ml + /dev/nvidia* are visible.
echo "--- PyTorch matmul via containerd ---"
sudo ctr -n k8s.io run --rm --gpus 0 \
  --mount type=bind,src=/home/khra-oksana/slurm-test,dst=/scripts,options=rbind:ro \
  docker.io/pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime \
  bench-$SLURM_JOB_ID \
  python /scripts/benchmark.py
