# final_app.py - complete cleaned app.py
import os
print("DB PATH USED BY APP:", os.path.abspath("leave.db"))

import sqlite3
import tempfile
import random
from datetime import datetime
from functools import wraps
from fpdf import FPDF
from flask import send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file
)
from flask_mail import Mail, Message


from openpyxl import Workbook
from werkzeug.utils import secure_filename

# ---------------- CONFIG ----------------
DB_NAME = "leave.db"
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-key")
MAIL_USERNAME = os.environ.get("faiyajalamkpv62040@gmail.com", "")
MAIL_PASSWORD = os.environ.get("rlwg tkyk ldfo kzbx", "")

DEVELOPER_EMAIL = "developer@admin.com"
DEVELOPER_PASS = "dev123"

UPLOAD_FOLDER = "static/profile_images"

# ---------------- FLASK ----------------
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Mail config (optional)
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = MAIL_USERNAME
app.config["MAIL_PASSWORD"] = MAIL_PASSWORD

mail = Mail(app)


# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT,
            department TEXT,
            semester TEXT,
            roll_no TEXT,
            registration_no TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            admin_branch TEXT,
            photo TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
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

    c.execute("""
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

    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_user_id INTEGER,
            content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(from_user_id) REFERENCES users(id),
            FOREIGN KEY(to_user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

# Run table creation ONLY if DB does NOT exist
if not os.path.exists(DB_NAME):
    create_tables()



# ---------------- UTIL ----------------
def send_email(to, subject, body):
    try:
        msg = Message(subject, sender=MAIL_USERNAME, recipients=[to])
        msg.body = body
        mail.send(msg)
        print("Email sent successfully")
    except Exception as e:
        print("Email error:", e)



# ---------------- DECORATORS ----------------
def login_required(role=None):
    """
    Use as:
      @login_required()            -> requires login (any role)
      @login_required(role="admin") -> requires login and role==admin (case-insensitive)
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login first!", "danger")
                return redirect(url_for("login"))
            if role:
                user_role = session.get("user_role", "")
                if user_role is None or user_role.lower() != role.lower():
                    flash("Access denied!", "danger")
                    return redirect(url_for("login"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ---------------- AUTH & INDEX ----------------
@app.route("/")
def index():
    # redirect based on session role
    role = session.get("user_role", "")
    if role:
        if role.lower() == "admin":
            return redirect(url_for("admin_dashboard"))
        if role.lower() == "student":
            return redirect(url_for("student_dashboard"))
        if role.lower() == "developer":
            return redirect(url_for("developer_panel"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Single login route that supports optional developer mode:
    - /login?mode=developer  -> developer login page
    """
    mode = request.args.get("mode", "normal")

    # developer login
    if mode == "developer":
        if request.method == "POST":
            email = request.form.get("email", "").lower()
            password = request.form.get("password", "")
            if email == DEVELOPER_EMAIL and password == DEVELOPER_PASS:
                session["developer"] = True
                session["user_role"] = "developer"
                session["user_id"] = 0
                session["user_name"] = "Developer"
                return redirect(url_for("developer_panel"))
            flash("Invalid Developer Credentials!", "danger")
            return redirect(url_for("login", mode="developer"))
        return render_template("login.html", developer_mode=True)

    # normal login
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if not user:
            flash("Invalid Email or Password!", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["user_role"] = user["role"]
        session["user_name"] = user["name"]
        session["user_photo"] = user["photo"]


        # save admin_branch for admin users
        if user["role"] and user["role"].lower() == "admin":
            session["admin_branch"] = user["admin_branch"]

        # redirect by role
        if user["role"]:
            if user["role"].lower() == "admin":
                return redirect(url_for("admin_dashboard"))
            if user["role"].lower() == "student":
                return redirect(url_for("student_dashboard"))
            if user["role"].lower() == "developer":
                return redirect(url_for("developer_panel"))

        return redirect(url_for("index"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out!", "info")
    return redirect(url_for("login"))


# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            conn.close()
            flash("Email not found!", "danger")
            return redirect(url_for("forgot_password"))

        new_pass = "pass" + str(random.randint(1000, 9999))
        conn.execute("UPDATE users SET password=? WHERE id=?", (new_pass, user["id"]))
        conn.commit()
        conn.close()

        # try to send email (if configured)
        try:
            send_email(email, "Password Reset", f"Your new password is: {new_pass}")
        except Exception:
            pass

        flash("New password sent to your email (if configured)!", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# ---------------- REGISTRATION ----------------
@app.route("/register/student", methods=["GET", "POST"])
def register_student():
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        department = request.form.get("department", "")
        semester = request.form.get("semester", "")
        roll_no = request.form.get("roll_no", "")
        reg_no = request.form.get("registration_no", "")
        parent_phone = request.form.get("parent_phone", "")
        parent_email = request.form.get("parent_email", "")

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (name, email, password, role, department, semester, roll_no, registration_no, parent_phone, parent_email)
                VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?)
            """, (name, email, password, department, semester, roll_no, reg_no, parent_phone, parent_email))
            conn.commit()
            flash("Student Registered!", "success")
        except Exception:
            flash("Email already exists or error!", "danger")
        finally:
            conn.close()
        return redirect(url_for("login"))
    return render_template("register_student.html")


@app.route("/register/admin", methods=["GET", "POST"])
def register_admin():
    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        branch = request.form.get("admin_branch", "")

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (name, email, password, role, admin_branch)
                VALUES (?, ?, ?, 'admin', ?)
            """, (name, email, password, branch))
            conn.commit()
            flash("Admin Registered Successfully!", "success")
        except Exception:
            flash("Email already exists or error!", "danger")
        finally:
            conn.close()
        return redirect(url_for("login"))
    return render_template("register_admin.html")


# ---------------- STUDENT PROFILE / UPLOAD PHOTO ----------------
@app.route("/student/profile")
@login_required(role="student")
def student_profile():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("student_profile.html", user=user)


@app.route("/student/upload-photo", methods=["POST"])
@login_required(role="student")
def upload_photo():

    if "photo" not in request.files:
        flash("No file selected!", "danger")
        return redirect(url_for("student_profile"))

    file = request.files["photo"]

    if file.filename == "":
        flash("No file selected!", "danger")
        return redirect(url_for("student_profile"))

    # Secure filename
    original = secure_filename(file.filename)
    filename = f"{session['user_id']}_{original}"

    # FIXED PATH (CORRECT)
    folder = os.path.join(app.root_path, "static", "profile_images")

    filepath = os.path.join(folder, filename)
    file.save(filepath)

    conn = get_db()
    conn.execute(
        "UPDATE users SET photo=? WHERE id=?", 
        (filename, session["user_id"])
    )
    conn.commit()
    conn.close()

    flash("Profile photo updated!", "success")
    return redirect(url_for("student_profile"))


# ---------------- STUDENT DASHBOARD / SUPPORT / APPLY ----------------
@app.route("/student/dashboard")
@login_required(role="student")
def student_dashboard():

    conn = get_db()
    sid = session["user_id"]

    student = conn.execute("""
        SELECT department, semester
        FROM users
        WHERE id = ?
    """, (sid,)).fetchone()

    raw_department = student["department"]
    semester = student["semester"]

    # 🔥 FINAL FIX (ALL BRANCH)
    subject_dept = SUBJECT_DEPT_MAP.get(raw_department)

    # ---------- LEAVES ----------
    leaves = conn.execute("""
        SELECT *
        FROM leaves
        WHERE student_id=?
        ORDER BY applied_on DESC
    """, (sid,)).fetchall()

    stats = conn.execute("""
        SELECT 
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END),0) AS approved,
            COALESCE(SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END),0) AS pending,
            COALESCE(SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END),0) AS rejected
        FROM leaves
        WHERE student_id=?
    """, (sid,)).fetchone()

    # ---------- DAILY ----------
    attendance = conn.execute("""
        SELECT date, status
        FROM attendance
        WHERE student_id=?
        ORDER BY date DESC
    """, (sid,)).fetchall()

    # ---------- SUBJECT WISE (ALL BRANCH) ----------
    subject_attendance = conn.execute("""
        SELECT
            s.name AS subject,
            COUNT(a.id) AS total_classes,
            COALESCE(
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),0
            ) AS present_days
        FROM subjects s
        LEFT JOIN attendance a
            ON a.subject_id=s.id
           AND a.student_id=?
        WHERE s.department=?
          AND s.semester=?
        GROUP BY s.id
        ORDER BY s.name
    """, (sid, subject_dept, semester)).fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        leaves=leaves,
        stats=stats,
        attendance=attendance,
        subject_attendance=subject_attendance,
        semester=semester
    )



@app.route("/leave/apply", methods=["GET", "POST"])
@login_required(role="student")
def apply_leave():
    if request.method == "POST":
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")
        reason = request.form.get("reason")

        # ---------------- DATE VALIDATION ----------------
        try:
            d1 = datetime.strptime(from_date, "%Y-%m-%d")
            d2 = datetime.strptime(to_date, "%Y-%m-%d")
        except:
            flash("Invalid date format!", "danger")
            return redirect(url_for("apply_leave"))

        if d2 < d1:
            flash("To date cannot be before From date!", "danger")
            return redirect(url_for("apply_leave"))

        days = (d2 - d1).days + 1
        medical_filename = None

        # ---------------- MEDICAL CERTIFICATE (MANDATORY 15+ DAYS) ----------------
        if days >= 15:
            file = request.files.get("medical_file")

            if not file or file.filename == "":
                flash("Medical Certificate is REQUIRED for leave of 15 days or more!", "danger")
                return redirect(url_for("apply_leave"))

            filename = secure_filename(file.filename)

            allowed = (".pdf", ".jpg", ".jpeg", ".png")
            if not filename.lower().endswith(allowed):
                flash("Only PDF / JPG / PNG files allowed!", "danger")
                return redirect(url_for("apply_leave"))

            os.makedirs("static/medical", exist_ok=True)
            file.save(os.path.join("static/medical", filename))

            medical_filename = filename

        # ---------------- SAVE TO DATABASE ----------------
        conn = get_db()

        conn.execute("""
            INSERT INTO leaves
            (student_id, from_date, to_date, reason, medical_file)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            from_date,
            to_date,
            reason,
            medical_filename
        ))

        # ---------------- FETCH PARENT EMAIL ----------------
        parent = conn.execute("""
            SELECT name, parent_email
            FROM users
            WHERE id = ?
        """, (session["user_id"],)).fetchone()

        conn.commit()
        conn.close()

        # ---------------- SEND EMAIL TO PARENT (FREE) ----------------
        if parent and parent["parent_email"]:
            send_email(
                parent["parent_email"],
                "Leave Application Submitted",
                f"""
Dear Parent,

Your ward {parent['name']} has applied for leave.

Leave Duration : {days} day(s)
From Date      : {from_date}
To Date        : {to_date}
Reason         : {reason}

Medical Certificate : {"Attached in system" if medical_filename else "Not Required"}

Please login to the college portal for more details.

Regards,
College Leave Management System
                """
            )

        flash("Leave applied successfully! Parent notified via email.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("apply_leave.html")

@app.route("/student/attendance/subjects")
@login_required(role="student")
def student_subject_attendance():

    conn = get_db()
    student_id = session["user_id"]

    # ---------- STUDENT INFO ----------
    student = conn.execute("""
        SELECT department, semester
        FROM users
        WHERE id = ?
    """, (student_id,)).fetchone()

    if not student:
        conn.close()
        return []

    raw_department = student["department"]
    semester = student["semester"]

    # ---------- SUBJECT DEPARTMENT MAPPING ----------
    if raw_department and "CSE" in raw_department:
        subject_department = "CSE"
    elif raw_department == "CE":
        subject_department = "Civil"
    else:
        subject_department = raw_department

    # ---------- SUBJECT-WISE ATTENDANCE ----------
    data = conn.execute("""
        SELECT
            s.id AS subject_id,
            s.name AS subject,
            COUNT(a.id) AS total_classes,
            COALESCE(
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END),
                0
            ) AS present_days
        FROM subjects s
        LEFT JOIN attendance a
            ON a.subject_id = s.id
           AND a.student_id = ?
           AND a.semester = ?
        WHERE s.department = ?
          AND s.semester = ?
        GROUP BY s.id
        ORDER BY s.name
    """, (
        student_id,
        semester,
        subject_department,
        semester
    )).fetchall()

    conn.close()
    return data


# ---------------- ADMIN DASHBOARD / LEAVE UPDATE / SUPPORT ----------------
@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    conn = get_db()

    # 🔐 Admin branch
    branch = session.get("admin_branch", "") or ""

    # 🔔 Unread Support Messages Count
    unread_count = conn.execute("""
        SELECT COUNT(*) 
        FROM support_messages 
        WHERE seen = 0
    """).fetchone()[0]

    # 📄 Leave Applications (branch-wise)
    leaves = conn.execute("""
        SELECT l.*, u.name, u.roll_no, u.department
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE u.department LIKE ?
        ORDER BY l.applied_on DESC
    """, (f"{branch}%",)).fetchall()

    # 📊 Leave Statistics
    stats = {
        "total": conn.execute("""
            SELECT COUNT(*) 
            FROM leaves l 
            JOIN users u ON l.student_id = u.id 
            WHERE u.department LIKE ?
        """, (f"{branch}%",)).fetchone()[0],

        "approved": conn.execute("""
            SELECT COUNT(*) 
            FROM leaves l 
            JOIN users u ON l.student_id = u.id 
            WHERE l.status='Approved' 
              AND u.department LIKE ?
        """, (f"{branch}%",)).fetchone()[0],

        "pending": conn.execute("""
            SELECT COUNT(*) 
            FROM leaves l 
            JOIN users u ON l.student_id = u.id 
            WHERE l.status='Pending' 
              AND u.department LIKE ?
        """, (f"{branch}%",)).fetchone()[0],

        "rejected": conn.execute("""
            SELECT COUNT(*) 
            FROM leaves l 
            JOIN users u ON l.student_id = u.id 
            WHERE l.status='Rejected' 
              AND u.department LIKE ?
        """, (f"{branch}%",)).fetchone()[0],
    }

    # 🏫 Departments list (optional)
    departments = conn.execute("""
        SELECT DISTINCT department 
        FROM users 
        WHERE role='student'
    """).fetchall()

    conn.close()

    # ✅ PASS unread_count TO TEMPLATE
    return render_template(
        "admin_dashboard.html",
        leaves=leaves,
        stats=stats,
        departments=departments,
        unread_count=unread_count
    )


@app.route("/admin/leave/<int:lid>/update", methods=["POST"])
@login_required(role="admin")
def admin_update_leave(lid):
    status = request.form.get("status", "")
    reason = request.form.get("decision_reason", "")
    conn = get_db()
    conn.execute("UPDATE leaves SET status=?, decision_reason=? WHERE id=?", (status, reason, lid))
    conn.commit()
    conn.close()
    flash("Leave Updated Successfully!", "success")
    return redirect(url_for("admin_dashboard"))

# ----------------- STUDENT SUPPORT (SEND MESSAGE + VIEW REPLY) -----------------

@app.route("/student/support", methods=["GET", "POST"])
@login_required(role="student")
def student_support():
    conn = get_db()
    student_id = session["user_id"]

    # mark admin messages as seen
    conn.execute("""
        UPDATE support_messages
        SET seen = 1
        WHERE student_id = ? AND sender = 'admin'
    """, (student_id,))
    conn.commit()

    if request.method == "POST":
        msg = request.form.get("content", "").strip()
        if not msg:
            flash("Message cannot be empty", "danger")
            return redirect(url_for("student_support"))

        conn.execute("""
            INSERT INTO support_messages (student_id, sender, message)
            VALUES (?, 'student', ?)
        """, (student_id, msg))
        conn.commit()

        return redirect(url_for("student_support"))

    messages = conn.execute("""
        SELECT * FROM support_messages
        WHERE student_id = ?
        ORDER BY created_at ASC
    """, (student_id,)).fetchall()

    conn.close()
    return render_template("student_support.html", messages=messages)


# ----------------- ADMIN SUPPORT (VIEW + REPLY) -----------------
@app.route("/admin/support")
@login_required(role="admin")
def admin_support():
    conn = get_db()

    students = conn.execute("""
        SELECT
            u.id,
            u.name,
            u.semester,
            u.registration_no,
            COUNT(sm.id) AS unread
        FROM users u
        JOIN support_messages sm ON sm.student_id = u.id
        WHERE u.role='student'
        GROUP BY u.id
        ORDER BY MAX(sm.created_at) DESC
    """).fetchall()

    conn.close()
    return render_template("admin_support.html", students=students)

@app.route("/admin/support/reply/<int:student_id>", methods=["POST"])
@login_required(role="admin")
def admin_support_reply(student_id):
    reply = request.form.get("reply", "").strip()
    if not reply:
        return redirect(url_for("admin_support_chat", student_id=student_id))

    conn = get_db()
    conn.execute("""
        INSERT INTO support_messages (student_id, sender, message)
        VALUES (?, 'admin', ?)
    """, (student_id, reply))
    conn.commit()
    conn.close()

    return redirect(url_for("admin_support_chat", student_id=student_id))


# ----------------- ADMIN SEND REPLY -----------------
@app.route("/admin/support/<int:student_id>")
@login_required(role="admin")
def admin_support_chat(student_id):
    conn = get_db()

    student = conn.execute("""
        SELECT id, name, semester, registration_no
        FROM users
        WHERE id = ? AND role = 'student'
    """, (student_id,)).fetchone()

    if not student:
        conn.close()
        flash("Student not found", "danger")
        return redirect(url_for("admin_support"))

    messages = conn.execute("""
        SELECT * FROM support_messages
        WHERE student_id = ?
        ORDER BY created_at ASC
    """, (student_id,)).fetchall()

    # mark student messages seen
    conn.execute("""
        UPDATE support_messages
        SET seen = 1
        WHERE student_id = ? AND sender = 'student'
    """, (student_id,))
    conn.commit()

    conn.close()
    return render_template(
        "admin_support_chat.html",
        student=student,
        messages=messages,
        student_id=student_id
    )


# ---------------- ADMIN USERS / EDIT / DELETE / RESET ----------------
@app.route("/admin/users")
@login_required(role="admin")
def admin_users():
    branch = session.get("admin_branch", "") or ""
    conn = get_db()
    users = conn.execute("""
    SELECT 
        id,
        name,
        email,
        department,
        roll_no,
        registration_no,
        parent_phone,
        parent_email
    FROM users
    WHERE role='student'
      AND department LIKE ?
    ORDER BY id DESC
""", (f"{branch}%",)).fetchall()

    return render_template("admin_users.html", users=users)


@app.route("/admin/user/<int:uid>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def edit_user(uid):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        flash("User not found!", "danger")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        department = request.form.get("department", "")
        roll_no = request.form.get("roll_no", "")
        conn.execute("UPDATE users SET name=?, email=?, department=?, roll_no=? WHERE id=?", (name, email, department, roll_no, uid))
        conn.commit()
        conn.close()
        flash("User Updated Successfully!", "success")
        return redirect(url_for("admin_users"))

    conn.close()
    return render_template("edit_user.html", user=user)


@app.route("/admin/user/<int:uid>/delete")
@login_required(role="admin")
def admin_delete_user(uid):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    flash("Student Deleted!", "warning")
    return redirect(url_for("admin_users"))


@app.route("/admin/user/<int:uid>/reset-password")
@login_required(role="admin")
def admin_reset_password(uid):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if not user:
        conn.close()
        flash("User not found!", "danger")
        return redirect(url_for("admin_users"))

    new_pass = "pass" + str(random.randint(1000, 9999))
    conn.execute("UPDATE users SET password=? WHERE id=?", (new_pass, uid))
    conn.commit()
    conn.close()

    flash(f"New password for {user['name']} is: {new_pass}", "success")
    return redirect(url_for("admin_users"))


# ---------------- ADMIN ATTENDANCE / EXPORT ----------------
# Subjects department mapping
SUBJECT_DEPT_MAP = {
    "CSE": "CSE",
    "CSE (Network)": "CSE",
    "CSE (Cyber Security)": "CSE",

    "Civil": "Civil",
    "CE": "Civil",

   "Mechanical": "Mechanical",
    "Mechanical Engineering": "Mechanical",
    "ME": "Mechanical",

    "Electrical": "EE",
    "EE": "EE",

    "Electronics": "ECE",
    "ECE": "ECE"
}

@app.route("/admin/attendance", methods=["GET", "POST"])
@login_required(role="admin")
def admin_attendance():

    conn = get_db()
    admin_branch = session.get("admin_branch")
    # examples:
    # "CSE (Network)", "CSE (Cyber Security)", "CE", "EE", "ECE", "Mechanical"

    # ---------------- HELPER ----------------
    def normalize(val):
        if val in (None, "", "None", "null"):
            return None
        return val

    # ---------------- GET / POST ----------------
    if request.method == "POST":
        semester = normalize(request.form.get("semester"))
        subject_id = normalize(request.form.get("subject_id"))
        sub_branch = normalize(request.form.get("sub_branch"))
    else:
        semester = normalize(request.args.get("semester"))
        subject_id = normalize(request.args.get("subject_id"))
        sub_branch = normalize(request.args.get("sub_branch"))

    # ---------------- SAFE INT ----------------
    semester = int(semester) if semester else None
    subject_id = int(subject_id) if subject_id else None

    # ---------------- DEPARTMENT LOGIC ----------------
    if admin_branch and "CSE" in admin_branch:
        subject_dept = "CSE"
        student_dept = sub_branch      # CSE (Network) / CSE (Cyber Security)
    elif admin_branch == "CE":
        subject_dept = "Civil"
        student_dept = "CE"
    else:
        subject_dept = admin_branch
        student_dept = admin_branch

    # ---------------- SUBJECT LIST ----------------
    subjects = []
    if subject_dept and semester:
        subjects = conn.execute("""
            SELECT id, name
            FROM subjects
            WHERE department = ?
              AND semester = ?
            ORDER BY name
        """, (subject_dept, semester)).fetchall()

    # ---------------- STUDENT LIST ----------------
    students = []
    if student_dept and semester:
        students = conn.execute("""
            SELECT id, name, roll_no, registration_no
            FROM users
            WHERE role='student'
              AND department = ?
              AND semester = ?
            ORDER BY roll_no
        """, (student_dept, semester)).fetchall()

    # ---------------- SAVE ATTENDANCE ----------------
    if request.method == "POST":

        if not subject_id:
            flash("Please select subject first!", "danger")
            conn.close()
            return redirect(url_for("admin_attendance", semester=semester))

        date = request.form.get("date")

        for s in students:
            status = request.form.get(f"status_{s['id']}")
            if status:
                conn.execute("""
                    INSERT INTO attendance
                    (student_id, subject_id, semester, date, status)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    s["id"],
                    subject_id,
                    semester,
                    date,
                    status
                ))

        conn.commit()
        conn.close()
        flash("Attendance saved successfully", "success")
        return redirect(url_for(  "admin_attendance",
         semester=semester,
         subject_id=subject_id,
         sub_branch=sub_branch
     ))


    conn.close()

    return render_template(
        "admin_attendance.html",
        admin_branch=admin_branch,
        sub_branch=sub_branch,
        semester=semester,
        subjects=subjects,
        students=students,
        subject_id=subject_id
    )
@app.route("/admin/attendance/records")
@login_required(role="admin")
def admin_attendance_records():

    conn = get_db()

    admin_branch = session.get("admin_branch")     # CSE / Civil / Mechanical etc
    sub_branch = request.args.get("sub_branch")    # CSE (Network) / CSE (Cyber Security)
    semester = request.args.get("semester")
    subject_id = request.args.get("subject_id")
    date = request.args.get("date")

    # ---------- FINAL BRANCH ----------
    if admin_branch == "CSE":
        final_branch = sub_branch
    else:
        final_branch = admin_branch

    if not final_branch:
        conn.close()
        return render_template(
            "admin_attendance_records.html",
            admin_branch=admin_branch,
            records=[],
            subjects=[]
        )

    subject_dept = SUBJECT_DEPT_MAP.get(final_branch)

    # ---------- SUBJECT LIST ----------
    subjects = []
    if semester and subject_dept:
        subjects = conn.execute("""
            SELECT id, name
            FROM subjects
            WHERE department=? AND semester=?
            ORDER BY name
        """, (subject_dept, semester)).fetchall()

    # ---------- ATTENDANCE RECORDS WITH % ----------
    query = """
        SELECT
            u.name,
            u.roll_no,
            u.registration_no,
            s.name AS subject,
            a.date,
            a.status,

            ROUND(
                (
                    SELECT COUNT(*)
                    FROM attendance a2
                    WHERE a2.student_id = u.id
                      AND a2.subject_id = a.subject_id
                      AND a2.status = 'Present'
                ) * 100.0
                /
                (
                    SELECT COUNT(*)
                    FROM attendance a3
                    WHERE a3.student_id = u.id
                      AND a3.subject_id = a.subject_id
                ),
            2) AS percentage

        FROM attendance a
        JOIN users u ON u.id = a.student_id
        JOIN subjects s ON s.id = a.subject_id
        WHERE u.department = ?
    """
    params = [final_branch]

    if semester:
        query += " AND a.semester = ?"
        params.append(int(semester))

    if subject_id:
        query += " AND a.subject_id = ?"
        params.append(int(subject_id))

    if date:
        query += " AND a.date = ?"
        params.append(date)

    query += " ORDER BY u.roll_no, a.date"

    records = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "admin_attendance_records.html",
        admin_branch=admin_branch,
        sub_branch=sub_branch,
        semester=semester,
        subject_id=subject_id,
        date=date,
        subjects=subjects,
        records=records
    )



@app.route("/admin/export/attendance/excel")
@login_required(role="admin")
def export_attendance_excel():

    import pandas as pd
    import tempfile
    from flask import send_file, redirect, url_for, flash

    conn = get_db()

    admin_branch = session.get("admin_branch")
    sub_branch = request.args.get("sub_branch")
    semester = request.args.get("semester")
    subject_id = request.args.get("subject_id")
    date = request.args.get("date")
    all_dates = request.args.get("all_dates")   # "1" or None

    # ---------- FINAL BRANCH ----------
    if admin_branch == "CSE":
        final_branch = sub_branch
    else:
        final_branch = admin_branch

    if not final_branch:
        flash("Please select branch", "danger")
        return redirect(url_for("admin_attendance_records"))

    query = """
        SELECT
            u.name AS Student,
            u.roll_no AS Roll,
            u.registration_no AS Registration,
            s.name AS Subject,
            a.date AS Date,
            a.status AS Status,

            ROUND(
                (
                    SELECT COUNT(*)
                    FROM attendance a2
                    WHERE a2.student_id = u.id
                      AND a2.subject_id = a.subject_id
                      AND a2.status = 'Present'
                ) * 100.0
                /
                (
                    SELECT COUNT(*)
                    FROM attendance a3
                    WHERE a3.student_id = u.id
                      AND a3.subject_id = a.subject_id
                ),
            2) AS Percentage

        FROM attendance a
        JOIN users u ON u.id = a.student_id
        JOIN subjects s ON s.id = a.subject_id
        WHERE u.department = ?
    """
    params = [final_branch]

    if semester:
        query += " AND a.semester = ?"
        params.append(int(semester))

    if subject_id:
        query += " AND a.subject_id = ?"
        params.append(int(subject_id))

    # 🔥 DATE FILTER ONLY WHEN NOT ALL_DATES
    if date and date.strip() != "" and not all_dates:
       query += " AND a.date = ?"
       params.append(date)

    query += " ORDER BY u.roll_no, a.date"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        flash("No attendance data found", "warning")
        return redirect(url_for("admin_attendance_records"))

    df = pd.DataFrame(rows, columns=rows[0].keys())

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    df.to_excel(tmp.name, index=False)

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name="attendance_report.xlsx"
    )

@app.route("/admin/attendance/pdf")
@login_required(role="admin")
def admin_attendance_pdf():

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import tempfile

    semester = int(request.args.get("semester"))
    subject_id = int(request.args.get("subject_id"))
    date = request.args.get("date")

    conn = get_db()

    data = conn.execute("""
        SELECT
            u.name,
            u.roll_no,
            COUNT(a.id) AS total,
            SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present
        FROM users u
        LEFT JOIN attendance a
          ON a.student_id=u.id
         AND a.subject_id=?
         AND a.semester=?
        GROUP BY u.id
        ORDER BY u.roll_no
    """, (subject_id, semester)).fetchall()

    conn.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)

    y = 800
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Attendance Report")
    y -= 30

    for r in data:
        percent = (r["present"]/r["total"]*100) if r["total"] else 0
        c.drawString(
            50, y,
            f"{r['roll_no']} | {r['name']} | {percent:.1f}%"
        )
        y -= 18
        if y < 50:
            c.showPage()
            y = 800

    c.save()

    return send_file(tmp.name, as_attachment=False)

from fpdf import FPDF
from fpdf import FPDF
from flask import send_file
import tempfile


# ---------------- DEVELOPER ----------------
@app.route("/developer/login", methods=["GET", "POST"])
def developer_login():
    if request.method == "POST":
        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        if email == DEVELOPER_EMAIL and password == DEVELOPER_PASS:
            session["developer"] = True
            session["user_role"] = "developer"
            session["user_id"] = 0
            session["user_name"] = "Developer"
            return redirect(url_for("developer_panel"))
        flash("Invalid Developer Credentials!", "danger")
        return redirect(url_for("developer_login"))
    return render_template("developer_login.html")


@app.route("/developer/logout")
def developer_logout():
    session.pop("developer", None)
    session.clear()
    return redirect(url_for("login"))


@app.route("/developer/panel")
def developer_panel():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    conn = get_db()
    users = conn.execute("SELECT id, name, email, role, department FROM users ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("developer_panel.html", users=users)


@app.route("/developer/clear/students")
def dev_clear_students():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE role='student'")
    conn.commit()
    conn.close()
    flash("All students deleted!", "danger")
    return redirect(url_for("developer_panel"))


@app.route("/developer/clear/leaves")
def dev_clear_leaves():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    conn = get_db()
    conn.execute("DELETE FROM leaves")
    conn.commit()
    conn.close()
    flash("All leaves deleted!", "danger")
    return redirect(url_for("developer_panel"))


@app.route("/developer/clear/attendance")
def dev_clear_attendance():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    conn = get_db()
    conn.execute("DELETE FROM attendance")
    conn.commit()
    conn.close()
    flash("All attendance deleted!", "danger")
    return redirect(url_for("developer_panel"))


@app.route("/developer/clear/admins")
def dev_clear_admins():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    conn = get_db()
    conn.execute("DELETE FROM users WHERE role='admin'")
    conn.commit()
    conn.close()
    flash("All admins deleted!", "danger")
    return redirect(url_for("developer_panel"))


@app.route("/developer/reset-db")
def dev_reset_db():
    if not session.get("developer"):
        return redirect(url_for("developer_login"))
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    create_tables()
    flash("Database reset!", "success")
    return redirect(url_for("developer_panel"))


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)