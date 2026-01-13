#!/bin/bash
# Jitsi JWT Authentication Fix Script
# Run this on your Jitsi server (192.168.117.153)
# Usage: sudo bash jitsi_fix_script.sh

set -e

echo "============================================"
echo "Jitsi JWT Authentication Fix Script"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root (sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Updating package list...${NC}"
apt update

echo ""
echo -e "${YELLOW}Step 2: Installing missing Lua dependencies...${NC}"
apt install -y lua-inspect lua-cjson lua-basexx

echo ""
echo -e "${YELLOW}Step 3: Installing/Reinstalling jitsi-meet-tokens...${NC}"
apt install -y jitsi-meet-tokens

echo ""
echo -e "${YELLOW}Step 4: Fixing Lua inspect.lua path (CRITICAL FIX)...${NC}"
# Find where inspect.lua is actually installed
INSPECT_PATH=$(find /usr -name "inspect.lua" 2>/dev/null | head -1)
if [ -n "$INSPECT_PATH" ]; then
    echo -e "${GREEN}Found inspect.lua at: $INSPECT_PATH${NC}"
    
    # Create directories that Prosody looks in
    mkdir -p /usr/share/lua/5.4
    mkdir -p /usr/local/share/lua/5.4
    
    # Create symlinks
    ln -sf "$INSPECT_PATH" /usr/share/lua/5.4/inspect.lua
    ln -sf "$INSPECT_PATH" /usr/local/share/lua/5.4/inspect.lua
    ln -sf "$INSPECT_PATH" /usr/lib/prosody/inspect.lua
    
    echo -e "${GREEN}Created symlinks for inspect.lua${NC}"
else
    echo -e "${RED}Warning: Could not find inspect.lua${NC}"
    # Try to install via luarocks
    apt install -y luarocks 2>/dev/null || true
    luarocks install inspect 2>/dev/null || true
fi

echo ""
echo -e "${YELLOW}Step 5: Updating Prosody plugin_paths...${NC}"
PLUGIN_PATH="/usr/share/jitsi-meet/prosody-plugins/"
if [ -d "$PLUGIN_PATH" ]; then
    echo -e "${GREEN}Jitsi Prosody plugins directory exists: $PLUGIN_PATH${NC}"
fi

# Update plugin_paths to include Jitsi plugins
if grep -q 'plugin_paths = { "/usr/local/lib/prosody/modules" }' /etc/prosody/prosody.cfg.lua; then
    sed -i 's|plugin_paths = { "/usr/local/lib/prosody/modules" }|plugin_paths = { "/usr/local/lib/prosody/modules", "/usr/share/jitsi-meet/prosody-plugins/" }|' /etc/prosody/prosody.cfg.lua
    echo -e "${GREEN}Added Jitsi plugins to plugin_paths${NC}"
elif grep -q "plugin_paths" /etc/prosody/prosody.cfg.lua; then
    echo -e "${YELLOW}plugin_paths already configured:${NC}"
    grep "plugin_paths" /etc/prosody/prosody.cfg.lua
else
    sed -i '1i plugin_paths = { "/usr/local/lib/prosody/modules", "/usr/share/jitsi-meet/prosody-plugins/" }' /etc/prosody/prosody.cfg.lua
    echo -e "${GREEN}Added plugin_paths configuration${NC}"
fi

echo ""
echo -e "${YELLOW}Step 6: Verifying symlinks...${NC}"
ls -la /usr/share/lua/5.4/inspect.lua 2>/dev/null && echo -e "${GREEN}✓ /usr/share/lua/5.4/inspect.lua exists${NC}" || echo -e "${RED}✗ Missing${NC}"
ls -la /usr/lib/prosody/inspect.lua 2>/dev/null && echo -e "${GREEN}✓ /usr/lib/prosody/inspect.lua exists${NC}" || echo -e "${RED}✗ Missing${NC}"

echo ""
echo -e "${YELLOW}Step 7: Restarting all Jitsi services...${NC}"
systemctl restart prosody
sleep 2
systemctl restart jicofo jitsi-videobridge2

echo ""
echo -e "${YELLOW}Step 8: Checking Prosody for errors...${NC}"
sleep 2
if journalctl -u prosody -n 30 --no-pager | grep -q "no field package.preload\['inspect'\]"; then
    echo -e "${RED}ERROR: inspect.lua still not found!${NC}"
    echo "Trying alternative fix..."
    
    # Alternative: copy the file directly
    cp "$INSPECT_PATH" /usr/lib/prosody/inspect.lua 2>/dev/null || true
    systemctl restart prosody
else
    echo -e "${GREEN}No inspect.lua errors found!${NC}"
fi

echo ""
echo -e "${YELLOW}Step 9: Final service status check...${NC}"
echo ""
echo "Prosody:"
systemctl is-active prosody && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"
echo ""
echo "Jicofo:"
systemctl is-active jicofo && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"
echo ""
echo "JVB:"
systemctl is-active jitsi-videobridge2 && echo -e "${GREEN}✓ Running${NC}" || echo -e "${RED}✗ Not running${NC}"

echo ""
echo -e "${YELLOW}Step 10: Testing token authentication...${NC}"
sleep 2
if journalctl -u prosody -n 20 --no-pager | grep -q "No available SASL mechanisms"; then
    echo -e "${RED}WARNING: Token authentication may still have issues${NC}"
    echo "Check logs with: sudo tail -f /var/log/prosody/prosody.log"
else
    echo -e "${GREEN}Token authentication appears to be working!${NC}"
fi

echo ""
echo "============================================"
echo -e "${GREEN}Fix script completed!${NC}"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Try joining a meeting from your dashboard"
echo "2. Watch logs while connecting:"
echo "   sudo tail -f /var/log/prosody/prosody.log"
echo ""
