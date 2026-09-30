#!/usr/bin/env bash
# CYCLO-NEXUS — satellite pipeline + inference on an Oracle Cloud Always-Free VM
# (Ubuntu 22.04/24.04, Ampere A1 ARM or x86). Master plan v4 Task 6.2.
#
# Usage (as a sudo-capable user, from the repository root on the VM):
#   bash deploy/oracle/setup.sh
# Then fill in /etc/cyclonexus/pipeline.env and start the services (printed at the end).
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="${APP_USER:-$(whoami)}"

echo "==> System packages"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-dev build-essential libgl1 libglib2.0-0 gdal-bin libgdal-dev

echo "==> Python virtualenv in $APP_DIR/.venv"
python3 -m venv "$APP_DIR/.venv"
# shellcheck disable=SC1091
source "$APP_DIR/.venv/bin/activate"
pip install --upgrade pip wheel
# CPU-only torch (works on ARM64 and x86_64)
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -r "$APP_DIR/inference/requirements.txt"
pip install -r "$APP_DIR/data_pipeline/requirements.txt"
pip uninstall -y opencv-python || true
pip install opencv-python-headless

echo "==> Environment file"
sudo mkdir -p /etc/cyclonexus
if [ ! -f /etc/cyclonexus/pipeline.env ]; then
  sudo cp "$APP_DIR/deploy/oracle/pipeline.env.example" /etc/cyclonexus/pipeline.env
  sudo chmod 600 /etc/cyclonexus/pipeline.env
  sudo chown "$APP_USER" /etc/cyclonexus/pipeline.env
fi

echo "==> systemd units"
for unit in cyclonexus-inference cyclonexus-pipeline; do
  sed -e "s#__APP_DIR__#$APP_DIR#g" -e "s#__APP_USER__#$APP_USER#g" \
    "$APP_DIR/deploy/oracle/$unit.service" | sudo tee "/etc/systemd/system/$unit.service" > /dev/null
done
sudo systemctl daemon-reload

cat <<EOF

Done. Next steps:
  1. Edit /etc/cyclonexus/pipeline.env (MOSDAC, NASA Earthdata, WEBHOOK_SECRET, BACKEND_API_URL).
  2. sudo systemctl enable --now cyclonexus-inference cyclonexus-pipeline
  3. journalctl -u cyclonexus-pipeline -f      # watch the first cycle
EOF
