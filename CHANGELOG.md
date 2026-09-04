# USJ MOU Dashboard - Changelog

## Latest Updates

### 📅 Expiry Period Tracking (v1.2)

#### New Features

1. **Multiple Expiry Periods**
   - Dashboard now shows MOUs expiring in:
     - ✅ 30 days
     - ✅ 60 days
     - ✅ 90 days
     - ✅ 180 days

2. **Interactive Dropdown Selector**
   - Located in the "MOUs Expiring Soon" section
   - Filter the list by period (30/60/90/180 days)
   - Updates dynamically without page reload

3. **Enhanced Email Digest**
   - Email now organized by periods:
     - Within 30 days (🔴 Red)
     - 30-60 days (🟠 Orange)
     - 60-90 days (🟡 Yellow)
     - 90-180 days (🔵 Blue)
   - Only sends when there are MOUs to report
   - Shows total count per period

4. **Improved Stats Cards**
   - Added 4 new stat cards for each expiry period
   - Quick overview at the top of dashboard

#### API Changes

| Endpoint | Change |
|----------|--------|
| `/api/stats` | Now returns `expiring_30`, `expiring_60`, `expiring_90`, `expiring_180` |
| `/api/expiring-soon` | Now accepts `?days=` parameter (e.g., `?days=60`) |
| `/api/expiring-by-period` | NEW - Returns all periods in one call |

#### Email Notification Logic

```
IF no MOUs expiring within 180 days:
    → Skip sending email
ELSE:
    → Send organized digest with sections for each period
```

---

### 📁 CSV Upload with Updates (v1.1)

#### Features
- Upload CSV files directly from browser
- **Updates existing MOUs** (matches by institution_number)
- **Adds new MOUs** (new institution_number)
- Drag-and-drop interface
- No command line needed

#### Updated Fields on Re-upload
- Country
- Institution name
- Signed date
- Duration/Status
- **Expiry date** ← Key field for tracking
- Notice period
- Mobility info

---

### 📄 PDF Export (v1.0)

#### Features
- Browser-based print-to-PDF (no installation)
- Optimized print layout
- Hides navigation buttons
- Formats charts for A4/Letter paper

#### How to Use
1. Click **📄 Export PDF** button
2. In print dialog: Select "Save as PDF"
3. Choose Landscape orientation
4. Click Save

---

## File Changes

| File | Purpose |
|------|---------|
| `app.py` | Added `/upload-csv`, `/api/expiring-soon?days=`, `/api/expiring-by-period` |
| `templates/dashboard.html` | Added period selector, updated stats cards |
| `templates/upload_csv.html` | NEW - Drag-and-drop upload page |
| `import_csv.py` | Updated to handle updates (not just inserts) |

---

## Usage Examples

### Check MOUs Expiring in Next 60 Days

**Dashboard:**
1. Open http://localhost:5001
2. Select "Next 60 days" from dropdown
3. View filtered list

**API:**
```bash
curl http://localhost:5001/api/expiring-soon?days=60
```

### Test Email Notification

```bash
cd /Users/Francisco/Documents/Mous/mou-dashboard
source venv/bin/activate
python -c "from app import send_expiry_notifications, app; app.app_context().push(); send_expiry_notifications()"
```

### Upload Updated CSV

1. Download fresh CSV from Google Sheets
2. Click **📁 Upload CSV** in dashboard
3. Drag file or click to browse
4. Click **📥 Import Data**
5. Dashboard updates automatically

---

## Email Configuration

To enable email notifications:

1. Edit `.env` file:
   ```env
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   SMTP_FROM=your-email@gmail.com
   SMTP_TO=recipient@example.com
   ```

2. Test with:
   ```bash
   python test_smtp.py
   ```

3. Daily emails run at 9:00 AM automatically

---

## Future Enhancements

- [ ] Auto-calculate expiry from signed_date + duration
- [ ] Email frequency preferences (daily/weekly/monthly)
- [ ] Multiple email recipients
- [ ] Export individual MOU details as PDF
- [ ] Calendar view of expiry dates
- [ ] Email notifications to specific officers per country/region
