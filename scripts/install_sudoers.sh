#!/usr/bin/env bash
#
# Least-Privilege Sudoers Installer for Linux Hardware Assistant
#
# Principle of Least Privilege:
# Instead of running the assistant or python process as root, this script grants
# the current user passwordless sudo access EXCLUSIVELY to read-only hardware telemetry:
# - /usr/sbin/dmidecode -t memory
# - /usr/sbin/dmidecode -t 1,2,3
#
# No shell escape or write capabilities are permitted.

set -euo pipefail

TARGET_USER="${SUDO_USER:-$USER}"
SUDOERS_FILE="/etc/sudoers.d/99-hardware-assistant"

echo "Configuring least-privilege hardware diagnostics for user: ${TARGET_USER}"

DMIDECODE_PATH="$(which dmidecode || echo '/usr/sbin/dmidecode')"

if [ ! -f "$DMIDECODE_PATH" ]; then
    echo "Warning: dmidecode is not installed. Installing via package manager..."
    if command -v apt-get &>/dev/null; then
        apt-get update && apt-get install -y dmidecode
    elif command -v dnf &>/dev/null; then
        dnf install -y dmidecode
    elif command -v pacman &>/dev/null; then
        pacman -Sy --noconfirm dmidecode
    fi
fi

# Create atomic sudoers configuration
TMP_SUDOERS="$(mktemp)"
cat <<EOF > "$TMP_SUDOERS"
# Hardware Assistant least-privilege read-only rules
${TARGET_USER} ALL=(ALL) NOPASSWD: ${DMIDECODE_PATH} -t memory, ${DMIDECODE_PATH} -t 1\,2\,3
EOF

# Validate syntax with visudo before installing
if visudo -cf "$TMP_SUDOERS"; then
    install -m 0440 "$TMP_SUDOERS" "$SUDOERS_FILE"
    rm -f "$TMP_SUDOERS"
    echo "Successfully installed least-privilege rule to ${SUDOERS_FILE}"
    echo "Hardware Assistant can now safely read motherboard DMI memory slots without root passwords."
else
    echo "Error: Generated sudoers file failed syntax check."
    rm -f "$TMP_SUDOERS"
    exit 1
fi

