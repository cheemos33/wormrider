#!/bin/bash

# 🚀 Crypto Trading Terminal - Deployment Script
# Automated deployment for production environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_TYPE=${1:-"docker"}  # docker, manual, or cloud
ENVIRONMENT=${2:-"production"}  # production, staging, or development
BACKUP_ENABLED=true

print_banner() {
    echo -e "${CYAN}"
    echo "  ____ _____ ____  _____ _____   _____ _____ ____  _   _ _   _ _____ ____  "
    echo " / ___|_   _/ ___||_   _| ____| |_   _| ____|  _ \| | | | \ | | ____|  _ \ "
    echo "| |     | | \___ \  | | |  _|     | | |  _| | |_) | | | |  \| |  _| | |_) |"
    echo "| |___  | |  ___) | | | | |___    | | | |___|  _ <| |_| | |\  | |___|  _ < "
    echo " \____| |_| |____/  |_| |_____|   |_| |_____|_| \_\\___/|_| \_|_____|_| \_\"
    echo -e "${NC}"
    echo -e "${PURPLE}🚀 Production Deployment Script${NC}"
    echo -e "${PURPLE}================================${NC}\n"
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

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root (not recommended for security)
check_user() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root is not recommended for security reasons"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Pre-deployment checks
pre_deployment_checks() {
    print_status "Running pre-deployment checks..."
    
    # Check if .env exists
    if [[ ! -f ".env" ]]; then
        print_error ".env file not found. Please configure your environment variables."
        exit 1
    fi
    
    # Check if mainnet configuration
    if grep -q "TESTNET" .env; then
        print_warning "Detected testnet configuration. Make sure this is intended for production."
        read -p "Continue with testnet? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check disk space
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $DISK_USAGE -gt 90 ]]; then
        print_error "Disk usage is ${DISK_USAGE}%. Please free up space before deployment."
        exit 1
    fi
    
    print_success "Pre-deployment checks passed"
}

# Backup existing deployment
backup_existing() {
    if [[ "$BACKUP_ENABLED" == "true" ]]; then
        print_status "Creating backup of existing deployment..."
        
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup data files
        if [[ -d "terminal/data" ]]; then
            cp -r terminal/data "$BACKUP_DIR/"
        fi
        
        # Backup configuration
        if [[ -f ".env" ]]; then
            cp .env "$BACKUP_DIR/"
        fi
        
        # Keep only last 5 backups
        ls -t backups/ | tail -n +6 | xargs -r rm -rf
        
        print_success "Backup created: $BACKUP_DIR"
    fi
}

# Docker deployment
deploy_docker() {
    print_status "Deploying with Docker..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Stop existing containers
    print_status "Stopping existing containers..."
    docker-compose down || true
    
    # Build and start new containers
    print_status "Building and starting containers..."
    docker-compose up -d --build
    
    # Wait for services to be ready
    print_status "Waiting for services to start..."
    sleep 30
    
    # Health check
    if curl -f http://localhost:8050/_alive &> /dev/null; then
        print_success "Docker deployment successful"
    else
        print_error "Health check failed. Check logs with: docker-compose logs"
        exit 1
    fi
}

# Manual deployment
deploy_manual() {
    print_status "Deploying manually..."
    
    # Check Python version
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_status "Using Python $PYTHON_VERSION"
    
    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install/update dependencies
    print_status "Installing dependencies..."
    pip install -r requirements.txt
    
    # Run database migrations (if any)
    print_status "Running database setup..."
    cd terminal
    python3 -c "
from data.analytics_db import analytics_db
print('Database initialized')
"
    cd ..
    
    # Start the application
    print_status "Starting application..."
    cd terminal
    nohup python3 app.py > ../logs/app.log 2>&1 &
    APP_PID=$!
    echo $APP_PID > ../logs/app.pid
    cd ..
    
    # Wait for application to start
    sleep 10
    
    # Health check
    if curl -f http://localhost:8050/_alive &> /dev/null; then
        print_success "Manual deployment successful (PID: $APP_PID)"
    else
        print_error "Health check failed. Check logs in logs/app.log"
        exit 1
    fi
}

# Cloud deployment (placeholder for cloud providers)
deploy_cloud() {
    print_status "Cloud deployment not yet implemented..."
    print_warning "Please use Docker or manual deployment for now"
    exit 1
}

# Post-deployment setup
post_deployment() {
    print_status "Running post-deployment setup..."
    
    # Set up log rotation
    if [[ ! -f "/etc/logrotate.d/crypto-trading-terminal" ]]; then
        print_status "Setting up log rotation..."
        sudo tee /etc/logrotate.d/crypto-trading-terminal > /dev/null << EOF
$(pwd)/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
}
EOF
    fi
    
    # Set up monitoring (optional)
    if command -v systemctl &> /dev/null; then
        print_status "Setting up systemd service..."
        sudo tee /etc/systemd/system/crypto-trading-terminal.service > /dev/null << EOF
[Unit]
Description=Crypto Trading Terminal
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/terminal/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable crypto-trading-terminal
        print_success "Systemd service configured"
    fi
    
    print_success "Post-deployment setup completed"
}

# Health monitoring
health_check() {
    print_status "Running health checks..."
    
    # Check if application is responding
    if curl -f http://localhost:8050/_alive &> /dev/null; then
        print_success "Application health check passed"
    else
        print_error "Application health check failed"
        return 1
    fi
    
    # Check database connectivity
    cd terminal
    python3 -c "
from data.analytics_db import analytics_db
try:
    # Test database connection
    analytics_db.get_all_signals()
    print('Database connectivity check passed')
except Exception as e:
    print(f'Database connectivity check failed: {e}')
    exit(1)
"
    cd ..
    
    # Check disk space
    DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $DISK_USAGE -gt 80 ]]; then
        print_warning "Disk usage is ${DISK_USAGE}%. Consider cleaning up logs."
    fi
    
    print_success "All health checks passed"
}

# Main deployment function
main() {
    print_banner
    
    print_status "Starting deployment process..."
    print_status "Deployment type: $DEPLOYMENT_TYPE"
    print_status "Environment: $ENVIRONMENT"
    
    check_user
    pre_deployment_checks
    backup_existing
    
    # Create logs directory
    mkdir -p logs
    
    # Deploy based on type
    case $DEPLOYMENT_TYPE in
        "docker")
            deploy_docker
            ;;
        "manual")
            deploy_manual
            ;;
        "cloud")
            deploy_cloud
            ;;
        *)
            print_error "Invalid deployment type: $DEPLOYMENT_TYPE"
            print_status "Valid options: docker, manual, cloud"
            exit 1
            ;;
    esac
    
    post_deployment
    health_check
    
    print_success "Deployment completed successfully!"
    
    echo -e "\n${CYAN}Access your trading terminal:${NC}"
    echo -e "• ${GREEN}Trading Interface:${NC} http://localhost:8050"
    echo -e "• ${GREEN}Analytics Dashboard:${NC} http://localhost:8050/analytics"
    
    echo -e "\n${CYAN}Useful commands:${NC}"
    case $DEPLOYMENT_TYPE in
        "docker")
            echo -e "• ${GREEN}View logs:${NC} docker-compose logs -f"
            echo -e "• ${GREEN}Stop service:${NC} docker-compose down"
            echo -e "• ${GREEN}Restart service:${NC} docker-compose restart"
            ;;
        "manual")
            echo -e "• ${GREEN}View logs:${NC} tail -f logs/app.log"
            echo -e "• ${GREEN}Stop service:${NC} kill \$(cat logs/app.pid)"
            echo -e "• ${GREEN}Restart service:${NC} ./scripts/deploy.sh manual"
            ;;
    esac
    
    echo -e "\n${GREEN}Happy Trading! 🚀${NC}\n"
}

# Show usage information
show_usage() {
    echo "Usage: $0 [DEPLOYMENT_TYPE] [ENVIRONMENT]"
    echo ""
    echo "DEPLOYMENT_TYPE:"
    echo "  docker    - Deploy using Docker (recommended)"
    echo "  manual    - Deploy manually with Python"
    echo "  cloud     - Deploy to cloud provider (not implemented)"
    echo ""
    echo "ENVIRONMENT:"
    echo "  production - Production deployment (default)"
    echo "  staging    - Staging deployment"
    echo "  development - Development deployment"
    echo ""
    echo "Examples:"
    echo "  $0 docker production"
    echo "  $0 manual staging"
}

# Handle command line arguments
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    show_usage
    exit 0
fi

# Run main function
main "$@"
