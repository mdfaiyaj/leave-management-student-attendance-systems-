from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, send_file
)
import sqlite3
from functools import wraps
from flask_mail import Mail, Message
from twilio.rest import Client
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from datetime import datetime
import random
import os
import requests
# ================= SMS FUNCTION ===================

def send_sms(phone, message):
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"

        params = {
            "authorization": "",  # <-- Replace with your API key
            "route": "q",                          # 'q' means Quick SMS route
            "message": message,
            "numbers": phone                       # Single or multiple numbers
        }

        response = requests.get(url, params=params)
        print("SMS sent →", response.text)
        return True

    except Exception as e:
        print("SMS Error →", e)
        return False

# ---------------- CONFIG ---------------- #
TWILIO_SID = ""
TWILIO_AUTH = ""
TWILIO_WHATSAPP = "whatsapp:"

DB_NAME = "leave.db"

app = Flask(__name__)
app.secret_key = "secret-key-change-this"

# ---- Email Config ----
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "faiyajalamkpv62040@gmail.com"
app.config["MAIL_PASSWORD"] = "xqprzjfumt8dqklo"   # Gmail App Password
mail = Mail(app)

# ---- Profile Photo Upload ----
UPLOAD_FOLDER = "static/profile_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ================= DB CONNECTION ================= #
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ================= UTILS ================= #
def send_whatsapp(to, msg):
    try:
        client = Client(TWILIO_SID, TWILIO_AUTH)
        client.messages.create(
            body=msg,
            from_=TWILIO_WHATSAPP,
            to="whatsapp:" + to
        )
        print("WhatsApp sent!")
    except Exception as e:
        print("WhatsApp Error:", e)


def send_email(to, subject, body):
    try:
        msg = Message(subject,
                      sender=app.config['MAIL_USERNAME'],
                      recipients=[to])
        msg.body = body
        mail.send(msg)
        print("Email sent!")
    except Exception as e:
        print("Email Error:", e)


# ================= AUTH DECORATORS ================= #
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
                flash("Access denied!", "danger")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ================= HOME ================= #
@app.route("/")
def index():
    if "user_role" in session:
        if session["user_role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        if session["user_role"] == "student":
            return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


# ================= REGISTER (STUDENT) ================= #
@app.route("/register/student", methods=["GET", "POST"])
def register_student():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()
        department = request.form["department"].strip()          # e.g. CSE (Network), CSE (Cybersecurity), CE, ME, ECE, EE
        semester = request.form["semester"].strip()              # NEW
        roll_no = request.form["roll_no"].strip()
        reg_no = request.form["registration_no"].strip()
        pphone = request.form["parent_phone"].strip()
        pemail = request.form["parent_email"].strip()

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO users 
                (name, email, password, role, department, semester, roll_no, registration_no, parent_phone, parent_email)
                VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?)
            """, (name, email, password, department, semester, roll_no, reg_no, pphone, pemail))

            conn.commit()
            flash("Student registered successfully!", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash("Error: " + str(e), "danger")

        finally:
            conn.close()

    return render_template("register_student.html")


# ================= REGISTER (ADMIN) ================= #
@app.route("/register/admin", methods=["GET", "POST"])
def register_admin():
    """
    Branch-wise admin:
    - admin_branch store karega: CSE, CE, ME, ECE, EE
    - CSE admin => dono department handle: CSE (Network) + CSE (Cybersecurity)
    """
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()
        admin_branch = request.form["admin_branch"].strip()   # NEW

        conn = get_db_connection()

        try:
            conn.execute("""
                INSERT INTO users (name, email, password, role, admin_branch)
                VALUES (?, ?, ?, 'admin', ?)
            """, (name, email, password, admin_branch))

            conn.commit()
            flash("Admin registered successfully!", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash("Error: " + str(e), "danger")

        finally:
            conn.close()

    return render_template("register_admin.html")


# ================= LOGIN ================= #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"].strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            session["user_photo"] = user["photo"]

            # ------------ ADMIN LOGIN ------------
            if user["role"] == "admin":
                session["admin_branch"] = user["admin_branch"]
                return redirect(url_for("admin_dashboard"))

            # ------------ STUDENT LOGIN ------------
            else:
                session["student_branch"] = user["department"]
                session["student_roll"] = user["roll_no"]
                session["student_reg"] = user["registration_no"]
                return redirect(url_for("student_dashboard"))

        else:
            flash("Invalid Email or Password", "danger")

    return render_template("login.html")



# ================= LOGOUT ================= #
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ================= FORGOT PASSWORD ================= #
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if not user:
            conn.close()
            flash("Email not found!", "danger")
            return redirect(url_for("forgot_password"))

        new_pass = "pass" + str(random.randint(1000, 9999))
        conn.execute(
            "UPDATE users SET password=? WHERE id=?",
            (new_pass, user["id"])
        )
        conn.commit()
        conn.close()

        send_email(email, "Password Reset",
                   f"Your new password is: {new_pass}")

        flash("New password sent!", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# ================= STUDENT PROFILE ================= #
@app.route("/student/profile")
@login_required
@role_required("student")
def student_profile():
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return render_template("student_profile.html", user=user)


# ================= UPLOAD PHOTO ================= #
@app.route("/student/upload-photo", methods=["POST"])
@login_required
@role_required("student")
def upload_photo():
    file = request.files.get("photo")

    if not file or file.filename == "":
        flash("No file selected!", "danger")
        return redirect(url_for("student_profile"))

    filename = secure_filename(f"{session['user_id']}_{file.filename}")
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(path)

    conn = get_db_connection()
    conn.execute(
        "UPDATE users SET photo=? WHERE id=?",
        (filename, session["user_id"])
    )
    conn.commit()
    conn.close()

    session["user_photo"] = filename

    flash("Photo updated!", "success")
    return redirect(url_for("student_profile"))


# ================= STUDENT SUPPORT ================= #
@app.route("/student/support", methods=["GET", "POST"])
@login_required
@role_required("student")
def student_support():
    conn = get_db_connection()

    if request.method == "POST":
        content = request.form["content"].strip()
        if content:
            conn.execute(
                """
                INSERT INTO messages (from_user_id, to_user_id, content)
                VALUES (?, ?, ?)
                """,
                (session["user_id"], 1, content)
            )
            conn.commit()
            flash("Message sent!", "success")

    msgs = conn.execute(
        """
        SELECT * FROM messages
        WHERE from_user_id=?
        ORDER BY created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template("student_support.html", messages=msgs)


# ================= STUDENT DASHBOARD ================= #
@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    sid = session["user_id"]
    conn = get_db_connection()

    leaves = conn.execute(
        "SELECT * FROM leaves WHERE student_id=? ORDER BY applied_on DESC",
        (sid,)
    ).fetchall()

    stats = conn.execute(
        """
        SELECT 
            COUNT(*) total,
            SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) approved,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) pending,
            SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) rejected
        FROM leaves WHERE student_id=?
        """,
        (sid,)
    ).fetchone()

    attendance = conn.execute(
        """
        SELECT date, status, semester
        FROM attendance
        WHERE student_id=?
        ORDER BY date DESC
        """,
        (sid,)
    ).fetchall()

    conn.close()

    return render_template(
        "student_dashboard.html",
        leaves=leaves,
        stats=stats,
        attendance=attendance
    )


# ================= APPLY LEAVE ================= #
@app.route("/leave/apply", methods=["GET", "POST"])
@login_required
@role_required("student")
def apply_leave():
    if request.method == "POST":
        from_date = request.form["from_date"]
        to_date = request.form["to_date"]
        reason = request.form["reason"].strip()

        conn = get_db_connection()

        # Insert leave request
        conn.execute(
            "INSERT INTO leaves (student_id, from_date, to_date, reason, status) VALUES (?, ?, ?, ?, ?)",
            (session["user_id"], from_date, to_date, reason, "Pending")
        )

        # Fetch student + parent info
        user = conn.execute(
            "SELECT name, parent_email, parent_phone FROM users WHERE id=?",
            (session["user_id"],)
        ).fetchone()

        conn.commit()
        conn.close()

        # ========== EMAIL TO PARENTS ==========
        if user and user["parent_email"]:
            body = f"""
Dear Parent,

A new leave request has been submitted by your ward: {user['name']}.

From Date : {from_date}
To Date   : {to_date}
Reason    : {reason}

This leave is currently pending for approval.

Regards,
Leave Management System
Government Engineering College Kaimur
"""
            send_email(
                user["parent_email"],
                "New Leave Application Submitted",
                body
            )

        # ========== SMS TO PARENTS ==========
        if user and user["parent_phone"]:
            sms_message = (
                f"Leave Applied\n"
                f"Student: {user['name']}\n"
                f"From: {from_date}\n"
                f"To: {to_date}\n"
                f"Reason: {reason}\n"
                f"- GEC Kaimur LMS"
            )

            send_sms(user["parent_phone"], sms_message)

        flash("Leave applied successfully! Parent notified via Email & SMS.", "success")
        return redirect(url_for("student_dashboard"))

    return render_template("apply_leave.html")



# ================= ADMIN DASHBOARD (BRANCH-WISE) ================= #
@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()

    admin_branch = session.get("admin_branch")  # e.g. "CSE", "CE", "ME", "ECE", "EE"

    # ---- Filters from query string (date + department for CSE split) ----
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    department_filter = request.args.get("department")  # only for CSE (Network / Cybersecurity)

    where_clauses = []
    params = []

    # Branch filter
    if admin_branch == "CSE":
        where_clauses.append("u.department LIKE 'CSE%'")  # CSE (Network) & CSE (Cybersecurity)
        # If specific CSE sub-branch selected
        if department_filter:
            where_clauses.append("u.department = ?")
            params.append(department_filter)
    else:
        where_clauses.append("u.department = ?")
        params.append(admin_branch)

    # Date filters
    if from_date:
        where_clauses.append("l.from_date >= ?")
        params.append(from_date)

    if to_date:
        where_clauses.append("l.to_date <= ?")
        params.append(to_date)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Leaves list
    leaves_sql = f"""
        SELECT l.*, u.name, u.roll_no, u.department
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE {where_sql}
        ORDER BY l.status='Pending' DESC, l.applied_on DESC
    """
    leaves = conn.execute(leaves_sql, params).fetchall()

    # Stats filtered
    stats_sql = f"""
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) AS approved,
            SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) AS pending,
            SUM(CASE WHEN status='Rejected' THEN 1 ELSE 0 END) AS rejected
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE {where_sql}
    """
    stats = conn.execute(stats_sql, params).fetchone()

    # Attendance stats (branch-wise)
    if admin_branch == "CSE":
        attendance_stats = conn.execute(
            """
            SELECT 
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN a.status='Absent'  THEN 1 ELSE 0 END) AS absent
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department LIKE 'CSE%'
            """
        ).fetchone()
    else:
        attendance_stats = conn.execute(
            """
            SELECT 
                SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN a.status='Absent'  THEN 1 ELSE 0 END) AS absent
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department = ?
            """,
            (admin_branch,)
        ).fetchone()

    # Department list for dropdown (CSE admin ke liye 2 sub-branches)
    if admin_branch == "CSE":
        departments = conn.execute(
            "SELECT DISTINCT department FROM users WHERE role='student' AND department LIKE 'CSE%'"
        ).fetchall()
    else:
        departments = conn.execute(
            "SELECT DISTINCT department FROM users WHERE role='student' AND department = ?",
            (admin_branch,)
        ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        leaves=leaves,
        stats=stats,
        attendance_stats=attendance_stats,
        departments=departments,
        filters={
            "from_date": from_date,
            "to_date": to_date,
            "department": department_filter
        }
    )


# ================= ADMIN UPDATE LEAVE ================= #
@app.route("/admin/leave/<int:leave_id>/update", methods=["POST"])
@login_required
@role_required("admin")
def update_leave(leave_id):
    status = request.form["status"]
    reason = request.form.get("decision_reason", "").strip()

    conn = get_db_connection()
    leave = conn.execute(
        """
        SELECT l.*, u.parent_phone, u.parent_email, u.name, u.department
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE l.id=?
        """,
        (leave_id,)
    ).fetchone()

    # ---------------- BRANCH SECURITY CHECK ---------------- #
    admin_branch = session.get("admin_branch")

    # If admin is not CSE, he can only access his branch
    if admin_branch and admin_branch != "CSE":
        if leave["department"] != admin_branch:
            conn.close()
            flash("You are not allowed to update this leave!", "danger")
            return redirect(url_for("admin_dashboard"))

    # If admin is CSE, he can access Network + Cybersecurity only
    if admin_branch == "CSE":
        if not leave["department"].startswith("CSE"):
            conn.close()
            flash("You are not allowed to update this leave!", "danger")
            return redirect(url_for("admin_dashboard"))


    # =========== SEND WHATSAPP (optional) =========== #
    if leave["parent_phone"]:
        whatsapp_msg = (
            f"Leave Update for {leave['name']}:\n"
            f"Status: {status}\nReason: {reason}"
        )
        send_whatsapp(leave["parent_phone"], whatsapp_msg)


    # =========== SEND EMAIL TO PARENT =========== #
    if leave["parent_email"]:
        email_body = (
            f"Leave Update for {leave['name']}:\n"
            f"Status: {status}\nReason: {reason}"
        )
        send_email(leave["parent_email"], "Leave Status Update", email_body)


    # =========== SEND SMS TO PARENT =========== #
    parent_phone = leave["parent_phone"]
    student_name = leave["name"]

    if parent_phone:
        if status == "Approved":
            sms_text = (
                f"Leave Approved: Your ward {student_name}'s leave has been approved. "
                f"Reason: {reason}"
            )
        else:
            sms_text = (
                f"Leave Rejected: Your ward {student_name}'s leave has been rejected. "
                f"Reason: {reason}"
            )

        send_sms(parent_phone, sms_text)

    # =========== UPDATE DB =========== #
    conn.execute(
        "UPDATE leaves SET status=?, decision_reason=? WHERE id=?",
        (status, reason, leave_id)
    )
    conn.commit()
    conn.close()

    flash("Leave updated successfully!", "success")
    return redirect(url_for("admin_dashboard"))

# ================= ADMIN SUPPORT ================= #
@app.route("/admin/support")
@login_required
@role_required("admin")
def admin_support():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        msgs = conn.execute(
            """
            SELECT m.*, u.name, u.department
            FROM messages m
            JOIN users u ON m.from_user_id = u.id
            WHERE u.department LIKE 'CSE%'
            ORDER BY m.created_at DESC
            """
        ).fetchall()
    else:
        msgs = conn.execute(
            """
            SELECT m.*, u.name, u.department
            FROM messages m
            JOIN users u ON m.from_user_id = u.id
            WHERE u.department = ?
            ORDER BY m.created_at DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()
    return render_template("admin_support.html", messages=msgs)


# ================= ADMIN VIEW STUDENT LEAVES ================= #
@app.route("/admin/student/<int:student_id>/leaves")
@login_required
@role_required("admin")
def student_leave_list(student_id):
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    student = conn.execute(
        "SELECT * FROM users WHERE id=?", (student_id,)
    ).fetchone()

    # Branch check
    if not student:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for("admin_dashboard"))

    if admin_branch == "CSE":
        if not student["department"].startswith("CSE"):
            conn.close()
            flash("You cannot view this student.", "danger")
            return redirect(url_for("admin_dashboard"))
    else:
        if student["department"] != admin_branch:
            conn.close()
            flash("You cannot view this student.", "danger")
            return redirect(url_for("admin_dashboard"))

    leaves = conn.execute(
        """
        SELECT * FROM leaves
        WHERE student_id=?
        ORDER BY applied_on DESC
        """,
        (student_id,)
    ).fetchall()

    conn.close()

    return render_template(
        "leave_list.html",
        student=student,
        leaves=leaves
    )


# ================= ADMIN USERS LIST (BRANCH-WISE) ================= #
@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        users = conn.execute(
            """
            SELECT id, name, email, department, roll_no,
                   parent_phone, parent_email, registration_no, semester
            FROM users
            WHERE role='student' AND department LIKE 'CSE%'
            ORDER BY id DESC
            """
        ).fetchall()
    else:
        users = conn.execute(
            """
            SELECT id, name, email, department, roll_no,
                   parent_phone, parent_email, registration_no, semester
            FROM users
            WHERE role='student' AND department = ?
            ORDER BY id DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()
    return render_template("admin_users.html", users=users)


# ================= DELETE USER ================= #
@app.route("/admin/user/<int:uid>/delete")
@login_required
@role_required("admin")
def delete_user(uid):
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()

    flash("User deleted!", "success")
    return redirect(url_for("admin_users"))


# ================= RESET PASSWORD ================= #
@app.route("/admin/user/<int:uid>/reset-password")
@login_required
@role_required("admin")
def admin_reset_password(uid):
    new_pass = "user" + str(random.randint(1000, 9999))

    conn = get_db_connection()
    user = conn.execute(
        "SELECT email FROM users WHERE id=?",
        (uid,)
    ).fetchone()

    conn.execute(
        "UPDATE users SET password=? WHERE id=?",
        (new_pass, uid)
    )
    conn.commit()
    conn.close()

    if user:
        send_email(
            user["email"],
            "Password Reset",
            f"Your new password is: {new_pass}"
        )

    flash("Password reset & emailed!", "success")
    return redirect(url_for("admin_users"))


# ================= ADMIN EDIT USER ================= #
@app.route("/admin/user/<int:uid>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_user(uid):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if request.method == "POST":
        conn.execute(
            """
            UPDATE users
            SET name=?, department=?, semester=?, roll_no=?,
                parent_phone=?, parent_email=?
            WHERE id=?
            """,
            (
                request.form["name"],
                request.form["department"],
                request.form["semester"],
                request.form["roll_no"],
                request.form["parent_phone"],
                request.form["parent_email"],
                uid
            )
        )
        conn.commit()
        conn.close()

        flash("Student updated!", "success")
        return redirect(url_for("admin_users"))

    conn.close()
    return render_template("user_edit.html", user=user)


# ================= ADMIN ATTENDANCE (BRANCH + SEMESTER STORED) ================= #
@app.route("/admin/attendance", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_attendance():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    # Branch-wise students
    if admin_branch == "CSE":
        students_raw = conn.execute(
            "SELECT id, name, roll_no, registration_no, semester FROM users WHERE role='student' AND department LIKE 'CSE%'"
        ).fetchall()
    else:
        students_raw = conn.execute(
            "SELECT id, name, roll_no, registration_no, semester FROM users WHERE role='student' AND department = ?",
            (admin_branch,)
        ).fetchall()

    students = []
    for s in students_raw:
        total = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=?",
            (s["id"],)
        ).fetchone()[0]

        present = conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='Present'",
            (s["id"],)
        ).fetchone()[0]

        percent = round((present / total) * 100, 1) if total > 0 else 0

        students.append({
            "id": s["id"],
            "name": s["name"],
            "roll_no": s["roll_no"],
            "registration_no": s["registration_no"],
            "semester": s["semester"],
            "percent": percent
        })

    # Save Attendance
    if request.method == "POST":
        date = request.form["date"]

        for s in students:
            status = request.form.get(f"status_{s['id']}")
            if status:
                conn.execute(
                    "INSERT INTO attendance (student_id, date, status, semester) VALUES (?, ?, ?, ?)",
                    (s["id"], date, status, s["semester"])
                )

        conn.commit()
        flash("Attendance saved!", "success")

    conn.close()

    return render_template("admin_attendance.html", students=students)


# ================= ATTENDANCE LIST (BRANCH-WISE) ================= #
@app.route("/admin/attendance/list")
@login_required
@role_required("admin")
def attendance_list():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        data = conn.execute(
            """
            SELECT a.date, a.status, a.semester,
                   u.name, u.roll_no, u.registration_no, u.department
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department LIKE 'CSE%'
            ORDER BY a.date DESC
            """
        ).fetchall()
    else:
        data = conn.execute(
            """
            SELECT a.date, a.status, a.semester,
                   u.name, u.roll_no, u.registration_no, u.department
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department = ?
            ORDER BY a.date DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()
    return render_template("attendance_list.html", data=data)


# ================= EXCEL EXPORT (BRANCH-WISE) ================= #
def _export_to_excel(headers, rows, filename_prefix, sheet_name):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    ws.append(headers)
    for r in rows:
        ws.append(list(r))

    os.makedirs("exports", exist_ok=True)
    filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join("exports", filename)
    wb.save(filepath)
    return filepath


@app.route("/admin/export/attendance")
@login_required
@role_required("admin")
def export_attendance():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        rows = conn.execute(
            """
            SELECT a.id, u.name, u.roll_no, u.registration_no, u.department,
                   a.date, a.status, a.semester
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department LIKE 'CSE%'
            ORDER BY a.date DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT a.id, u.name, u.roll_no, u.registration_no, u.department,
                   a.date, a.status, a.semester
            FROM attendance a
            JOIN users u ON a.student_id = u.id
            WHERE u.department = ?
            ORDER BY a.date DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()

    headers = ["ID", "Name", "Roll No", "Registration No", "Department", "Date", "Status", "Semester"]
    filepath = _export_to_excel(
        headers, rows, "attendance", "Attendance"
    )
    return send_file(filepath, as_attachment=True)


@app.route("/admin/export/leaves")
@login_required
@role_required("admin")
def export_leaves():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        rows = conn.execute(
            """
            SELECT l.id, u.name, u.roll_no, u.department,
                   l.from_date, l.to_date, l.status,
                   l.decision_reason, l.applied_on
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE u.department LIKE 'CSE%'
            ORDER BY l.applied_on DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT l.id, u.name, u.roll_no, u.department,
                   l.from_date, l.to_date, l.status,
                   l.decision_reason, l.applied_on
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE u.department = ?
            ORDER BY l.applied_on DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()

    headers = [
        "ID", "Name", "Roll No", "Department", "From", "To",
        "Status", "Decision Reason", "Applied On"
    ]
    filepath = _export_to_excel(
        headers, rows, "leaves", "Leaves"
    )
    return send_file(filepath, as_attachment=True)


@app.route("/admin/export/users")
@login_required
@role_required("admin")
def export_users():
    conn = get_db_connection()
    admin_branch = session.get("admin_branch")

    if admin_branch == "CSE":
        rows = conn.execute(
            """
            SELECT id, name, email, department, semester, roll_no,
                   registration_no, parent_phone, parent_email
            FROM users
            WHERE role='student' AND department LIKE 'CSE%'
            ORDER BY id DESC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, name, email, department, semester, roll_no,
                   registration_no, parent_phone, parent_email
            FROM users
            WHERE role='student' AND department = ?
            ORDER BY id DESC
            """,
            (admin_branch,)
        ).fetchall()

    conn.close()

    headers = [
        "ID", "Name", "Email", "Department", "Semester", "Roll No",
        "Registration No", "Parent Phone", "Parent Email"
    ]
    filepath = _export_to_excel(
        headers, rows, "students", "Students"
    )
    return send_file(filepath, as_attachment=True)


# ================= RUN APP ================= #
if __name__ == "__main__":
    app.run(debug=True)
