"""
Seed the database with test MOUs expiring at various dates.
Useful for testing the expiry tracking and email notifications.

Usage: python seed_test_data.py
"""

import random
from datetime import datetime, timedelta
from app import app, db, MOU, MOUPartner


# Sample data
COUNTRIES = [
    ('PRT', 'Portugal'),
    ('BRA', 'Brazil'),
    ('PHL', 'Philippines'),
    ('IDN', 'Indonesia'),
    ('THA', 'Thailand'),
    ('VNM', 'Vietnam'),
    ('IND', 'India'),
    ('JPN', 'Japan'),
    ('KOR', 'Korea'),
    ('ESP', 'Spain'),
    ('FRA', 'France'),
    ('DEU', 'Germany'),
    ('ITA', 'Italy'),
    ('ARG', 'Argentina'),
    ('COL', 'Colombia'),
    ('MOZ', 'Mozambique'),
    ('AGO', 'Angola'),
    ('AUS', 'Australia'),
    ('MYS', 'Malaysia'),
    ('SGP', 'Singapore'),
]

INSTITUTIONS = [
    'University of Lisbon',
    'University of São Paulo',
    'University of the Philippines',
    'University of Indonesia',
    'Chulalongkorn University',
    'Vietnam National University',
    'University of Delhi',
    'University of Tokyo',
    'Seoul National University',
    'Complutense University of Madrid',
    'Sorbonne University',
    'Technical University of Munich',
    'University of Bologna',
    'University of Buenos Aires',
    'National University of Colombia',
    'Eduardo Mondlane University',
    'Agostinho Neto University',
    'University of Melbourne',
    'University of Malaya',
    'National University of Singapore',
    'Catholic University of Portugal',
    'Federal University of Rio de Janeiro',
    'Ateneo de Manila University',
    'Gadjah Mada University',
    'Mahidol University',
    'University of Ho Chi Minh City',
    'Jawaharlal Nehru University',
    'Kyoto University',
    'Yonsei University',
    'University of Barcelona',
]

def seed_test_data():
    """Populate database with test MOUs."""
    
    with app.app_context():
        # Clear existing test data (optional - comment out to keep existing)
        # MOU.query.delete()
        # db.session.commit()
        
        today = datetime.now().date()
        created_count = 0
        
        # Create MOUs expiring in different periods
        test_scenarios = [
            # (days_from_now, count, status)
            (5, 2, 'ACTIVE'),      # Very urgent
            (15, 3, 'ACTIVE'),     # Within 30 days
            (25, 2, 'ACTIVE'),     # Within 30 days
            (45, 4, 'ACTIVE'),     # Within 60 days
            (55, 2, 'ACTIVE'),     # Within 60 days
            (75, 3, 'ACTIVE'),     # Within 90 days
            (85, 2, 'ACTIVE'),     # Within 90 days
            (120, 3, 'ACTIVE'),    # Within 180 days
            (150, 2, 'ACTIVE'),    # Within 180 days
            (200, 2, 'ACTIVE'),    # Beyond 180 days
            (300, 2, 'ACTIVE'),    # Far future
            (400, 1, 'ACTIVE'),    # Very far future
        ]
        
        institution_counter = 1000  # Start institution numbers at 1000
        
        for days_from_now, count, status in test_scenarios:
            expiry_date = today + timedelta(days=days_from_now)
            
            for i in range(count):
                # Pick random country and institution
                country_code, country_name = random.choice(COUNTRIES)
                institution_name = random.choice(INSTITUTIONS)
                
                # Add some variation to institution names
                if random.random() > 0.5:
                    institution_name = f"{institution_name} - Campus {chr(65 + i)}"
                
                # Calculate signed date (1-5 years ago)
                signed_date = today - timedelta(days=random.randint(365, 1825))
                
                # Duration in years
                duration_years = random.choice([1, 2, 3, 5])
                
                # Create MOU
                mou = MOU()
                mou.portuguese_speaking = country_name in ['Portugal', 'Brazil', 'Mozambique', 'Angola']
                mou.asean = country_name in ['Philippines', 'Indonesia', 'Thailand', 'Vietnam', 'Malaysia', 'Singapore']
                mou.signed_date = signed_date
                mou.duration = f'{duration_years} years'
                mou.status = status
                mou.expiry_date = expiry_date
                mou.renewal_terms = 'Automatic renewal if not terminated' if random.random() > 0.5 else 'Requires formal renewal'
                mou.notice_period = random.choice(['30 days', '60 days', '90 days', '3 months', '6 months'])
                mou.additional_info = 'Test data for dashboard' if random.random() > 0.7 else None
                mou.mobility_available = random.random() > 0.3  # 70% have mobility
                mou.mobility_info = 'Students and faculty exchange' if mou.mobility_available else None
                mou.other_projects = 'Research collaboration' if random.random() > 0.5 else None
                mou.website_status = 'Yes' if random.random() > 0.3 else 'No'
                mou.last_sync = datetime.utcnow()
                partner = MOUPartner()
                partner.country_code = country_code
                partner.country = country_name
                partner.institution_number = institution_counter
                partner.institution = institution_name
                partner.sort_order = 0
                mou.partners.append(partner)
                
                db.session.add(mou)
                institution_counter += 1
                created_count += 1
        
        # Add some NOT ACTIVE MOUs
        for i in range(5):
            country_code, country_name = random.choice(COUNTRIES)
            mou = MOU()
            mou.portuguese_speaking = False
            mou.asean = False
            mou.signed_date = today - timedelta(days=random.randint(730, 1460))
            mou.duration = 'NOT ACTIVE - Expired'
            mou.status = 'NOT ACTIVE'
            mou.expiry_date = today - timedelta(days=random.randint(30, 365))
            mou.notice_period = None
            mou.last_sync = datetime.utcnow()
            partner = MOUPartner()
            partner.country_code = country_code
            partner.country = country_name
            partner.institution_number = institution_counter
            partner.institution = f"{random.choice(INSTITUTIONS)} (Expired)"
            partner.sort_order = 0
            mou.partners.append(partner)
            
            db.session.add(mou)
            institution_counter += 1
            created_count += 1
        
        db.session.commit()
        
        # Print summary
        print(f"✅ Created {created_count} test MOUs")
        
        # Show distribution
        print("\n📊 Expiry Distribution:")
        print("-" * 50)
        
        periods = [
            ('Within 30 days', 30),
            ('30-60 days', 60),
            ('60-90 days', 90),
            ('90-180 days', 180),
            ('Beyond 180 days', None)
        ]
        
        for label, days in periods:
            if days:
                if label == 'Within 30 days':
                    count = MOU.query.filter(
                        MOU.status == 'ACTIVE',
                        MOU.expiry_date != None,
                        MOU.expiry_date >= today,
                        MOU.expiry_date <= today + timedelta(days=days)
                    ).count()
                else:
                    prev_days = periods[periods.index((label, days)) - 1][1]
                    count = MOU.query.filter(
                        MOU.status == 'ACTIVE',
                        MOU.expiry_date != None,
                        MOU.expiry_date >= today + timedelta(days=prev_days),
                        MOU.expiry_date <= today + timedelta(days=days)
                    ).count()
            else:
                count = MOU.query.filter(
                    MOU.status == 'ACTIVE',
                    MOU.expiry_date != None,
                    MOU.expiry_date > today + timedelta(days=180)
                ).count()
            
            print(f"  {label}: {count} MOUs")
        
        # Show NOT ACTIVE count
        not_active = MOU.query.filter_by(status='NOT ACTIVE').count()
        print(f"  NOT ACTIVE: {not_active} MOUs")
        print("-" * 50)
        
        total = MOU.query.count()
        print(f"\n📈 Total MOUs in database: {total}")


if __name__ == '__main__':
    print("🌱 Seeding database with test MOUs...")
    seed_test_data()
    print("\n✅ Done! Refresh your dashboard to see the new data.")
