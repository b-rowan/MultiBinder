#!/usr/bin/env bash
# MultiBinder — Proxmox LXC Installer
# Run on your Proxmox host:
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/b-rowan/MultiBinder/main/install.sh)"

set -euo pipefail

GITHUB_REPO="https://github.com/b-rowan/MultiBinder"

# ─── Colors ───────────────────────────────────────────────────────────────────
YW="\033[33m"
BL="\033[36m"
RD="\033[01;31m"
GN="\033[1;92m"
DGN="\033[32m"
CL="\033[m"
BOLD="\033[1m"
BFR="\\r\\033[K"
CM="${GN}✓${CL}"
CROSS="${RD}✗${CL}"
INFO="${BL}ℹ${CL}"

# ─── Output helpers ───────────────────────────────────────────────────────────
msg_info()  { echo -ne " ${INFO}  ${1}..."; }
msg_ok()    { echo -e "${BFR} ${CM}  ${1}"; }
msg_error() { echo -e "${BFR} ${CROSS}  ${1}"; exit 1; }

header_info() {
  clear
  echo -e "${BL}"
  cat <<'EOF'
  __  ___    _ _   ___ _         _
 |  \/  |  _| | |_(_) |__ __ _| |_ __| | ___ _ _
 | |\/| | || | |  _| | '_ \ | || | / _` |/ -_) '_|
 |_|  |_|\_,_|_|\__|_|_.__/ \_,_|_\__,_|\___|_|

EOF
  echo -e "${CL}${DGN}  MTG Collection & Deck Tracker — Proxmox LXC Installer${CL}"
  echo ""
}

# ─── Preflight checks ─────────────────────────────────────────────────────────
check_proxmox() {
  if ! command -v pveversion &>/dev/null; then
    msg_error "This script must be run on a Proxmox VE host"
  fi
  if [[ "$(whoami)" != "root" ]]; then
    msg_error "This script must be run as root"
  fi
  if ! command -v whiptail &>/dev/null; then
    msg_error "whiptail is required but not installed"
  fi
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
next_ctid() {
  local id=100
  while pct status "$id" &>/dev/null; do ((id++)); done
  echo "$id"
}

default_storage() {
  pvesm status -content rootdir 2>/dev/null | awk 'NR>1 {print $1; exit}'
}

# ─── Main ─────────────────────────────────────────────────────────────────────
header_info
check_proxmox

NEXT_ID=$(next_ctid)
DEF_STORAGE=$(default_storage)
DEF_STORAGE="${DEF_STORAGE:-local-lvm}"

# ─── Interactive configuration ────────────────────────────────────────────────
CT_ID=$(whiptail --title "MultiBinder Installer" \
  --inputbox "Container ID:" 8 40 "$NEXT_ID" 3>&1 1>&2 2>&3) || exit 0

CT_HOSTNAME=$(whiptail --title "MultiBinder Installer" \
  --inputbox "Hostname:" 8 40 "multibinder" 3>&1 1>&2 2>&3) || exit 0

CT_STORAGE=$(whiptail --title "MultiBinder Installer" \
  --inputbox "Storage pool:" 8 40 "$DEF_STORAGE" 3>&1 1>&2 2>&3) || exit 0

CT_MEMORY=$(whiptail --title "MultiBinder Installer" \
  --inputbox "Memory (MB):" 8 40 "2048" 3>&1 1>&2 2>&3) || exit 0

CT_DISK=$(whiptail --title "MultiBinder Installer" \
  --inputbox "Disk size (GB):" 8 40 "8" 3>&1 1>&2 2>&3) || exit 0

CT_CORES=$(whiptail --title "MultiBinder Installer" \
  --inputbox "CPU cores:" 8 40 "2" 3>&1 1>&2 2>&3) || exit 0

# Pangolin / Newt config
USE_PANGOLIN=false
PANGOLIN_ENDPOINT=""
NEWT_ID_VAL=""
NEWT_SECRET_VAL=""

if whiptail --title "MultiBinder Installer" \
  --yesno "Configure Pangolin reverse proxy (Newt)?" 8 55; then
  USE_PANGOLIN=true

  PANGOLIN_ENDPOINT=$(whiptail --title "Pangolin Config" \
    --inputbox "Pangolin server URL:\n(e.g. https://pangolin.yourdomain.com)" 9 60 "" 3>&1 1>&2 2>&3) || exit 0

  NEWT_ID_VAL=$(whiptail --title "Pangolin Config" \
    --inputbox "Newt Site ID:" 8 50 "" 3>&1 1>&2 2>&3) || exit 0

  NEWT_SECRET_VAL=$(whiptail --title "Pangolin Config" \
    --passwordbox "Newt Site Secret:" 8 50 3>&1 1>&2 2>&3) || exit 0
fi

# Confirm
PANGOLIN_LINE="No"
[[ "$USE_PANGOLIN" == "true" ]] && PANGOLIN_LINE="Yes (${PANGOLIN_ENDPOINT})"

whiptail --title "MultiBinder Installer" --yesno \
"Ready to install with these settings:

  Container ID : $CT_ID
  Hostname     : $CT_HOSTNAME
  Storage      : $CT_STORAGE
  Memory       : ${CT_MEMORY} MB
  Disk         : ${CT_DISK} GB
  Cores        : $CT_CORES
  Pangolin     : $PANGOLIN_LINE

Proceed?" 18 58 || exit 0

echo ""

# ─── Template ─────────────────────────────────────────────────────────────────
TEMPLATE="ubuntu-24.04-standard_24.04-2_amd64.tar.zst"
TEMPLATE_STORAGE="local"

msg_info "Checking Ubuntu 24.04 LXC template"
if ! pveam list "$TEMPLATE_STORAGE" 2>/dev/null | grep -q "ubuntu-24.04"; then
  msg_info "Downloading Ubuntu 24.04 template (this may take a moment)"
  pveam update &>/dev/null
  pveam download "$TEMPLATE_STORAGE" "$TEMPLATE" &>/dev/null \
    || msg_error "Failed to download LXC template"
fi
msg_ok "Template ready"

# ─── Create LXC ───────────────────────────────────────────────────────────────
CT_PASSWORD=$(openssl rand -base64 16)

msg_info "Creating LXC container $CT_ID"
pct create "$CT_ID" \
  "${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE}" \
  --hostname "$CT_HOSTNAME" \
  --cores "$CT_CORES" \
  --memory "$CT_MEMORY" \
  --swap 512 \
  --rootfs "${CT_STORAGE}:${CT_DISK}" \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 \
  --unprivileged 1 \
  --ostype ubuntu \
  --password "$CT_PASSWORD" \
  --start 0 &>/dev/null \
  || msg_error "Failed to create container"
msg_ok "Container $CT_ID created"

# ─── Start container ──────────────────────────────────────────────────────────
msg_info "Starting container"
pct start "$CT_ID" &>/dev/null

# Wait until shell is responsive
for i in {1..30}; do
  pct exec "$CT_ID" -- true 2>/dev/null && break
  sleep 2
done
msg_ok "Container started"

# ─── Install Docker ───────────────────────────────────────────────────────────
msg_info "Installing Docker"
pct exec "$CT_ID" -- bash -c '
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
' &>/dev/null || msg_error "Docker installation failed"
msg_ok "Docker installed"

# ─── Clone repository ─────────────────────────────────────────────────────────
msg_info "Cloning MultiBinder from GitHub"
pct exec "$CT_ID" -- bash -c "
  git clone ${GITHUB_REPO} /opt/multibinder
  mkdir -p /opt/multibinder/data
" &>/dev/null || msg_error "Failed to clone repository"
msg_ok "Repository cloned to /opt/multibinder"

# ─── Write .env ───────────────────────────────────────────────────────────────
msg_info "Writing configuration"
SECRET_KEY=$(openssl rand -hex 32)

{
  echo "SECRET_KEY=${SECRET_KEY}"
  if [[ "$USE_PANGOLIN" == "true" ]]; then
    echo "PANGOLIN_ENDPOINT=${PANGOLIN_ENDPOINT}"
    echo "NEWT_ID=${NEWT_ID_VAL}"
    echo "NEWT_SECRET=${NEWT_SECRET_VAL}"
  fi
} > /tmp/multibinder_env_${CT_ID}

pct push "$CT_ID" "/tmp/multibinder_env_${CT_ID}" /opt/multibinder/.env \
  || msg_error "Failed to write .env"
pct exec "$CT_ID" -- chmod 600 /opt/multibinder/.env
rm -f "/tmp/multibinder_env_${CT_ID}"
msg_ok "Configuration written"

# ─── Start services ───────────────────────────────────────────────────────────
msg_info "Building and starting MultiBinder (first build may take a few minutes)"

if [[ "$USE_PANGOLIN" == "true" ]]; then
  COMPOSE_CMD="docker compose --profile pangolin up -d --build"
else
  COMPOSE_CMD="docker compose up -d --build"
fi

pct exec "$CT_ID" -- bash -c "
  cd /opt/multibinder
  ${COMPOSE_CMD}
" || msg_error "Failed to start services"
msg_ok "MultiBinder started"

# ─── Get container IP ─────────────────────────────────────────────────────────
CT_IP=$(pct exec "$CT_ID" -- hostname -I 2>/dev/null | awk '{print $1}')

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GN}╔══════════════════════════════════════════════╗${CL}"
echo -e "${GN}║     MultiBinder installed successfully!      ║${CL}"
echo -e "${GN}╚══════════════════════════════════════════════╝${CL}"
echo ""
echo -e "  ${BOLD}Container:${CL}     $CT_ID ($CT_HOSTNAME)"
echo -e "  ${BOLD}IP address:${CL}    ${CT_IP:-<check with: pct exec $CT_ID -- hostname -I>}"
echo -e "  ${BOLD}App URL:${CL}       http://${CT_IP:-<ip>}:8000"
echo ""
echo -e "  ${BOLD}Root password:${CL} $CT_PASSWORD"
echo -e "  ${DGN}  (SSH: ssh root@${CT_IP:-<ip>})${CL}"
echo ""
if [[ "$USE_PANGOLIN" == "true" ]]; then
  echo -e "  ${BOLD}Pangolin:${CL}      Set resource target → http://app:8000"
  echo ""
fi
echo -e "  ${BOLD}Migrating existing data?${CL}"
echo -e "  ${DGN}  Copy your database into the container:${CL}"
echo -e "  ${DGN}  pct push $CT_ID ./multibinder.sqlite3 /opt/multibinder/data/multibinder.sqlite3${CL}"
echo ""
echo -e "  ${BOLD}Manage the app:${CL}"
echo -e "  ${DGN}  pct exec $CT_ID -- bash${CL}"
echo -e "  ${DGN}  cd /opt/multibinder && docker compose logs -f${CL}"
echo ""
