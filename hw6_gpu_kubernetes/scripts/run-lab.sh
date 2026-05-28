#!/usr/bin/env bash
# Runbook for "GPU Kubernetes cluster" lab.
# Run STEP BY STEP on the lab VM (khra-oksana@111.88.152.253).
# Do NOT run end-to-end blindly — verify outputs between sections.
#
# Convention:
#   $LAB_DIR     — where this repo is uploaded on the VM, default /home/khra-oksana/k8s-gpu-lab
#   $REPORT_DIR  — where to drop logs / outputs for the report

set -euo pipefail

LAB_DIR="${LAB_DIR:-/home/khra-oksana/k8s-gpu-lab}"
REPORT_DIR="${REPORT_DIR:-$LAB_DIR/report}"
mkdir -p "$REPORT_DIR"

step() { printf '\n==== %s ====\n' "$*"; }

# ---------------------------------------------------------------------------
# 0. VM and GPU inventory (record for the report)
# ---------------------------------------------------------------------------
collect_inventory() {
    step "VM inventory"
    {
        echo "# uname"
        uname -a
        echo
        echo "# lsb_release"
        lsb_release -a 2>/dev/null || cat /etc/os-release
        echo
        echo "# nproc / memory"
        nproc
        free -h
        echo
        echo "# block devices"
        lsblk
        echo
        echo "# pci nvidia"
        lspci | grep -i nvidia || true
    } | tee "$REPORT_DIR/00-vm-inventory.txt"
}

# ---------------------------------------------------------------------------
# 1. Cleanup old NVIDIA / CUDA / kubelet (only if VM is dirty)
# ---------------------------------------------------------------------------
cleanup_old_packages() {
    step "Cleanup old NVIDIA / k8s artifacts"
    dpkg -l | egrep 'nvidia|libnvidia|cuda' || true
    lsmod | grep nvidia || true
    which nvidia-smi || true

    sudo systemctl stop kubelet containerd || true
    sudo systemctl disable kubelet containerd || true
    sudo kubeadm reset -f || true

    sudo apt-mark unhold kubelet kubeadm kubectl 2>/dev/null || true
    sudo apt-get purge -y \
        'nvidia-*' 'libnvidia-*' 'cuda-*' \
        nvidia-container-toolkit nvidia-container-toolkit-base \
        libnvidia-container-tools libnvidia-container1 nvidia-docker2 \
        containerd containerd.io \
        kubelet kubeadm kubectl kubernetes-cni || true
    sudo apt-get autoremove -y --purge
    sudo apt-get autoclean

    sudo /usr/bin/nvidia-uninstall 2>/dev/null || true

    sudo rm -rf /etc/kubernetes /var/lib/kubelet /var/lib/etcd \
        /var/lib/cni /etc/cni /opt/cni /var/run/kubernetes \
        /var/lib/containerd /etc/containerd
    echo "Reboot recommended now. Re-run this script after reboot, skipping cleanup."
}

# ---------------------------------------------------------------------------
# 2. Linux node preparation (swap off, kernel modules, sysctl)
# ---------------------------------------------------------------------------
prepare_node() {
    step "Prepare Linux node"
    sudo swapoff -a
    sudo sed -ri '/\sswap\s/s/^#?/#/' /etc/fstab

    cat <<'EOF' | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
    sudo modprobe overlay
    sudo modprobe br_netfilter

    cat <<'EOF' | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
EOF
    sudo sysctl --system
}

# ---------------------------------------------------------------------------
# 3. containerd
# ---------------------------------------------------------------------------
install_containerd() {
    step "Install containerd"
    sudo apt-get update
    sudo apt-get install -y containerd apt-transport-https ca-certificates curl gpg jq

    sudo mkdir -p /etc/containerd
    containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
    sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

    sudo systemctl restart containerd
    sudo systemctl enable containerd
    sudo systemctl status containerd --no-pager
}

# ---------------------------------------------------------------------------
# 4. Kubernetes 1.34 (kubelet, kubeadm, kubectl)
# ---------------------------------------------------------------------------
install_kubernetes() {
    step "Install Kubernetes 1.34"
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.34/deb/Release.key |
        sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
    echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.34/deb/ /' |
        sudo tee /etc/apt/sources.list.d/kubernetes.list
    sudo apt-get update
    sudo apt-get install -y kubelet kubeadm kubectl
    sudo apt-mark hold kubelet kubeadm kubectl

    {
        kubeadm version
        kubectl version --client
    } | tee "$REPORT_DIR/04-k8s-versions.txt"
}

# ---------------------------------------------------------------------------
# 5. kubeadm init, kubeconfig, untaint, Flannel CNI
# ---------------------------------------------------------------------------
init_cluster() {
    step "kubeadm init + Flannel"
    sudo kubeadm init --pod-network-cidr=10.244.0.0/16 | tee "$REPORT_DIR/05-kubeadm-init.txt"

    mkdir -p "$HOME/.kube"
    sudo cp -i /etc/kubernetes/admin.conf "$HOME/.kube/config"
    sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"

    kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true

    kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

    echo "Wait for node Ready and kube-system pods Running..."
    kubectl wait --for=condition=Ready node --all --timeout=300s

    kubectl get nodes -o wide | tee "$REPORT_DIR/05-kubectl-get-nodes.txt"
    kubectl get pods -A | tee "$REPORT_DIR/05-kubectl-get-pods-all.txt"
}

# ---------------------------------------------------------------------------
# 6. Helm
# ---------------------------------------------------------------------------
install_helm() {
    step "Install Helm"
    curl -fsSL -o /tmp/get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
    chmod 700 /tmp/get_helm.sh
    /tmp/get_helm.sh
    helm version | tee "$REPORT_DIR/06-helm-version.txt"
}

# ---------------------------------------------------------------------------
# 7. NVIDIA GPU Operator 25.10.1
# ---------------------------------------------------------------------------
install_gpu_operator() {
    step "Install NVIDIA GPU Operator"
    kubectl create namespace gpu-operator --dry-run=client -o yaml | kubectl apply -f -
    kubectl label --overwrite namespace gpu-operator \
        pod-security.kubernetes.io/enforce=privileged

    kubectl apply -f "$LAB_DIR/gpu-lab/device-plugin-sharing-config.yaml"

    helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
    helm repo update

    helm upgrade --install gpu-operator nvidia/gpu-operator \
        -n gpu-operator \
        --version=v25.10.1 \
        --set driver.enabled=true \
        --set driver.version=580.105.08 \
        --set toolkit.enabled=true \
        --set dcgmExporter.enabled=true \
        --set devicePlugin.config.name=device-plugin-config \
        --set devicePlugin.config.default=default

    echo "Waiting for GPU Operator pods (can take 10+ minutes for driver build)..."
    for _ in $(seq 1 60); do
        if kubectl get ds -n gpu-operator nvidia-device-plugin-daemonset \
            -o jsonpath='{.status.numberReady}' 2>/dev/null | grep -q '^[1-9]'; then
            break
        fi
        sleep 15
        kubectl get pods -n gpu-operator
    done

    kubectl get pods -n gpu-operator | tee "$REPORT_DIR/07-gpu-operator-pods.txt"

    NODE="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
    kubectl describe node "$NODE" | sed -n '/Capacity:/,/Allocatable:/p' \
        | tee "$REPORT_DIR/07-node-capacity.txt"

    DS="$(kubectl get ds -n gpu-operator -o jsonpath='{.items[?(@.metadata.labels.app=="nvidia-driver-daemonset")].metadata.name}')"
    kubectl exec -n gpu-operator "ds/$DS" -- nvidia-smi \
        | tee "$REPORT_DIR/07-nvidia-smi-from-driver-ds.txt"
}

# ---------------------------------------------------------------------------
# 8. gpu-lab namespace + benchmark ConfigMap
# ---------------------------------------------------------------------------
prepare_workload_namespace() {
    step "Create gpu-lab namespace and bench script ConfigMap"
    kubectl apply -f "$LAB_DIR/manifests/namespace.yaml"
    kubectl apply -f "$LAB_DIR/gpu-lab/torch-benchmark-configmap.yaml"
    kubectl get namespace gpu-lab
}

# ---------------------------------------------------------------------------
# 9. JupyterLab smoke test
# ---------------------------------------------------------------------------
jupyter_smoke_test() {
    step "JupyterLab smoke test"
    kubectl apply -f "$LAB_DIR/gpu-lab/jupyterlab.yaml"
    kubectl wait --for=condition=available --timeout=600s \
        deployment/jupyterlab -n gpu-lab
    kubectl get pods -n gpu-lab -l app=jupyterlab

    # Run torch sanity check from inside the pod and capture it.
    POD="$(kubectl get pods -n gpu-lab -l app=jupyterlab -o jsonpath='{.items[0].metadata.name}')"
    kubectl exec -n gpu-lab "$POD" -- python -c '
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("device_name", torch.cuda.get_device_name(0))
' | tee "$REPORT_DIR/09-jupyter-torch-check.txt"

    kubectl exec -n gpu-lab "$POD" -- nvidia-smi \
        | tee "$REPORT_DIR/09-nvidia-smi-from-jupyter.txt"

    # Note: the methodology says to delete jupyterlab after the check,
    # but we keep it for live UI demonstration in the report. Delete manually
    # with: kubectl delete deployment jupyterlab -n gpu-lab
}

# ---------------------------------------------------------------------------
# 10. kube-prometheus-stack + DCGM ServiceMonitor
# ---------------------------------------------------------------------------
install_monitoring() {
    step "Install kube-prometheus-stack + DCGM ServiceMonitor"
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update

    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

    helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
        -n monitoring

    kubectl wait --for=condition=available --timeout=600s \
        deployment -n monitoring -l app.kubernetes.io/name=grafana

    kubectl label svc -n gpu-operator nvidia-dcgm-exporter monitor=dcgm --overwrite
    kubectl apply -f "$LAB_DIR/gpu-lab/dcgm-servicemonitor.yaml"

    kubectl get servicemonitor -n gpu-operator \
        | tee "$REPORT_DIR/10-dcgm-servicemonitor.txt"

    GRAFANA_PASS="$(kubectl get secret -n monitoring monitoring-grafana \
        -o jsonpath='{.data.admin-password}' | base64 -d)"
    echo "Grafana admin password: $GRAFANA_PASS" \
        | tee "$REPORT_DIR/10-grafana-password.txt"

    echo "Port-forward Grafana:  kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80"
    echo "From your laptop:      ssh -L 3000:localhost:3000 khra-oksana@111.88.152.253"
}

# ---------------------------------------------------------------------------
# 11. Experiment 1: exclusive GPU
# ---------------------------------------------------------------------------
run_exclusive() {
    step "Experiment 1: exclusive GPU"
    NODE="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
    kubectl label node "$NODE" nvidia.com/device-plugin.config- || true
    kubectl rollout restart -n gpu-operator daemonset/nvidia-device-plugin-daemonset
    kubectl rollout status -n gpu-operator daemonset/nvidia-device-plugin-daemonset

    kubectl describe node "$NODE" | sed -n '/Capacity:/,/Allocatable:/p' \
        | tee "$REPORT_DIR/11-exclusive-capacity.txt"

    kubectl delete job -n gpu-lab --ignore-not-found torch-benchmark
    kubectl apply -f "$LAB_DIR/gpu-lab/torch-benchmark-exclusive.yaml"

    kubectl wait --for=condition=complete --timeout=900s job/torch-benchmark -n gpu-lab \
        || kubectl wait --for=condition=failed --timeout=10s job/torch-benchmark -n gpu-lab

    kubectl logs -n gpu-lab job/torch-benchmark | tee "$REPORT_DIR/11-exclusive-logs.txt"
}

# ---------------------------------------------------------------------------
# 12. Experiment 2: time-slicing (4 replicas)
# ---------------------------------------------------------------------------
run_time_slicing() {
    step "Experiment 2: time-slicing"
    NODE="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
    kubectl label node "$NODE" nvidia.com/device-plugin.config=t4-timeslicing-4 --overwrite
    kubectl rollout restart -n gpu-operator daemonset/nvidia-device-plugin-daemonset
    kubectl rollout status -n gpu-operator daemonset/nvidia-device-plugin-daemonset
    sleep 10

    kubectl describe node "$NODE" | sed -n '/Capacity:/,/Allocatable:/p' \
        | tee "$REPORT_DIR/12-timeslicing-capacity.txt"

    for i in 1 2 3 4; do
        kubectl delete job -n gpu-lab --ignore-not-found "torch-benchmark-ts-$i"
        sed "s/name: torch-benchmark/name: torch-benchmark-ts-$i/" \
            "$LAB_DIR/gpu-lab/torch-benchmark-shared.yaml" | kubectl apply -f -
    done

    for i in 1 2 3 4; do
        kubectl wait --for=condition=complete --timeout=1200s "job/torch-benchmark-ts-$i" -n gpu-lab \
            || kubectl wait --for=condition=failed --timeout=10s "job/torch-benchmark-ts-$i" -n gpu-lab \
            || true
    done

    for i in 1 2 3 4; do
        echo "===== torch-benchmark-ts-$i ====="
        kubectl logs -n gpu-lab "job/torch-benchmark-ts-$i"
    done | tee "$REPORT_DIR/12-timeslicing-logs.txt"
}

# ---------------------------------------------------------------------------
# 13. Experiment 3: MPS (4 replicas; may be flaky on T4 — that's allowed)
# ---------------------------------------------------------------------------
run_mps() {
    step "Experiment 3: MPS"
    NODE="$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')"
    kubectl label node "$NODE" nvidia.com/device-plugin.config=t4-mps-4 --overwrite
    kubectl rollout restart -n gpu-operator daemonset/nvidia-device-plugin-daemonset
    kubectl rollout status -n gpu-operator daemonset/nvidia-device-plugin-daemonset
    sleep 10

    kubectl describe node "$NODE" | sed -n '/Capacity:/,/Allocatable:/p' \
        | tee "$REPORT_DIR/13-mps-capacity.txt"

    for i in 1 2 3 4; do
        kubectl delete job -n gpu-lab --ignore-not-found "torch-benchmark-mps-$i"
        sed "s/name: torch-benchmark/name: torch-benchmark-mps-$i/" \
            "$LAB_DIR/gpu-lab/torch-benchmark-shared.yaml" | kubectl apply -f -
    done

    for i in 1 2 3 4; do
        kubectl wait --for=condition=complete --timeout=1200s "job/torch-benchmark-mps-$i" -n gpu-lab \
            || kubectl wait --for=condition=failed --timeout=10s "job/torch-benchmark-mps-$i" -n gpu-lab \
            || true
    done

    for i in 1 2 3 4; do
        echo "===== torch-benchmark-mps-$i ====="
        kubectl logs -n gpu-lab "job/torch-benchmark-mps-$i" || true
    done | tee "$REPORT_DIR/13-mps-logs.txt"
}

# ---------------------------------------------------------------------------
# 14. Final inventory for the report
# ---------------------------------------------------------------------------
final_inventory() {
    step "Final inventory"
    {
        echo "# kubectl get nodes -o wide"
        kubectl get nodes -o wide
        echo
        echo "# kubectl get pods -A"
        kubectl get pods -A
        echo
        echo "# helm list -A"
        helm list -A
        echo
        echo "# GPU Operator version"
        helm list -n gpu-operator
    } | tee "$REPORT_DIR/99-final-state.txt"
}

# ---------------------------------------------------------------------------
# Driver. Comment out steps you don't need.
# ---------------------------------------------------------------------------
case "${1:-all}" in
    inventory) collect_inventory ;;
    cleanup)   cleanup_old_packages ;;
    prep)      prepare_node ;;
    containerd) install_containerd ;;
    k8s)       install_kubernetes ;;
    init)      init_cluster ;;
    helm)      install_helm ;;
    gpu)       install_gpu_operator ;;
    ns)        prepare_workload_namespace ;;
    jupyter)   jupyter_smoke_test ;;
    monitoring) install_monitoring ;;
    exclusive) run_exclusive ;;
    timeslicing) run_time_slicing ;;
    mps)       run_mps ;;
    final)     final_inventory ;;
    all)
        collect_inventory
        prepare_node
        install_containerd
        install_kubernetes
        init_cluster
        install_helm
        install_gpu_operator
        prepare_workload_namespace
        jupyter_smoke_test
        install_monitoring
        run_exclusive
        run_time_slicing
        run_mps
        final_inventory
        ;;
    *)
        echo "Unknown step: $1"
        echo "Usage: $0 [inventory|cleanup|prep|containerd|k8s|init|helm|gpu|ns|jupyter|monitoring|exclusive|timeslicing|mps|final|all]"
        exit 1
        ;;
esac
