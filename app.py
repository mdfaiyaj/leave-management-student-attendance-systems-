# final_app.py - complete cleaned app.py
import os
print("DB PATH USED BY APP:", os.path.abspath("leave.db"))
import requests
from bs4 import BeautifulSoup
import re
import sqlite3
import tempfile
import random
from datetime import datetime
from functools import wraps
from fpdf import FPDF
from flask import send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image
import fitz
from pdf2docx import Converter
import pdfplumber
import pandas as pd
from docx import Document
import pytesseract
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file
)
from flask_mail import Mail, Message


from openpyxl import Workbook
from werkzeug.utils import secure_filename
ADMIN_SECURITY_CODE = "GEC_KAIMUR_2025"

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
def ensure_reg_unique():
    conn = get_db()
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_reg_college ON users(registration_no, college)"
    )
    conn.commit()
    conn.close()

def ensure_status_column():
    conn = get_db()
    cols = conn.execute("PRAGMA table_info(users)").fetchall()
    names = [c[1] for c in cols]

    if "status" not in names:
        conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
        conn.commit()

    conn.close()
def ensure_semester_logs():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS semester_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            from_sem TEXT,
            to_sem TEXT,
            affected_ids TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
def ensure_beu_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS beu_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_no TEXT,
            semester TEXT,
            subject TEXT,
            marks INTEGER
        )
    """)
    conn.commit()
    conn.close()
# ================= BEU FETCH MODULE =================
# ================= BEU RESULT FETCH MODULE =================
import requests
from bs4 import BeautifulSoup

SEM_TEXT = {
    "1": "1st",
    "2": "2nd",
    "3": "3rd",
    "4": "4th",
    "5": "5th",
    "6": "6th",
    "7": "7th",
    "8": "8th"
}

ROMAN = {
    "1": "I", "2": "II", "3": "III", "4": "IV",
    "5": "V", "6": "VI", "7": "VII", "8": "VIII"
}

def fetch_and_store_beu(reg, sem):

    sem = str(sem)

    url = (
        "https://beu-bih.ac.in/result-one/"
        f"B.Tech.%20{sem}th%20Semester%20Examination,%202025"
        f"?exam_held=July%2F2025"
        f"&semester={sem}"
    )

    try:
        session_req = requests.Session()

        # STEP 1 → open result page
        page = session_req.get(url, timeout=20)

        soup = BeautifulSoup(page.text, "html.parser")

        # STEP 2 → prepare form data
        data = {
            "regNo": reg
        }

        # STEP 3 → submit registration number
        result = session_req.post(url, data=data, timeout=20)

        html = result.text

        # DEBUG
        print(html)

        if "Student Name" not in html:
            print("No result found")
            return False

        soup = BeautifulSoup(html, "html.parser")

        rows = soup.find_all("tr")

        conn = get_db()

        # old result delete
        conn.execute("""
            DELETE FROM beu_results
            WHERE registration_no=? AND semester=?
        """, (reg, sem))

        for tr in rows:

            cols = tr.find_all("td")

            if len(cols) >= 3:

                subject = cols[0].get_text(strip=True)
                marks_text = cols[-1].get_text(strip=True)

                m = re.search(r"\d+", marks_text)

                if m:

                    marks = int(m.group())

                    conn.execute("""
                        INSERT INTO beu_results
                        (registration_no, semester, subject, marks)
                        VALUES (?, ?, ?, ?)
                    """, (
                        reg,
                        sem,
                        subject,
                        marks
                    ))

        conn.commit()
        conn.close()

        print("BEU Result fetched")
        return True

    except Exception as e:
        print("BEU ERROR:", e)
        return False



def parse_beu_marks(html):

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.find_all("tr")

    subjects = []

    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            sub = cols[1].get_text(strip=True)
            mark_text = cols[-1].get_text(strip=True)

            m = re.search(r"\d+", mark_text)
            if m:
                subjects.append((sub, int(m.group())))

    if not subjects:
        return None

    highest = max(subjects, key=lambda x: x[1])

    return {
        "subjects": subjects,
        "highest_subject": highest[0],
        "highest_marks": highest[1]
    }

def fix_users_unique_email():
    conn = get_db()

    # create new table with correct constraint
    conn.execute("""
       CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    password TEXT,
    role TEXT,
    department TEXT,
    semester TEXT,
    roll_no TEXT,
    registration_no TEXT,
    parent_phone TEXT,
    parent_email TEXT,
    admin_branch TEXT,
    college TEXT,
    photo TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT email_college_unique UNIQUE(email, college)
)

    """)

    # copy data
    conn.execute("""
        INSERT OR IGNORE INTO users_new
        SELECT * FROM users
    """)

    # replace old table
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_new RENAME TO users")

    conn.commit()
    conn.close()

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
    # ---------- COLLEGES ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS colleges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS qr_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE,
    subject_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    used INTEGER DEFAULT 0
    )
  """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS semester_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        from_sem TEXT,
        to_sem TEXT,
        affected_ids TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    # ---------- USERS ----------
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            role TEXT,
            department TEXT,
            semester TEXT,
            roll_no TEXT,
            registration_no TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            admin_branch TEXT,
            college TEXT,
            photo TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(email, college)
        )
    """)
    

    conn.commit()
    conn.close()
def insert_default_colleges():
    colleges = [
"SITAMARHI INSTITUTE OF TECHNOLOGY",
"B. P. MANDAL COLLEGE OF ENGINEERING, MADHEPURA",
"GOVERNMENT ENGINEERING COLLEGE VAISHALI",
"GOVERNMENT ENGINEERING COLLEGE BANKA",
"GOVERNMENT ENGINEERING COLLEGE BHOJPUR",
"GOVERNMENT ENGINEERING COLLEGE NAWADA",
"NALANDA COLLEGE OF ENGINEERING, CHANDI",
"LOKNAYAK JAI PRAKASH INSTITUTE OF TECHNOLOGY, CHAPRA",
"GOVERNMENT ENGINEERING COLLEGE SAMASTIPUR",
"PURNEA COLLEGE OF ENGINEERING",
"GOVERNMENT ENGINEERING COLLEGE SHEOHAR",
"SERSHAH ENGINEERING COLLEGE, SASARAM",
"BAKHTIYARPUR COLLEGE OF ENGINEERING",
"SAHARSA COLLEGE OF ENGINEERING",
"RASHRAKAVI RAMDHARI SINGH DINKAR COLLEGE OF ENGINEERING, BEGUSARAI",
"GOVERNMENT ENGINEERING COLLEGE KISHANGANJ",
"SUPAUL COLLEGE OF ENGINEERING",
"KATIHAR ENGINEERING COLLEGE",
"GOVERNMENT ENGINEERING COLLEGE JAMUI",
"GOVERNMENT ENGINEERING COLLEGE BUXAR",
"BHAGALPUR COLLEGE OF ENGINEERING",
"DARBHANGA COLLEGE OF ENGINEERING",
"GOVERNMENT ENGINEERING COLLEGE JEHANABAD",
"MUZAFFARPUR INSTITUTE OF TECHNOLOGY",
"GOVERNMENT ENGINEERING COLLEGE SHEIKHPURA",
"GOVERNMENT ENGINEERING COLLEGE WEST CHAMPARAN",
"GOVERNMENT ENGINEERING COLLEGE SIWAN",
"GOVERNMENT ENGINEERING COLLEGE MADHUBANI",
"GOVERNMENT ENGINEERING COLLEGE LAKHISARAI",
"GOVERNMENT ENGINEERING COLLEGE KHAGARIA",
"GOVERNMENT ENGINEERING COLLEGE AURANGABAD",
"SHRI PHANISHWAR NATH RENU ENGINEERING COLLEGE, ARARIA",
"GOVERNMENT ENGINEERING COLLEGE GOPALGANJ",
"GOVERNMENT ENGINEERING COLLEGE MUNGER",
"GAYA COLLEGE OF ENGINEERING",
"GOVERNMENT ENGINEERING COLLEGE ARWAL",
"MOTIHARI COLLEGE OF ENGINEERING",
"DR. APJ ABDUL KALAM WOMENS INSTITUTE OF TECHNOLOGY",
"ADWAITA MISSION INSTITUTE OF TECHNOLOGY",
"MAULANA AZAD COLLEGE OF ENGINEERING AND TECHNOLOGY",
"SIWAN ENGINEERING & TECHNICAL INSTITUTE",
"K.K. COLLEGE OF ENGINEERING & MANAGEMENT",
"BIRLA INSTITUTE OF TECHNOLOGY, PATNA",
"VIDYA VIHAR INSTITUTE OF TECHNOLOGY",
"NETAJI SUBHAS INSTITUTE OF TECHNOLOGY",
"BUDDHA INSTITUTE OF TECHNOLOGY",
"MILLIA KISHANGANJ COLLEGE OF ENGINEERING & TECHNOLOGY",
"MILLIA INSTITUTE OF TECHNOLOGY",
"MOTHER'S INSTITUTE OF TECHNOLOGY",
"PATNA SAHIB TECHNICAL CAMPUS",
"AZMET INSTITUTE OF TECHNOLOGY",
"R.P. SHARMA INSTITUTE OF TECHNOLOGY",
"SITYOG INSTITUTE OF TECHNOLOGY",
"EXALT COLLEGE OF ENGINEERING & TECHNOLOGY",
"MOTI BABU INSTITUTE OF TECHNOLOGY"
    ]

    conn = get_db()
    for col in colleges:
        conn.execute(
            "INSERT OR IGNORE INTO colleges (name) VALUES (?)",
            (col,)
        )
    conn.commit()
    conn.close()

# Run table creation ONLY if DB does NOT exist
if not os.path.exists(DB_NAME):
    create_tables()

# 🔥 ENSURE NEW COLUMNS ALWAYS EXIST
# 🔥 ENSURE NEW TABLES & COLUMNS
ensure_status_column()
ensure_semester_logs()
ensure_beu_table()
insert_default_colleges()
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
import secrets
import string
from datetime import datetime, timedelta

def generate_tokens():
    full_token = secrets.token_urlsafe(16)

    display_token = (
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.digits) +
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.digits)
    )

    return full_token, display_token
@app.route("/select-college", methods=["GET","POST"])
def select_college():
    conn = get_db()

    if request.method == "POST":
        college = request.form.get("college")
        if not college:
            flash("Please select college","danger")
            return redirect(url_for("select_college"))

        session["college"] = college
        conn.close()
        return redirect(url_for("login"))

    colleges = conn.execute(
        "SELECT DISTINCT name FROM colleges ORDER BY name"
    ).fetchall()

    conn.close()
    return render_template("select_college.html", colleges=colleges)



# ---------------- AUTH & INDEX ----------------
@app.route("/")
def index():

    # 🔒 college must be selected first
    if "college" not in session:
        return redirect(url_for("select_college"))

    role = session.get("user_role")

    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    elif role == "student":
        return redirect(url_for("student_dashboard"))
    elif role == "developer":
        return redirect(url_for("developer_panel"))

    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():

    # 🔒 College must be selected
    if "college" not in session:
        return redirect(url_for("select_college"))

    mode = request.args.get("mode", "normal")

    # ================= DEVELOPER LOGIN =================
    if mode == "developer":

        if request.method == "POST":

            email = request.form.get("email", "").lower()
            password = request.form.get("password", "")

            if email == DEVELOPER_EMAIL and password == DEVELOPER_PASS:

                session["developer"] = True
                session["user_role"] = "developer"
                session["user_id"] = 0
                session["user_name"] = "Developer"

                # ✅ POPUP FLAG
                session["login_success"] = True

                return redirect(url_for("developer_panel"))

            flash("Invalid Developer Credentials!", "danger")
            return redirect(url_for("login", mode="developer"))

        return render_template("login.html", developer_mode=True)

    # ================= NORMAL LOGIN =================
    if request.method == "POST":

        email = request.form.get("email", "").lower()
        password = request.form.get("password", "")
        college = session.get("college")

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email=? AND password=? AND college=?
            """,
            (email, password, college)
        ).fetchone()

        conn.close()

        # ❌ INVALID LOGIN
        if not user:

            flash("Invalid Email or Password!", "danger")

            return render_template(
                "login.html",
                login_failed=True
            )

        # ✅ SESSION SET
        session["user_id"] = user["id"]
        session["user_role"] = user["role"]
        session["user_name"] = user["name"]
        session["user_photo"] = user["photo"]
        session["college"] = user["college"]

        # ✅ SUCCESS POPUP
        session["login_success"] = True

        # ✅ ADMIN BRANCH
        if user["role"] and user["role"].lower() == "admin":
            session["admin_branch"] = user["admin_branch"]

        # ================= ROLE REDIRECT =================
        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))

        elif user["role"] == "student":
            return redirect(url_for("student_dashboard"))

        elif user["role"] == "developer":
            return redirect(url_for("developer_panel"))

        return redirect(url_for("index"))

    return render_template("login.html")
    
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out!", "info")
    return redirect(url_for("select_college"))   # 🔥 back to college select



# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email","").lower()
        college = session.get("college")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND college=?",
            (email, college)
        ).fetchone()

        if not user:
            conn.close()
            flash("Email not found in this college!", "danger")
            return redirect(url_for("forgot_password"))

        new_pass = "pass" + str(random.randint(1000,9999))
        conn.execute(
            "UPDATE users SET password=? WHERE id=?",
            (new_pass, user["id"])
        )
        conn.commit()
        conn.close()

        try:
            send_email(email, "Password Reset", f"Your new password is: {new_pass}")
        except:
            pass

        flash("New password sent!", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")

# ================= PROCESS TOOL =================

# ================= PDF & IMAGE TOOLS =================

# =========================================================
# PDF & IMAGE TOOLS IMPORTS
# =========================================================

from PIL import Image
import fitz
import os
from pdf2docx import Converter
import pdfplumber
import pandas as pd
import pytesseract
from docx import Document

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# TOOLS PAGE
# =========================================================

@app.route("/tools")
@login_required()
def tools():

    return render_template("tools.html")


# =========================================================
# PROCESS TOOL
# =========================================================

@app.route("/upload-tool", methods=["POST"])
@login_required()
def upload_tool():

    file = request.files.get("file")
    action = request.form.get("action")

    if not file:

        flash("No file selected", "danger")

        return redirect("/tools")

    filepath = os.path.join(
        UPLOAD_FOLDER,
        file.filename
    )

    file.save(filepath)

    # =================================================
    # IMAGE RESIZE
    # =================================================

    if action == "resize_image":

        width = int(
            request.form.get("width", 800)
        )

        height = int(
            request.form.get("height", 800)
        )

        output = "static/output.jpg"

        img = Image.open(filepath)

        img = img.resize((width, height))

        img.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # PDF RESIZE
    # =================================================

    elif action == "resize_pdf":

        output = "static/output.pdf"

        pdf = fitz.open(filepath)

        for page in pdf:

            page.set_mediabox(
                fitz.Rect(0, 0, 595, 842)
            )

        pdf.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # PDF TO WORD
    # =================================================

    elif action == "pdf_word":

        output = "static/output.docx"

        cv = Converter(filepath)

        cv.convert(output)

        cv.close()

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # PDF TO EXCEL
    # =================================================

    elif action == "pdf_excel":

        output = "static/output.xlsx"

        data = []

        with pdfplumber.open(filepath) as pdf:

            for page in pdf.pages:

                table = page.extract_table()

                if table:

                    for row in table:

                        data.append(row)

        df = pd.DataFrame(data)

        df.to_excel(
            output,
            index=False
        )

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # IMAGE TO TEXT OCR
    # =================================================

    elif action == "ocr":

        img = Image.open(filepath)

        text = pytesseract.image_to_string(img)

        return render_template(
            "ocr_result.html",
            text=text
        )

    # =================================================
    # PDF TEXT EDIT
    # =================================================

    elif action == "edit_pdf_text":

        old_text = request.form.get("old_text")
        new_text = request.form.get("new_text")

        output = "static/edited.pdf"

        pdf = fitz.open(filepath)

        for page in pdf:

            areas = page.search_for(old_text)

            for area in areas:

                page.draw_rect(
                    area,
                    color=(1,1,1),
                    fill=(1,1,1)
                )

                page.insert_text(
                    (area.x0, area.y1 - 2),
                    new_text,
                    fontsize=11,
                    color=(0,0,0)
                )

        pdf.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # IMAGE TO EXCEL
    # =================================================

    elif action == "image_excel":

        output = "static/output.xlsx"

        img = Image.open(filepath)

        text = pytesseract.image_to_string(img)

        lines = text.split("\n")

        df = pd.DataFrame(
            lines,
            columns=["Text"]
        )

        df.to_excel(
            output,
            index=False
        )

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # IMAGE TO WORD
    # =================================================

    elif action == "image_word":

        output = "static/output.docx"

        img = Image.open(filepath)

        text = pytesseract.image_to_string(img)

        doc = Document()

        doc.add_paragraph(text)

        doc.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # IMAGE TO PDF
    # =================================================

    elif action == "image_pdf":

        output = "static/output.pdf"

        img = Image.open(filepath)

        if img.mode != "RGB":

            img = img.convert("RGB")

        img.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # PDF TO IMAGE
    # =================================================

    elif action == "pdf_image":

        pdf = fitz.open(filepath)

        page = pdf[0]

        pix = page.get_pixmap()

        output = "static/page1.png"

        pix.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # COMPRESS IMAGE
    # =================================================

    elif action == "compress_image":

        output = "static/compressed.jpg"

        img = Image.open(filepath)

        img.save(
            output,
            optimize=True,
            quality=40
        )

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # ROTATE PDF
    # =================================================

    elif action == "rotate_pdf":

        output = "static/rotated.pdf"

        pdf = fitz.open(filepath)

        for page in pdf:

            page.set_rotation(90)

        pdf.save(output)

        return send_file(
            output,
            as_attachment=True
        )

    # =================================================
    # INVALID ACTION
    # =================================================

    flash("Invalid action", "danger")

    return redirect("/tools")

# ---------------- REGISTRATION ----------------
@app.route("/register/student", methods=["GET", "POST"])
def register_student():
    if request.method == "POST":
        college = session.get("college")

        conn = get_db()
        try:
            conn.execute("""
                INSERT INTO users (
                    name, email, password, role,
                    department, semester, roll_no,
                    registration_no, parent_phone, parent_email,
                    college
                )
                VALUES (?, ?, ?, 'student', ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.form.get("name"),
                request.form.get("email","").lower(),
                request.form.get("password"),
                request.form.get("department"),
                request.form.get("semester"),
                request.form.get("roll_no"),
                request.form.get("registration_no"),
                request.form.get("parent_phone"),
                request.form.get("parent_email"),
                college
            ))
            conn.commit()
            flash("Student Registered!", "success")
        except:
            flash("Email already exists in this college!", "danger")
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
        security_code = request.form.get("security_code", "")
        college = session.get("college")   # ✅ selected college

        # 🔐 SECURITY CODE CHECK
        if security_code != ADMIN_SECURITY_CODE:
            flash("❌ Invalid Admin Security Code", "danger")
            return redirect(url_for("register_admin"))

        conn = get_db()

        # ✅ check same email in same college
        existing = conn.execute(
            "SELECT id FROM users WHERE email=? AND college=?",
            (email, college)
        ).fetchone()

        if existing:
            conn.close()
            flash("Admin already registered in this college!", "danger")
            return redirect(url_for("register_admin"))

        # ✅ correct insert
        conn.execute("""
            INSERT INTO users
            (name, email, password, role, admin_branch, college)
            VALUES (?, ?, ?, 'admin', ?, ?)
        """, (name, email, password, branch, college))

        conn.commit()
        conn.close()

        flash("✅ Admin Registered Successfully!", "success")
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


import qrcode
import uuid
import os
from io import BytesIO
from flask import jsonify
from datetime import datetime, timedelta

@app.route("/generate-qr", methods=["POST"])
@login_required(role="admin")
def generate_qr():

    data = request.get_json()

    subject_id = data.get("subject_id")

    if not subject_id:
        return jsonify({
            "error": "Subject missing"
        }), 400

    token = str(uuid.uuid4())[:8]

    expires_at = (
        datetime.now() + timedelta(minutes=2)
    ).strftime("%H:%M:%S")

    os.makedirs("static/qr", exist_ok=True)

    filename = f"{token}.png"

    filepath = os.path.join(
        "static/qr",
        filename
    )

    qr_data = f"{subject_id}:{token}"

    img = qrcode.make(qr_data)

    img.save(filepath)

    return jsonify({

        "success": True,

        "qr": f"/static/qr/{filename}",

        "token": token,

        "expires": expires_at

    })
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

# ================= STUDENT RESULT =================
from flask import request, render_template
import requests
from bs4 import BeautifulSoup

# ================= STUDENT RESULT =================
@app.route('/student/result', methods=['GET', 'POST'])
@login_required(role="student")
def student_result():

    result_data = None
    error = None

    if request.method == 'POST':

        reg_no = request.form.get('registration_no')
        semester = request.form.get('semester')

        try:

            session_req = requests.Session()

            # STEP 1 → OPEN PAGE
            url = "https://results.beup.ac.in/"

            page = session_req.get(url, timeout=20)

            soup = BeautifulSoup(page.text, "html.parser")

            # STEP 2 → GET ASP.NET TOKENS
            viewstate = soup.find("input", {"id": "__VIEWSTATE"})
            eventvalidation = soup.find("input", {"id": "__EVENTVALIDATION"})
            viewstategenerator = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})

            payload = {
                "__VIEWSTATE": viewstate["value"] if viewstate else "",
                "__EVENTVALIDATION": eventvalidation["value"] if eventvalidation else "",
                "__VIEWSTATEGENERATOR": viewstategenerator["value"] if viewstategenerator else "",

                # REGISTRATION NUMBER
                "txtRegNo": reg_no,

                # BUTTON
                "btnSearch": "Search"
            }

            # STEP 3 → SUBMIT
            response = session_req.post(
                url,
                data=payload,
                timeout=30
            )

            html = response.text

            # STEP 4 → PARSE RESULT
            soup = BeautifulSoup(html, "html.parser")

            tables = soup.find_all("table")

            if not tables:
                error = "Result not found!"
            else:
                result_data = html

        except Exception as e:
            error = str(e)

    return render_template(
        "student_result.html",
        result_data=result_data,
        error=error
    )
@app.route('/fetch-result', methods=['POST'])
@login_required(role="student")
def fetch_result():

    reg_no = request.form.get("registration_no")
    semester = request.form.get("semester")

    try:

        url = "https://results.beup.ac.in/"

        response = requests.get(url, timeout=20)

        return response.text

    except Exception as e:

        return f"""
        <div style='padding:30px;color:red;font-size:25px'>
            Error: {str(e)}
        </div>
        """

# ================= ADMIN RESULT DASHBOARD =================
@app.route("/admin/result")
@login_required(role="admin")
def admin_result():

    conn = get_db()

    subject_high = conn.execute("""
        SELECT subject, MAX(marks) as high_marks
        FROM beu_results
        GROUP BY subject
        ORDER BY subject
    """).fetchall()

    toppers = conn.execute("""
        SELECT registration_no, SUM(marks) as total
        FROM beu_results
        GROUP BY registration_no
        ORDER BY total DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return render_template(
        "admin_result.html",
        subject_high=subject_high,
        toppers=toppers
    )



# ================= ADMIN BATCH FETCH =================
@app.route("/admin/result/fetch", methods=["POST"])
@login_required(role="admin")
def admin_result_fetch():

    sem = request.form.get("semester")
    branch = session.get("admin_branch")

    conn = get_db()

    # 🔥 flexible match
    students = conn.execute("""
        SELECT registration_no
        FROM users
        WHERE role='student'
        AND semester=?
        AND department LIKE ?
    """, (sem, f"%{branch}%")).fetchall()

    print("DEBUG students found:", len(students))

    count = 0

    for s in students:
        reg = s["registration_no"]
        ok = fetch_and_store_beu(reg, sem)
        if ok:
            count += 1
        else:
            print("FAILED:", reg)

    conn.close()

    flash(f"{count} students result fetched", "success")
    return redirect(url_for("admin_result"))


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

    # 🔐 Admin branch (login time pe set hota hai)
    raw_branch = session.get("admin_branch", "") or ""

    # 🔁 NORMALIZE branch for subjects table
    SUBJECT_DEPT_MAP = {
        "CSE": "CSE",
        "CSE (Network)": "CSE",
        "CSE (Cyber Security)": "CSE",

        "Civil": "Civil",
        "Civil Engineering": "Civil",

        "Mechanical": "Mechanical",
        "Mechanical Engineering": "Mechanical",
        "ME": "Mechanical",

        "Electrical": "EE",
        "EE": "EE",

        "Electronics": "ECE",
        "ECE": "ECE"
    }

    subject_dept = SUBJECT_DEPT_MAP.get(raw_branch, raw_branch)

    # 🔔 Unread Support Messages Count (branch-wise)
    unread_count = conn.execute("""
        SELECT COUNT(*)
        FROM support_messages sm
        JOIN users u ON sm.student_id = u.id
        WHERE sm.seen = 0
          AND u.department LIKE ?
    """, (f"%{raw_branch}%",)).fetchone()[0]

    # 📄 Leave Applications (branch-wise)
    leaves = conn.execute("""
        SELECT
            l.*,
            u.name,
            u.roll_no,
            u.registration_no,
            u.semester,
            u.department
        FROM leaves l
        JOIN users u ON l.student_id = u.id
        WHERE u.department LIKE ?
        ORDER BY l.applied_on DESC
    """, (f"%{raw_branch}%",)).fetchall()

    # 📊 Leave Statistics
    stats = {
        "total": conn.execute("""
            SELECT COUNT(*)
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE u.department LIKE ?
        """, (f"%{raw_branch}%",)).fetchone()[0],

        "approved": conn.execute("""
            SELECT COUNT(*)
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE l.status='Approved'
              AND u.department LIKE ?
        """, (f"%{raw_branch}%",)).fetchone()[0],

        "pending": conn.execute("""
            SELECT COUNT(*)
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE l.status='Pending'
              AND u.department LIKE ?
        """, (f"%{raw_branch}%",)).fetchone()[0],

        "rejected": conn.execute("""
            SELECT COUNT(*)
            FROM leaves l
            JOIN users u ON l.student_id = u.id
            WHERE l.status='Rejected'
              AND u.department LIKE ?
        """, (f"%{raw_branch}%",)).fetchone()[0],
    }

    # 📚 ✅ SUBJECT LIST (FOR QR CODE)  🔥🔥
    subjects = conn.execute("""
        SELECT id, name
        FROM subjects
        WHERE department = ?
        ORDER BY name
    """, (subject_dept,)).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        leaves=leaves,
        stats=stats,
        unread_count=unread_count,
        subjects=subjects   # ✅ VERY IMPORTANT FOR QR
    )

import qrcode
import base64
import random
import string
from io import BytesIO
from datetime import datetime, timedelta
from flask import jsonify

@app.route("/admin/generate-qr/<int:subject_id>")
@login_required(role="admin")
def admin_generate_qr(subject_id):

    now = datetime.now()
    expires_at = now + timedelta(minutes=2)

    # 🔐 FULL TOKEN (QR ke andar)
    full_token = secrets.token_urlsafe(16)

    # 👁️ DISPLAY TOKEN (5 char)
    display_token = (
        secrets.choice(string.digits) +
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.digits) +
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.digits)
    )

    conn = get_db()
    conn.execute("""
        INSERT INTO qr_tokens (full_token, display_token, subject_id, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
    """, (full_token, display_token, subject_id, expires_at))
    conn.commit()
    conn.close()

    # 📷 QR IMAGE
    qr = qrcode.make(full_token)
    buf = BytesIO()
    qr.save(buf)
    img_base64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({
        "qr": img_base64,
        "display_token": display_token,
        "expires": expires_at.strftime("%H:%M:%S")
    })




@app.route("/admin/update-leave/<int:lid>/update", methods=["POST"])
@login_required(role="admin")
def admin_update_leave(lid):

    status = request.form.get("status")

    conn = get_db()

    conn.execute(
        "UPDATE leaves SET status=? WHERE id=?",
        (status, lid)
    )

    conn.commit()
    conn.close()

    flash("Leave Updated Successfully!", "success")

    return redirect(url_for("admin_dashboard"))

@app.route("/student/submit-token", methods=["POST"])
@login_required(role="student")
def student_submit_token():

    token_input = request.form.get("token")
    student_id = session["user_id"]

    conn = get_db()

    qr = conn.execute("""
        SELECT * FROM qr_tokens
        WHERE display_token = ?
          AND expires_at > CURRENT_TIMESTAMP
          AND used = 0
    """, (token_input,)).fetchone()

    if not qr:
        conn.close()
        flash("❌ Invalid or Expired Token", "danger")
        return redirect(url_for("student_dashboard"))

    # ✅ Mark attendance
    conn.execute("""
        INSERT INTO attendance (student_id, subject_id, date, status)
        VALUES (?, ?, DATE('now'), 'Present')
    """, (student_id, qr["subject_id"]))

    # 🔒 Token mark as used
    conn.execute("""
        UPDATE qr_tokens SET used = 1 WHERE id = ?
    """, (qr["id"],))

    conn.commit()
    conn.close()

    flash("✅ Attendance marked successfully", "success")
    return redirect(url_for("student_dashboard"))

@app.route("/admin/semester-control", methods=["GET", "POST"])
@login_required(role="admin")
def semester_control():

    conn = get_db()
    branch = session.get("admin_branch")

    # ================= APPLY =================
    if request.method == "POST":

        sem = request.form.get("semester")
        action = request.form.get("action")
        target = request.form.get("target")
        selected_ids = request.form.getlist("student_ids")

        # ---- target students ----
        if target == "all":
            students = conn.execute("""
                SELECT id, semester
                FROM users
                WHERE role='student'
                AND semester=?
                AND department LIKE ?
                AND COALESCE(status,'active')='active'
            """, (sem, f"%{branch}%")).fetchall()

        else:  # selected
            if not selected_ids:
                flash("No students selected", "danger")
                return redirect(url_for("semester_control", semester=sem))

            q = ",".join(["?"] * len(selected_ids))
            students = conn.execute(f"""
                SELECT id, semester
                FROM users
                WHERE id IN ({q})
            """, selected_ids).fetchall()

        if not students:
            flash("No students found", "danger")
            return redirect(url_for("semester_control", semester=sem))

        affected_ids = []

        # ---- apply action ----
        for s in students:
            sid = s["id"]
            cur = int(s["semester"])

            if action == "promote":
                new_sem = cur + 1
                conn.execute("UPDATE users SET semester=? WHERE id=?", (new_sem, sid))

            elif action == "reset":
                new_sem = max(1, cur - 1)
                conn.execute("UPDATE users SET semester=? WHERE id=?", (new_sem, sid))

            elif action == "yearback":
                pass  # semester same

            elif action == "passout":
                conn.execute("UPDATE users SET status='passout' WHERE id=?", (sid,))

            affected_ids.append(str(sid))

        # ---- log ----
        conn.execute("""
            INSERT INTO semester_logs
            (admin_id, action, from_sem, to_sem, affected_ids)
            VALUES (?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            action,
            sem,
            "",
            ",".join(affected_ids)
        ))

        conn.commit()
        flash(f"{len(affected_ids)} students updated", "success")
        return redirect(url_for("semester_control", semester=sem))

    # ================= PREVIEW =================
    sem = request.args.get("semester")
    students = []
    counts = None

    if sem:
        students = conn.execute("""
            SELECT id, name, roll_no, registration_no, semester,
                   COALESCE(status,'active') as status
            FROM users
            WHERE role='student'
            AND semester=?
            AND department LIKE ?
            ORDER BY roll_no
        """, (sem, f"%{branch}%")).fetchall()

        counts = {
            "total": len(students),
            "active": conn.execute("""
                SELECT COUNT(*) FROM users
                WHERE semester=? AND department LIKE ?
                AND COALESCE(status,'active')='active'
            """, (sem, f"%{branch}%")).fetchone()[0],

            "passout": conn.execute("""
                SELECT COUNT(*) FROM users
                WHERE status='passout'
                AND department LIKE ?
            """, (f"%{branch}%",)).fetchone()[0],

            "promoted": conn.execute("""
                SELECT COUNT(*) FROM semester_logs
                WHERE action='promote' AND from_sem=?
            """, (sem,)).fetchone()[0],

            "yearback": conn.execute("""
                SELECT COUNT(*) FROM semester_logs
                WHERE action='yearback' AND from_sem=?
            """, (sem,)).fetchone()[0],
        }

    conn.close()

    return render_template(
        "semester_control.html",
        students=students,
        semester=sem,
        counts=counts
    )

@app.route("/admin/semester/report")
@login_required(role="admin")
def semester_report_pdf():

    sem = request.args.get("semester")
    rtype = request.args.get("type", "all")
    branch = session.get("admin_branch")

    conn = get_db()

    query = """
        SELECT name, roll_no, registration_no,
               COALESCE(status,'active') as status
        FROM users
        WHERE role='student'
        AND department LIKE ?
    """
    params = [f"%{branch}%"]

    if rtype == "active":
        query += " AND semester=? AND COALESCE(status,'active')='active'"
        params.append(sem)

    elif rtype == "passout":
        query += " AND status='passout'"

    elif rtype == "all":
        query += " AND semester=?"
        params.append(sem)

    students = conn.execute(query, params).fetchall()
    conn.close()

    # ---- PDF ----
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import tempfile

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    c = canvas.Canvas(tmp.name, pagesize=A4)

    y = 800
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, f"Semester {sem} {rtype.upper()} Students")
    y -= 30

    c.setFont("Helvetica", 10)

    for s in students:
        c.drawString(50, y, s["name"])
        c.drawString(200, y, s["roll_no"])
        c.drawString(280, y, s["registration_no"] or "")
        c.drawString(420, y, s["status"])
        y -= 15
        if y < 50:
            c.showPage()
            y = 800

    c.save()

    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f"{rtype}_semester_{sem}.pdf"
    )


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
import pdfplumber
import re

@app.route("/admin/attendance-upload", methods=["GET","POST"])
@login_required(role="admin")
def admin_attendance_upload():

    if request.method == "POST":

        semester = request.form.get("semester")
        branch = request.form.get("branch")
        file = request.files.get("file")

        if not file:
            flash("No file uploaded", "danger")
            return redirect(url_for("admin_attendance_upload"))

        text = ""

        if file.filename.endswith(".pdf"):
            with pdfplumber.open(file) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += "\n" + t

        elif file.filename.endswith(".xlsx"):
            import pandas as pd
            df = pd.read_excel(file)
            text = df.to_string()

        else:
            flash("Only PDF or Excel allowed", "danger")
            return redirect(url_for("admin_attendance_upload"))

        # ---------- EXTRACT REG + NAME ----------
        pattern = r"(\\d{10,})\\s+([A-Za-z .]+)"
        matches = re.findall(pattern, text)

        conn = get_db()

        count = 0

        for reg, name in matches:

            exists = conn.execute("""
                SELECT id FROM users
                WHERE registration_no=?
            """, (reg,)).fetchone()

            if not exists:
                conn.execute("""
                    INSERT INTO users
                    (name, registration_no, role, department, semester)
                    VALUES (?, ?, 'student', ?, ?)
                """, (name.strip(), reg, branch, semester))
                count += 1

        conn.commit()
        conn.close()

        flash(f"{count} students imported successfully", "success")
        return redirect(url_for("admin_users"))

    return render_template("admin_attendance_upload.html")


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
           ORDER BY CAST(registration_no AS INTEGER) ASC
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
@app.route("/admin/attendance-records")
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