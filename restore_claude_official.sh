#!/bin/bash

# restore_claude_official.sh
# Reverts Claude Code configuration from z.ai back to official Anthropic API
# Usage: curl -O "https://your-domain/restore_claude_official.sh" && bash ./restore_claude_official.sh

set -e

CLAUDE_CONFIG_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_CONFIG_DIR/settings.json"

echo "=== Claude Code Official API Restore Script ==="
echo ""

# Check if config directory exists
if [ ! -d "$CLAUDE_CONFIG_DIR" ]; then
    echo "Error: Claude Code config directory not found at $CLAUDE_CONFIG_DIR"
    echo "Please ensure Claude Code is installed."
    exit 1
fi

# Check if settings file exists
if [ ! -f "$SETTINGS_FILE" ]; then
    echo "Error: Settings file not found at $SETTINGS_FILE"
    exit 1
fi

# Backup current settings
BACKUP_FILE="$SETTINGS_FILE.backup.$(date +%Y%m%d_%H%M%S)"
echo "Creating backup: $BACKUP_FILE"
cp "$SETTINGS_FILE" "$BACKUP_FILE"

# Check current ANTHROPIC_BASE_URL
CURRENT_URL=$(grep -o '"ANTHROPIC_BASE_URL"[^,]*' "$SETTINGS_FILE" | grep -o 'https://[^"]*' || echo "")

if [ -z "$CURRENT_URL" ]; then
    echo "Note: No ANTHROPIC_BASE_URL found in settings."
elif echo "$CURRENT_URL" | grep -q "z.ai"; then
    echo "Detected z.ai configuration: $CURRENT_URL"
else
    echo "Current base URL is not z.ai: $CURRENT_URL"
    echo "Proceeding anyway..."
fi

echo ""
echo "This script will:"
echo "  1. Set ANTHROPIC_BASE_URL to https://api.anthropic.com"
echo "  2. Prompt you for your official Anthropic API key"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Prompt for API key
echo ""
echo "Enter your official Anthropic API key:"
echo "(Get one at https://console.anthropic.com/)"
read -p "API key: " API_KEY

if [ -z "$API_KEY" ]; then
    echo "Error: API key cannot be empty."
    echo "Restoring backup..."
    mv "$BACKUP_FILE" "$SETTINGS_FILE"
    exit 1
fi

# Validate API key format (sk-ant-...)
if [[ ! "$API_KEY" =~ ^sk-ant- ]]; then
    echo "Warning: API key doesn't match expected format (sk-ant-...)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        mv "$BACKUP_FILE" "$SETTINGS_FILE"
        exit 0
    fi
fi

# Update settings.json using Python (more reliable than sed for JSON)
if command -v python3 &> /dev/null; then
    python3 - "$SETTINGS_FILE" "$API_KEY" << 'PYTHON_SCRIPT'
import json
import sys

settings_file = sys.argv[1]
api_key = sys.argv[2]

with open(settings_file, 'r') as f:
    settings = json.load(f)

# Update env section
if 'env' not in settings:
    settings['env'] = {}

settings['env']['ANTHROPIC_AUTH_TOKEN'] = api_key
settings['env']['ANTHROPIC_BASE_URL'] = 'https://api.anthropic.com'

# Remove any z.ai specific variables
settings['env'].pop('ZAI_API_KEY', None)

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)
PYTHON_SCRIPT
    echo "Settings updated successfully."
else
    # Fallback to sed if Python not available
    echo "Python not found, using sed for basic updates..."
    # Update base URL
    sed -i.tmp 's|"ANTHROPIC_BASE_URL": "https://[^"]*"|"ANTHROPIC_BASE_URL": "https://api.anthropic.com"|' "$SETTINGS_FILE"
    # Update auth token (simple replacement, assumes format)
    sed -i.tmp "s|\"ANTHROPIC_AUTH_TOKEN\": \".*\"|\"ANTHROPIC_AUTH_TOKEN\": \"$API_KEY\"|" "$SETTINGS_FILE"
    rm -f "$SETTINGS_FILE.tmp"
    echo "Settings updated (basic mode)."
fi

echo ""
echo "=== Restore Complete ==="
echo ""
echo "Your Claude Code is now configured to use:"
echo "  API Endpoint: https://api.anthropic.com"
echo ""
echo "Backup saved to: $BACKUP_FILE"
echo ""
echo "Test your configuration with:"
echo "  claude version"
echo "  claude auth whoami"
echo ""
