#!/bin/bash
#####################################################
# NiftyBot Management Script
# Quick commands for managing your deployed bot
#
# Usage:
#   ./manage.sh <command>
#####################################################

LOGFILE="/var/log/niftybot.log"
ERRORLOG="/var/log/niftybot-error.log"

case "$1" in
    start)
        echo "Starting NiftyBot..."
        sudo systemctl start niftybot
        sudo systemctl status niftybot
        ;;

    stop)
        echo "Stopping NiftyBot..."
        sudo systemctl stop niftybot
        echo "Bot stopped."
        ;;

    restart)
        echo "Restarting NiftyBot..."
        sudo systemctl restart niftybot
        sudo systemctl status niftybot
        ;;

    status)
        sudo systemctl status niftybot
        ;;

    logs)
        echo "Showing last 50 lines of logs (Ctrl+C to exit)..."
        tail -50 $LOGFILE
        ;;

    live)
        echo "Following live logs (Ctrl+C to exit)..."
        tail -f $LOGFILE
        ;;

    errors)
        echo "Showing recent errors..."
        tail -50 $ERRORLOG
        ;;

    trades)
        echo "Showing recent trades..."
        grep -E "ENTRY|EXIT|Signal" $LOGFILE | tail -20
        ;;

    pnl)
        echo "Today's P&L summary..."
        grep "P&L" $LOGFILE | tail -20
        ;;

    positions)
        echo "Checking active positions..."
        grep "Position" $LOGFILE | tail -10
        ;;

    update)
        echo "Updating NiftyBot code..."
        sudo systemctl stop niftybot
        cd /opt/niftybot
        git pull
        source venv/bin/activate
        pip install -r requirements.txt --upgrade
        sudo systemctl start niftybot
        echo "Update complete!"
        ;;

    paper)
        echo "Switching to PAPER trading mode..."
        sudo sed -i 's/ExecStart=.*/ExecStart=\/opt\/niftybot\/venv\/bin\/python3 run.py --paper --bot nifty,banknifty/' /etc/systemd/system/niftybot.service
        sudo systemctl daemon-reload
        sudo systemctl restart niftybot
        echo "✅ Switched to PAPER mode"
        ;;

    live-mode)
        echo "⚠️  WARNING: Switching to LIVE trading mode!"
        read -p "Are you sure? This will trade with REAL MONEY! (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            sudo sed -i 's/ExecStart=.*/ExecStart=\/opt\/niftybot\/venv\/bin\/python3 run.py --bot nifty,banknifty/' /etc/systemd/system/niftybot.service
            sudo systemctl daemon-reload
            sudo systemctl restart niftybot
            echo "🔴 Switched to LIVE mode - REAL MONEY AT RISK!"
        else
            echo "Cancelled."
        fi
        ;;

    monitor)
        echo "Real-time trade monitoring (Ctrl+C to exit)..."
        tail -f $LOGFILE | grep --line-buffered -E "Signal|ENTRY|EXIT|P&L"
        ;;

    health)
        echo "=== NiftyBot Health Check ==="
        echo ""
        echo "Service Status:"
        systemctl is-active niftybot && echo "✅ Running" || echo "❌ Stopped"
        echo ""
        echo "Last 5 log entries:"
        tail -5 $LOGFILE
        echo ""
        echo "Recent errors (last 5):"
        tail -5 $ERRORLOG
        echo ""
        echo "Disk space:"
        df -h / | tail -1
        echo ""
        echo "Memory usage:"
        free -h | grep Mem
        ;;

    backup)
        echo "Creating backup..."
        BACKUP_DIR="/opt/niftybot-backups"
        mkdir -p $BACKUP_DIR
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        tar -czf "$BACKUP_DIR/niftybot_$TIMESTAMP.tar.gz" \
            -C /opt/niftybot \
            --exclude='venv' \
            --exclude='__pycache__' \
            --exclude='*.pyc' \
            .
        echo "✅ Backup created: $BACKUP_DIR/niftybot_$TIMESTAMP.tar.gz"
        ;;

    help|*)
        echo "NiftyBot Management Commands:"
        echo ""
        echo "  start       - Start the bot"
        echo "  stop        - Stop the bot"
        echo "  restart     - Restart the bot"
        echo "  status      - Show bot status"
        echo ""
        echo "  logs        - Show recent logs"
        echo "  live        - Follow live logs"
        echo "  errors      - Show recent errors"
        echo "  trades      - Show recent trades"
        echo "  pnl         - Show P&L summary"
        echo "  positions   - Show active positions"
        echo "  monitor     - Real-time trade monitoring"
        echo ""
        echo "  update      - Pull latest code and restart"
        echo "  paper       - Switch to paper trading"
        echo "  live-mode   - Switch to live trading (⚠️ REAL MONEY)"
        echo ""
        echo "  health      - Run health check"
        echo "  backup      - Create backup of code"
        echo "  help        - Show this help"
        echo ""
        ;;
esac
