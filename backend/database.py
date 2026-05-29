"""
Database Configuration and Models for SmartClass Analytics
SQLite Database - Auto-creates on first run
"""

import sqlite3
import hashlib
import uuid
from datetime import datetime
from contextlib import contextmanager

# Database file path
DB_PATH = 'smartclass.db'

# ==================== DATABASE CONNECTION ====================

@contextmanager
def get_db():
    """Get database connection with context manager"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_db_connection():
    """Simple database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== INITIALIZATION ====================

def init_database():
    """Create all tables if they don't exist"""
    with get_db() as conn:
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
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                class_id TEXT NOT NULL,
                date DATE NOT NULL,
                status TEXT DEFAULT 'present',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (class_id) REFERENCES classes(class_id)
            )
        ''')
        
        # Backup logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backup_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id TEXT NOT NULL,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup_type TEXT NOT NULL,
                file_size INTEGER,
                FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id)
            )
        ''')
        
        print("✅ Database initialized successfully")

# ==================== HELPER FUNCTIONS ====================

def generate_id(prefix):
    """Generate unique ID (e.g., TCH_abc123_1234567890)"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    """Verify password against hash"""
    return hash_password(password) == password_hash

def get_grade(score):
    """Convert score to letter grade"""
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 50: return 'D'
    return 'F'

def get_remarks(score):
    """Get remarks based on score"""
    if score >= 90: return 'Excellent'
    if score >= 80: return 'Very Good'
    if score >= 70: return 'Good'
    if score >= 50: return 'Satisfactory'
    return 'Needs Improvement'

# ==================== TEACHER QUERIES ====================

class TeacherDB:
    @staticmethod
    def create(teacher_id, fullname, email, school, subject, password_hash):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO teachers (teacher_id, fullname, email, school, subject, password_hash)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (teacher_id, fullname, email, school, subject, password_hash))
            return cursor.lastrowid
    
    @staticmethod
    def find_by_email(email):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers WHERE email = ?', (email,))
            return cursor.fetchone()
    
    @staticmethod
    def find_by_id(teacher_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM teachers WHERE teacher_id = ?', (teacher_id,))
            return cursor.fetchone()

# ==================== CLASS QUERIES ====================

class ClassDB:
    @staticmethod
    def create(class_id, teacher_id, name, academic_year, term=1):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO classes (class_id, teacher_id, name, academic_year, term)
                VALUES (?, ?, ?, ?, ?)
            ''', (class_id, teacher_id, name, academic_year, term))
            return class_id
    
    @staticmethod
    def get_by_teacher(teacher_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, COUNT(s.id) as student_count,
                       AVG(m.score) as average
                FROM classes c
                LEFT JOIN students s ON c.class_id = s.class_id
                LEFT JOIN marks m ON s.student_id = m.student_id
                WHERE c.teacher_id = ?
                GROUP BY c.class_id
            ''', (teacher_id,))
            return cursor.fetchall()
    
    @staticmethod
    def delete(class_id, teacher_id):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM classes WHERE class_id = ? AND teacher_id = ?', 
                          (class_id, teacher_id))
            return cursor.rowcount > 0

# ==================== STUDENT QUERIES ====================

class StudentDB:
    @staticmethod
    def create(student_id, class_id, name, registration_number=None, parent_phone=None):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students (student_id, class_id, name, registration_number, parent_phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, class_id, name, registration_number, parent_phone))
            return student_id
    
    @staticmethod
    def get_by_class(class_id):
        with get_db() as conn:
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
            return cursor.fetchall()
    
    @staticmethod
    def update_marks(student_id, term1=None, term2=None, term3=None, subject='Physics'):
        with get_db() as conn:
            cursor = conn.cursor()
            # Get class_id first
            cursor.execute('SELECT class_id FROM students WHERE student_id = ?', (student_id,))
            result = cursor.fetchone()
            if not result:
                return False
            class_id = result['class_id']
            
            for term, score in [(1, term1), (2, term2), (3, term3)]:
                if score is not None:
                    grade = get_grade(score)
                    remarks = get_remarks(score)
                    cursor.execute('''
                        INSERT OR REPLACE INTO marks (student_id, class_id, term, subject, score, grade, remarks)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (student_id, class_id, term, subject, score, grade, remarks))
            return True

# ==================== LESSON PLAN QUERIES ====================

class LessonPlanDB:
    @staticmethod
    def create(teacher_id, class_id, day_of_week, start_time, duration, topic=None):
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO lesson_plans (teacher_id, class_id, day_of_week, start_time, duration, topic)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (teacher_id, class_id, day_of_week, start_time, duration, topic))
            return cursor.lastrowid
    
    @staticmethod
    def get_by_teacher(teacher_id):
        with get_db() as conn:
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
            return cursor.fetchall()

# ==================== DEMO DATA ====================

def load_demo_data():
    """Load demo data for testing"""
    print("📊 Loading demo data...")
    
    # Check if data already exists
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM teachers')
        count = cursor.fetchone()[0]
        if count > 0:
            print("Demo data already loaded")
            return
    
    # Create demo teacher
    teacher_id = generate_id('TCH')
    password_hash = hash_password('password123')
    TeacherDB.create(teacher_id, 'Mr. Jean UWIMANA', 'teacher@school.rw', 
                    'G.S. Saint Andre', 'Physics', password_hash)
    
    # Create demo classes
    class1 = ClassDB.create(generate_id('CLS'), teacher_id, 'Physics S4A', '2026', 3)
    class2 = ClassDB.create(generate_id('CLS'), teacher_id, 'Physics S3B', '2026', 3)
    
    # Create demo students
    students_data = [
        ('UWAMAHORO Eric', '2024001', '0788XXXXXX', 82, 88, 94),
        ('IRADUKUNDA Diane', '2024002', '0788XXXXXX', 85, 89, 91),
        ('NSENGIYUMVA Jean', '2024003', '0788XXXXXX', 80, 85, 88),
        ('MUKAMANA Grace', '2024004', '0788XXXXXX', 45, 58, 71),
        ('NDAYISABA Pierre', '2024005', '0788XXXXXX', 38, 42, 41),
    ]
    
    for name, reg, phone, t1, t2, t3 in students_data:
        student_id = generate_id('STU')
        StudentDB.create(student_id, class1, name, reg, phone)
        StudentDB.update_marks(student_id, t1, t2, t3)
    
    print("✅ Demo data loaded successfully")

# ==================== MAIN ====================

if __name__ == '__main__':
    init_database()
    load_demo_data()
    print("Database ready!")
