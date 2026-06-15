#!/usr/bin/env bash
#
# setup-orin-nano.sh — post-flash setup script for a fresh Jetson Orin Nano
# running JetPack 6.x (Ubuntu 22.04). Idempotent: safe to re-run.
#
# What it does, in order:
#   1. Verifies we are on Ubuntu 22.04 (Jammy) so ROS 2 Humble works natively
#   2. Installs ROS 2 Humble desktop + colcon + rosdep
#   3. Adds the current user to the dialout group (needed for /dev/ttyUSB*)
#   4. Sets up rosdep
#   5. Clones (or updates) the workspace and the trac_ik dependency under ~/humanoid_ws/src
#   6. Installs Python deps from requirements.txt
#   7. Installs chrony for NTP time-sync (important for ROS-timestamps)
#   8. Builds the workspace with colcon
#   9. Verifies that the by-path symlinks exist with at least one ESP32 plugged in
#
# What it does NOT do (manual steps, intentionally — they require interactive
# downloads or hardware presence):
#   - Flashing JetPack itself (use NVIDIA SDK Manager from a host PC)
#   - Installing the ZED SDK (needs a manual .run download from Stereolabs)
#   - Installing the ZED ROS 2 wrapper (separate workspace, see README.md)
#   - Configuring static IP / DHCP-reservation for 192.168.1.105
#   - Copying SSH keys
#
# Usage:
#   chmod +x setup-orin-nano.sh
#   ./setup-orin-nano.sh
#
# After it finishes: log out and log back in for the dialout group change to
# take effect, then re-run colcon if needed and proceed with the manual steps.

set -euo pipefail

WORKSPACE_DIR="${HOME}/humanoid_ws"
WORKSPACE_REPO="https://github.com/dk-teknologisk-ALMC/energirobotter-ros-workspace-alex.git"
WORKSPACE_BRANCH="alex/min-opgave"
TRACIK_REPO="https://bitbucket.org/traclabs/trac_ik.git"
TRACIK_BRANCH="jazzy"

log()  { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n'  "$*"; }
err()  { printf '\033[1;31m[err]\033[0m %s\n'   "$*" >&2; }

# ---------------------------------------------------------------------------
# Step 1: verify Ubuntu 22.04
# ---------------------------------------------------------------------------
log "Checking OS version..."
if ! grep -q '^VERSION_ID="22.04"' /etc/os-release; then
    err "Not Ubuntu 22.04. ROS 2 Humble requires 22.04 (Jammy)."
    err "Got: $(grep PRETTY_NAME /etc/os-release || echo unknown)"
    exit 1
fi
log "Ubuntu 22.04 confirmed."

# ---------------------------------------------------------------------------
# Step 2: install ROS 2 Humble
# ---------------------------------------------------------------------------
if ! command -v ros2 &>/dev/null; then
    log "Installing ROS 2 Humble apt repo..."
    sudo apt-get update
    sudo apt-get install -y software-properties-common curl gnupg lsb-release
    sudo add-apt-repository universe -y
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
        | sudo tee /etc/apt/sources.list.d/ros2.list >/dev/null

    log "Installing ros-humble-desktop + tooling..."
    sudo apt-get update
    sudo apt-get install -y \
        ros-humble-desktop \
        ros-dev-tools \
        python3-colcon-common-extensions \
        python3-rosdep \
        python3-vcstool \
        git
else
    log "ROS 2 already installed; skipping."
fi

# ---------------------------------------------------------------------------
# Step 3: dialout group
# ---------------------------------------------------------------------------
if id -nG "$USER" | grep -qw dialout; then
    log "User $USER already in dialout group."
else
    log "Adding $USER to dialout group (takes effect on next login)..."
    sudo usermod -a -G dialout "$USER"
fi

# ---------------------------------------------------------------------------
# Step 4: rosdep
# ---------------------------------------------------------------------------
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
    log "Initialising rosdep..."
    sudo rosdep init
fi
log "Updating rosdep database..."
rosdep update

# ---------------------------------------------------------------------------
# Step 5: clone workspace + trac_ik
# ---------------------------------------------------------------------------
mkdir -p "${WORKSPACE_DIR}/src"

if [[ -d "${WORKSPACE_DIR}/src/energirobotter-ros-workspace-alex/.git" ]]; then
    log "Workspace repo already cloned; pulling latest on ${WORKSPACE_BRANCH}..."
    git -C "${WORKSPACE_DIR}/src/energirobotter-ros-workspace-alex" \
        fetch origin "${WORKSPACE_BRANCH}"
    git -C "${WORKSPACE_DIR}/src/energirobotter-ros-workspace-alex" \
        checkout "${WORKSPACE_BRANCH}"
    git -C "${WORKSPACE_DIR}/src/energirobotter-ros-workspace-alex" \
        pull --ff-only origin "${WORKSPACE_BRANCH}"
else
    log "Cloning workspace repo..."
    git -C "${WORKSPACE_DIR}/src" clone --recursive \
        --branch "${WORKSPACE_BRANCH}" \
        "${WORKSPACE_REPO}"
fi

if [[ -d "${WORKSPACE_DIR}/src/trac_ik/.git" ]]; then
    log "trac_ik already cloned; skipping."
else
    log "Cloning trac_ik (${TRACIK_BRANCH} branch)..."
    git -C "${WORKSPACE_DIR}/src" clone --branch "${TRACIK_BRANCH}" "${TRACIK_REPO}"
    # Skip the MoveIt plugin per main README:
    touch "${WORKSPACE_DIR}/src/trac_ik/trac_ik_kinematics_plugin/COLCON_IGNORE"
fi

# ---------------------------------------------------------------------------
# Step 6: Python requirements
# ---------------------------------------------------------------------------
REQ_FILE="${WORKSPACE_DIR}/src/energirobotter-ros-workspace-alex/requirements.txt"
if [[ -f "${REQ_FILE}" ]]; then
    log "Installing Python deps from requirements.txt..."
    pip3 install --user -r "${REQ_FILE}"
else
    warn "requirements.txt not found at ${REQ_FILE}; skipping pip install."
fi

# ---------------------------------------------------------------------------
# Step 7: chrony for time-sync
# ---------------------------------------------------------------------------
if ! command -v chronyd &>/dev/null; then
    log "Installing chrony for NTP time-sync..."
    sudo apt-get install -y chrony
    sudo systemctl enable --now chrony
else
    log "chrony already installed."
fi

# ---------------------------------------------------------------------------
# Step 8: build the workspace
# ---------------------------------------------------------------------------
log "Running rosdep install for workspace..."
# shellcheck source=/dev/null
source /opt/ros/humble/setup.bash
cd "${WORKSPACE_DIR}"
rosdep install --from-paths src --ignore-src -r -y || \
    warn "rosdep install reported issues; some deps may need manual handling (e.g. ZED SDK)."

log "Building workspace with colcon (this may take a while)..."
colcon build --symlink-install \
    --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE=/usr/bin/python3 \
    || { err "colcon build failed."; exit 1; }

# ---------------------------------------------------------------------------
# Step 9: verify by-path symlinks
# ---------------------------------------------------------------------------
log "Checking /dev/serial/by-path/ symlinks (plug in at least one ESP32 first)..."
if ls /dev/serial/by-path/ 2>/dev/null | grep -q '^platform-3610000\.usb-usb-0:2\.[123]:1\.0-port0$'; then
    log "Expected by-path symlinks present:"
    ls -la /dev/serial/by-path/ | grep 'platform-3610000\.usb-usb-0:2\.[123]:1\.0-port0' || true
    log "These match the hard-coded paths in wattson_servo_manager_node.py."
else
    warn "No matching by-path symlinks found. Either no ESP32 is plugged in,"
    warn "or this Orin Nano has a different USB-controller path prefix."
    warn "When an ESP32 is plugged in, run:"
    warn "    ls -l /dev/serial/by-path/"
    warn "If the path prefix is NOT 'platform-3610000.usb-...' you must update"
    warn "the hard-coded port_path strings in:"
    warn "    src/energirobotter-ros-workspace-alex/pkgs_control/servo_control/servo_control/wattson_servo_manager_node.py"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
log "Done."
echo
echo "Next steps (manual):"
echo "  1) Log out and back in for dialout group change to take effect."
echo "  2) Add convenience aliases to ~/.bashrc:"
echo "        alias shumble='source /opt/ros/humble/setup.bash'"
echo "        alias sw='source ~/humanoid_ws/install/setup.bash'"
echo "  3) Configure network so this Jetson lands on 192.168.1.105"
echo "     (static IP via netplan, or DHCP reservation in your router)."
echo "  4) Install the ZED SDK manually — see README.md."
echo "  5) Install the ZED ROS 2 wrapper in a separate workspace — see README.md."
echo "  6) Copy your laptop's SSH public key to ~/.ssh/authorized_keys here."
echo "  7) Test the stack:"
echo "        shumble && sw && ros2 launch energirobotter_bringup servos.launch.py"
