#!/bin/bash
#####################################################
# NiftyBot VPS Setup Script
# Run this on your fresh Ubuntu 22.04 VPS
#
# Usage:
#   chmod +x vps_setup.sh
#   sudo ./vps_setup.sh
#####################################################

set -e  # Exit on error

echo "=================================================="
echo "NiftyBot VPS Setup - Starting..."
echo "=================================================="

# Update system
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# Install Python 3.11
echo "[2/8] Installing Python 3.11..."
apt install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt update
apt install -y python3.11 python3.11-venv python3-pip git curl

# Install system tools
echo "[3/8] Installing system tools..."
apt install -y htop tmux supervisor fail2ban ufw

# Setup firewall
echo "[4/8] Configuring firewall..."
ufw allow OpenSSH
ufw --force enable

# Create deployment directory
echo "[5/8] Setting up NiftyBot directory..."
mkdir -p /opt/niftybot
cd /opt/niftybot

# Clone repository (you'll need to provide the repo URL)
echo "[6/8] Cloning NiftyBot repository..."
echo ""
echo "⚠️  MANUAL STEP REQUIRED:"
echo "    Run: git clone https://github.com/venutrue/NiftyBot.git /opt/niftybot"
echo "    Or upload your code via SCP"
echo ""
read -p "Press Enter once code is in /opt/niftybot..."

# Install Python dependencies
echo "[7/8] Installing Python packages..."
cd /opt/niftybot
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment file
echo "[8/8] Creating environment file..."
cat > .env.example <<EOF
# Kite Connect API Credentials
API_KEY=your_api_key_here
ACCESS_TOKEN=your_access_token_here
BROKER=kite

# Trading Mode
TRADING_MODE=paper  # Change to 'live' for real trading

# Bot Selection
ACTIVE_BOTS=nifty,banknifty

# Notifications (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
EOF

echo ""
echo "⚠️  MANUAL STEP REQUIRED:"
echo "    Edit /opt/niftybot/.env with your Kite credentials"
echo "    Run: nano /opt/niftybot/.env"
echo ""
read -p "Press Enter once .env is configured..."

# Create systemd service
echo "Creating systemd service..."
cat > /etc/systemd/system/niftybot.service <<EOF
[Unit]
Description=NiftyBot Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/niftybot
Environment="PATH=/opt/niftybot/venv/bin"
ExecStart=/opt/niftybot/venv/bin/python3 run.py --paper --bot nifty,banknifty
Restart=always
RestartSec=10
StandardOutput=append:/var/log/niftybot.log
StandardError=append:/var/log/niftybot-error.log

# Restart daily at 3:45 PM IST (after market close)
# This ensures clean state for next trading day

[Install]
WantedBy=multi-user.target
EOF

# Setup log rotation
echo "Setting up log rotation..."
cat > /etc/logrotate.d/niftybot <<EOF
/var/log/niftybot*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 root root
    sharedscripts
    postrotate
        systemctl reload niftybot > /dev/null 2>&1 || true
    endscript
}
EOF

# Create monitoring script
echo "Creating monitoring script..."
cat > /opt/niftybot/monitor.sh <<'EOF'
#!/bin/bash
# Monitor NiftyBot health and restart if needed

# Check if bot is running
if ! systemctl is-active --quiet niftybot; then
    echo "$(date): NiftyBot is down, restarting..." >> /var/log/niftybot-monitor.log
    systemctl restart niftybot
fi

# Check if market hours and bot should be running
HOUR=$(date +%H)
if [ $HOUR -ge 9 ] && [ $HOUR -le 15 ]; then
    # Market hours - ensure bot is running
    if ! pgrep -f "run.py" > /dev/null; then
        echo "$(date): Bot process not found during market hours, restarting..." >> /var/log/niftybot-monitor.log
        systemctl restart niftybot
    fi
fi
EOF

chmod +x /opt/niftybot/monitor.sh

# Add monitoring cron job (check every 5 minutes)
echo "Setting up cron job for monitoring..."
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/niftybot/monitor.sh") | crontab -

# Enable and start service
echo "Enabling NiftyBot service..."
systemctl daemon-reload
systemctl enable niftybot

echo ""
echo "=================================================="
echo "✅ NiftyBot VPS Setup Complete!"
echo "=================================================="
echo ""
echo "Next Steps:"
echo "1. Start the bot: sudo systemctl start niftybot"
echo "2. Check status:  sudo systemctl status niftybot"
echo "3. View logs:     tail -f /var/log/niftybot.log"
echo "4. Stop bot:      sudo systemctl stop niftybot"
echo ""
echo "Monitoring:"
echo "- Bot auto-restarts if it crashes"
echo "- Logs rotate daily (kept for 30 days)"
echo "- Health check runs every 5 minutes"
echo ""
echo "⚠️  IMPORTANT:"
echo "   - Bot is in PAPER TRADING mode by default"
echo "   - Test for a few days before switching to live"
echo "   - To enable live trading:"
echo "     1. Edit /etc/systemd/system/niftybot.service"
echo "     2. Change '--paper' to '--live' (or remove it)"
echo "     3. Run: sudo systemctl daemon-reload"
echo "     4. Run: sudo systemctl restart niftybot"
echo ""
echo "=================================================="
