# NiftyBot VPS Deployment Guide

Complete guide to deploy NiftyBot on a cloud VPS for 24/7 operation.

---

## 🎯 Why VPS?

| Issue | Laptop | VPS |
|-------|--------|-----|
| **Reliability** | ❌ Sleep/shutdown kills bot | ✅ Always running |
| **Stop-Loss Execution** | ❌ Missed if laptop sleeps | ✅ Always monitored |
| **Internet Connection** | ❌ WiFi drops = bot down | ✅ 99.9% uptime |
| **Power Supply** | ❌ Battery dies = bot down | ✅ Always powered |
| **Auto-Restart** | ❌ Manual restart needed | ✅ Auto-restarts on crash |
| **Cost** | Free (but risky) | $6/month (worth it!) |

---

## 📋 Pre-Deployment Checklist

- [ ] Kite API credentials ready (API key + access token)
- [ ] GitHub account (to clone repository)
- [ ] Credit card for VPS signup
- [ ] 30 minutes of free time

---

## 🚀 Deployment Steps

### **Step 1: Create VPS (10 minutes)**

#### **Option A: DigitalOcean (Recommended)**

1. Go to https://www.digitalocean.com
2. Sign up (get $200 credit for 60 days)
3. Click **Create** → **Droplets**
4. Choose:
   - **Image:** Ubuntu 22.04 LTS x64
   - **Plan:** Basic ($6/month)
   - **CPU:** Regular Intel with SSD (1GB RAM)
   - **Datacenter:** Bangalore, India (lowest latency)
   - **Authentication:** SSH key (recommended) or password
5. Click **Create Droplet**
6. **Note the IP address** (e.g., 165.22.xxx.xxx)

#### **Option B: AWS Lightsail**

1. Go to https://lightsail.aws.amazon.com
2. Create instance
3. Choose:
   - **Platform:** Linux/Unix
   - **Blueprint:** Ubuntu 22.04 LTS
   - **Plan:** $5/month (1GB RAM)
   - **Region:** Mumbai (ap-south-1)
4. Create instance
5. Note the IP address

---

### **Step 2: Connect to VPS (2 minutes)**

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Example:
ssh root@165.22.123.45

# First login, it will ask to verify fingerprint, type 'yes'
```

---

### **Step 3: Upload Code to VPS (5 minutes)**

#### **Method A: Git Clone (If repository is public)**

```bash
# On VPS:
apt install -y git
git clone https://github.com/venutrue/NiftyBot.git /opt/niftybot
cd /opt/niftybot
```

#### **Method B: SCP Upload (If repository is private)**

```bash
# On your laptop (in NiftyBot directory):
tar -czf niftybot.tar.gz \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.git' \
  --exclude='venv' \
  .

# Upload to VPS
scp niftybot.tar.gz root@your-vps-ip:/opt/

# On VPS:
cd /opt
tar -xzf niftybot.tar.gz
mv NiftyBot niftybot  # or whatever the extracted folder name is
```

---

### **Step 4: Run Setup Script (10 minutes)**

```bash
# On VPS:
cd /opt/niftybot/deploy
chmod +x vps_setup.sh
sudo ./vps_setup.sh

# Follow the prompts:
# - Wait for packages to install
# - Press Enter when code is uploaded
# - Edit .env with your Kite credentials
# - Press Enter to continue
```

---

### **Step 5: Configure Credentials (3 minutes)**

```bash
# Create .env file
cd /opt/niftybot
cp .env.example .env
nano .env

# Add your Kite credentials:
API_KEY=your_api_key_here
ACCESS_TOKEN=your_access_token_here
BROKER=kite

# Save: Ctrl+O, Enter
# Exit: Ctrl+X
```

---

### **Step 6: Start Bot (1 minute)**

```bash
# Start the bot
sudo systemctl start niftybot

# Check status
sudo systemctl status niftybot

# Should show: "active (running)"
```

---

### **Step 7: Monitor Bot (Ongoing)**

```bash
# View live logs
tail -f /var/log/niftybot.log

# View errors
tail -f /var/log/niftybot-error.log

# Check bot status
sudo systemctl status niftybot

# Restart bot
sudo systemctl restart niftybot

# Stop bot
sudo systemctl stop niftybot
```

---

## 🎛️ Management Commands

### **Daily Operations:**

```bash
# Check if bot is running
systemctl is-active niftybot

# View recent logs (last 50 lines)
tail -50 /var/log/niftybot.log

# Search logs for errors
grep ERROR /var/log/niftybot.log

# Search logs for trades
grep "ENTRY\|EXIT" /var/log/niftybot.log

# Monitor in real-time
tail -f /var/log/niftybot.log | grep --line-buffered "Signal\|ENTRY\|EXIT"
```

### **Updating Code:**

```bash
# Stop bot
sudo systemctl stop niftybot

# Pull latest code (if using git)
cd /opt/niftybot
git pull

# Or upload new code via SCP

# Restart bot
sudo systemctl start niftybot
```

### **Change Trading Mode:**

```bash
# Edit service file
sudo nano /etc/systemd/system/niftybot.service

# Change line:
ExecStart=/opt/niftybot/venv/bin/python3 run.py --paper --bot nifty,banknifty

# To (for live trading):
ExecStart=/opt/niftybot/venv/bin/python3 run.py --bot nifty,banknifty

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart niftybot
```

---

## 📊 Monitoring & Alerts

### **Setup Telegram Notifications (Optional)**

```bash
# Install additional package
source /opt/niftybot/venv/bin/activate
pip install python-telegram-bot

# Add to .env:
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Bot will send notifications on:
# - Trades executed
# - Errors encountered
# - Daily P&L summary
```

### **Setup Email Alerts:**

```bash
# Install mailutils
sudo apt install -y mailutils

# Create alert script
cat > /opt/niftybot/send_alert.sh <<'EOF'
#!/bin/bash
if ! systemctl is-active --quiet niftybot; then
    echo "NiftyBot is down!" | mail -s "NiftyBot Alert" your-email@gmail.com
fi
EOF

chmod +x /opt/niftybot/send_alert.sh

# Add to crontab (check every 15 minutes)
(crontab -l; echo "*/15 * * * * /opt/niftybot/send_alert.sh") | crontab -
```

---

## 🔒 Security Best Practices

### **1. Disable Root Login**

```bash
# Create new user
adduser trader
usermod -aG sudo trader

# Switch to new user
su - trader

# Disable root login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart sshd
```

### **2. Setup SSH Key Authentication**

```bash
# On your laptop:
ssh-keygen -t rsa -b 4096

# Copy public key to VPS
ssh-copy-id trader@your-vps-ip

# Disable password login
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### **3. Setup Fail2Ban (Auto-ban brute force)**

```bash
# Already installed by setup script
# Check status
sudo systemctl status fail2ban

# View banned IPs
sudo fail2ban-client status sshd
```

---

## 📈 Performance Optimization

### **Check Resource Usage:**

```bash
# View CPU and memory
htop

# Check disk space
df -h

# View bot process
ps aux | grep run.py
```

### **If Bot Uses Too Much Memory:**

```bash
# Edit service to limit memory
sudo nano /etc/systemd/system/niftybot.service

# Add under [Service]:
MemoryMax=512M

sudo systemctl daemon-reload
sudo systemctl restart niftybot
```

---

## 🆘 Troubleshooting

### **Bot Won't Start:**

```bash
# Check logs for errors
sudo journalctl -u niftybot -n 50

# Check if Python works
/opt/niftybot/venv/bin/python3 --version

# Test bot manually
cd /opt/niftybot
source venv/bin/activate
python run.py --status
```

### **Bot Crashes Frequently:**

```bash
# Check error logs
tail -100 /var/log/niftybot-error.log

# Check if Kite connection is valid
cd /opt/niftybot
source venv/bin/activate
python -c "from executor.trade_executor import KiteExecutor; e = KiteExecutor(); print(e.connect())"
```

### **Can't SSH into VPS:**

- Check if VPS is running (DigitalOcean console)
- Verify IP address is correct
- Check if firewall allows SSH (port 22)
- Try from different network (your office WiFi might block SSH)

---

## 💰 Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| **VPS** | $6/month | DigitalOcean Basic Droplet |
| **Kite API** | Free | Included with Zerodha account |
| **Domain (optional)** | $12/year | For web dashboard |
| **Total** | **~$6-7/month** | Worth it for peace of mind! |

---

## ✅ Post-Deployment Checklist

After deployment, verify:

- [ ] Bot starts automatically on VPS reboot
- [ ] Logs are being written to /var/log/niftybot.log
- [ ] Paper trades are executing correctly
- [ ] Stop-losses are being honored
- [ ] Bot auto-restarts if it crashes
- [ ] You can SSH into VPS from your laptop
- [ ] Firewall is enabled and configured
- [ ] Fail2ban is protecting against brute force

---

## 🎯 Going Live Checklist

Before switching to live trading:

- [ ] **Test in paper mode for at least 1 week**
- [ ] Verify all trades are being logged
- [ ] Verify stop-losses work correctly
- [ ] Verify daily P&L calculations are accurate
- [ ] Check bot behavior during market close
- [ ] Test manual stop (Ctrl+C) from SSH session
- [ ] Verify bot reconnects after VPS reboot
- [ ] Set up monitoring alerts (Telegram/Email)
- [ ] Have emergency shutdown plan ready
- [ ] Start with small capital (10-20k)

---

## 📞 Support

If you encounter issues:

1. Check logs: `tail -f /var/log/niftybot.log`
2. Check bot status: `systemctl status niftybot`
3. Restart bot: `sudo systemctl restart niftybot`
4. Check GitHub issues: https://github.com/venutrue/NiftyBot/issues

---

**Remember:** Always test in paper mode first. Never risk real money until you're 100% confident the bot works correctly on the VPS!
