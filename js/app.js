// SmartClass Analytics - Main Application
// Teacher Portal for Rwanda Education System

// ==================== AUTHENTICATION ====================
class Auth {
    constructor() {
        this.token = localStorage.getItem('teacherToken');
        this.teacherName = localStorage.getItem('teacherName');
        this.teacherEmail = localStorage.getItem('teacherEmail');
    }

    isAuthenticated() {
        return this.token !== null;
    }

    logout() {
        localStorage.removeItem('teacherToken');
        localStorage.removeItem('teacherName');
        localStorage.removeItem('teacherEmail');
        window.location.href = '/index.html';
    }

    getToken() {
        return this.token;
    }
}

// ==================== THEME MANAGER ====================
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'dark';
        this.applyTheme();
        this.setupToggle();
    }

    applyTheme() {
        if (this.currentTheme === 'light') {
            document.body.classList.add('light-theme');
        } else {
            document.body.classList.remove('light-theme');
        }
    }

    toggle() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('theme', this.currentTheme);
        this.applyTheme();
    }

    setupToggle() {
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
        }
    }
}

// ==================== SIDEBAR MANAGER ====================
class SidebarManager {
    constructor() {
        this.sidebar = document.getElementById('sidebar');
        this.mainContent = document.querySelector('.main-content');
        this.menuToggle = document.getElementById('menuToggle');
        this.closeBtn = document.getElementById('closeSidebar');
        this.setupEvents();
    }

    setupEvents() {
        if (this.menuToggle) {
            this.menuToggle.addEventListener('click', () => this.toggle());
        }
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.close());
        }
    }

    toggle() {
        if (window.innerWidth <= 768) {
            this.sidebar.classList.toggle('open');
        } else {
            this.sidebar.classList.toggle('collapsed');
            this.mainContent.classList.toggle('expanded');
        }
    }

    close() {
        if (window.innerWidth <= 768) {
            this.sidebar.classList.remove('open');
        } else {
            this.sidebar.classList.add('collapsed');
            this.mainContent.classList.add('expanded');
        }
    }
}

// ==================== NOTIFICATION MANAGER ====================
class NotificationManager {
    constructor() {
        this.dropdown = document.getElementById('notificationsDropdown');
        this.btn = document.getElementById('notificationsBtn');
        this.badge = document.getElementById('notificationBadge');
        this.setupEvents();
    }

    setupEvents() {
        if (this.btn) {
            this.btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleDropdown();
            });
        }

        document.addEventListener('click', () => {
            if (this.dropdown) {
                this.dropdown.classList.remove('show');
            }
        });

        if (this.dropdown) {
            this.dropdown.addEventListener('click', (e) => e.stopPropagation());
        }
    }

    toggleDropdown() {
        if (this.dropdown) {
            this.dropdown.classList.toggle('show');
        }
    }

    updateBadge(count) {
        if (this.badge) {
            this.badge.textContent = count;
            this.badge.style.display = count > 0 ? 'inline' : 'none';
        }
    }
}

// ==================== API SERVICE ====================
class API {
    constructor() {
        this.baseUrl = '/api';
        this.auth = new Auth();
    }

    async request(endpoint, method = 'GET', data = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.auth.getToken()}`
            }
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, options);
            const result = await response.json();
            
            if (response.status === 401) {
                this.auth.logout();
            }
            
            return result;
        } catch (error) {
            console.error('API Error:', error);
            return { success: false, message: 'Network error' };
        }
    }

    // Teacher endpoints
    getTeacherProfile() {
        return this.request('/teacher/profile');
    }

    // Class endpoints
    getClasses() {
        return this.request('/classes');
    }

    getClassStudents(classId) {
        return this.request(`/classes/${classId}/students`);
    }

    addClass(data) {
        return this.request('/classes', 'POST', data);
    }

    deleteClass(classId) {
        return this.request(`/classes/${classId}`, 'DELETE');
    }

    // Student endpoints
    addStudent(classId, data) {
        return this.request(`/classes/${classId}/students`, 'POST', data);
    }

    updateStudentMarks(studentId, marks) {
        return this.request(`/students/${studentId}/marks`, 'PUT', marks);
    }

    // Analytics endpoints
    getClassAnalytics(classId) {
        return this.request(`/analytics/class/${classId}`);
    }

    getPredictiveInsights() {
        return this.request('/analytics/predict');
    }

    // Lesson Planner
    uploadLessonPlan(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        return fetch('/api/lesson-planner/upload', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${this.auth.getToken()}` },
            body: formData
        }).then(res => res.json());
    }

    getLessonSchedule() {
        return this.request('/lesson-planner/schedule');
    }
}

// ==================== CLASS MANAGER ====================
class ClassManager {
    constructor() {
        this.api = new API();
        this.classes = [];
    }

    async loadClasses() {
        const result = await this.api.getClasses();
        if (result.success) {
            this.classes = result.data;
            this.renderClasses();
        }
        return result;
    }

    renderClasses() {
        const container = document.getElementById('performanceList');
        if (!container) return;

        let html = '';
        for (const cls of this.classes) {
            html += `
                <div class="performance-item">
                    <div class="class-info">
                        <span class="class-name">${cls.name}</span>
                        <span class="student-count">${cls.student_count} students</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${cls.average}%; background: ${this.getProgressColor(cls.average)};"></div>
                    </div>
                    <div class="class-stats">
                        <span class="percentage">${cls.average}%</span>
                        <span class="trend ${cls.trend > 0 ? 'up' : 'down'}">${cls.trend > 0 ? '↑' : '↓'} ${Math.abs(cls.trend)}%</span>
                    </div>
                </div>
            `;
        }
        container.innerHTML = html;
    }

    getProgressColor(percentage) {
        if (percentage >= 80) return '#10B981';
        if (percentage >= 60) return '#3B82F6';
        if (percentage >= 50) return '#F59E0B';
        return '#EF4444';
    }
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    // Initialize managers
    const auth = new Auth();
    
    // Check authentication (skip on login page)
    if (!window.location.pathname.includes('index.html') && !auth.isAuthenticated()) {
        window.location.href = '/index.html';
        return;
    }

    // Initialize components
    new ThemeManager();
    new SidebarManager();
    new NotificationManager();
    
    // Set teacher name
    const teacherName = localStorage.getItem('teacherName');
    const teacherNameElements = document.querySelectorAll('#teacherName, #teacherNameHeader');
    teacherNameElements.forEach(el => {
        if (el) el.textContent = teacherName || 'Teacher';
    });

    // Load classes on dashboard
    if (document.getElementById('performanceList')) {
        const classManager = new ClassManager();
        classManager.loadClasses();
    }

    // Setup logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => auth.logout());
    }
});
