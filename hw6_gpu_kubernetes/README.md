# hw6: GPU Kubernetes cluster lab

Все артефакты для лабораторной "Развертывание GPU-кластера Kubernetes".

## Структура

```
hw6_gpu_kubernetes/
├── README.md                              — этот файл
├── docs/
│   └── REPORT.md                          — шаблон отчёта на сдачу
├── manifests/
│   └── namespace.yaml                     — gpu-lab namespace
├── gpu-lab/
│   ├── device-plugin-sharing-config.yaml  — ConfigMap (default / time-slicing / MPS)
│   ├── jupyterlab.yaml                    — JupyterLab smoke test (deployment + svc)
│   ├── dcgm-servicemonitor.yaml           — ServiceMonitor для DCGM Exporter
│   ├── torch-benchmark-configmap.yaml     — benchmark.py в ConfigMap
│   ├── torch-benchmark-exclusive.yaml     — Job, nvidia.com/gpu: 1
│   └── torch-benchmark-shared.yaml        — Job, nvidia.com/gpu.shared: 1 (для ts/mps)
└── scripts/
    ├── run-lab.sh                         — runbook со всеми шагами
    ├── ssh-wait.sh                        — wait-loop до появления SSH-доступа
    └── dra-pod.yaml                       — bonus: DRA-вариант benchmark Job
```

## Как пользоваться

1. **Ждать SSH.** Запустить `scripts/ssh-wait.sh`. Когда вернётся `READY`, можно копировать на VM.
2. **Скопировать каталог на VM.**
   ```bash
   scp -r hw6_gpu_kubernetes khra-oksana@111.88.152.253:/home/khra-oksana/k8s-gpu-lab
   ```
3. **Зайти на VM и запускать шаги по очереди.**
   ```bash
   ssh khra-oksana@111.88.152.253
   cd /home/khra-oksana/k8s-gpu-lab

   # Прогон по шагам:
   ./scripts/run-lab.sh inventory
   ./scripts/run-lab.sh cleanup       # только если VM грязная — после reboot
   ./scripts/run-lab.sh prep          # потом reboot
   ./scripts/run-lab.sh containerd
   ./scripts/run-lab.sh k8s
   ./scripts/run-lab.sh init
   ./scripts/run-lab.sh helm
   ./scripts/run-lab.sh gpu           # GPU Operator — до 10 минут
   ./scripts/run-lab.sh ns
   ./scripts/run-lab.sh jupyter
   ./scripts/run-lab.sh monitoring
   ./scripts/run-lab.sh exclusive
   ./scripts/run-lab.sh timeslicing
   ./scripts/run-lab.sh mps           # экспериментально
   ./scripts/run-lab.sh final
   ```
4. **Port-forward для UI.**
   ```bash
   # на VM:
   kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
   kubectl port-forward -n gpu-lab svc/jupyterlab 8888:8888
   # на ноутбуке:
   ssh -L 3000:localhost:3000 -L 8888:localhost:8888 khra-oksana@111.88.152.253
   ```
   Grafana: `http://localhost:3000` (admin / см. `report/10-grafana-password.txt`).
   JupyterLab: `http://localhost:8888/lab?token=gpu-lab-token`.
5. **Скриншоты Grafana** (dashboard 12239 или Explore с DCGM_FI_*) приложить к отчёту.
6. **Заполнить `docs/REPORT.md`** значениями из `report/*.txt`.

## Что собирается в `report/` на VM

Скрипт собирает:

- inventory VM, версии k8s/helm,
- `kubectl get nodes -o wide`, `kubectl get pods -A`,
- `nvidia-smi` из driver daemonset и из jupyter pod,
- node capacity для каждого режима,
- логи всех Job'ов exclusive / ts-1..4 / mps-1..4 → JSON-результаты бенчмарка,
- финальный snapshot кластера.
