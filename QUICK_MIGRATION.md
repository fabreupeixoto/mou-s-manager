# 🚀 Quick Migration Guide

## Package: `mou-dashboard-deploy.zip` (59 KB)

---

## ✅ What's Included

- Complete Flask application with all features
- Email notifications (tested & working)
- CSV upload (rebuilds database)
- PDF export (browser print)
- World map with institution lists
- Expiry tracking by period (30/60/90/180 days)
- nginx + gunicorn configuration
- systemd service for auto-start
- Cron job for daily emails
- Test database with 220 MOUs

---

## 📦 Deploy in 5 Steps

### Step 1: Upload to Server

```bash
# From your Mac (replace with your server details)
scp mou-dashboard-deploy.zip user@your-server-ip:/tmp/
```

### Step 2: Extract on Server

```bash
# SSH to your server
ssh user@your-server-ip

# Create directory and extract
sudo mkdir -p /var/www/mou-dashboard
sudo unzip /tmp/mou-dashboard-deploy.zip -d /var/www/mou-dashboard
cd /var/www/mou-dashboard/mou-dashboard
```

### Step 3: Configure Email

```bash
# Copy example env file
cp .env.example .env

# Edit with your Gmail credentials
nano .env
```

**Required changes:**
```env
# Email Configuration
SMTP_USERNAME=fabreupeixoto@gmail.com
SMTP_PASSWORD=YOUR-16-CHAR-APP-PASSWORD
SMTP_FROM=fabreupeixoto@gmail.com
SMTP_TO=francisco.peixoto@usj.edu.mo

# Flask Security (generate random key)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

### Step 4: Run Deployment Script

```bash
sudo bash deploy.sh
```

The script will:
- Install Python, nginx, gunicorn
- Set up virtual environment
- Configure systemd service
- Configure nginx
- Offer to set up cron job for emails
- Start all services

### Step 5: Import Your Real Data

**Option A: Web Interface (Recommended)**
1. Go to `http://your-server-ip`
2. Click **📁 Upload CSV**
3. Upload your MOU data CSV from Google Sheets

**Option B: Command Line**
```bash
source venv/bin/activate
python3 import_csv.py /path/to/your-mou-data.csv
```

---

## 🔧 Post-Deployment

### Set Up SSL (Free HTTPS)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Configure Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

### Test Email Notifications

```bash
cd /var/www/mou-dashboard/mou-dashboard
source venv/bin/activate
python3 send_notifications.py
```

---

## 📊 Verify Installation

### Check Services

```bash
sudo systemctl status mou-dashboard
sudo systemctl status nginx
```

### View Logs

```bash
# App logs
sudo journalctl -u mou-dashboard -f

# Email notifications
tail -f /var/log/mou-dashboard-notifications.log

# nginx logs
sudo tail -f /var/log/nginx/mou-dashboard.error.log
```

### Test in Browser

- **HTTP:** http://your-server-ip
- **HTTPS:** https://your-domain.com (after SSL setup)

---

## 🔑 Important Files

| File | Purpose |
|------|---------|
| `.env` | **Your configuration** (email, secret key) |
| `instance/mou.db` | SQLite database |
| `/var/log/mou-dashboard-notifications.log` | Email logs |
| `/etc/systemd/system/mou-dashboard.service` | App service |
| `/etc/nginx/sites-available/mou-dashboard` | nginx config |

---

## 🆘 Troubleshooting

### App won't start
```bash
sudo systemctl status mou-dashboard
sudo journalctl -u mou-dashboard -n 50 --no-pager
```

### Email not sending
```bash
# Test manually
cd /var/www/mou-dashboard/mou-dashboard
source venv/bin/activate
python3 send_notifications.py
```

### Permission errors
```bash
sudo chown -R www-data:www-data /var/www/mou-dashboard
sudo chmod -R 755 /var/www/mou-dashboard
```

### Can't access website
```bash
# Check nginx
sudo nginx -t
sudo systemctl status nginx

# Check firewall
sudo ufw status
```

---

## 📧 Email Setup Reminder

**Gmail App Password Required:**

1. Go to https://myaccount.google.com/apppasswords
2. Enable 2-Step Verification (if not enabled)
3. Create App Password for "Mail"
4. Copy 16-character password (no spaces)
5. Paste in `.env`: `SMTP_PASSWORD=xxxxxxxxxxxxxxxx`

**Test:**
```bash
python3 test_smtp.py
```

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Restart app | `sudo systemctl restart mou-dashboard` |
| Restart nginx | `sudo systemctl restart nginx` |
| View app logs | `sudo journalctl -u mou-dashboard -f` |
| Test email | `python3 send_notifications.py` |
| Update code | `cd /var/www/mou-dashboard/mou-dashboard && sudo git pull && sudo systemctl restart mou-dashboard` |
| Backup DB | `sudo cp /var/www/mou-dashboard/mou-dashboard/instance/mou.db /backup/mou-$(date +%Y%m%d).db` |

---

## ✅ Deployment Checklist

- [ ] Upload ZIP to server
- [ ] Extract to `/var/www/mou-dashboard`
- [ ] Edit `.env` with email credentials
- [ ] Generate SECRET_KEY
- [ ] Run `sudo bash deploy.sh`
- [ ] Upload MOU data via CSV
- [ ] Test email: `python3 send_notifications.py`
- [ ] Set up SSL with certbot
- [ ] Configure firewall
- [ ] Test in browser

---

**🎉 You're done!** Your MOU Dashboard is live and sending expiry notifications daily at 9 AM!
