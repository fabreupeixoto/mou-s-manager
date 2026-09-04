# USJ MOU Dashboard - Production Deployment Guide

## Prerequisites

- Ubuntu/Debian server (recommended) or any Linux distribution
- Domain name or server IP address
- Root or sudo access

---

## Step 1: Install Dependencies on Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python, pip, nginx, and git
sudo apt install -y python3 python3-pip python3-venv nginx git

# Install wkhtmltopdf (for PDF export)
sudo apt install -y wkhtmltopdf
```

---

## Step 2: Copy Project to Server

### Option A: Using Git (Recommended)

```bash
# Create directory
sudo mkdir -p /var/www/mou-dashboard
sudo chown $USER:$USER /var/www/mou-dashboard

# Clone your repository
cd /var/www/mou-dashboard
git clone <your-repo-url> .
```

### Option B: Using SCP

```bash
# From your local machine
cd /Users/Francisco/Documents/Mous/mou-dashboard
scp -r * user@your-server-ip:/var/www/mou-dashboard/
```

---

## Step 3: Set Up Python Virtual Environment

```bash
cd /var/www/mou-dashboard

# Create virtual environment
python3 -m venv venv

# Activate and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-prod.txt
```

---

## Step 4: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit with your production settings
nano .env
```

**Production .env:**
```env
# Google Sheets (optional)
GOOGLE_SERVICE_ACCOUNT_FILE=/var/www/mou-dashboard/credentials.json
GOOGLE_SPREADSHEET_ID=19u0zXbaZqOdBNkuNEuIHys7UXggGN73-

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_TO=recipient@example.com

# Flask Production Settings
SECRET_KEY=<generate-random-key>
FLASK_ENV=production

# Generate a secret key with: python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Step 5: Set Up Database

```bash
# Initialize the database
source venv/bin/activate
python3 -c "from app import init_db, app; app.app_context().push(); init_db()"

# Or import from CSV
python3 import_csv.py /path/to/your/file.csv
```

---

## Step 6: Configure Gunicorn Systemd Service

```bash
# Copy service file
sudo cp mou-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable mou-dashboard
sudo systemctl start mou-dashboard

# Check status
sudo systemctl status mou-dashboard
```

---

## Step 7: Configure nginx

```bash
# Copy nginx config
sudo cp nginx.conf /etc/nginx/sites-available/mou-dashboard

# Edit with your domain/IP
sudo nano /etc/nginx/sites-available/mou-dashboard
# Change: server_name your-domain.com;

# Enable site
sudo ln -s /etc/nginx/sites-available/mou-dashboard /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
```

---

## Step 8: Configure Firewall

```bash
# Allow HTTP and HTTPS
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH

# Enable firewall (if not already enabled)
sudo ufw enable

# Check status
sudo ufw status
```

---

## Step 9: Set Up SSL (Recommended)

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal is configured automatically
# Test renewal with:
sudo certbot renew --dry-run
```

---

## Step 10: Verify Deployment

1. **Check services:**
   ```bash
   sudo systemctl status mou-dashboard
   sudo systemctl status nginx
   ```

2. **Check logs:**
   ```bash
   # App logs
   sudo journalctl -u mou-dashboard -f
   
   # nginx logs
   sudo tail -f /var/log/nginx/mou-dashboard.access.log
   sudo tail -f /var/log/nginx/mou-dashboard.error.log
   ```

3. **Test in browser:**
   - http://your-domain.com (or http://your-server-ip)
   - https://your-domain.com (if SSL configured)

---

## Maintenance Commands

```bash
# Restart app
sudo systemctl restart mou-dashboard

# Restart nginx
sudo systemctl restart nginx

# View logs
sudo journalctl -u mou-dashboard --since "1 hour ago"

# Update code (if using git)
cd /var/www/mou-dashboard
sudo git pull
sudo systemctl restart mou-dashboard

# Backup database
sudo cp /var/www/mou-dashboard/mou.db /backup/mou-backup-$(date +%Y%m%d).db
```

---

## Troubleshooting

### App won't start
```bash
# Check service status
sudo systemctl status mou-dashboard

# Check logs
sudo journalctl -u mou-dashboard -n 50 --no-pager

# Test gunicorn manually
cd /var/www/mou-dashboard
source venv/bin/activate
gunicorn --workers 3 --bind 0.0.0.0:5000 app:app
```

### nginx errors
```bash
# Test config
sudo nginx -t

# Check error log
sudo tail -f /var/log/nginx/mou-dashboard.error.log
```

### Permission issues
```bash
# Fix ownership
sudo chown -R www-data:www-data /var/www/mou-dashboard
sudo chmod -R 755 /var/www/mou-dashboard
```

---

## Cloud Platform Options

### DigitalOcean App Platform (Simpler)
1. Push code to GitHub
2. Connect DigitalOcean App Platform
3. Deploy automatically

### Heroku
```bash
# Add to project:
# Procfile: web: gunicorn app:app
# runtime.txt: python-3.12.0

heroku create mou-dashboard
git push heroku main
heroku open
```

### PythonAnywhere
1. Sign up at pythonanywhere.com
2. Upload code
3. Configure WSGI
4. Set up virtual environment

---

## Security Checklist

- [ ] Change SECRET_KEY to random value
- [ ] Enable HTTPS/SSL
- [ ] Configure firewall (UFW)
- [ ] Use strong passwords
- [ ] Keep system updated: `sudo apt update && sudo apt upgrade`
- [ ] Regular database backups
- [ ] Monitor logs regularly
- [ ] Limit email notifications to necessary recipients

---

## Estimated Costs

| Service | Monthly Cost |
|---------|-------------|
| DigitalOcean Droplet (1GB) | $6/month |
| Linode Nanode (1GB) | $5/month |
| AWS EC2 t2.micro | ~$9/month |
| Heroku (Basic) | $7/month |
| PythonAnywhere (Developer) | $5/month |

---

## Need Help?

Check logs first! Most issues are visible in:
- `/var/log/nginx/mou-dashboard.error.log`
- `sudo journalctl -u mou-dashboard`
