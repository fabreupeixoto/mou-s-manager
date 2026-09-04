# USJ MOU Dashboard - Deployment Package

## 📦 Package Contents

This deployment package includes all recent changes and features:

### Core Application
- `app.py` - Flask application with all features
- `requirements.txt` - Development dependencies
- `requirements-prod.txt` - Production dependencies (with gunicorn)

### Templates
- `templates/dashboard.html` - Main dashboard with:
  - Stats cards (Total, Active, Expiring 60 days, Portuguese, ASEAN, Mobility)
  - Interactive charts with percentages
  - World map with institution lists on pin click
  - Expiry period selector (30/60/90/180 days)
  - Print-optimized PDF export with complete expiry lists
  - Tooltips showing institution names on hover
- `templates/upload_csv.html` - CSV upload page (rebuilds database)

### Features Included
✅ CSV upload (rebuilds database from scratch)
✅ PDF export via browser print (no wkhtmltopdf needed)
✅ Expiry tracking by period (30/60/90/180 days)
✅ Email digest with categorized expiry sections
✅ World map with institution lists per country
✅ Stat card tooltips with institution names
✅ Country chart with percentage tooltips
✅ Last sync timestamp in navbar
✅ Smart email notifications (only sends when MOUs expiring)

### Deployment Files
- `deploy.sh` - One-command deployment script
- `mou-dashboard.service` - systemd service configuration
- `nginx.conf` - nginx reverse proxy configuration
- `.env.example` - Environment variables template
- `.gitignore` - Git ignore rules

### Documentation
- `README.md` - Project overview and setup
- `DEPLOYMENT.md` - Complete production deployment guide
- `CHANGELOG.md` - Recent changes and version history

### Utility Scripts
- `import_csv.py` - Command-line CSV import
- `seed_test_data.py` - Generate test data
- `test_smtp.py` - Test email configuration
- `test_sheets.py` - Test Google Sheets connection

---

## 🚀 Quick Deploy

### On Your Ubuntu Server:

```bash
# 1. Create directory
sudo mkdir -p /var/www/mou-dashboard
sudo chown $USER:$USER /var/www/mou-dashboard
cd /var/www/mou-dashboard

# 2. Upload and extract zip
# (Upload mou-dashboard-deploy.zip here via SCP/SFTP)
unzip mou-dashboard-deploy.zip
cd mou-dashboard

# 3. Run deployment script
sudo bash deploy.sh
```

### Or Manual Deployment:

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx git wkhtmltopdf

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-prod.txt

# Configure environment
cp .env.example .env
nano .env  # Edit with your settings

# Initialize database
python3 -c "from app import db, app; app.app_context().push(); db.create_all()"

# Import your data
python3 import_csv.py /path/to/your/file.csv

# Set up systemd service
sudo cp mou-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mou-dashboard
sudo systemctl start mou-dashboard

# Configure nginx
sudo cp nginx.conf /etc/nginx/sites-available/mou-dashboard
sudo ln -s /etc/nginx/sites-available/mou-dashboard /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo systemctl restart nginx
```

---

## ⚙️ Configuration Required

Before running, edit `.env` with:

```env
# Email (for expiry notifications)
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_TO=recipient@example.com

# Flask
SECRET_KEY=<generate-random-32-char-hex>

# Google Sheets (optional)
GOOGLE_SPREADSHEET_ID=19u0zXbaZqOdBNkuNEuIHys7UXggGN73-
```

Generate secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📊 Post-Deployment

### 1. Import Your Data

```bash
# Option A: Upload CSV via web interface
# Go to http://your-server-ip/upload-csv

# Option B: Command line
python3 import_csv.py /path/to/mou-data.csv
```

### 2. Test Email Notifications

```bash
python3 -c "from app import send_expiry_notifications, app; app.app_context().push(); send_expiry_notifications()"
```

### 3. Set Up SSL (Recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 4. Configure Firewall

```bash
sudo ufw allow 'Nginx Full'
sudo ufw allow OpenSSH
sudo ufw enable
```

---

## 🔍 Maintenance

### View Logs
```bash
# App logs
sudo journalctl -u mou-dashboard -f

# nginx logs
sudo tail -f /var/log/nginx/mou-dashboard.error.log
```

### Restart Services
```bash
sudo systemctl restart mou-dashboard
sudo systemctl restart nginx
```

### Update Code
```bash
cd /var/www/mou-dashboard/mou-dashboard
sudo git pull  # if using git
sudo systemctl restart mou-dashboard
```

### Backup Database
```bash
sudo cp /var/www/mou-dashboard/mou-instance/mou.db /backup/mou-$(date +%Y%m%d).db
```

---

## 📁 Package Structure

```
mou-dashboard-deploy.zip (2.5 MB)
├── app.py                          # Main application (639 lines)
├── requirements.txt                # Dev dependencies
├── requirements-prod.txt           # Production dependencies
├── import_csv.py                   # CSV import script
├── seed_test_data.py               # Test data generator
├── test_smtp.py                    # Email test script
├── test_sheets.py                  # Google Sheets test
├── deploy.sh                       # Auto-deployment script
├── mou-dashboard.service           # systemd service
├── nginx.conf                      # nginx config
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore
├── README.md                       # Project readme
├── DEPLOYMENT.md                   # Deployment guide
├── CHANGELOG.md                    # Version history
├── templates/
│   ├── dashboard.html              # Main dashboard (934 lines)
│   └── upload_csv.html             # Upload page (350 lines)
└── instance/
    └── mou.db                      # SQLite database (with test data)
```

---

## 🎯 Recent Changes (Included)

### Map Enhancements
- ✅ Institution list on pin click
- ✅ Status color coding (green/red)
- ✅ Expiry dates per institution
- ✅ Scrollable list for many institutions

### Dashboard Stats
- ✅ Removed redundant expiry cards (kept only 60 days)
- ✅ Last Sync moved to navbar
- ✅ Tooltips with institution names on hover
- ✅ Country chart with percentage tooltips

### PDF Export
- ✅ Browser-based print (no installation)
- ✅ Complete expiry lists by period at bottom
- ✅ Color-coded by urgency
- ✅ Dropdown selector hidden in print

### Email Notifications
- ✅ Organized by period (30/60/90/180 days)
- ✅ Only sends when MOUs expiring
- ✅ Shows institution list per period

### CSV Upload
- ✅ Rebuilds database from scratch
- ✅ Warning message before import
- ✅ Drag-and-drop interface

---

## 📞 Support

For issues or questions:
1. Check `DEPLOYMENT.md` for detailed guide
2. View logs: `sudo journalctl -u mou-dashboard`
3. Test locally before deploying

---

**Package Created:** 2026-07-04
**Version:** 1.2 (Production Ready)
**Total Files:** 24
**Database:** Includes test data (220 MOUs)
**Email:** ✅ Tested and working (Gmail SMTP)

## ✅ Tested Features

- [x] Dashboard loads correctly
- [x] CSV upload rebuilds database
- [x] PDF export via browser print
- [x] Expiry tracking by period
- [x] Email notifications (Gmail SMTP)
- [x] Map with institution lists
- [x] Stat card tooltips
- [x] Country chart percentages
