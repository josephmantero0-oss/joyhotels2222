# AWS EC2 Deployment Guide - Ubuntu

## 🖥️ Part 1: Launching Your EC2 Instance

Since you have an AWS account, you can use the **Free Tier**.

### Step 1: Launch an Instance
1. Go to the **AWS Management Console** and search for **EC2**.
2. Click **Launch Instance**.
3. **Name:** `JoyHotels-Server`
4. **AMI (OS):** Select **Ubuntu 22.04 LTS** (or 24.04 LTS). Make sure it says `Free tier eligible`.
5. **Instance Type:** `t2.micro` (Free tier eligible).

### Step 2: Create a Key Pair (.pem)
1. Scroll down to **Key pair (login)**.
2. Click **Create new key pair**.
3. Name it `joyhotels-key` and select **.pem** format.
4. Click **Create** and it will download to your computer. **Keep this file extremely safe!**

### Step 3: Network & Security Group (Firewall)
1. Under **Network settings**, check these boxes:
   - Allow SSH traffic from Anywhere (Port 22)
   - Allow HTTP traffic from the internet (Port 80)
   - Allow HTTPS traffic from the internet (Port 443)
2. Click **Launch instance**.

### Step 4: Get Your Elastic IP (Optional but Recommended)
By default, AWS changes your IP every time you restart the server. To keep the same IP:
1. On the left menu, go to **Elastic IPs**.
2. Click **Allocate Elastic IP address** -> **Allocate**.
3. Select the new IP, click **Actions** -> **Associate Elastic IP address**.
4. Choose your `JoyHotels-Server` instance and click **Associate**.
This IP address is now permanent.

---

## 🔐 Part 2: SSH - Connecting to Your Server

AWS uses the `.pem` key instead of a password for security.

### Connecting from Windows
Open **PowerShell** in the folder where your `.pem` file was downloaded (e.g., Downloads).

1. Fix permissions for the key (required by AWS on Windows):
```powershell
icacls.exe joyhotels-key.pem /reset
icacls.exe joyhotels-key.pem /grant:r "$($env:USERNAME):(r)"
icacls.exe joyhotels-key.pem /inheritance:r
```

2. Connect via SSH:
```powershell
ssh -i joyhotels-key.pem ubuntu@YOUR_ELASTIC_IP
```
> [!NOTE]
> The default username for Ubuntu on AWS EC2 is `ubuntu`, not `root`.

---

## 🚀 Part 3: Deploying the App (Similar to Hostinger)

Since AWS EC2 runs Ubuntu, the next steps are nearly identical to traditional VPS hosting!

### 1. System Update
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install Python Environment & Nginx
```bash
sudo apt install python3 python3-pip python3-venv nginx -y
```

### 3. Upload Your Code
Since AWS uses a key file, uploading via SCP from another PowerShell window on your PC looks like this:
```powershell
scp -i C:\Path\To\joyhotels-key.pem -r C:\Users\JOY\OneDrive\Desktop\joyhotels\* ubuntu@YOUR_ELASTIC_IP:/home/ubuntu/joyhotels/
```
*(Alternatively, you can push your code to GitHub and clone it directly on the server!).*

Run these commands on the server to prepare the directory (If uploading directly via SCP):
```bash
mkdir -p /home/ubuntu/joyhotels
```

### 4. Setup Virtual Environment
```bash
cd /home/ubuntu/joyhotels
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### 5. Setup Gunicorn Systemd Service
```bash
sudo nano /etc/systemd/system/joyhotels.service
```
Paste this (note the user is `ubuntu`):
```ini
[Unit]
Description=JoyHotels Gunicorn Server
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/joyhotels
Environment="PATH=/home/ubuntu/joyhotels/venv/bin"
ExecStart=/home/ubuntu/joyhotels/venv/bin/gunicorn --workers 3 --bind unix:joyhotels.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl start joyhotels
sudo systemctl enable joyhotels
```

### 6. Setup Nginx (Reverse Proxy)
```bash
sudo nano /etc/nginx/sites-available/joyhotels
```
Paste this config:
```nginx
server {
    listen 80;
    server_name YOUR_ELASTIC_IP_OR_DOMAIN;

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/ubuntu/joyhotels/joyhotels.sock;
    }

    location /static {
        alias /home/ubuntu/joyhotels/static;
        expires 30d;
    }
}
```

Enable Nginx site:
```bash
sudo ln -s /etc/nginx/sites-available/joyhotels /etc/nginx/sites-enabled
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

Your app is now live on AWS EC2!
