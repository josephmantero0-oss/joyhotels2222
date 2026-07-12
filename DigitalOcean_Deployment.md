# DigitalOcean Droplet Deployment Guide for JoyHotels ($4 Plan)

Deploying your Flask application to a $4/month DigitalOcean Droplet is a great, cost-effective choice. The $4 plan provides 512MB RAM, 1 shared CPU, 10GB NVMe SSD, and 500GB outbound transfer, which is sufficient for light traffic or personal use. We will use **Ubuntu 24.04 (or 22.04) LTS**, **Gunicorn**, and **Nginx**.

## Step 1: Create the Droplet

1. Log in to [DigitalOcean](https://cloud.digitalocean.com/).
2. Click **Create -> Droplets**.
3. **Region**: Choose the region closest to your target users (e.g., New York, London, Bangalore).
4. **Choose an image**: Select **Ubuntu 22.04 LTS** (or 24.04 LTS).
5. **Choose Size**: Under **Shared CPU**, select **Basic**. Keep scrolling down and select the **$4/mo** option (512MB RAM, 10GB SSD, 1 vCPU).
6. **Authentication Method**: It is highly recommended to use **SSH Keys** for better security. If you don't have one, you can click "New SSH Key" and follow the instructions to generate one, or select **Password** and create a strong root password.
7. **Hostname**: Give your droplet a name, like `joyhotels-droplet`.
8. Click **Create Droplet**.

## Step 2: Connect to Your Droplet

Once the droplet is created, look for its **IPv4 address** (e.g., `192.168.1.1`).

Open a terminal or command prompt and connect via SSH:

```bash
ssh root@YOUR_DROPLET_IP
```
*(If you used a password, enter it when prompted.)*

## Step 3: Install Required Dependencies

Update the underlying system and install Python, pip, Nginx, and Git:

```bash
apt update && apt upgrade -y
apt install python3-pip python3-dev build-essential libssl-dev libffi-dev python3-setuptools python3-venv nginx git -y
```

## Step 4: Clone Your Project and Set Up the Environment

Let's place your project in `/var/www/joyhotels`.

```bash
# Create directory
mkdir -p /var/www/joyhotels
cd /var/www/joyhotels

# You can upload your code using Git (if on GitHub) or SCP/SFTP from your local machine.
# If using git:
# git clone YOUR_GITHUB_REPO_URL .

# IF NOT USING GIT (Uploading manually):
# On your LOCAL machine (Windows), open a new PowerShell and run:
# scp -r C:\Users\JOY\OneDrive\Desktop\joyhotels\* root@YOUR_DROPLET_IP:/var/www/joyhotels/
```

After uploading your files to `/var/www/joyhotels`:

```bash
cd /var/www/joyhotels

# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Install the Python dependencies (includes Flask and gunicorn)
pip install -r requirements.txt
pip install gunicorn
```

*(Note: If you have a `.env` file locally with API keys, make sure to create it on the server too: `nano .env` server-side, paste the contents, and save).*

## Step 5: Configure Gunicorn as a Systemd Service

We need to make sure the app starts automatically when the droplet boots and if it crashes.

Notice you already have a `joyhotels.service` file in your repository, but let's create it in the correct system location:

```bash
nano /etc/systemd/system/joyhotels.service
```

Add the following (adjust `WorkingDirectory` if you put your app somewhere else):

```ini
[Unit]
Description=Gunicorn instance to serve JoyHotels
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/joyhotels
Environment="PATH=/var/www/joyhotels/.venv/bin"
# $4 droplets have limited RAM, so we use max 2 workers to save memory
ExecStart=/var/www/joyhotels/.venv/bin/gunicorn --workers 2 --bind unix:joyhotels.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```

Save and close the file (`Ctrl+O`, `Enter`, `Ctrl+X`).

Now start and enable the Gunicorn service:

```bash
systemctl start joyhotels
systemctl enable joyhotels
```

Check the status to ensure it's running:
```bash
systemctl status joyhotels
```

## Step 6: Configure Nginx to Proxy Requests

Now we configure Nginx to pass web traffic to Gunicorn.

```bash
nano /etc/nginx/sites-available/joyhotels
```

Paste the following configuration:

```nginx
server {
    listen 80;
    server_name YOUR_DROPLET_IP; # Or your domain like joyhotels.com if you have one

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/joyhotels/joyhotels.sock;
    }
}
```

Save and close the file.

Enable the configuration by linking it to `sites-enabled`:

```bash
ln -s /etc/nginx/sites-available/joyhotels /etc/nginx/sites-enabled
```

Test the Nginx configuration for syntax errors:

```bash
nginx -t
```
*(You should see "syntax is ok" and "test is successful")*

Restart Nginx:

```bash
systemctl restart nginx
```

## Step 7: Adjust the Firewall

DigitalOcean droplets should be secured using a firewall (UFW). Allow Nginx and SSH traffic:

```bash
ufw allow 'Nginx Full'
ufw allow OpenSSH
ufw enable
# Type 'y' when it warns you that it might disrupt existing ssh connections
```

## Step 8: Done!

You should now be able to view your application by navigating to your Droplet's IP address in your web browser:

`http://YOUR_DROPLET_IP/`

---
**Note about the $4 Droplet / Memory constraints:**
Since the $4 droplet only has 512MB of RAM, it is recommended to add a Swap File. Otherwise, `pip install` or your web server running out of memory might cause the instance to freeze. 

Run these commands to add 1GB of swap memory:
```bash
fallocate -l 1G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```
