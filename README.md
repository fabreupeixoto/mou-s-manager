# USJ MOU Dashboard

A web analytics dashboard for tracking University of Saint Joseph's Memoranda of Understanding (MOUs) with partner institutions worldwide.

## Features

- Analytics Dashboard - Real-time statistics and KPIs
- Interactive Charts - Country distribution, status breakdown, expiry timeline
- World Map - OpenStreetMap visualization with MOU pins per country
- Expiry Alerts - Email notifications for MOUs expiring within 3 months
- CSV Upload - Easy drag-and-drop CSV import (no Google API needed)
- PDF Export - Download dashboard analytics as PDF report
- Google Sheets Sync - Optional live data synchronization

## Quick Start (Development)

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your settings
python app.py
```

Access at: **http://localhost:5001**

## Production Deployment

### Automated (Recommended)

```bash
git clone git@github.com:fabreupeixoto/mou-s-manager.git /var/www/mou-dashboard
cd /var/www/mou-dashboard
chmod +x deploy.sh
sudo ./deploy.sh your-domain.com
```

### Manual Steps

1. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib libpq-dev
   ```

2. **Create virtual environment:**
   ```bash
   cd /var/www/mou-dashboard
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements-prod.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   nano .env  # Set SECRET_KEY, DATABASE_URL, SMTP credentials
   ```

4. **Set up PostgreSQL:**
   ```bash
   sudo -u postgres psql -c "CREATE USER mou_user WITH PASSWORD 'your-password';"
   sudo -u postgres psql -c "CREATE DATABASE mou_dashboard OWNER mou_user;"
   # Update DATABASE_URL in .env
   ```

5. **Initialize database:**
   ```bash
   python3 -c "from app import db, app; app.app_context().push(); db.create_all()"
   ```

6. **Create uploads directory:**
   ```bash
   mkdir -p uploads
   chown www-data:www-data uploads
   ```

7. **Configure systemd:**
   ```bash
   sudo cp mou-dashboard.service /etc/systemd/system/
   sudo systemctl enable mou-dashboard
   sudo systemctl start mou-dashboard
   ```

8. **Configure nginx:**
   ```bash
   sudo cp nginx.conf /etc/nginx/sites-available/mou-dashboard
   sudo ln -sf /etc/nginx/sites-available/mou-dashboard /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl restart nginx
   ```

9. **Set up SSL:**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

## Google Sheets API Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Google Sheets API**
3. Create a Service Account and download the JSON key
4. Save as `credentials.json` in the project folder
5. Share your Google Sheet with the service account email

## Email Notifications

Configure SMTP in `.env`:

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_TO=recipient@example.com
```

For Gmail, use an [App Password](https://myaccount.google.com/apppasswords) (2FA required).

Notifications run daily at 9:00 AM via cron. Install with:
```bash
crontab mou-dashboard.cron
```

## Project Structure

```
mou-dashboard/
├── app.py                    # Main Flask application
├── reports.py                # PDF export and analytics
├── import_csv.py             # CSV import script
├── migrate_to_pg.py          # SQLite to PostgreSQL migration
├── seed_test_data.py         # Test data seeder
├── send_notifications.py     # Email notification sender
├── test_smtp.py              # SMTP configuration test
├── requirements.txt          # Development dependencies
├── requirements-prod.txt     # Production dependencies
├── .env.example              # Environment variables template
├── deploy.sh                 # Automated deployment script
├── mou-dashboard.service     # Systemd service unit
├── mou-dashboard.cron        # Cron job for notifications
├── nginx.conf                # Nginx configuration
├── templates/
│   ├── dashboard.html        # Main dashboard UI
│   ├── login.html            # Login page
│   ├── manage.html           # MOU management page
│   ├── upload_csv.html       # CSV upload page
│   ├── admin_users.html      # User administration
│   ├── admin_faculties.html  # Faculty administration
│   ├── admin_settings.html   # Settings page
│   ├── faculties_list.html   # Faculties listing
│   └── faculty_detail.html   # Faculty detail view
└── static/                   # Static files (CSS, JS)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/login` | GET/POST | Login page |
| `/manage` | GET | MOU management |
| `/upload-csv` | GET/POST | CSV upload |
| `/admin/users` | GET | User administration |
| `/admin/faculties` | GET | Faculty administration |
| `/admin/settings` | GET | Settings |
| `/faculties` | GET | Faculties listing |
| `/faculty/<id>` | GET | Faculty detail |
| `/export-pdf` | GET | Export dashboard as PDF |
| `/api/stats` | GET | Dashboard statistics |
| `/api/mous-by-country` | GET | MOU count by country |
| `/api/mous-by-status` | GET | MOU count by status |
| `/api/expiry-timeline` | GET | Expiry timeline (12 months) |
| `/api/map-data` | GET | Country data for map |
| `/api/expiring-soon` | GET | MOUs expiring within 3 months |
| `/api/sync` | POST | Trigger Google Sheets sync |

## Technologies

- **Backend:** Flask, SQLAlchemy, APScheduler
- **Database:** PostgreSQL (production) / SQLite (development)
- **Charts:** Chart.js
- **Maps:** Leaflet + OpenStreetMap
- **UI:** Bootstrap 5
- **PDF:** ReportLab, Matplotlib

## License

Internal use only - University of Saint Joseph
