#!/bin/bash

# 🐼 Crypto Trading Terminal - One-Click Setup Script
# This script automates the complete setup process for the trading terminal

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ASCII Art Banner
print_banner() {
    echo -e "${CYAN}"
    echo "  ____ _____ ____  _____ _____   _____ _____ ____  _   _ _   _ _____ ____  "
    echo " / ___|_   _/ ___||_   _| ____| |_   _| ____|  _ \| | | | \ | | ____|  _ \ "
    echo "| |     | | \___ \  | | |  _|     | | |  _| | |_) | | | |  \| |  _| | |_) |"
    echo "| |___  | |  ___) | | | | |___    | | | |___|  _ <| |_| | |\  | |___|  _ < "
    echo " \____| |_| |____/  |_| |_____|   |_| |_____|_| \_\\___/|_| \_|_____|_| \_\"
    echo -e "${NC}"
    echo -e "${PURPLE}🚀 Advanced Crypto Trading Terminal Setup${NC}"
    echo -e "${PURPLE}==========================================${NC}\n"
}

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    # Check Python version
    if command_exists python3; then
        PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
        if [[ $(echo "$PYTHON_VERSION >= 3.9" | bc -l) -eq 1 ]]; then
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python 3.9+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 not found. Please install Python 3.9+"
        exit 1
    fi
    
    # Check pip
    if command_exists pip3; then
        print_success "pip3 found"
    else
        print_error "pip3 not found. Please install pip3"
        exit 1
    fi
    
    # Check git
    if command_exists git; then
        print_success "Git found"
    else
        print_error "Git not found. Please install Git"
        exit 1
    fi
    
    # Check available memory
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        MEMORY=$(sysctl -n hw.memsize)
        MEMORY_GB=$((MEMORY / 1024 / 1024 / 1024))
    else
        # Linux
        MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
    fi
    
    if [[ $MEMORY_GB -ge 4 ]]; then
        print_success "System memory: ${MEMORY_GB}GB (sufficient)"
    else
        print_warning "System memory: ${MEMORY_GB}GB (4GB+ recommended)"
    fi
}

# Create virtual environment
setup_virtual_env() {
    print_status "Setting up Python virtual environment..."
    
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    else
        print_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    print_success "Virtual environment activated"
    
    # Upgrade pip
    pip install --upgrade pip
    print_success "pip upgraded to latest version"
}

# Install dependencies
install_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Install requirements
    pip install -r requirements.txt
    print_success "All dependencies installed successfully"
    
    # Verify critical packages
    python3 -c "import dash, plotly, pandas, numpy; print('Core packages verified')"
    print_success "Core packages verified"
}

# Setup configuration
setup_configuration() {
    print_status "Setting up configuration files..."
    
    # Create .env file if it doesn't exist
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            print_success "Configuration file created from template"
        else
            print_warning "No .env.example found, creating basic .env file"
            cat > .env << EOF
# Hyperliquid API Configuration
HYPERLIQUID_TESTNET_RPC_URL=https://api.hyperliquid-testnet.xyz/info
HYPERLIQUID_MAINNET_RPC_URL=https://api.hyperliquid.xyz/info

# Wallet Configuration (Testnet - Replace with your keys)
WALLET_ADDRESS=your_wallet_address_here
PRIVATE_KEY=your_private_key_here

# Trading Parameters
TRADING_BUDGET=200.0
POSITION_SIZE=10.0
RSI_THRESHOLD=18

# Dashboard Configuration
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8050
UPDATE_INTERVAL_SECONDS=60
DASHBOARD_DEBUG=false
EOF
        fi
    else
        print_success "Configuration file already exists"
    fi
    
    # Create necessary directories
    mkdir -p terminal/data
    mkdir -p terminal/logs
    print_success "Data directories created"
}

# Initialize database
initialize_database() {
    print_status "Initializing analytics database..."
    
    cd terminal
    python3 -c "
from data.analytics_db import analytics_db
print('Analytics database initialized successfully')
"
    cd ..
    print_success "Analytics database ready"
}

# Test installation
test_installation() {
    print_status "Testing installation..."
    
    cd terminal
    
    # Test imports
    python3 -c "
import sys
sys.path.append('.')
try:
    from config import config
    from data.hyperliquid_api import api_client_testnet
    from trading.signal_trader import SignalTrader
    print('✅ All modules imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"
    
    cd ..
    print_success "Installation test passed"
}

# Create startup scripts
create_startup_scripts() {
    print_status "Creating startup scripts..."
    
    # Create start.sh
    cat > start.sh << 'EOF'
#!/bin/bash
echo "🐼 Starting Crypto Trading Terminal..."
source venv/bin/activate
cd terminal
python app.py
EOF
    chmod +x start.sh
    
    # Create stop.sh
    cat > stop.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping Crypto Trading Terminal..."
pkill -f "python app.py" || true
echo "Terminal stopped"
EOF
    chmod +x stop.sh
    
    print_success "Startup scripts created"
}

# Display final instructions
show_completion_message() {
    echo -e "\n${GREEN}🎉 Setup Complete! 🎉${NC}\n"
    
    echo -e "${CYAN}Next Steps:${NC}"
    echo -e "1. ${YELLOW}Configure your API keys:${NC} Edit the .env file with your Hyperliquid credentials"
    echo -e "2. ${YELLOW}Start the terminal:${NC} Run ${GREEN}./start.sh${NC} or ${GREEN}python terminal/app.py${NC}"
    echo -e "3. ${YELLOW}Access the interface:${NC} Open http://localhost:8050 in your browser"
    echo -e "4. ${YELLOW}Analytics dashboard:${NC} Visit http://localhost:8050/analytics"
    
    echo -e "\n${PURPLE}Quick Commands:${NC}"
    echo -e "• ${GREEN}./start.sh${NC}     - Start the trading terminal"
    echo -e "• ${GREEN}./stop.sh${NC}      - Stop the trading terminal"
    echo -e "• ${GREEN}./setup.sh${NC}     - Re-run this setup script"
    
    echo -e "\n${CYAN}Configuration Files:${NC}"
    echo -e "• ${YELLOW}.env${NC}          - Environment variables and API keys"
    echo -e "• ${YELLOW}terminal/config.py${NC} - Trading parameters"
    
    echo -e "\n${BLUE}Important Notes:${NC}"
    echo -e "• This setup uses ${YELLOW}testnet${NC} by default (safe for testing)"
    echo -e "• All trades use testnet funds (no real money at risk)"
    echo -e "• Check the README.md for detailed documentation"
    
    echo -e "\n${GREEN}Happy Trading! 🚀${NC}\n"
}

# Main setup function
main() {
    print_banner
    
    print_status "Starting automated setup process..."
    
    check_requirements
    setup_virtual_env
    install_dependencies
    setup_configuration
    initialize_database
    test_installation
    create_startup_scripts
    show_completion_message
    
    print_success "Setup completed successfully!"
}

# Check if running on macOS and install bc if needed
if [[ "$OSTYPE" == "darwin"* ]]; then
    if ! command_exists bc; then
        print_status "Installing bc for version comparison..."
        if command_exists brew; then
            brew install bc
        else
            print_warning "bc not found. Please install it manually: brew install bc"
        fi
    fi
fi

# Run main function
main "$@"
