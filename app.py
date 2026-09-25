import os
import sqlite3
import uuid
from datetime import datetime, date

from flask import (Flask, g, render_template, request, redirect,
                   url_for, session, flash)
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# App configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'college_events.db')

app = Flask(__name__)
app.secret_key = 'college-event-management-secret-key'

CATEGORIES = ['Technical', 'Cultural', 'Sports', 'Workshop',
              'Seminar', 'Hackathon', 'Quiz', 'Paper Presentation']
EVENT_STATUSES = ['Upcoming', 'Open', 'Closed', 'Ongoing',
                  'Completed', 'Cancelled']


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    row_id = cur.lastrowid
    cur.close()
    return row_id


# ---------------------------------------------------------------------------
# Database initialisation + demo data
# ---------------------------------------------------------------------------
def init_db():
    db_exists = os.path.exists(DATABASE)
    conn = sqlite3.connect(DATABASE)
    cur = conn.cursor()

    cur.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT,
        event_date TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        venue TEXT,
        max_participants INTEGER DEFAULT 50,
        registration_deadline TEXT,
        coordinator_id INTEGER,
        status TEXT DEFAULT 'Upcoming',
        created_at TEXT NOT NULL,
        FOREIGN KEY (coordinator_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id TEXT NOT NULL UNIQUE,
        student_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registered_at TEXT NOT NULL,
        status TEXT DEFAULT 'Confirmed',
        UNIQUE(student_id, event_id),
        FOREIGN KEY (student_id) REFERENCES users(id),
        FOREIGN KEY (event_id) REFERENCES events(id)
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER NOT NULL,
        student_id INTEGER,
        position TEXT NOT NULL,
        student_name TEXT,
        student_reg_no TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (event_id) REFERENCES events(id),
        FOREIGN KEY (student_id) REFERENCES users(id)
    );
    ''')

    # Default admin account
    admin_email = 'admin@college.com'
    exists = cur.execute('SELECT id FROM users WHERE email = ?',
                         (admin_email,)).fetchone()
    if not exists:
        cur.execute(
            'INSERT INTO users (name, email, password, role, created_at) '
            'VALUES (?, ?, ?, ?, ?)',
            ('Administrator', admin_email,
             generate_password_hash('admin123'), 'admin',
             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Sample coordinator account
    coord = cur.execute('SELECT id FROM users WHERE email = ?',
                        ('coordinator@college.com',)).fetchone()
    if not coord:
        cur.execute(
            'INSERT INTO users (name, email, password, role, created_at) '
            'VALUES (?, ?, ?, ?, ?)',
            ('Event Coordinator', 'coordinator@college.com',
             generate_password_hash('coord123'), 'coordinator',
             datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Sample events
    event_count = cur.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    if event_count == 0:
        coord_id = cur.execute(
            'SELECT id FROM users WHERE role = ? LIMIT 1',
            ('coordinator',)).fetchone()[0]
        samples = [
            ('Cyber Security Workshop',
             'A hands-on workshop covering ethical hacking, network security '
             'basics and penetration testing tools. Bring your laptop.',
             'Workshop', '2026-10-15', '09:00', '16:00',
             'Computer Lab 1', 60, '2026-10-10', coord_id, 'Open'),
            ('Technical Quiz',
             'Test your technical knowledge across programming, networking, '
             'and emerging technologies. Team of 2 members.',
             'Quiz', '2026-10-22', '10:00', '12:00',
             'Seminar Hall A', 100, '2026-10-18', coord_id, 'Open'),
            ('Hackathon 2026',
             '24-hour national level hackathon. Build innovative solutions '
             'for real-world problems. Team size: 2-4.',
             'Hackathon', '2026-11-05', '08:00', '20:00',
             'Innovation Center', 120, '2026-10-30', coord_id, 'Open'),
            ('Paper Presentation',
             'Present your research papers in domains of AI, IoT, Cloud '
             'Computing and Data Science. Individual or pair.',
             'Paper Presentation', '2026-11-12', '09:30', '13:00',
             'Conference Hall', 50, '2026-11-05', coord_id, 'Upcoming'),
            ('Cultural Fest - Rhythms 2026',
             'Annual cultural fest featuring dance, music, drama and '
             'fashion show. Open to all departments.',
             'Cultural', '2026-12-03', '16:00', '22:00',
             'Open Air Auditorium', 500, '2026-11-28', coord_id, 'Upcoming'),
        ]
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for s in samples:
            cur.execute('''
                INSERT INTO events (title, description, category, event_date,
                    start_time, end_time, venue, max_participants,
                    registration_deadline, coordinator_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        s + (now,))

    # Sample notifications
    notif_count = cur.execute(
        'SELECT COUNT(*) FROM notifications').fetchone()[0]
    if notif_count == 0:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cur.execute(
            'INSERT INTO notifications (title, message, created_at) '
            'VALUES (?, ?, ?)',
            ('Welcome to College Event Management System',
             'Stay updated with all the latest college events. '
             'Register now!', now))
        cur.execute(
            'INSERT INTO notifications (title, message, created_at) '
            'VALUES (?, ?, ?)',
            ('Hackathon 2026 Registrations Open',
             'Register your teams for Hackathon 2026 before the deadline.',
             now))

    conn.commit()
    cur.close()
    conn.close()
    if not db_exists:
        print('Database college_events.db created successfully.')


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def current_user():
    user_id = session.get('user_id')
    if user_id is None:
        return None
    return query('SELECT * FROM users WHERE id = ?', (user_id,), one=True)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard_redirect_route'))
        return f(*args, **kwargs)
    return wrapper


def coordinator_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'coordinator'):
            flash('Coordinator access required.', 'danger')
            return redirect(url_for('dashboard_redirect_route'))
        return f(*args, **kwargs)
    return wrapper


def dashboard_redirect():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    if role == 'coordinator':
        return redirect(url_for('coordinator_dashboard'))
    return redirect(url_for('student_dashboard'))


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    user = current_user()
    unread = 0
    if user:
        unread = query('SELECT COUNT(*) c FROM notifications',
                       (), one=True)['c']
    return dict(current_user=user, categories=CATEGORIES,
                notif_count=unread, today=date.today().isoformat())


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------
@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('images/favicon.ico')


@app.route('/')
def index():
    upcoming = query(
        "SELECT * FROM events WHERE status IN ('Open','Upcoming') "
        "AND event_date >= ? ORDER BY event_date LIMIT 3",
        (date.today().isoformat(),))
    total_events = query('SELECT COUNT(*) c FROM events', (), one=True)['c']
    total_students = query(
        "SELECT COUNT(*) c FROM users WHERE role='student'",
        (), one=True)['c']
    total_reg = query('SELECT COUNT(*) c FROM registrations',
                      (), one=True)['c']
    return render_template('index.html', upcoming=upcoming,
                           total_events=total_events,
                           total_students=total_students,
                           total_reg=total_reg)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')
        user = query('SELECT * FROM users WHERE email = ?', (email,), one=True)
        if user and check_password_hash(user['password'], password):
            session.clear()
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            flash(f'Welcome back, {user["name"]}!', 'success')
            return dashboard_redirect()
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not name or not email or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        existing = query('SELECT id FROM users WHERE email = ?',
                         (email,), one=True)
        if existing:
            flash('Email already registered. Please login.', 'danger')
            return render_template('register.html')
        execute('INSERT INTO users (name, email, password, role, created_at) '
                'VALUES (?, ?, ?, ?, ?)',
                (name, email, generate_password_hash(password), 'student',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash('Account created successfully. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard_redirect_route():
    return dashboard_redirect()


@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if session.get('role') != 'student':
        return dashboard_redirect()
    uid = session['user_id']
    upcoming = query(
        "SELECT * FROM events WHERE status IN ('Open','Upcoming') "
        "AND event_date >= ? ORDER BY event_date LIMIT 5",
        (date.today().isoformat(),))
    my_regs = query(
        '''SELECT r.*, e.title, e.event_date, e.venue, e.status
           FROM registrations r JOIN events e ON r.event_id = e.id
           WHERE r.student_id = ? ORDER BY r.registered_at DESC''', (uid,))
    status_counts = {}
    for r in my_regs:
        status_counts[r['status']] = status_counts.get(r['status'], 0) + 1
    notifications = query(
        'SELECT * FROM notifications ORDER BY created_at DESC LIMIT 5')
    return render_template('student_dashboard.html', upcoming=upcoming,
                           my_regs=my_regs, status_counts=status_counts,
                           notifications=notifications)


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_students = query(
        "SELECT COUNT(*) c FROM users WHERE role='student'",
        (), one=True)['c']
    total_events = query('SELECT COUNT(*) c FROM events', (), one=True)['c']
    upcoming = query(
        "SELECT COUNT(*) c FROM events WHERE status IN "
        "('Open','Upcoming') AND event_date >= ?",
        (date.today().isoformat(),), one=True)['c']
    total_reg = query('SELECT COUNT(*) c FROM registrations',
                      (), one=True)['c']
    completed = query(
        "SELECT COUNT(*) c FROM events WHERE status='Completed'",
        (), one=True)['c']
    recent_events = query(
        'SELECT * FROM events ORDER BY created_at DESC LIMIT 5')
    recent_regs = query(
        '''SELECT r.*, u.name student_name, e.title event_title
           FROM registrations r
           JOIN users u ON r.student_id = u.id
           JOIN events e ON r.event_id = e.id
           ORDER BY r.registered_at DESC LIMIT 5''')
    return render_template('admin_dashboard.html',
                           total_students=total_students,
                           total_events=total_events, upcoming=upcoming,
                           total_reg=total_reg, completed=completed,
                           recent_events=recent_events,
                           recent_regs=recent_regs)


@app.route('/coordinator/dashboard')
@login_required
def coordinator_dashboard():
    if session.get('role') not in ('coordinator', 'admin'):
        return dashboard_redirect()
    uid = session['user_id']
    if session['role'] == 'admin':
        assigned = query('SELECT * FROM events ORDER BY event_date')
    else:
        assigned = query(
            'SELECT * FROM events WHERE coordinator_id = ? '
            'ORDER BY event_date', (uid,))
    participant_count = query(
        '''SELECT COUNT(*) c FROM registrations r
           JOIN events e ON r.event_id = e.id
           WHERE e.coordinator_id = ?''', (uid,), one=True)['c']
    if session['role'] == 'admin':
        participant_count = query(
            'SELECT COUNT(*) c FROM registrations',
            (), one=True)['c']
    upcoming = [e for e in assigned
                if e['event_date'] >= date.today().isoformat()
                and e['status'] in ('Open', 'Upcoming', 'Ongoing')]
    status_map = {}
    for e in assigned:
        status_map[e['status']] = status_map.get(e['status'], 0) + 1
    return render_template('coordinator_dashboard.html',
                           assigned=assigned,
                           participant_count=participant_count,
                           upcoming_count=len(upcoming),
                           status_map=status_map)


# ---------------------------------------------------------------------------
# Events (public)
# ---------------------------------------------------------------------------
@app.route('/events')
def events():
    search = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    sql = '''SELECT e.*, u.name coordinator_name,
             (SELECT COUNT(*) FROM registrations r
              WHERE r.event_id = e.id) reg_count
             FROM events e LEFT JOIN users u ON e.coordinator_id = u.id
             WHERE e.status != 'Cancelled' '''
    args = []
    if search:
        sql += ' AND (e.title LIKE ? OR e.description LIKE ? OR e.venue LIKE ?)'
        like = f'%{search}%'
        args += [like, like, like]
    if category:
        sql += ' AND e.category = ?'
        args.append(category)
    sql += ' ORDER BY e.event_date'
    event_list = query(sql, args)
    return render_template('events.html', events=event_list,
                           search=search, selected_category=category)


@app.route('/event/<int:event_id>')
def event_details(event_id):
    event = query(
        '''SELECT e.*, u.name coordinator_name,
           (SELECT COUNT(*) FROM registrations r
            WHERE r.event_id = e.id) reg_count
           FROM events e LEFT JOIN users u ON e.coordinator_id = u.id
           WHERE e.id = ?''', (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('events'))
    my_reg = None
    if 'user_id' in session and session.get('role') == 'student':
        my_reg = query(
            'SELECT * FROM registrations WHERE student_id = ? AND event_id = ?',
            (session['user_id'], event_id), one=True)
    results = query(
        'SELECT * FROM results WHERE event_id = ? ORDER BY id', (event_id,))
    registered = []
    if session.get('role') in ('admin', 'coordinator'):
        registered = query(
            '''SELECT r.*, u.name student_name, u.email student_email
               FROM registrations r JOIN users u ON r.student_id = u.id
               WHERE r.event_id = ? ORDER BY r.registered_at DESC''',
            (event_id,))
    return render_template('event_details.html', event=event,
                           my_reg=my_reg, results=results,
                           registered=registered)


@app.route('/event/<int:event_id>/register', methods=['GET', 'POST'])
@login_required
def event_register(event_id):
    if session.get('role') != 'student':
        flash('Only students can register for events.', 'warning')
        return redirect(url_for('event_details', event_id=event_id))
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('events'))
    uid = session['user_id']
    existing = query('SELECT * FROM registrations WHERE student_id = ? '
                     'AND event_id = ?', (uid, event_id), one=True)
    if existing:
        flash('You have already registered for this event.', 'warning')
        return redirect(url_for('event_details', event_id=event_id))
    if request.method == 'POST':
        if event['status'] == 'Cancelled':
            flash('This event has been cancelled.', 'danger')
        elif (event['registration_deadline'] and
              event['registration_deadline'] < date.today().isoformat()):
            flash('Registration deadline has passed.', 'danger')
        else:
            reg_count = query(
                'SELECT COUNT(*) c FROM registrations WHERE event_id = ?',
                (event_id,), one=True)['c']
            if reg_count >= event['max_participants']:
                flash('Event is full.', 'danger')
            else:
                reg_id = 'REG-' + uuid.uuid4().hex[:8].upper()
                execute(
                    '''INSERT INTO registrations
                       (registration_id, student_id, event_id,
                        registered_at, status)
                       VALUES (?, ?, ?, ?, 'Confirmed')''',
                    (reg_id, uid, event_id,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                flash(f'Registration successful! Your Registration ID: '
                      f'{reg_id}', 'success')
                return redirect(url_for('my_events'))
        return redirect(url_for('event_details', event_id=event_id))
    return render_template('event_details.html', event=event,
                           my_reg=None, register_mode=True, results=[])


@app.route('/my-events')
@login_required
def my_events():
    if session.get('role') != 'student':
        return dashboard_redirect()
    regs = query(
        '''SELECT r.*, e.title, e.event_date, e.start_time, e.end_time,
           e.venue, e.category, e.status event_status
           FROM registrations r JOIN events e ON r.event_id = e.id
           WHERE r.student_id = ? ORDER BY e.event_date''',
        (session['user_id'],))
    return render_template('my_events.html', regs=regs)


@app.route('/profile')
@login_required
def profile():
    user = current_user()
    reg_count = 0
    if user['role'] == 'student':
        reg_count = query('SELECT COUNT(*) c FROM registrations '
                          'WHERE student_id = ?',
                          (user['id'],), one=True)['c']
    return render_template('profile.html', user=user, reg_count=reg_count)


@app.route('/notifications')
@login_required
def notifications():
    notifs = query('SELECT * FROM notifications ORDER BY created_at DESC')
    return render_template('notifications.html', notifs=notifs)


@app.route('/results')
def results_page():
    rows = query(
        '''SELECT res.*, e.title event_title, e.event_date
           FROM results res JOIN events e ON res.event_id = e.id
           ORDER BY res.event_id, res.id''')
    grouped = {}
    for r in rows:
        grouped.setdefault(r['event_title'], []).append(r)
    return render_template('results.html', grouped=grouped)


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------
@app.route('/admin/events')
@admin_required
def manage_events():
    event_list = query(
        '''SELECT e.*, u.name coordinator_name,
           (SELECT COUNT(*) FROM registrations r
            WHERE r.event_id = e.id) reg_count
           FROM events e LEFT JOIN users u ON e.coordinator_id = u.id
           ORDER BY e.event_date''')
    return render_template('manage_events.html', events=event_list)


@app.route('/admin/event/add', methods=['GET', 'POST'])
@admin_required
def add_event():
    coordinators = query(
        "SELECT id, name FROM users WHERE role IN "
        "('coordinator','admin') ORDER BY name")
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        event_date = request.form.get('event_date', '')
        if not title or not event_date:
            flash('Title and event date are required.', 'danger')
            return render_template('add_event.html', coordinators=coordinators,
                                   categories=CATEGORIES,
                                   statuses=EVENT_STATUSES,
                                   form=request.form)
        execute('''INSERT INTO events (title, description, category,
                   event_date, start_time, end_time, venue, max_participants,
                   registration_deadline, coordinator_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (title, request.form.get('description', ''),
                 request.form.get('category', 'Technical'),
                 event_date,
                 request.form.get('start_time', ''),
                 request.form.get('end_time', ''),
                 request.form.get('venue', ''),
                 int(request.form.get('max_participants') or 50),
                 request.form.get('registration_deadline', ''),
                 request.form.get('coordinator_id') or None,
                 request.form.get('status', 'Upcoming'),
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        execute('INSERT INTO notifications (title, message, created_at) '
                'VALUES (?, ?, ?)',
                (f'New Event: {title}',
                 f'A new event "{title}" has been announced. '
                 f'Date: {event_date}. Register now!',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash('Event created successfully.', 'success')
        return redirect(url_for('manage_events'))
    return render_template('add_event.html', coordinators=coordinators,
                           categories=CATEGORIES, statuses=EVENT_STATUSES,
                           form={})


@app.route('/admin/event/edit/<int:event_id>', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('manage_events'))
    coordinators = query(
        "SELECT id, name FROM users WHERE role IN "
        "('coordinator','admin') ORDER BY name")
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        event_date = request.form.get('event_date', '')
        if not title or not event_date:
            flash('Title and event date are required.', 'danger')
            return render_template('edit_event.html', event=event,
                                   coordinators=coordinators,
                                   categories=CATEGORIES,
                                   statuses=EVENT_STATUSES)
        execute('''UPDATE events SET title=?, description=?, category=?,
                   event_date=?, start_time=?, end_time=?, venue=?,
                   max_participants=?, registration_deadline=?,
                   coordinator_id=?, status=? WHERE id=?''',
                (title, request.form.get('description', ''),
                 request.form.get('category', 'Technical'),
                 event_date,
                 request.form.get('start_time', ''),
                 request.form.get('end_time', ''),
                 request.form.get('venue', ''),
                 int(request.form.get('max_participants') or 50),
                 request.form.get('registration_deadline', ''),
                 request.form.get('coordinator_id') or None,
                 request.form.get('status', 'Upcoming'),
                 event_id))
        if request.form.get('status') == 'Cancelled':
            execute('INSERT INTO notifications (title, message, created_at) '
                    'VALUES (?, ?, ?)',
                    (f'Event Cancelled: {title}',
                     f'The event "{title}" has been cancelled.',
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        else:
            execute('INSERT INTO notifications (title, message, created_at) '
                    'VALUES (?, ?, ?)',
                    (f'Event Updated: {title}',
                     f'The event "{title}" has been updated. '
                     f'Check details now.',
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash('Event updated successfully.', 'success')
        return redirect(url_for('manage_events'))
    return render_template('edit_event.html', event=event,
                           coordinators=coordinators,
                           categories=CATEGORIES, statuses=EVENT_STATUSES)


@app.route('/admin/event/delete/<int:event_id>', methods=['POST'])
@admin_required
def delete_event(event_id):
    event = query('SELECT title FROM events WHERE id = ?',
                  (event_id,), one=True)
    if event:
        db = get_db()
        db.execute('DELETE FROM results WHERE event_id = ?', (event_id,))
        db.execute('DELETE FROM registrations WHERE event_id = ?',
                   (event_id,))
        db.execute('DELETE FROM events WHERE id = ?', (event_id,))
        db.commit()
        flash(f'Event "{event["title"]}" deleted.', 'success')
    else:
        flash('Event not found.', 'danger')
    return redirect(url_for('manage_events'))


@app.route('/admin/participants')
@admin_required
def participants():
    event_id = request.args.get('event_id', type=int)
    sql = '''SELECT r.*, u.name student_name, u.email student_email,
             e.title event_title, e.event_date
             FROM registrations r
             JOIN users u ON r.student_id = u.id
             JOIN events e ON r.event_id = e.id'''
    args = []
    if event_id:
        sql += ' WHERE r.event_id = ?'
        args.append(event_id)
    sql += ' ORDER BY r.registered_at DESC'
    regs = query(sql, args)
    event_list = query('SELECT id, title FROM events ORDER BY event_date')
    return render_template('participants.html', regs=regs,
                           events=event_list,
                           selected_event=event_id)


@app.route('/admin/students')
@admin_required
def manage_students():
    students = query(
        "SELECT * FROM users WHERE role='student' ORDER BY created_at DESC")
    return render_template('participants.html', students=students,
                           manage_students_mode=True, regs=[],
                           events=[])


@app.route('/admin/student/delete/<int:student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    db = get_db()
    db.execute('DELETE FROM registrations WHERE student_id = ?',
               (student_id,))
    db.execute('DELETE FROM results WHERE student_id = ?', (student_id,))
    db.execute("DELETE FROM users WHERE id = ? AND role='student'",
               (student_id,))
    db.commit()
    flash('Student removed.', 'success')
    return redirect(url_for('manage_students'))


@app.route('/admin/notification/add', methods=['GET', 'POST'])
@admin_required
def add_notification():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        if not title:
            flash('Title is required.', 'danger')
        else:
            execute('INSERT INTO notifications (title, message, created_at) '
                    'VALUES (?, ?, ?)',
                    (title, message,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            flash('Notification added.', 'success')
            return redirect(url_for('notifications'))
    return render_template('notifications.html', notifs=[],
                           add_mode=True,
                           all_notifs=query(
                               'SELECT * FROM notifications '
                               'ORDER BY created_at DESC'))


@app.route('/admin/result/add', methods=['GET', 'POST'])
@admin_required
def add_result():
    event_list = query('SELECT id, title FROM events ORDER BY event_date')
    students = query("SELECT id, name FROM users WHERE role='student' "
                     "ORDER BY name")
    if request.method == 'POST':
        event_id = request.form.get('event_id', type=int)
        position = request.form.get('position', '').strip()
        student_id = request.form.get('student_id', type=int) or None
        student_name = request.form.get('student_name', '').strip()
        student_reg_no = request.form.get('student_reg_no', '').strip()
        if not event_id or not position:
            flash('Event and position are required.', 'danger')
        else:
            execute('''INSERT INTO results (event_id, student_id, position,
                       student_name, student_reg_no, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (event_id, student_id, position, student_name,
                     student_reg_no,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            event = query('SELECT title FROM events WHERE id = ?',
                          (event_id,), one=True)
            execute('INSERT INTO notifications (title, message, created_at) '
                    'VALUES (?, ?, ?)',
                    (f'Results Published: {event["title"] if event else ""}',
                     f'Results for the event are now available. '
                     f'{position} place: {student_name or "TBA"}',
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            flash('Result added successfully.', 'success')
            return redirect(url_for('results_page'))
    return render_template('results.html', grouped={}, add_mode=True,
                           events=event_list, students=students)


# ---------------------------------------------------------------------------
# Coordinator routes
# ---------------------------------------------------------------------------
@app.route('/coordinator/event/edit/<int:event_id>', methods=['GET', 'POST'])
@coordinator_required
def coordinator_edit_event(event_id):
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    if (session.get('role') == 'coordinator' and
            event['coordinator_id'] != session['user_id']):
        flash('You are not assigned to this event.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    if request.method == 'POST':
        execute('''UPDATE events SET title=?, description=?, category=?,
                   event_date=?, start_time=?, end_time=?, venue=?,
                   max_participants=?, registration_deadline=?,
                   status=? WHERE id=?''',
                (request.form.get('title', event['title']),
                 request.form.get('description', event['description']),
                 request.form.get('category', event['category']),
                 request.form.get('event_date', event['event_date']),
                 request.form.get('start_time', event['start_time']),
                 request.form.get('end_time', event['end_time']),
                 request.form.get('venue', event['venue']),
                 int(request.form.get('max_participants')
                     or event['max_participants']),
                 request.form.get('registration_deadline',
                                  event['registration_deadline']),
                 request.form.get('status', event['status']),
                 event_id))
        execute('INSERT INTO notifications (title, message, created_at) '
                'VALUES (?, ?, ?)',
                (f'Event Update: {event["title"]}',
                 f'Status is now: {request.form.get("status", event["status"])}',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash('Event updated successfully.', 'success')
        return redirect(url_for('coordinator_dashboard'))
    return render_template('edit_event.html', event=event,
                           coordinators=[], categories=CATEGORIES,
                           statuses=EVENT_STATUSES,
                           coordinator_mode=True)


@app.route('/coordinator/event/<int:event_id>/status', methods=['POST'])
@coordinator_required
def coordinator_update_status(event_id):
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    if (session.get('role') == 'coordinator' and
            event['coordinator_id'] != session['user_id']):
        flash('You are not assigned to this event.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    status = request.form.get('status')
    if status in EVENT_STATUSES:
        execute('UPDATE events SET status = ? WHERE id = ?',
                (status, event_id))
        execute('INSERT INTO notifications (title, message, created_at) '
                'VALUES (?, ?, ?)',
                (f'{event["title"]}: {status}',
                 f'The status of "{event["title"]}" is now {status}.',
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        flash('Event status updated.', 'success')
    return redirect(request.referrer or url_for('coordinator_dashboard'))


@app.route('/coordinator/event/<int:event_id>/participants')
@coordinator_required
def coordinator_participants(event_id):
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    if (session.get('role') == 'coordinator' and
            event['coordinator_id'] != session['user_id']):
        flash('You are not assigned to this event.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    regs = query(
        '''SELECT r.*, u.name student_name, u.email student_email,
           e.title event_title, e.event_date
           FROM registrations r
           JOIN users u ON r.student_id = u.id
           JOIN events e ON r.event_id = e.id
           WHERE r.event_id = ? ORDER BY r.registered_at DESC''',
        (event_id,))
    return render_template('participants.html', regs=regs,
                           events=[{'id': event['id'],
                                    'title': event['title']}],
                           selected_event=event_id, event=event)


@app.route('/coordinator/result/add/<int:event_id>', methods=['GET', 'POST'])
@coordinator_required
def coordinator_add_result(event_id):
    event = query('SELECT * FROM events WHERE id = ?',
                  (event_id,), one=True)
    if not event:
        flash('Event not found.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    if (session.get('role') == 'coordinator' and
            event['coordinator_id'] != session['user_id']):
        flash('You are not assigned to this event.', 'danger')
        return redirect(url_for('coordinator_dashboard'))
    students = query("SELECT id, name FROM users WHERE role='student' "
                     "ORDER BY name")
    if request.method == 'POST':
        position = request.form.get('position', '').strip()
        student_id = request.form.get('student_id', type=int) or None
        student_name = request.form.get('student_name', '').strip()
        student_reg_no = request.form.get('student_reg_no', '').strip()
        if not position:
            flash('Position is required.', 'danger')
        else:
            execute('''INSERT INTO results (event_id, student_id, position,
                       student_name, student_reg_no, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (event_id, student_id, position, student_name,
                     student_reg_no,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            execute('INSERT INTO notifications (title, message, created_at) '
                    'VALUES (?, ?, ?)',
                    (f'Results Published: {event["title"]}',
                     f'{position} place: {student_name or "TBA"}',
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            flash('Result added.', 'success')
            return redirect(url_for('results_page'))
    grouped = {}
    rows = query('SELECT * FROM results WHERE event_id = ? ORDER BY id',
                 (event_id,))
    if rows:
        grouped[event['title']] = rows
    return render_template('results.html', grouped=grouped, add_mode=True,
                           events=[{'id': event['id'],
                                    'title': event['title']}],
                           students=students, event=event)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
# Hosted servers (gunicorn / waitress) import the `app` object directly and
# call init_db() via the WSGI entry script, so the database is created there.
PORT = int(os.environ.get('PORT', 5000))

if __name__ == '__main__':
    init_db()
    if os.environ.get('RENDER') or os.environ.get('PYTHONANYWHERE_DOMAIN'):
        app.run(host='0.0.0.0', port=PORT, debug=False)
    else:
        app.run(debug=True)
