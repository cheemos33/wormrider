#!/bin/bash

# 🖼️ Screenshot Addition Script
# This script helps you add actual screenshots to the repository

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_banner() {
    echo -e "${BLUE}"
    echo "🖼️  Screenshot Addition Helper"
    echo "=============================="
    echo -e "${NC}"
}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

main() {
    print_banner
    
    echo -e "${YELLOW}This script helps you add actual screenshots to your repository.${NC}"
    echo ""
    echo "📁 Screenshot files needed:"
    echo "1. docs/screenshots/trading-terminal-main.png"
    echo "2. docs/screenshots/analytics-dashboard.png"
    echo ""
    echo "📋 Instructions:"
    echo "1. Take screenshots of your trading terminal and analytics dashboard"
    echo "2. Save them with the exact filenames above"
    echo "3. Replace the placeholder files in docs/screenshots/"
    echo "4. Run: git add docs/screenshots/ && git commit -m 'Add UI screenshots'"
    echo "5. Run: git push origin main"
    echo ""
    echo "📏 Recommended screenshot specifications:"
    echo "- Format: PNG (for best quality)"
    echo "- Width: 1920px or higher"
    echo "- Show the full interface clearly"
    echo "- Capture during active trading for realistic data"
    echo ""
    echo "🎯 Current placeholder files:"
    ls -la docs/screenshots/
    echo ""
    echo "✅ README.md is already configured to display these screenshots!"
    echo "✅ Once you add the actual images, they'll appear automatically on GitHub."
}

main "$@"
