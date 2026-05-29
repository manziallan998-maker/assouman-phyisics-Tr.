from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
import jwt
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import pandas as pd
import json
from database import get_db, init_database, TeacherDB, ClassDB, StudentDB

# Initialize database on startup
init_database()

# Use database functions
teacher = TeacherDB.find_by_email('teacher@school.rw')
classes = ClassDB.get_by_teacher(teacher_id)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smartclass-secret-key-2026')
CORS(app)

# Database setup
DB_PATH = 'smartclass.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Teachers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT UNIQUE NOT NULL,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            school TEXT NOT NULL,
            subject TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Classes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id TEXT UNIQUE NOT NULL,
            teacher_id TEXT NOT NULL,
            name TEXT NOT NULL,
            academic_year TEXT NOT NULL,
            term INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
        )
    ''')
    
    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            class_id TEXT NOT NULL,
            name TEXT NOT NULL,
            registration_number TEXT UNIQUE,
            parent_phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(class_id)
        )
    ''')
    
    # Marks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            term INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score INTEGER,
            grade TEXT,
            remarks TEXT,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id)
        )
    ''')
    
    # Lesson plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lesson_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            day_of_week TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration INTEGER NOT NULL,
            topic TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id),
            FOREIGN KEY (class_id) REFERENCES classes(class_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Call init_db
init_db()

# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

def generate_token(teacher_id):
    return jwt.encode({
        'teacher_id': teacher_id,
        'exp': datetime.utcnow() + timedelta(days=30)
    }, app.secret_key, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, app.secret_key, algorithms=['HS256'])
        return payload['teacher_id']
    except:
        return None

# ==================== AUTHENTICATION ROUTES ====================
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    teacher_id = generate_id('TCH')
    password_hash = hash_password(data['password'])
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO teachers (teacher_id, fullname, email, school, subject, password_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (teacher_id, data['fullname'], data['email'], data['school'], data['subject'], password_hash))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Account created successfully'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Email already exists'})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    password_hash = hash_password(data['password'])
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM teachers WHERE email = ? AND password_hash = ?', 
                   (data['email'], password_hash))
    teacher = cursor.fetchone()
    conn.close()
    
    if teacher:
        token = generate_token(teacher['teacher_id'])
        return jsonify({
            'success': True,
            'token': token,
            'name': teacher['fullname'],
            'teacher_id': teacher['teacher_id']
        })
    else:
        return jsonify({'success': False, 'message': 'Invalid credentials'})

# ==================== TEACHER ROUTES ====================
@app.route('/api/teacher/profile', methods=['GET'])
def get_teacher_profile():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT teacher_id, fullname, email, school, subject FROM teachers WHERE teacher_id = ?', (teacher_id,))
    teacher = cursor.fetchone()
    conn.close()
    
    if teacher:
        return jsonify({'success': True, 'data': dict(teacher)})
    return jsonify({'success': False, 'message': 'Teacher not found'})

# ==================== CLASS ROUTES ====================
@app.route('/api/classes', methods=['GET'])
def get_classes():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.*, 
               COUNT(s.id) as student_count,
               AVG(m.score) as average
        FROM classes c
        LEFT JOIN students s ON c.class_id = s.class_id
        LEFT JOIN marks m ON s.student_id = m.student_id AND m.term = 1
        WHERE c.teacher_id = ?
        GROUP BY c.class_id
    ''', (teacher_id,))
    
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'data': classes})

@app.route('/api/classes', methods=['POST'])
def add_class():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    class_id = generate_id('CLS')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO classes (class_id, teacher_id, name, academic_year, term)
        VALUES (?, ?, ?, ?, ?)
    ''', (class_id, teacher_id, data['name'], data.get('academic_year', '2026'), data.get('term', 1)))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'class_id': class_id})

@app.route('/api/classes/<class_id>', methods=['DELETE'])
def delete_class(class_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute('SELECT teacher_id FROM classes WHERE class_id = ?', (class_id,))
    cls = cursor.fetchone()
    
    if not cls or cls['teacher_id'] != teacher_id:
        conn.close()
        return jsonify({'success': False, 'message': 'Class not found'})
    
    cursor.execute('DELETE FROM classes WHERE class_id = ?', (class_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# ==================== STUDENT ROUTES ====================
@app.route('/api/classes/<class_id>/students', methods=['GET'])
def get_class_students(class_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.*, 
               m1.score as term1, m2.score as term2, m3.score as term3
        FROM students s
        LEFT JOIN marks m1 ON s.student_id = m1.student_id AND m1.term = 1
        LEFT JOIN marks m2 ON s.student_id = m2.student_id AND m2.term = 2
        LEFT JOIN marks m3 ON s.student_id = m3.student_id AND m3.term = 3
        WHERE s.class_id = ?
        ORDER BY (COALESCE(m1.score,0) + COALESCE(m2.score,0) + COALESCE(m3.score,0)) / 3 DESC
    ''', (class_id,))
    
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'data': students})

@app.route('/api/classes/<class_id>/students', methods=['POST'])
def add_student(class_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    student_id = generate_id('STU')
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO students (student_id, class_id, name, registration_number, parent_phone)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, class_id, data['name'], data.get('registration_number'), data.get('parent_phone')))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'student_id': student_id})

@app.route('/api/students/<student_id>/marks', methods=['PUT'])
def update_student_marks(student_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    for term in [1, 2, 3]:
        score = data.get(f'term{term}')
        if score is not None:
            grade = get_grade(score)
            remarks = get_remarks(score)
            
            cursor.execute('''
                INSERT OR REPLACE INTO marks (student_id, class_id, term, subject, score, grade, remarks)
                VALUES (?, (SELECT class_id FROM students WHERE student_id = ?), ?, ?, ?, ?, ?)
            ''', (student_id, student_id, term, data.get('subject', 'Physics'), score, grade, remarks))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

def get_grade(score):
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 50: return 'D'
    return 'F'

def get_remarks(score):
    if score >= 90: return 'Excellent'
    if score >= 80: return 'Very Good'
    if score >= 70: return 'Good'
    if score >= 50: return 'Satisfactory'
    return 'Needs Improvement'

# ==================== ANALYTICS ROUTES ====================
@app.route('/api/analytics/class/<class_id>', methods=['GET'])
def get_class_analytics(class_id):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get grade distribution
    cursor.execute('''
        SELECT grade, COUNT(*) as count
        FROM marks m
        JOIN students s ON m.student_id = s.student_id
        WHERE s.class_id = ? AND m.term = 3
        GROUP BY grade
    ''', (class_id,))
    distribution = {row['grade']: row['count'] for row in cursor.fetchall()}
    
    # Get top performers
    cursor.execute('''
        SELECT s.name, m.score
        FROM students s
        JOIN marks m ON s.student_id = m.student_id
        WHERE s.class_id = ? AND m.term = 3
        ORDER BY m.score DESC
        LIMIT 5
    ''', (class_id,))
    top_performers = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'success': True,
        'data': {
            'distribution': distribution,
            'top_performers': top_performers
        }
    })

@app.route('/api/analytics/predict', methods=['GET'])
def get_predictive_insights():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get students with declining performance
    cursor.execute('''
        SELECT s.name, m1.score as term1, m2.score as term2, m3.score as term3,
               (m3.score - m1.score) as change
        FROM students s
        JOIN marks m1 ON s.student_id = m1.student_id AND m1.term = 1
        JOIN marks m2 ON s.student_id = m2.student_id AND m2.term = 2
        JOIN marks m3 ON s.student_id = m3.student_id AND m3.term = 3
        WHERE m3.score < 50 AND m3.score < m2.score
        ORDER BY change ASC
        LIMIT 10
    ''')
    
    at_risk = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'data': {'at_risk': at_risk}})

# ==================== LESSON PLANNER ====================
@app.route('/api/lesson-planner/upload', methods=['POST'])
def upload_lesson_plan():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if file and file.filename.endswith(('.xlsx', '.xls', '.csv')):
        # Parse file
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        # Expected columns: Class, Day, Start Time, Duration
        schedules = []
        for _, row in df.iterrows():
            schedule = {
                'class_name': row.iloc[0],
                'day': row.iloc[1],
                'start_time': row.iloc[2],
                'duration': int(row.iloc[3])
            }
            schedules.append(schedule)
        
        # Store in database
        conn = get_db()
        cursor = conn.cursor()
        
        # Get class_id from class name
        for schedule in schedules:
            cursor.execute('SELECT class_id FROM classes WHERE name = ? AND teacher_id = ?', 
                          (schedule['class_name'], teacher_id))
            cls = cursor.fetchone()
            if cls:
                cursor.execute('''
                    INSERT INTO lesson_plans (teacher_id, class_id, day_of_week, start_time, duration)
                    VALUES (?, ?, ?, ?, ?)
                ''', (teacher_id, cls['class_id'], schedule['day'], schedule['start_time'], schedule['duration']))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Uploaded {len(schedules)} lessons', 'data': schedules})
    
    return jsonify({'success': False, 'message': 'Invalid file format'})

@app.route('/api/lesson-planner/schedule', methods=['GET'])
def get_lesson_schedule():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT lp.*, c.name as class_name
        FROM lesson_plans lp
        JOIN classes c ON lp.class_id = c.class_id
        WHERE lp.teacher_id = ?
        ORDER BY 
            CASE lp.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
            END,
            lp.start_time
    ''', (teacher_id,))
    
    schedules = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'success': True, 'data': schedules})

# ==================== SMART GROUPS ====================
@app.route('/api/groups/create', methods=['POST'])
def create_smart_groups():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    teacher_id = verify_token(token)
    
    if not teacher_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    data = request.json
    class_id = data['class_id']
    num_groups = data['num_groups']
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get students with their average marks
    cursor.execute('''
        SELECT s.student_id, s.name, 
               AVG(m.score) as average
        FROM students s
        LEFT JOIN marks m ON s.student_id = m.student_id
        WHERE s.class_id = ?
        GROUP BY s.student_id
        ORDER BY average DESC
    ''', (class_id,))
    
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Sort by performance (best first)
    students.sort(key=lambda x: x.get('average', 0), reverse=True)
    
    # Create balanced groups
    groups = [[] for _ in range(num_groups)]
    
    # Distribute best students as group leaders
    for i in range(min(len(students), num_groups)):
        groups[i].append(students[i])
        students[i]['is_leader'] = True
    
    remaining = students[num_groups:]
    
    # Distribute remaining students in round-robin fashion
    for i, student in enumerate(remaining):
        group_idx = i % num_groups
        groups[group_idx].append(student)
    
    result_groups = []
    for i, group in enumerate(groups):
        group_avg = sum(s.get('average', 0) for s in group) / len(group) if group else 0
        result_groups.append({
            'group_number': i + 1,
            'leader': group[0]['name'] if group else None,
            'members': [{'name': s['name'], 'average': s.get('average', 0)} for s in group],
            'average': round(group_avg, 1)
        })
    
    return jsonify({'success': True, 'data': result_groups})

# ==================== RUN SERVER ====================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
