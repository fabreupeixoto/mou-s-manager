"""
Import MOU data from CSV file.
Use this if you don't want to use Google Sheets API.

Usage: python import_csv.py /path/to/file.csv
"""

import sys
import csv
from datetime import datetime
from app import app, db, MOU, MOUPartner, MOUSignee, mou_partner_faculties, activity_mous, parse_date


def import_from_csv(csv_path):
    """Import MOUs from CSV file - rebuilds database from scratch."""
    with app.app_context():
        # Create tables
        db.create_all()
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Find header row
        header_idx = 0
        for i, row in enumerate(rows):
            if len(row) > 2 and 'COUNTRY CODE' in row[0]:
                header_idx = i
                break
        
        data_rows = rows[header_idx + 1:]
        
        # DELETE ALL existing MOUs - rebuild from scratch
        db.session.execute(MOUSignee.__table__.delete())
        db.session.execute(MOUPartner.__table__.delete())
        db.session.execute(mou_partner_faculties.delete())
        db.session.execute(activity_mous.delete())
        MOU.query.delete()
        db.session.commit()
        
        imported = 0
        
        for row in data_rows:
            if len(row) < 6 or not row[2].strip():
                continue
            
            try:
                inst_num = int(row[2]) if row[2].strip() else None
            except ValueError:
                inst_num = None
            
            if not inst_num:
                continue
            
            mou = MOU()
            mou.portuguese_speaking = row[3].strip() == '1' if len(row) > 3 else False
            mou.asean = row[4].strip() == '1' if len(row) > 4 else False
            mou.signed_date = parse_date(row[6]) if len(row) > 6 else None
            mou.duration = row[7].strip() if len(row) > 7 else None

            duration_str = row[7].upper() if len(row) > 7 else ''
            if 'NOT ACTIVE' in duration_str:
                mou.status = 'NOT ACTIVE'
            elif 'ACTIVE' in duration_str:
                mou.status = 'ACTIVE'
            else:
                mou.status = 'UNKNOWN'

            mou.expiry_date = parse_date(row[8]) if len(row) > 8 else None
            mou.renewal_terms = row[9].strip() if len(row) > 9 else None
            mou.notice_period = row[10].strip() if len(row) > 10 else None
            mou.additional_info = row[11].strip() if len(row) > 11 else None
            mou.mobility_available = row[12].strip().upper() == 'Y' if len(row) > 12 and row[12].strip() else False
            mou.mobility_info = row[13].strip() if len(row) > 13 else None
            mou.other_projects = row[14].strip() if len(row) > 14 else None
            mou.website_status = row[15].strip() if len(row) > 15 else None
            mou.last_sync = datetime.utcnow()
            partner = MOUPartner()
            partner.country_code = row[0].strip() if row[0].strip() else None
            partner.country = row[1].strip() if row[1].strip() else None
            partner.institution_number = inst_num
            partner.institution = row[5].strip() if len(row) > 5 else None
            partner.sort_order = 0
            mou.partners.append(partner)

            db.session.add(mou)
            imported += 1
        
        db.session.commit()
        print(f"✅ Database rebuilt with {imported} MOUs from {csv_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        # Default path
        csv_path = '/Users/Francisco/Downloads/1. In Use - USJ MOUs - ALL with Expiry Dates.xlsx - MOU (Institutions).csv'
    else:
        csv_path = sys.argv[1]
    
    import_from_csv(csv_path)
