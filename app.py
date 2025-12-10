# final_app.py - complete cleaned app.py
import os
import sqlite3
import random
from datetime import datetime
from functools import wraps

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
MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")

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
    except Exception:
        # ignore email errors silently
        pass


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
    sid = session["user_id"]
    conn = get_db()
    leaves = conn.execute("SELECT * FROM leaves WHERE student_id=? ORDER BY applied_on DESC", (sid,)).fetchall()
    stats = conn.execute("""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) AS rejected
        FROM leaves
        WHERE student_id=?
    """, (sid,)).fetchone()
    attendance = conn.execute("SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC", (sid,)).fetchall()
    conn.close()
    return render_template("student_dashboard.html", leaves=leaves, stats=stats, attendance=attendance)


@app.route("/leave/apply", methods=["GET", "POST"])
@login_required(role="student")
def apply_leave():
    if request.method == "POST":
        from_date = request.form.get("from_date", "")
        to_date = request.form.get("to_date", "")
        reason = request.form.get("reason", "")

        conn = get_db()
        conn.execute("INSERT INTO leaves (student_id, from_date, to_date, reason) VALUES (?, ?, ?, ?)",
                     (session["user_id"], from_date, to_date, reason))
        conn.commit()
        conn.close()
        flash("Leave Applied!", "success")
        return redirect(url_for("student_dashboard"))
    return render_template("apply_leave.html")


# ---------------- ADMIN DASHBOARD / LEAVE UPDATE / SUPPORT ----------------
@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    conn = get_db()
    branch = session.get("admin_branch", "") or ""
    leaves = conn.execute("""
        SELECT l.*, u.name, u.roll_no, u.department
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE u.department LIKE ?
        ORDER BY l.applied_on DESC
    """, (f"{branch}%",)).fetchall()

    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM leaves l JOIN users u ON l.student_id=u.id WHERE u.department LIKE ?", (f"{branch}%",)).fetchone()[0],
        "approved": conn.execute("SELECT COUNT(*) FROM leaves l JOIN users u ON l.student_id=u.id WHERE l.status='Approved' AND u.department LIKE ?", (f"{branch}%",)).fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM leaves l JOIN users u ON l.student_id=u.id WHERE l.status='Pending' AND u.department LIKE ?", (f"{branch}%",)).fetchone()[0],
        "rejected": conn.execute("SELECT COUNT(*) FROM leaves l JOIN users u ON l.student_id=u.id WHERE l.status='Rejected' AND u.department LIKE ?", (f"{branch}%",)).fetchone()[0],
    }

    departments = conn.execute("SELECT DISTINCT department FROM users WHERE role='student'").fetchall()
    conn.close()

    return render_template("admin_dashboard.html", leaves=leaves, stats=stats, departments=departments, filters={"from_date": "", "to_date": "", "department": ""})


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

@app.route('/student/support', methods=["GET", "POST"])
@login_required(role="student")
def student_support():
    conn = get_db()

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        if content:
            conn.execute("""
                INSERT INTO support_messages (student_id, content)
                VALUES (?, ?)
            """, (session["user_id"], content))
            conn.commit()
            flash("Message sent successfully", "success")

    # Fetch student messages + admin reply
    msgs = conn.execute("""
        SELECT content, reply, created_at 
        FROM support_messages
        WHERE student_id = ?
        ORDER BY created_at DESC
    """, (session["user_id"],)).fetchall()

    conn.close()
    return render_template("student_support.html", messages=msgs)


# ----------------- ADMIN SUPPORT (VIEW + REPLY) -----------------

@app.route('/admin/support')
@login_required(role="admin")
def admin_support():
    conn = get_db()

    msgs = conn.execute("""
        SELECT 
            sm.id,
            u.name AS student_name,
            sm.content AS student_message,
            sm.reply AS admin_reply,
            sm.created_at
        FROM support_messages sm
        JOIN users u ON sm.student_id = u.id
        ORDER BY sm.created_at DESC
    """).fetchall()

    conn.close()
    return render_template("admin_support.html", messages=msgs)


# ----------------- ADMIN SEND REPLY -----------------

@app.route('/admin/support/reply/<int:id>', methods=["POST"])
@login_required(role="admin")
def admin_support_reply(id):
    reply = request.form.get("reply", "").strip()

    conn = get_db()
    conn.execute("""
        UPDATE support_messages
        SET reply = ?
        WHERE id = ?
    """, (reply, id))
    conn.commit()
    conn.close()

    flash("Reply sent!", "success")
    return redirect(url_for("admin_support"))


# ---------------- ADMIN USERS / EDIT / DELETE / RESET ----------------
@app.route("/admin/users")
@login_required(role="admin")
def admin_users():
    branch = session.get("admin_branch", "") or ""
    conn = get_db()
    users = conn.execute("SELECT id, name, email, roll_no, department FROM users WHERE role='student' AND department LIKE ? ORDER BY id DESC", (f"{branch}%",)).fetchall()
    conn.close()
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
@app.route("/admin/attendance", methods=["GET", "POST"])
@login_required(role="admin")
def admin_attendance():
    conn = get_db()
    branch = session.get("admin_branch", "") or ""
    students = conn.execute("SELECT id, name, roll_no, registration_no, semester FROM users WHERE role='student' AND department LIKE ? ORDER BY roll_no ASC", (f"{branch}%",)).fetchall()

    student_data = []
    for s in students:
        total = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?", (s["id"],)).fetchone()[0]
        present = conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'", (s["id"],)).fetchone()[0]
        percent = round((present / total) * 100, 1) if total > 0 else 0
        student_data.append({
            "id": s["id"],
            "name": s["name"],
            "roll_no": s["roll_no"],
            "registration_no": s["registration_no"],
            "semester": s["semester"],
            "percent": percent
        })

    if request.method == "POST":
        date = request.form.get("date", "")
        for s in student_data:
            status = request.form.get(f"status_{s['id']}")
            if status:
                conn.execute("INSERT INTO attendance (student_id, date, status, semester) VALUES (?, ?, ?, ?)", (s["id"], date, status, s["semester"]))
        conn.commit()
        conn.close()
        flash("Attendance saved!", "success")
        return redirect(url_for("admin_attendance"))

    conn.close()
    return render_template("admin_attendance.html", students=student_data)


@app.route("/admin/attendance/list")
@login_required(role="admin")
def attendance_list():
    conn = get_db()
    branch = session.get("admin_branch", "") or ""

    data = conn.execute("""
        SELECT 
            a.date,
            a.status,
            a.semester,
            u.name,
            u.roll_no,
            u.registration_no,
            u.department
        FROM attendance a
        JOIN users u ON a.student_id = u.id
        WHERE u.department LIKE ?
        ORDER BY a.date DESC
    """, (f"{branch}%",)).fetchall()

    conn.close()
    return render_template("attendance_list.html", data=data)


@app.route("/admin/export/attendance")
@login_required(role="admin")
def export_attendance():
    conn = get_db()
    branch = session.get("admin_branch", "") or ""
    rows = conn.execute("""
        SELECT a.id, u.name, u.roll_no, u.registration_no, u.department, a.date, a.status, a.semester
        FROM attendance a
        JOIN users u ON a.student_id=u.id
        WHERE u.department LIKE ?
        ORDER BY a.date DESC
    """, (f"{branch}%",)).fetchall()
    conn.close()

    headers = ["ID", "Name", "Roll No", "Reg No", "Department", "Date", "Status", "Semester"]
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
    os.makedirs("exports", exist_ok=True)
    filename = f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    path = os.path.join("exports", filename)
    wb.save(path)
    return send_file(path, as_attachment=True)


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
