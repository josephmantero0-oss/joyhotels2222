# VPS Deployment Guide - Hostinger Ubuntu

## 🖥️ What is a VPS?

A **Virtual Private Server (VPS)** is your own private computer in the cloud. Unlike shared hosting:

| Shared Hosting | VPS |
|----------------|-----|
| Limited control | Full root access |
| Pre-installed software | Install anything |
| Shared resources | Dedicated RAM/CPU |
| Managed by host | You manage it |

> [!IMPORTANT]
> **You are responsible for security, updates, and maintenance.** This guide will teach you how.

---

## 🔧 Part 1: Hostinger VPS Setup

### Step 1: Purchase & Access

1. Go to [Hostinger VPS](https://www.hostinger.in/vps-hosting)
2. Choose a plan (KVM 1 with 4GB RAM is sufficient)
3. Select **Ubuntu 22.04** as your OS
4. After purchase, go to **hPanel → VPS → Manage**

### Step 2: Get Your Credentials

In hPanel, you'll see:
- **IP Address**: e.g., `123.45.67.89`
- **Root Password**: (set during setup)
- **SSH Port**: Usually `22`

---

## 🔐 Part 2: SSH - Connecting to Your Server

### What is SSH?
SSH (Secure Shell) is how you remotely control your server via command line.

### Connecting from Windows

**Option A: Windows Terminal (Recommended)**
```powershell
ssh root@YOUR_IP_ADDRESS
```

**Option B: PuTTY**
1. Download [PuTTY](https://www.putty.org/)
2. Enter IP, Port 22, click Open
3. Login as `root`

### First Login
```bash
# You'll see something like:
Welcome to Ubuntu 22.04 LTS
root@vps-12345:~# _
```

> [!TIP]
> The `#` means you're root (admin). Regular users see `$`.

---

## 🐧 Part 3: Linux Basics

### Essential Commands

```bash
# Navigation
pwd                    # Print current directory
ls                     # List files
ls -la                 # List ALL files (including hidden)
cd /path/to/folder     # Change directory
cd ..                  # Go up one level
cd ~                   # Go to home directory

# File Operations
cat filename           # View file content
nano filename          # Edit file (Ctrl+X to exit)
cp file1 file2         # Copy
mv file1 file2         # Move/Rename
rm filename            # Delete file
rm -rf folder          # Delete folder (DANGEROUS!)

# System
sudo command           # Run as admin
apt update            # Update package list
apt upgrade           # Upgrade installed packages
apt install package   # Install new package
systemctl status X    # Check if service X is running
systemctl restart X   # Restart service X

# Disk & Memory
df -h                 # Disk space
free -h               # RAM usage
htop                  # Live system monitor (apt install htop)
```

### File Permissions
```bash
# Format: -rwxrwxrwx (owner-group-others)
chmod 755 file        # Owner: full, Others: read+execute
chmod 600 file        # Owner: read+write only (for secrets)
chown user:group file # Change ownership
```

---

## 🛡️ Part 4: Security Setup (DO THIS FIRST!)

### Step 1: Update System
```bash
apt update && apt upgrade -y
```

### Step 2: Create Non-Root User
```bash
# Create user
adduser joseph              # Replace with your name
usermod -aG sudo joseph     # Give admin rights

# Test login in NEW terminal before proceeding!
ssh joseph@YOUR_IP
```

### Step 3: Disable Root Login
```bash
sudo nano /etc/ssh/sshd_config

# Find and change:
PermitRootLogin no

# Save and restart SSH
sudo systemctl restart sshd
```

### Step 4: Setup Firewall
```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh          # Port 22
sudo ufw allow http         # Port 80
sudo ufw allow https        # Port 443
sudo ufw enable
sudo ufw status
```

### Step 5: Fail2Ban (Blocks Brute Force)
```bash
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 🐍 Part 5: Python Environment

### Install Python & Tools
```bash
sudo apt install python3 python3-pip python3-venv -y
```

### Create App Directory
```bash
sudo mkdir -p /var/www/joyhotels
sudo chown $USER:$USER /var/www/joyhotels
cd /var/www/joyhotels
```

### Upload Your Code

**Option A: Git (Recommended)**
```bash
git clone https://github.com/YOUR_REPO.git .
```

**Option B: SCP (From your Windows)**
```powershell
scp -r C:\Users\JOY\OneDrive\Desktop\joyhotels\* joseph@YOUR_IP:/var/www/joyhotels/
```

### Setup Virtual Environment
```bash
cd /var/www/joyhotels
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn        # Production server
```

---

## 🌐 Part 6: Gunicorn - Production Server

### What is Gunicorn?
Flask's built-in server is for development only. Gunicorn handles production traffic.

### Test Gunicorn
```bash
cd /var/www/joyhotels
source venv/bin/activate
gunicorn --bind 0.0.0.0:5000 wsgi:app
```

### Create Systemd Service
```bash
sudo nano /etc/systemd/system/joyhotels.service
```

Paste this:
```ini
[Unit]
Description=JoyHotels Gunicorn Server
After=network.target

[Service]
User=joseph
Group=www-data
WorkingDirectory=/var/www/joyhotels
Environment="PATH=/var/www/joyhotels/venv/bin"
ExecStart=/var/www/joyhotels/venv/bin/gunicorn --workers 3 --bind unix:joyhotels.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl start joyhotels
sudo systemctl enable joyhotels
sudo systemctl status joyhotels   # Should show "active (running)"
```

---

## 🔀 Part 7: Nginx - Reverse Proxy

### What is Nginx?
Nginx sits in front of Gunicorn, handling HTTPS, static files, and load balancing.

### Install Nginx
```bash
sudo apt install nginx -y
```

### Configure Site
```bash
sudo nano /etc/nginx/sites-available/joyhotels
```

Paste this:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;  # Or use IP

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/joyhotels/joyhotels.sock;
    }

    location /static {
        alias /var/www/joyhotels/static;
        expires 30d;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/joyhotels /etc/nginx/sites-enabled
sudo nginx -t                    # Test config
sudo systemctl restart nginx
```

---

## 🔒 Part 8: SSL Certificate (HTTPS)

### Using Let's Encrypt (Free!)
```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow the prompts. Certbot will:
1. Verify domain ownership
2. Generate certificate
3. Auto-configure Nginx
4. Setup auto-renewal

Test renewal:
```bash
sudo certbot renew --dry-run
```

---

## 📋 Part 9: Maintenance Commands

### Daily Operations
```bash
# Check app status
sudo systemctl status joyhotels

# View logs
sudo journalctl -u joyhotels -f      # Live logs
sudo journalctl -u joyhotels --since "1 hour ago"

# Restart after code changes
sudo systemctl restart joyhotels

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### Updating Your App
```bash
cd /var/www/joyhotels
git pull                              # If using Git
source venv/bin/activate
pip install -r requirements.txt       # If deps changed
sudo systemctl restart joyhotels
```

### SaaS Migration (New!)
If you are moving from the old version to the new SaaS version, you **MUST** run the migration script on the VPS:
```bash
cd /var/www/joyhotels
source venv/bin/activate
python3 migrate_saas.py
sudo systemctl restart joyhotels
```

> [!IMPORTANT]
> **Super Admin Login**:
> Once updated, use `admin_joy` / `admin123` to access the platform management dashboard.

### Backup Database
```bash
# Manual backup
cp /var/www/joyhotels/hotel.db ~/backups/hotel_$(date +%Y%m%d).db

# Automated daily backup (add to crontab)
crontab -e
# Add this line:
0 2 * * * cp /var/www/joyhotels/hotel.db /home/joseph/backups/hotel_$(date +\%Y\%m\%d).db
```

---

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| 502 Bad Gateway | Check if Gunicorn is running: `sudo systemctl status joyhotels` |
| Permission denied | Fix socket permissions: `sudo chmod 755 /var/www/joyhotels` |
| Static files 404 | Check Nginx `location /static` path |
| SSL not working | Run `sudo certbot --nginx` again |
| Can't SSH | Check firewall: `sudo ufw status`, ensure port 22 allowed |

---

## 🎯 Quick Reference Card

```bash
# Start/Stop/Restart App
sudo systemctl start joyhotels
sudo systemctl stop joyhotels
sudo systemctl restart joyhotels

# View Logs
sudo journalctl -u joyhotels -f

# Reload Nginx
sudo systemctl reload nginx

# Check Everything
sudo systemctl status joyhotels nginx

# Emergency: If locked out
# Use Hostinger's VNC console in hPanel
```

---

> [!CAUTION]
> **Never share your SSH password or private keys!**
> If compromised, your entire server is at risk.
