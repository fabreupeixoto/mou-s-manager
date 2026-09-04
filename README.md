# USJ MOU Dashboard

A web analytics dashboard for tracking University of Saint Joseph's Memoranda of Understanding (MOUs) with partner institutions worldwide.

## Features

- 📊 **Analytics Dashboard** - Real-time statistics and KPIs
- 📈 **Interactive Charts** - Country distribution, status breakdown, expiry timeline
- 🗺️ **World Map** - OpenStreetMap visualization with MOU pins per country
- ⚠️ **Expiry Alerts** - Email notifications for MOUs expiring within 3 months
- 📁 **CSV Upload** - Easy drag-and-drop CSV import (no Google API needed)
- 📄 **PDF Export** - Download dashboard analytics as PDF report
- 🔄 **Google Sheets Sync** - Optional live data synchronization

## Setup Instructions

### 1. Install Dependencies

```bash
cd mou-dashboard
pip install -r requirements.txt
```

### 2. Google Sheets API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the **Google Sheets API**
4. Create credentials (Service Account)
5. Download the JSON key file and save as `credentials.json` in the project folder
6. Share your Google Sheet with the service account email (found in the JSON file)

### 3. Configure Environment Variables

Copy the example environment file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Google Sheets API Credentials
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
GOOGLE_SPREADSHEET_ID=19u0zXbaZqOdBNkuNEuIHys7UXggGN73-

# Email Configuration (SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use App Password, not regular password
SMTP_FROM=your-email@gmail.com
SMTP_TO=recipient@example.com

# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

#### Gmail App Password Setup

If using Gmail:
1. Go to your Google Account settings
2. Enable 2-Factor Authentication
3. Generate an App Password at [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
4. Use this password in `SMTP_PASSWORD`

### 4. Run the Application

```bash
python app.py
```

Access the dashboard at: **http://localhost:5001**

## Using the Dashboard

### Upload CSV Data

1. Click **📁 Upload CSV** button in the dashboard
2. Drag and drop your CSV file or click to browse
3. Click **📥 Import Data**
4. New MOUs will be added to the database

**To export CSV from Google Sheets:**
- Open your Google Sheet
- Click **File** → **Download** → **Comma Separated Values (.csv)**

### Export PDF Report

1. Click **📄 Export PDF** button in the dashboard
2. In the print dialog, select **"Save as PDF"** as destination
3. Choose **Landscape** orientation for best results
4. Click **Save**

**No installation required!** Uses your browser's built-in print-to-PDF feature.

**Tip:** Wait for all charts to load before exporting for best results.

### Email Notifications

Configure SMTP in `.env` to receive daily expiry alerts at 9 AM.

See "Email Configuration" section above.

## Project Structure

```
mou-dashboard/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .env                  # Your configuration (create from .env.example)
├── credentials.json      # Google Sheets API credentials (optional)
├── mou.db                # SQLite database (auto-created)
├── import_csv.py         # CSV import script (command line)
├── test_smtp.py          # Email test script
├── test_sheets.py        # Google Sheets test script
├── templates/
│   ├── dashboard.html    # Dashboard UI
│   └── upload_csv.html   # CSV upload page
└── static/               # Static files (if needed)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/upload-csv` | GET/POST | CSV upload page |
| `/export-pdf` | GET | Export dashboard as PDF |
| `/api/stats` | GET | Dashboard statistics |
| `/api/mous-by-country` | GET | MOU count by country |
| `/api/mous-by-status` | GET | MOU count by status |
| `/api/expiry-timeline` | GET | Expiry timeline (12 months) |
| `/api/map-data` | GET | Country data for map |
| `/api/expiring-soon` | GET | MOUs expiring within 3 months |
| `/api/sync` | POST | Trigger Google Sheets sync |

## Email Notifications

- **Schedule**: Daily at 9:00 AM
- **Trigger**: MOUs expiring within 90 days (3 months)
- **Content**: Table with institution, country, expiry date, days remaining, notice period

To manually test email notifications:

```python
from app import send_expiry_notifications, app

with app.app_context():
    send_expiry_notifications()
```

## Technologies Used

- **Backend**: Flask, SQLAlchemy, APScheduler
- **Database**: SQLite
- **Charts**: Chart.js
- **Maps**: Leaflet + OpenStreetMap
- **UI**: Bootstrap 5
- **Data Source**: Google Sheets API

## Troubleshooting

### Google Sheets Connection Error
- Ensure the service account email has access to the spreadsheet
- Verify `GOOGLE_SPREADSHEET_ID` is correct
- Check that `credentials.json` is in the correct location

### Email Not Sending
- Verify SMTP credentials in `.env`
- For Gmail, ensure you're using an App Password, not your regular password
- Check that 2FA is enabled on your Google account

### Map Not Showing
- Check browser console for JavaScript errors
- Ensure internet connection (OpenStreetMap tiles are loaded via CDN)

## License

Internal use only - University of Saint Joseph
