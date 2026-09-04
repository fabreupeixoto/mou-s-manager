"""One-time migration: copy the existing SQLite database into PostgreSQL.

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/db \
    SRC_SQLITE=/path/to/mou.db \
    python migrate_to_pg.py

Reads tables from the SQLite source and writes into the PostgreSQL DB that the
app is configured to use. Preserves primary keys so FKs remain valid.
"""
import os
import sqlite3
import sys
from datetime import datetime, date

from app import app, db, User, Faculty, FacultyAccess, MOU, MOUPartner, MOUSignee
from app import Activity, Document, activity_mous, mou_partner_faculties

SRC = os.getenv('SRC_SQLITE', 'instance/mou.db')


def col_names(cursor):
    return [d[0] for d in cursor.description]


def main():
    if not os.path.isfile(SRC):
        print(f'Source SQLite not found: {SRC}')
        sys.exit(1)
    conn = sqlite3.connect(SRC)
    conn.row_factory = sqlite3.Row

    with app.app_context():
        db.create_all()
        existing = db.session.execute(db.text('SELECT COUNT(*) FROM mous')).scalar() or 0
        if existing:
            print(f'PG "mous" already has {existing} rows. Refusing to migrate over existing data.')
            print('If this is intended, clear the target database first.')
            sys.exit(1)

        # Remove any pre-seeded default users (e.g. from deploy/setup.sh) so the
        # legacy user set (with original IDs/passwords) can be imported cleanly.
        seeded = User.query.count()
        if seeded:
            User.query.delete()
            db.session.commit()
            print(f'removed {seeded} pre-seeded user(s) - importing legacy users instead')

        # Users
        for r in conn.execute('SELECT * FROM users ORDER BY id'):
            u = User(id=r['id'], username=r['username'],
                     full_name=r['full_name'], email=r['email'],
                     role=r['role'], created_at=_dt(r['created_at']))
            u.password_hash = r['password_hash']
            db.session.add(u)
        print('users copied')

        # Faculties
        for r in conn.execute('SELECT * FROM faculties ORDER BY id'):
            db.session.add(Faculty(id=r['id'], name=r['name'],
                                   description=r['description'],
                                   created_at=_dt(r['created_at'])))
        print('faculties copied')

        # Faculty accesses
        for r in conn.execute('SELECT * FROM faculty_accesses ORDER BY id'):
            db.session.add(FacultyAccess(id=r['id'], user_id=r['user_id'],
                                         faculty_id=r['faculty_id'],
                                         created_at=_dt(r['created_at'])))
        print('faculty_accesses copied')

        # MOUs + partners (+signees) + faculty junction
        mou_rows = conn.execute('SELECT * FROM mous ORDER BY id')
        for r in mou_rows:
            scope = 'faculty' if r['faculty_id'] else 'university'
            mou = MOU(id=r['id'], portuguese_speaking=bool(r['portuguese_speaking']),
                      asean=bool(r['asean']),
                      signed_date=_dd(r['signed_date']),
                      duration=r['duration'], expiry_date=_dd(r['expiry_date']),
                      renewal_terms=r['renewal_terms'], notice_period=r['notice_period'],
                      additional_info=r['additional_info'],
                      mobility_available=bool(r['mobility_available']),
                      mobility_info=r['mobility_info'], other_projects=r['other_projects'],
                      website_status=r['website_status'], status=r['status'],
                      signed_file=r['signed_file'], scope=scope,
                      last_sync=_dt(r['last_sync']))
            partner = MOUPartner(institution=r['institution'], country=r['country'],
                                 country_code=r['country_code'],
                                 institution_number=r['institution_number'], sort_order=0)
            if r['contact_person'] or r['contact_email']:
                partner.signees.append(MOUSignee(name=r['contact_person'],
                                                 role=None, email=r['contact_email']))
            mou.partners.append(partner)
            if r['faculty_id']:
                fac = db.session.get(Faculty, r['faculty_id'])
                if fac:
                    partner.faculties.append(fac)
            db.session.add(mou)
        print('mous + partners migrated')

        # Activities
        for r in conn.execute('SELECT * FROM activities ORDER BY id'):
            db.session.add(Activity(id=r['id'], faculty_id=r['faculty_id'],
                                    title=r['title'], description=r['description'],
                                    activity_date=_dd(r['activity_date']),
                                    created_by=r['created_by'],
                                    created_at=_dt(r['created_at'])))
        print('activities copied')

        # Documents
        for r in conn.execute('SELECT * FROM documents ORDER BY id'):
            db.session.add(Document(id=r['id'], activity_id=r['activity_id'],
                                    filename=r['filename'], filepath=r['filepath'],
                                    file_type=r['file_type'], file_size=r['file_size'],
                                    uploaded_by=r['uploaded_by'],
                                    uploaded_at=_dt(r['uploaded_at'])))
        print('documents copied')

        db.session.commit()

        # Junction tables (raw inserts)
        for r in conn.execute('SELECT activity_id, mou_id FROM activity_mous'):
            db.session.execute(activity_mous.insert().values(activity_id=r['activity_id'],
                                                             mou_id=r['mou_id']))
        partner_map = {m.id: m.partners[0].id for m in MOU.query.all() if m.partners}
        for r in conn.execute('SELECT id AS mou_id, faculty_id FROM mous WHERE faculty_id IS NOT NULL'):
            pid = partner_map.get(r['mou_id'])
            if pid:
                db.session.execute(mou_partner_faculties.insert().values(partner_id=pid,
                                                                         faculty_id=r['faculty_id']))
        db.session.commit()
        print('junction tables copied')

        # Verify
        for t in ['users', 'faculties', 'faculty_accesses', 'mous', 'mou_partners',
                  'activities', 'documents', 'activity_mous', 'mou_partner_faculties']:
            n = db.session.execute(db.text(f'SELECT COUNT(*) FROM {t}')).scalar()
            print(f'  PG {t}: {n}')

        # Reset identity sequences to max(id)+1 for tables with explicit IDs
        for table, seq in [
            ('users', 'users_id_seq'), ('faculties', 'faculties_id_seq'),
            ('faculty_accesses', 'faculty_accesses_id_seq'), ('mous', 'mous_id_seq'),
            ('mou_partners', 'mou_partners_id_seq'), ('mou_signees', 'mou_signees_id_seq'),
            ('activities', 'activities_id_seq'), ('documents', 'documents_id_seq'),
        ]:
            maxid = db.session.execute(
                db.text(f"SELECT COALESCE(MAX(id),0) FROM {table}")).scalar() or 0
            db.session.execute(db.text(f"SELECT setval('{seq}', :v, true)"), {'v': maxid + 1})
        db.session.commit()
        print('identity sequences reset')

    conn.close()
    print('Migration complete.')


def _dt(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime.combine(v, datetime.min.time())
    s = str(v).strip().replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _dd(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ('%Y-%m-%d',):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


if __name__ == '__main__':
    main()
