#!/usr/bin/env bash
# Poll the lab VM until SSH key auth works, then print a ready banner.
set -u

USER_HOST="${USER_HOST:-khra-oksana@111.88.152.253}"
INTERVAL="${INTERVAL:-30}"

while true; do
    if ssh -o StrictHostKeyChecking=no \
           -o ConnectTimeout=5 \
           -o PasswordAuthentication=no \
           -o BatchMode=yes \
           "$USER_HOST" "echo ready" >/dev/null 2>&1; then
        echo "$(date +%T)  $USER_HOST  READY"
        ssh -o StrictHostKeyChecking=no "$USER_HOST" "uname -a; lsb_release -a 2>/dev/null; nvidia-smi 2>&1 | head -25"
        exit 0
    fi
    echo "$(date +%T)  $USER_HOST  still waiting..."
    sleep "$INTERVAL"
done
