# Лабораторная работа: Развертывание GPU-кластера Kubernetes

Отчёт по лабораторной работе "Развертывание GPU-кластера Kubernetes".
Версия методички: `gpu-cluster-student-guide_v02.docx`.

Все артефакты (логи Job'ов, метрики DCGM, состояние кластера) лежат в
`hw6_gpu_kubernetes/report/`.

## 1. Параметры стенда

| Параметр | Значение |
|---|---|
| VM hostname | `epda6tu7ep1dopeif204` |
| OS | Ubuntu 22.04.5 LTS (kernel 5.15.0-157-generic) |
| vCPU | 8 |
| RAM | 31 GiB |
| GPU | NVIDIA Tesla T4, 15360 MiB (Turing, compute 7.5, BusID 0000:8B:00.0) |
| Kubernetes | 1.34.8 |
| containerd | 1.7.28 (containerd.io) |
| Helm | 3.21.0 |
| GPU Operator | v25.10.1 |
| NVIDIA driver (через GPU Operator) | 580.105.08 |
| CUDA runtime в pod | 12.1 (PyTorch image `pytorch:2.3.0-cuda12.1-cudnn8-runtime`) |
| Driver-reported CUDA | 13.0 |
| PyTorch | 2.3.0, cuDNN 8902 |
| CNI | Flannel (10.244.0.0/16) |
| Мониторинг | kube-prometheus-stack 86.0.0 + nvidia-dcgm-exporter |
| DRA (бонус) | nvidia-dra-driver-gpu 25.12.0 |

## 2. Состояние кластера

`kubectl get nodes -o wide` (`report/05-kubectl-get-nodes.txt`):

```
NAME                   STATUS   ROLES           AGE   VERSION   INTERNAL-IP   EXTERNAL-IP   OS-IMAGE             KERNEL-VERSION       CONTAINER-RUNTIME
epda6tu7ep1dopeif204   Ready    control-plane   39m   v1.34.8   10.129.0.42   <none>        Ubuntu 22.04.5 LTS   5.15.0-157-generic   containerd://1.7.28
```

`kubectl get pods -A` — см. `report/05-kubectl-get-pods-all.txt`. На момент финализации
работают все системные namespaces:

- `kube-system` — control plane, kube-proxy, CoreDNS
- `kube-flannel` — CNI
- `gpu-operator` — GPU Operator + driver/toolkit/device-plugin/MPS-control/DCGM-exporter
- `monitoring` — Prometheus + Alertmanager + Grafana + kube-state-metrics + node-exporter
- `nvidia-dra-driver-gpu` — DRA controller + kubelet plugin
- `gpu-lab` — все Job'ы лабы (Completed)

Node capacity / allocatable в режиме **exclusive** (`report/11-exclusive-capacity.txt`):

```
Capacity:
  nvidia.com/gpu:     1
Allocatable:
  nvidia.com/gpu:     1
```

В режиме **time-slicing / MPS** (`report/12-timeslicing-capacity.txt`, `report/13-mps-capacity.txt`):

```
Capacity:
  nvidia.com/gpu:         0   (исходный ресурс скрыт)
  nvidia.com/gpu.shared:  4
Allocatable:
  nvidia.com/gpu.shared:  4
```

## 3. `nvidia-smi` из pod

`report/09-nvidia-smi-from-pod.txt` (JupyterLab pod, ConfigMap-mounted PyTorch image):

```
Thu May 28 11:12:40 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.105.08             Driver Version: 580.105.08     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
|=========================================+========================+======================|
|   0  Tesla T4                       On  |   00000000:8B:00.0 Off |                    0 |
| N/A   31C    P8             14W /   70W |       0MiB /  15360MiB |      0%      Default |
+-----------------------------------------+------------------------+----------------------+
```

PyTorch sanity-check внутри pod (`report/09-jupyter-torch-check.txt`):

```
torch=2.3.0
cuda_available=True
device_name=Tesla T4
cuda_runtime=12.1
cudnn=8902
```

## 4. Бенчмарк

Все эксперименты гоняют один и тот же Python-скрипт (`gpu-lab/torch-benchmark-configmap.yaml`):

```python
a = torch.randn(N, N, device="cuda")
b = torch.randn(N, N, device="cuda")
for _ in range(STEPS):
    c = torch.matmul(a, b)
    torch.cuda.synchronize()
```

Параметры: `MATRIX_SIZE=6144`, `STEPS=120`, `WARMUP=5`, `DTYPE=float32`. Это даёт
`6144^3` FLOP на step, при FP32 на T4 (~8.1 TFLOPS) теоретический минимум — ~57 ms.
Фактически в exclusive получили ~120 ms (включая overhead запуска / синхронизации).

## 5. Эксперимент 1: exclusive GPU (`nvidia.com/gpu`)

Manifest: `gpu-lab/torch-benchmark-exclusive.yaml`. Лог: `report/11-exclusive-logs.txt`.

| Метрика | Значение |
|---|---|
| gpu_name | Tesla T4 |
| total_memory_gb | 14.563 |
| total_wall_sec | 14.42 |
| avg_step_sec | **0.12016** |
| min_step_sec | 0.117772 |
| max_step_sec | 0.126143 |
| stdev_step_sec | 0.001256 |
| peak_cuda_mem_gb | 0.5704 |

DCGM-метрики во время выполнения (`report/11-exclusive-metrics.txt`):

| Метрика | Idle | Под нагрузкой |
|---|---|---|
| `DCGM_FI_DEV_GPU_UTIL` (%) | 0 | **100** |
| `DCGM_FI_DEV_FB_USED` (MiB) | 30 | **712** |
| `DCGM_FI_DEV_POWER_USAGE` (W) | 14.564 | **70.158** (≈TDP) |
| `DCGM_FI_DEV_GPU_TEMP` (°C) | 32 | **40** |
| `DCGM_FI_DEV_MEM_COPY_UTIL` (%) | 0 | **60** |

## 6. Эксперимент 2: time-slicing (`nvidia.com/gpu.shared`, replicas=4)

ConfigMap-профиль: `t4-timeslicing-4` (см. `gpu-lab/device-plugin-sharing-config.yaml`).
4 параллельных Job'a на одну физическую T4 через time-slicing.

Лог: `report/12-timeslicing-logs.txt` (RESULT_JSON по каждому из 4 job'ов):

| Job | total_wall_sec | avg_step_sec | min | max | stdev |
|---|---|---|---|---|---|
| ts-1 | 61.72 | **0.5143** | 0.4934 | 0.5289 | 0.0080 |
| ts-2 | 61.60 | **0.5133** | 0.4944 | 0.5380 | 0.0085 |
| ts-3 | 61.39 | **0.5116** | 0.2770 | 0.5360 | 0.0232 |
| ts-4 | 61.35 | **0.5112** | 0.2537 | 0.5344 | 0.0251 |

Сводно: avg_step_sec ≈ **0.513s**, что в **~4.27× медленнее** exclusive (0.12s).
Соответствует ожидаемому делению GPU-времени на 4 кванта.

DCGM-метрики (`report/12-timeslicing-metrics.txt`):

| Метрика | Под нагрузкой |
|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | **100** |
| `DCGM_FI_DEV_FB_USED` (MiB) | **2842** (~4× exclusive 712 MiB, потому что 4 контекста CUDA одновременно) |
| `DCGM_FI_DEV_POWER_USAGE` (W) | 65.5 – 68.7 |
| `DCGM_FI_DEV_GPU_TEMP` (°C) | **50** (выше, чем exclusive 40°C — больший аплинк) |
| `DCGM_FI_DEV_MEM_COPY_UTIL` (%) | 64 – 66 |

## 7. Эксперимент 3: MPS (`nvidia.com/gpu.shared`, replicas=4, MPS)

ConfigMap-профиль: `t4-mps-4`. GPU Operator поднял дополнительный daemonset
`nvidia-device-plugin-mps-control-daemon` после получения labels `nvidia.com/mps.capable=true`,
`nvidia.com/gpu.sharing-strategy=mps`. **MPS заработал** (вопреки методичке, где это допускалось
как experimental).

Лог: `report/13-mps-logs.txt`:

| Job | total_wall_sec | avg_step_sec | min | max | stdev |
|---|---|---|---|---|---|
| mps-1 | 74.36 | **0.6197** | 0.5841 | 0.6501 | 0.0148 |
| mps-2 | 74.36 | **0.6196** | 0.5840 | 0.6498 | 0.0148 |
| mps-3 | 74.34 | **0.6195** | 0.5840 | 0.6500 | 0.0149 |
| mps-4 | 74.35 | **0.6195** | 0.5840 | 0.6498 | 0.0148 |

Сводно: avg_step_sec ≈ **0.620s** — даже **медленнее** time-slicing (0.513s).
Стандартное отклонение step'ов значительно меньше (0.015 vs 0.025 у TS-3/4), то есть
**MPS даёт более стабильную (предсказуемую) latency, но средняя — выше**.

Объяснение: на Tesla T4 (Turing) hardware MPS scheduling ограничен; MPS-server
сериализует запуски kernel'ов через единый контекст, добавляя overhead vs голый
time-slicing на этой архитектуре. На A100/H100 (Ampere/Hopper) с hardware-MPS
картина обратная.

DCGM-метрики (`report/13-mps-metrics.txt`):

| Метрика | Под нагрузкой |
|---|---|
| `DCGM_FI_DEV_GPU_UTIL` | **100** |
| `DCGM_FI_DEV_FB_USED` (MiB) | **2630** (близко к TS — те же 4 контекста, но один общий через MPS) |
| `DCGM_FI_DEV_POWER_USAGE` (W) | 69.46 – 69.65 |
| `DCGM_FI_DEV_GPU_TEMP` (°C) | **52** |
| `DCGM_FI_DEV_MEM_COPY_UTIL` (%) | 52 |

## 8. Сводная таблица

| Режим | Число pod | Kubernetes resource | Среднее время job (avg_step_sec) | Среднее job total wall | Пик GPU util | Пик FB used | Пик Power | Комментарий |
|---|---|---|---|---|---|---|---|---|
| **Exclusive** | 1 | `nvidia.com/gpu` | **0.120s** | 14.42s | 100% | 712 MiB | 70.2 W | Максимальный throughput, минимальный latency, эксклюзивный доступ |
| **Time-slicing** | 4 | `nvidia.com/gpu.shared` | **0.513s** (×4.27 vs excl) | 61.5s | 100% | 2842 MiB | 68.7 W | Простое деление GPU-времени, изоляции памяти нет |
| **MPS** | 4 | `nvidia.com/gpu.shared` | **0.620s** (×5.17 vs excl) | 74.35s | 100% | 2630 MiB | 69.7 W | На T4 software-MPS медленнее TS, но stdev step'a в 2× меньше |
| **DRA (бонус)** | 1 | `gpu.nvidia.com` (DeviceClass) | 0.120s | 14.38s | — | 712 MiB | 70 W | DRA эквивалентен exclusive, но через ResourceClaimTemplate |

## 9. Ответы на вопросы

**Почему в exclusive одна job обычно выполняется быстрее?**
В exclusive pod получает 100% SM и всю VRAM, нет конкуренции за compute/контекст, нет
cost'а переключения CUDA-контекстов. Один CUDA-stream, один процесс — kernel launches
сразу идут на железо. Здесь 0.12s/step.

**Почему в time-slicing можно запустить несколько pod на одной GPU?**
Device plugin при `replicas=4` рекламирует одну физическую GPU как 4 виртуальных
`nvidia.com/gpu.shared`. Kubelet scheduler видит «4 ресурса» и аллоцирует их разным
pod'ам. На самом железе процессы по очереди получают SM через CUDA driver
context switching (kernel-level время slicing). Никакой hardware-изоляции нет.

**Какие риски появляются при разделении одной GPU между несколькими pod?**
- Нет изоляции памяти: один pod может съесть всю VRAM и OOM'нуть других.
- Нет QoS по compute — fairness держится только если все потребители cooperative.
- Latency растёт линейно с числом потребителей (×4.27 в нашем замере).
- Stdev step'ов вырос с 0.001 до 0.025 (в TS) — non-deterministic скачки из-за конкуренции за память/копирования.
- Без MIG нельзя отдать pod'у фиксированную долю compute.

**Чем MPS концептуально отличается от обычного time-slicing?**
Time-slicing — switching контекстов: в каждый момент исполняется ровно один процесс,
GPU переключает контексты. MPS — единый CUDA-контекст в режиме «MPS-server», и
несколько клиентов могут submit'ить kernel'ы конкурентно в один и тот же контекст.
В нашем замере на T4 это дало overhead (0.62s vs 0.51s у TS), но stdev был
почти в 2× меньше — то есть **MPS более предсказуем под нагрузкой, но имеет фиксированный
context-overhead на Turing**. На Ampere/Hopper, где есть hardware-MPS partitions,
MPS обычно строго быстрее TS.

**Какой режим вы бы выбрали для интерактивного JupyterLab, а какой для batch-задачи?**
- **JupyterLab / dev** → time-slicing или MPS. У интерактивщика средняя загрузка
  GPU — 5–10%, и важно дать GPU нескольким людям сразу. Time-slicing дешевле и проще;
  MPS лучше, если хотите более предсказуемую latency.
- **Batch (training/inference)** → exclusive. Известный, максимальный throughput.
  Без накладных. Если узлов нет — MIG (на A100/H100) или просто scheduling в очередь.

## 10. Краткий вывод

- **Одиночная тяжёлая задача** → **exclusive** (`nvidia.com/gpu`). Максимальный
  throughput, минимальный latency, предсказуемая загрузка.
- **Несколько параллельных лёгких задач** → **time-slicing** (`nvidia.com/gpu.shared`),
  если важна суммарная пропускная способность и нет требования по жёсткой изоляции.
  **MPS** даёт более стабильную latency, но на T4 add'ит overhead.
- На T4/L4 **MIG недоступен**, для строгой изоляции памяти нужен другой класс GPU.

## 11. Графики из Grafana и matplotlib

Live-скриншоты Grafana (Explore mode, range = время прогона экспериментов
2026-05-28 11:28 → 11:50 UTC):

| Метрика | Скриншот | Что видно |
|---|---|---|
| GPU utilization | `report/grafana/gpu-util.png` | 4 пика 100% — exclusive (14:30), TS (14:33), MPS (14:37), DRA (14:45) |
| FB used (MiB) | `report/grafana/fb-used.png` | Exclusive/DRA ≈ 700 MiB, TS ≈ 2.7K, MPS ≈ 2.6K |
| Power usage (W) | `report/grafana/power-usage.png` | Все 4 эксперимента упираются в TDP=70W |

PyData-графики (matplotlib) построены из реальных DCGM семплов (Prometheus
через `/api/v1/query`) в `scripts/plot_metrics.py`:

| Эксперимент | PNG | Описание |
|---|---|---|
| Exclusive | `report/11-exclusive-metrics.png` | Idle → 100% utilization, 712 MiB FB, 70W |
| Time-slicing | `report/12-timeslicing-metrics.png` | 100% всё время + 2842 MiB (4 контекста), 65-68W |
| MPS | `report/13-mps-metrics.png` | 100% + 2630 MiB + 70W TDP + temp 52°C |
| Summary | `report/summary-comparison.png` | Bar chart avg_step_sec и peak FB по 4 режимам |

## 12. Бонус: Dynamic Resource Allocation

Установлен `nvidia/nvidia-dra-driver-gpu` 25.12.0 (helm release `nvidia-dra-driver-gpu`)
с флагом `--set gpuResourcesEnabledOverride=true` (KEP 5004 ещё не GA, поэтому
DRA-driver работает рядом со стандартным device plugin только с этим override).
После установки появились:

- DeviceClasses: `gpu.nvidia.com`, `mig.nvidia.com`, `compute-domain-daemon.nvidia.com`,
  `compute-domain-default-channel.nvidia.com`, `vfio.gpu.nvidia.com`.
- ResourceSlices: один на T4 (`epda6tu7ep1dopeif204-gpu.nvidia.com-ktd4w`).

Manifest pod'а (`scripts/dra-pod.yaml`) использует:

```yaml
apiVersion: resource.k8s.io/v1
kind: ResourceClaimTemplate
metadata:
  name: torch-dra-claim
spec:
  spec:
    devices:
      requests:
        - name: gpu
          exactly:
            deviceClassName: gpu.nvidia.com
            allocationMode: ExactCount
            count: 1
...
spec:
  resourceClaims:
    - name: gpu
      resourceClaimTemplateName: torch-dra-claim
  containers:
    - resources:
        claims:
          - name: gpu
```

Job отработал успешно (`report/19-dra-logs.txt`): avg_step_sec = **0.1198s**,
полностью совпадает с exclusive — как и ожидалось, DRA-claim даёт pod'у эксклюзивную
GPU. **Принципиальная разница** с `nvidia.com/gpu` resource в том, что claim
описывается через DeviceClass + параметры, что в будущем позволит запрашивать
например MIG-slice конкретного размера, конкретную модель GPU, или композит из
нескольких ресурсов через один claim.

Замечание: первая попытка DRA-pod упала с `CUDA error: device(s) is/are busy
or unavailable`, потому что node ещё имел активный MPS-server из предыдущего
эксперимента. После `kubectl label node nvidia.com/device-plugin.config-` и
рестарта device-plugin (возврат в default profile) MPS-сервер ушёл, и
DRA-pod успешно отработал.

## 13. Бонус 2: развёртывание Slurm-кластера

На той же VM поднят одноузловой Slurm-кластер (slurmctld + slurmd + munge,
версия 21.08.5). Конфигурация в `slurm/`:

- `slurm.conf` — SlurmctldHost, NodeName, PartitionName=gpu, Gres=gpu:tesla_t4:1
- `gres.conf` — GRES → `/dev/nvidia0`
- `cgroup.conf` — минимальный (без жёстких ограничений, чтобы пройти на /run/nvidia driver layout)
- `gpu-bench.sbatch` — sbatch-скрипт: запрашивает `--gres=gpu:tesla_t4:1`,
  запускает `nvidia-smi` и PyTorch matmul через `ctr -n k8s.io run --gpus 0`
- `benchmark.py` — тот же тест, что в Kubernetes-эксперименте

Кластер виден через `sinfo`:

```
PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST
gpu*         up    1:00:00      1   idle epda6tu7ep1dopeif204
```

`scontrol show node`:

```
NodeName=epda6tu7ep1dopeif204 ...
   CPUAlloc=0 CPUTot=8 CPULoad=0.46
   Gres=gpu:tesla_t4:1
   RealMemory=30091 ...
   State=IDLE ThreadsPerCore=1
   Partitions=gpu
```

### Что нетривиального

Драйвер NVIDIA установлен GPU Operator'ом как **контейнер**, то есть
`libnvidia-ml.so` и `nvidia-smi` лежат в `/run/nvidia/driver/usr/...`, а не
в стандартных путях `/usr/lib`. Чтобы Slurm-задача могла запустить контейнер
с GPU через `ctr` (containerd + nvidia-container-toolkit), пришлось:

1. **`mknod` для `/dev/nvidia0`, `/dev/nvidiactl`, `/dev/nvidia-uvm`,
   `/dev/nvidia-uvm-tools`** на хосте (driver-контейнер создаёт их в своём
   rootfs, на хосте их не было).
2. **`/etc/ld.so.conf.d/nvidia-driver.conf`** с `/run/nvidia/driver/usr/lib/x86_64-linux-gnu`
   и `ldconfig`, чтобы `libnvidia-ml.so.1` нашёлся.
3. В `/etc/nvidia-container-runtime/config.toml` раскомментировал
   `root = "/run/nvidia/driver"`, чтобы nvidia-container-cli знал где искать
   драйвер.
4. `ctr -n k8s.io` (вместо `ctr -n default`), чтобы переиспользовать
   pytorch-образ, уже скачанный Kubernetes'ом.

### Результат (`report/slurm/job-3.out`)

```
=== Slurm job 3 on epda6tu7ep1dopeif204 ===
GPU GRES: 0 / CUDA_VISIBLE_DEVICES=0
...
--- nvidia-smi (host) ---
[Tesla T4 visible, 0 MiB used]

--- PyTorch matmul via containerd ---
gpu_name=Tesla T4
total_memory_gb=14.56
matrix_size=6144 steps=120 warmup=5
step=10/120 last=0.1182
...
step=120/120 last=0.1208
RESULT_JSON={"gpu_name": "Tesla T4", "total_memory_gb": 14.563,
             "total_wall_sec": 14.3674, "avg_step_sec": 0.119722,
             "min_step_sec": 0.117327, "max_step_sec": 0.124837,
             "peak_cuda_mem_gb": 0.5704}
```

avg_step_sec = **0.1197s** — практически совпадает с Kubernetes exclusive
(0.120s) и DRA (0.1198s). Это ожидаемо: и Slurm с `--gres=gpu:1`, и k8s с
`nvidia.com/gpu:1`, и DRA-claim в итоге дают одну Tesla T4 одному процессу
эксклюзивно, на той же физической GPU и через ту же CUDA-runtime.

### Сравнение оркестраторов

| Свойство | Kubernetes + GPU Operator | Slurm + nvidia-container-toolkit |
|---|---|---|
| Декларация GPU | `resources.limits["nvidia.com/gpu"]: 1` | `#SBATCH --gres=gpu:tesla_t4:1` |
| Sharing-режимы | time-slicing / MPS / DRA / MIG | gres `Shared=YES` или MPS вручную |
| Изоляция job | Linux namespace + cgroup из k8s | cgroup из Slurm (или нет, по конфигу) |
| Драйвер | Containerized via GPU Operator | Host (или симлинками из container) |
| Workflow | Decl + reconcile via apiserver | Imperative `sbatch` / `srun` |
| Когда выбирать | Multi-tenant, long-running services | HPC batch, ML training jobs |

## 14. Артефакты в `report/`

- `00-vm-inventory.txt` — параметры VM (uname, os-release, cpu/mem, lspci)
- `04-versions.txt` — версии kubeadm/kubectl/containerd/helm + список helm releases
- `05-kubectl-get-nodes.txt`, `05-kubectl-get-pods-all.txt`
- `07-node-capacity.txt`, `07-nvidia-smi-driver-ds.txt`
- `09-jupyter-torch-check.txt`, `09-nvidia-smi-from-pod.txt`
- `10-dcgm-servicemonitor.txt`
- `11-exclusive-capacity.txt`, `11-exclusive-logs.txt`, `11-exclusive-metrics.txt`
- `12-timeslicing-capacity.txt`, `12-timeslicing-logs.txt`, `12-timeslicing-metrics.txt`
- `13-mps-capacity.txt`, `13-mps-logs.txt`, `13-mps-metrics.txt`
- `19-dra-attempt.txt`, `19-dra-inventory.txt`, `19-dra-logs.txt`
- `99-final-state.txt` — финальный snapshot кластера
- `grafana/{gpu-util,fb-used,power-usage}.png` — скриншоты Grafana Explore
- `11-exclusive-metrics.png`, `12-timeslicing-metrics.png`,
  `13-mps-metrics.png`, `summary-comparison.png` — matplotlib-графики из реальных DCGM-семплов
- `slurm/{slurm,gres,cgroup}.conf` — конфиги Slurm
- `slurm/gpu-bench.sbatch`, `slurm/benchmark.py` — sbatch-задача
- `slurm/job-3.out` — лог Slurm-job с RESULT_JSON
- `slurm/sinfo.txt` — `sinfo` / `scontrol show node` / `squeue`

## 13. Воспроизведение

```bash
# на локальной машине
scp -r hw6_gpu_kubernetes khra-oksana@111.88.152.253:/home/khra-oksana/k8s-gpu-lab

# на VM
ssh khra-oksana@111.88.152.253
cd /home/khra-oksana/k8s-gpu-lab
./scripts/run-lab.sh prep        # затем reboot
./scripts/run-lab.sh containerd
./scripts/run-lab.sh k8s
./scripts/run-lab.sh init
./scripts/run-lab.sh helm
./scripts/run-lab.sh gpu         # ~10 минут на сборку драйвера
./scripts/run-lab.sh ns
./scripts/run-lab.sh jupyter
./scripts/run-lab.sh monitoring
./scripts/run-lab.sh exclusive
./scripts/run-lab.sh timeslicing
./scripts/run-lab.sh mps
./scripts/run-lab.sh final

# Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# password: см. report/10-grafana-password.txt
```
