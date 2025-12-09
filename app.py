# app.py - Final integrated app with Developer Panel
import os
import sqlite3
import random
from datetime import datetime
from functools import wraps

import requests
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, abort
)
from flask_mail import Mail, Message
from openpyxl import Workbook
from werkzeug.utils import secure_filename

# ---------- Config from environment ----------
DB_NAME = os.environ.get("DB_NAME", "leave.db")
FAST2SMS_API_KEY = os.environ.get("FAST2SMS_API_KEY", "")
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-change-me")
DEVELOPER_USERNAME = os.environ.get("DEVELOPER_USERNAME", "devfaiyaj")
DEVELOPER_PASSWORD = os.environ.get("DEVELOPER_PASSWORD", "faiyaj@123")

UPLOAD_FOLDER = "static/profile_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- Flask app ----------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Mail config
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD
mail = Mail(app)

# ---------- Database helper ----------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- Initialize DB / Create tables ----------
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    # users: admin or student
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT,
        department TEXT,
        admin_branch TEXT,
        semester TEXT,
        roll_no TEXT,
        registration_no TEXT,
        parent_phone TEXT,
        parent_email TEXT,
        photo TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # leaves
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        from_date TEXT,
        to_date TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Pending',
        decision_reason TEXT,
        applied_on TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """)
    # attendance
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        date TEXT,
        status TEXT,
        semester TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """)
    # messages (support)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        to_user_id INTEGER,
        content TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(from_user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

# Make sure tables exist at app start
create_tables()

# ---------- Utilities: Email / SMS ----------
def send_email(to, subject, body):
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        app.logger.warning("Mail credentials not set; skipping email.")
        return False
    try:
        msg = Message(subject, sender=MAIL_USERNAME, recipients=[to])
        msg.body = body
        mail.send(msg)
        app.logger.info(f"Email sent to {to}")
        return True
    except Exception as e:
        app.logger.error("Email Error: %s", e)
        return False

def send_sms(phone, message):
    # Fast2SMS example (HTTP GET)
    if not FAST2SMS_API_KEY:
        app.logger.warning("FAST2SMS_API_KEY not set; skipping SMS.")
        return False
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        params = {
            "authorization": FAST2SMS_API_KEY,
            "route": "q",
            "message": message,
            "numbers": phone
        }
        resp = requests.get(url, params=params, timeout=10)
        app.logger.info("SMS response: %s", resp.text)
        return True
    except Exception as e:
        app.logger.error("SMS Error: %s", e)
        return False

# ---------- Decorators ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("user_role") != role:
                flash("Access denied.", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

def developer_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("developer"):
            flash("Developer access required.", "danger")
            return redirect(url_for("developer_login"))
        return f(*args, **kwargs)
    return wrapper

# ---------- Routes: Basic ----------
@app.route("/")
def index():
    if "user_role" in session:
        if session["user_role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))

# ---------- Registration ----------
@app.route("/register/student", methods=["GET", "POST"])
def register_student():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        department = request.form.get("department", "").strip()
        semester = request.form.get("semester", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        registration_no = request.form.get("registration_no", "").strip()
        parent_phone = request.form.get("parent_phone", "").strip()
        parent_email = request.form.get("parent_email", "").strip()

        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO users
                (name, email, password, role, department, semester, roll_no, registration_no, parent_phone, parent_email)
                VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?)
            """, (name, email, password, department, semester, roll_no, registration_no, parent_phone, parent_email))
            conn.commit()
            flash("Student registered successfully! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        finally:
            conn.close()
    return render_template("register_student.html")

@app.route("/register/admin", methods=["GET", "POST"])
def register_admin():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        admin_branch = request.form.get("admin_branch", "").strip()  # e.g. CSE, CE
        conn = get_db_connection()
        try:
            conn.execute("""
                INSERT INTO users (name, email, password, role, admin_branch)
                VALUES (?, ?, ?, 'admin', ?)
            """, (name, email, password, admin_branch))
            conn.commit()
            flash("Admin registered successfully!", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
        finally:
            conn.close()
    return render_template("register_admin.html")

# ---------- Login / Logout ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            session["user_photo"] = user["photo"]
            # admin branch
            if user["role"] == "admin":
                session["admin_branch"] = user["admin_branch"]
                return redirect(url_for("admin_dashboard"))
            else:
                session["student_branch"] = user["department"]
                session["student_roll"] = user["roll_no"]
                session["student_reg"] = user["registration_no"]
                return redirect(url_for("student_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))

# ---------- Forgot password ----------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            conn.close()
            flash("Email not found", "danger")
            return redirect(url_for("forgot_password"))
        new_pass = "pass" + str(random.randint(1000, 9999))
        conn.execute("UPDATE users SET password=? WHERE id=?", (new_pass, user["id"]))
        conn.commit()
        conn.close()
        if user["parent_email"]:
            send_email(user["parent_email"], "Password Reset", f"Your new password is: {new_pass}")
        # also send to user email if present
        send_email(email, "Password Reset", f"Your new password is: {new_pass}")
        flash("New password sent to email(s) (if available).", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

# ---------- Student profile & upload ----------
@app.route("/student/profile")
@login_required
@role_required("student")
def student_profile():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("student_profile.html", user=user)

@app.route("/student/upload-photo", methods=["POST"])
@login_required
@role_required("student")
def student_upload_photo():
    if "photo" not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for("student_profile"))
    f = request.files["photo"]
    if not f or f.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("student_profile"))
    filename = secure_filename(f"{session['user_id']}_{f.filename}")
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    f.save(path)
    conn = get_db_connection()
    conn.execute("UPDATE users SET photo=? WHERE id=?", (filename, session["user_id"]))
    conn.commit()
    conn.close()
    session["user_photo"] = filename
    flash("Photo updated!", "success")
    return redirect(url_for("student_profile"))

# ---------- Student support (messages) ----------
@app.route("/student/support", methods=["GET", "POST"])
@login_required
@role_required("student")
def student_support():
    conn = get_db_connection()
    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            conn.execute("INSERT INTO messages (from_user_id, to_user_id, content) VALUES (?, ?, ?)",
                         (session["user_id"], 1, content))
            conn.commit()
            flash("Message sent to admin", "success")
    msgs = conn.execute("SELECT m.*, u.name FROM messages m JOIN users u ON m.from_user_id=u.id WHERE m.from_user_id=? ORDER BY m.created_at DESC", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("student_support.html", messages=msgs)

# ---------- Student dashboard ----------
@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    sid = session["user_id"]
    conn = get_db_connection()
    leaves = conn.execute("SELECT * FROM leaves WHERE student_id=? ORDER BY applied_on DESC", (sid,)).fetchall()
    stats = conn.execute("""
        SELECT 
            COUNT(*) total,
            SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) approved,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) pending,
            SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) rejected
        FROM leaves WHERE student_id=?
    """, (sid,)).fetchone()
    attendance = conn.execute("SELECT date, status, semester FROM attendance WHERE student_id=? ORDER BY date DESC", (sid,)).fetchall()
    conn.close()
    return render_template("student_dashboard.html", leaves=leaves, stats=stats, attendance=attendance)

# ---------- Apply leave (student) ----------
@app.route("/leave/apply", methods=["GET", "POST"])
@login_required
@role_required("student")
def apply_leave():
    if request.method == "POST":
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")
        reason = request.form.get("reason", "").strip()
        conn = get_db_connection()
        conn.execute("INSERT INTO leaves (student_id, from_date, to_date, reason, status) VALUES (?, ?, ?, ?, 'Pending')",
                     (session["user_id"], from_date, to_date, reason))
        user = conn.execute("SELECT name, parent_email, parent_phone FROM users WHERE id=?", (session["user_id"],)).fetchone()
        conn.commit()
        conn.close()
        # notify parent via email + sms (if available)
        if user and user["parent_email"]:
            body = f"""Dear Parent,

Your ward {user['name']} has applied for leave.

From: {from_date}
To: {to_date}
Reason: {reason}

Status: Pending

Regards,
GEC Kaimur LMS"""
            send_email(user["parent_email"], "Leave Application Submitted", body)
        if user and user["parent_phone"]:
            sms_msg = f"Leave Applied: {user['name']}. From {from_date} To {to_date}. Status: Pending."
            send_sms(user["parent_phone"], sms_msg)
        flash("Leave applied; parent notified (if contacts provided).", "success")
        return redirect(url_for("student_dashboard"))
    return render_template("apply_leave.html")

# ---------- Admin Dashboard (branch-wise filters) ----------
@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    # optional filters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    department_filter = request.args.get("department")
    where = []
    params = []
    if admin_branch == "CSE":
        where.append("u.department LIKE 'CSE%'")
        if department_filter:
            where.append("u.department = ?")
            params.append(department_filter)
    else:
        where.append("u.department = ?")
        params.append(admin_branch)
    if from_date:
        where.append("l.from_date >= ?"); params.append(from_date)
    if to_date:
        where.append("l.to_date <= ?"); params.append(to_date)
    where_sql = " AND ".join(where) if where else "1=1"
    leaves = conn.execute(f"""
        SELECT l.*, u.name, u.roll_no, u.department
        FROM leaves l JOIN users u ON l.student_id = u.id
        WHERE {where_sql}
        ORDER BY l.status='Pending' DESC, l.applied_on DESC
    """, params).fetchall()
    stats = conn.execute(f"""
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) approved,
               SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) pending,
               SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) rejected
        FROM leaves l JOIN users u ON l.student_id = u.id
        WHERE {where_sql}
    """, params).fetchone()
    # attendance stats
    if admin_branch == "CSE":
        attendance_stats = conn.execute("""
            SELECT SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) present,
                   SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) absent
            FROM attendance a JOIN users u ON a.student_id = u.id
            WHERE u.department LIKE 'CSE%'
        """).fetchone()
        departments = conn.execute("SELECT DISTINCT department FROM users WHERE role='student' AND department LIKE 'CSE%'").fetchall()
    else:
        attendance_stats = conn.execute("""
            SELECT SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) present,
                   SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) absent
            FROM attendance a JOIN users u ON a.student_id = u.id
            WHERE u.department = ?
        """, (admin_branch,)).fetchone()
        departments = conn.execute("SELECT DISTINCT department FROM users WHERE role='student' AND department = ?", (admin_branch,)).fetchall()
    conn.close()
    return render_template("admin_dashboard.html", leaves=leaves, stats=stats, attendance_stats=attendance_stats, departments=departments, filters={"from_date": from_date, "to_date": to_date, "department": department_filter})

# ---------- Admin update leave ----------
@app.route("/admin/leave/<int:leave_id>/update", methods=["POST"])
@login_required
@role_required("admin")
def update_leave(leave_id):
    status = request.form.get("status")
    decision_reason = request.form.get("decision_reason", "").strip()
    conn = get_db_connection()
    leave = conn.execute("""
        SELECT l.*, u.parent_phone, u.parent_email, u.name, u.department
        FROM leaves l JOIN users u ON l.student_id = u.id WHERE l.id=?
    """, (leave_id,)).fetchone()
    if not leave:
        conn.close()
        flash("Leave not found", "danger")
        return redirect(url_for("admin_dashboard"))
    # branch checks
    admin_branch = session.get("admin_branch")
    if admin_branch and admin_branch != "CSE" and leave["department"] != admin_branch:
        conn.close()
        flash("You are not allowed to update this leave!", "danger")
        return redirect(url_for("admin_dashboard"))
    if admin_branch == "CSE" and not leave["department"].startswith("CSE"):
        conn.close()
        flash("You are not allowed to update this leave!", "danger")
        return redirect(url_for("admin_dashboard"))
    # notify parent: sms + email
    if leave["parent_phone"]:
        if status == "Approved":
            text = f"Leave Approved for {leave['name']}. Reason: {decision_reason}"
        else:
            text = f"Leave Rejected for {leave['name']}. Reason: {decision_reason}"
        send_sms(leave["parent_phone"], text)
    if leave["parent_email"]:
        send_email(leave["parent_email"], "Leave Status Update", f"Status: {status}\nReason: {decision_reason}")
    # update db
    conn.execute("UPDATE leaves SET status=?, decision_reason=? WHERE id=?", (status, decision_reason, leave_id))
    conn.commit()
    conn.close()
    flash("Leave updated!", "success")
    return redirect(url_for("admin_dashboard"))

# ---------- Admin support ----------
@app.route("/admin/support")
@login_required
@role_required("admin")
def admin_support():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        msgs = conn.execute("""
            SELECT m.*, u.name, u.department FROM messages m JOIN users u ON m.from_user_id=u.id WHERE u.department LIKE 'CSE%' ORDER BY m.created_at DESC
        """).fetchall()
    else:
        msgs = conn.execute("""
            SELECT m.*, u.name, u.department FROM messages m JOIN users u ON m.from_user_id=u.id WHERE u.department=? ORDER BY m.created_at DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    return render_template("admin_support.html", messages=msgs)

# ---------- Admin view user leaves ----------
@app.route("/admin/student/<int:student_id>/leaves")
@login_required
@role_required("admin")
def student_leave_list(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM users WHERE id=?", (student_id,)).fetchone()
    if not student:
        conn.close()
        flash("Student not found", "danger")
        return redirect(url_for("admin_dashboard"))
    leaves = conn.execute("SELECT * FROM leaves WHERE student_id=? ORDER BY applied_on DESC", (student_id,)).fetchall()
    conn.close()
    return render_template("leave_list.html", student=student, leaves=leaves)

# ---------- Admin users list ----------
@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        users = conn.execute("""
            SELECT id, name, email, department, roll_no, parent_phone, parent_email, registration_no, semester FROM users WHERE role='student' AND department LIKE 'CSE%' ORDER BY id DESC
        """).fetchall()
    else:
        users = conn.execute("""
            SELECT id, name, email, department, roll_no, parent_phone, parent_email, registration_no, semester FROM users WHERE role='student' AND department=? ORDER BY id DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)

@app.route("/admin/user/<int:uid>/delete")
@login_required
@role_required("admin")
def admin_delete_user(uid):
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    flash("User deleted", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/user/<int:uid>/reset-password")
@login_required
@role_required("admin")
def admin_reset_password(uid):
    new_pass = "user" + str(random.randint(1000, 9999))
    conn = get_db_connection()
    user = conn.execute("SELECT email FROM users WHERE id=?", (uid,)).fetchone()
    conn.execute("UPDATE users SET password=? WHERE id=?", (new_pass, uid))
    conn.commit()
    conn.close()
    if user and user["email"]:
        send_email(user["email"], "Password Reset by Admin", f"Your new password: {new_pass}")
    flash("Password reset & emailed", "success")
    return redirect(url_for("admin_users"))

# ---------- Attendance: Admin marks all students for a date ----------
@app.route("/admin/attendance", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_attendance():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        students_raw = conn.execute("SELECT id, name, roll_no, registration_no, semester FROM users WHERE role='student' AND department LIKE 'CSE%'").fetchall()
    else:
        students_raw = conn.execute("SELECT id, name, roll_no, registration_no, semester FROM users WHERE role='student' AND department=?", (admin_branch,)).fetchall()
    students = []
    for s in students_raw:
        total = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?", (s["id"],)).fetchone()[0]
        present = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (s["id"],)).fetchone()[0]
        percent = round((present/total)*100,1) if total>0 else 0
        students.append({"id": s["id"], "name": s["name"], "roll_no": s["roll_no"], "registration_no": s["registration_no"], "semester": s["semester"], "percent": percent})
    if request.method == "POST":
        date = request.form.get("date")
        # save each student's status from form fields named status_{id}
        for s in students:
            status = request.form.get(f"status_{s['id']}")
            if status:
                conn.execute("INSERT INTO attendance (student_id, date, status, semester) VALUES (?, ?, ?, ?)", (s["id"], date, status, s["semester"]))
        conn.commit()
        flash("Attendance saved!", "success")
    conn.close()
    return render_template("admin_attendance.html", students=students)

# ---------- Attendance list ----------
@app.route("/admin/attendance/list")
@login_required
@role_required("admin")
def attendance_list():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        data = conn.execute("""
            SELECT a.date, a.status, a.semester, u.name, u.roll_no, u.registration_no, u.department
            FROM attendance a JOIN users u ON a.student_id=u.id WHERE u.department LIKE 'CSE%' ORDER BY a.date DESC
        """).fetchall()
    else:
        data = conn.execute("""
            SELECT a.date, a.status, a.semester, u.name, u.roll_no, u.registration_no, u.department
            FROM attendance a JOIN users u ON a.student_id=u.id WHERE u.department=? ORDER BY a.date DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    return render_template("attendance_list.html", data=data)

# ---------- Exports ----------
def _export_to_excel(headers, rows, prefix, sheet_name):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for r in rows:
        ws.append(list(r))
    os.makedirs("exports", exist_ok=True)
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join("exports", filename)
    wb.save(path)
    return path

@app.route("/admin/export/attendance")
@login_required
@role_required("admin")
def export_attendance():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        rows = conn.execute("""
            SELECT a.id, u.name, u.roll_no, u.registration_no, u.department, a.date, a.status, a.semester
            FROM attendance a JOIN users u ON a.student_id=u.id WHERE u.department LIKE 'CSE%' ORDER BY a.date DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT a.id, u.name, u.roll_no, u.registration_no, u.department, a.date, a.status, a.semester
            FROM attendance a JOIN users u ON a.student_id=u.id WHERE u.department=? ORDER BY a.date DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    headers = ["ID","Name","Roll No","Registration No","Department","Date","Status","Semester"]
    path = _export_to_excel(headers, rows, "attendance", "Attendance")
    return send_file(path, as_attachment=True)

@app.route("/admin/export/leaves")
@login_required
@role_required("admin")
def export_leaves():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        rows = conn.execute("""
            SELECT l.id, u.name, u.roll_no, u.department, l.from_date, l.to_date, l.status, l.decision_reason, l.applied_on
            FROM leaves l JOIN users u ON l.student_id=u.id WHERE u.department LIKE 'CSE%' ORDER BY l.applied_on DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT l.id, u.name, u.roll_no, u.department, l.from_date, l.to_date, l.status, l.decision_reason, l.applied_on
            FROM leaves l JOIN users u ON l.student_id=u.id WHERE u.department=? ORDER BY l.applied_on DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    headers = ["ID","Name","Roll No","Department","From","To","Status","Decision Reason","Applied On"]
    path = _export_to_excel(headers, rows, "leaves", "Leaves")
    return send_file(path, as_attachment=True)

@app.route("/admin/export/users")
@login_required
@role_required("admin")
def export_users():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")
    if admin_branch == "CSE":
        rows = conn.execute("""
            SELECT id, name, email, department, semester, roll_no, registration_no, parent_phone, parent_email FROM users WHERE role='student' AND department LIKE 'CSE%' ORDER BY id DESC
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT id, name, email, department, semester, roll_no, registration_no, parent_phone, parent_email FROM users WHERE role='student' AND department=? ORDER BY id DESC
        """, (admin_branch,)).fetchall()
    conn.close()
    headers = ["ID","Name","Email","Department","Semester","Roll No","Registration No","Parent Phone","Parent Email"]
    path = _export_to_excel(headers, rows, "students", "Students")
    return send_file(path, as_attachment=True)

# ---------- Developer Login & Panel ----------
@app.route("/developer/login", methods=["GET", "POST"])
def developer_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == os.environ.get("DEVELOPER_USERNAME", DEVELOPER_USERNAME) and password == os.environ.get("DEVELOPER_PASSWORD", DEVELOPER_PASSWORD):
            session["developer"] = True
            flash("Developer logged in", "success")
            return redirect(url_for("developer_panel"))
        flash("Invalid developer credentials", "danger")
    return render_template("developer_login.html")

@app.route("/developer/logout")
def developer_logout():
    session.pop("developer", None)
    flash("Developer logged out", "info")
    return redirect(url_for("login"))

@app.route("/developer/panel")
@developer_required
def developer_panel():
    conn = get_db_connection()
    users = conn.execute("SELECT id, name, email, role, department FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("developer_panel.html", users=users)

@app.route("/developer/clear/students")
@developer_required
def developer_clear_students():
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE role='student'")
    conn.commit()
    conn.close()
    flash("All students deleted", "warning")
    return redirect(url_for("developer_panel"))

@app.route("/developer/clear/leaves")
@developer_required
def developer_clear_leaves():
    conn = get_db_connection()
    conn.execute("DELETE FROM leaves")
    conn.commit()
    conn.close()
    flash("All leaves deleted", "warning")
    return redirect(url_for("developer_panel"))

@app.route("/developer/clear/attendance")
@developer_required
def developer_clear_attendance():
    conn = get_db_connection()
    conn.execute("DELETE FROM attendance")
    conn.commit()
    conn.close()
    flash("All attendance deleted", "warning")
    return redirect(url_for("developer_panel"))

@app.route("/developer/reset-db")
@developer_required
def developer_reset_db():
    try:
        if os.path.exists(DB_NAME):
            os.remove(DB_NAME)
        create_tables()
        flash("Database reset to fresh state", "success")
    except Exception as e:
        flash("Error resetting DB: " + str(e), "danger")
    return redirect(url_for("developer_panel"))
# ================= DELETE ALL ADMINS =================
@app.route("/developer/delete-admins")
def developer_clear_admins():
    if not session.get("is_developer"):
        flash("Access denied!", "danger")
        return redirect(url_for("developer_login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE role='admin'")
    conn.commit()
    conn.close()

    flash("All admins deleted successfully!", "success")
    return redirect(url_for("developer_panel"))

# ---------- Init DB route (manual) ----------
@app.route("/init-db")
def init_db_route():
    # This route helps you initialize DB once on server (protected lightly)
    create_tables()
    return "DB initialized."
# ================= AUTO CREATE DEVELOPER ================= #
def create_developer():
    conn = get_db_connection()

    dev = conn.execute(
        "SELECT * FROM users WHERE role='developer'"
    ).fetchone()

    if not dev:
        conn.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES ('Developer', 'developer@admin.com', 'dev123', 'developer')
        """)
        conn.commit()

    conn.close()

create_developer()

# ---------- Run ----------
if __name__ == "__main__":
    # Port for Render or local default 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

