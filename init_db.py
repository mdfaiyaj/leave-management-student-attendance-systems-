import sqlite3

def create_tables():
    conn = sqlite3.connect("leave.db")
    c = conn.cursor()

    # ---------- TABLES ----------
    c.executescript("""
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS subjects;
    DROP TABLE IF EXISTS attendance;
    DROP TABLE IF EXISTS leaves;
    DROP TABLE IF EXISTS support_messages;

    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        department TEXT,
        semester INTEGER,
        roll_no TEXT,
        registration_no TEXT,
        parent_phone TEXT,
        parent_email TEXT,
        admin_branch TEXT,
        photo TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE qr_tokens (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       full_token TEXT,
       display_token TEXT,
       subject_id INTEGER,
       expires_at DATETIME,
       used INTEGER DEFAULT 0
   );

    CREATE TABLE subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester INTEGER NOT NULL
    );

    CREATE TABLE attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        subject_id INTEGER NOT NULL,
        semester INTEGER NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE leaves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        from_date TEXT NOT NULL,
        to_date TEXT NOT NULL,
        medical_file TEXT,
        applied_on TEXT DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Pending',
        decision_reason TEXT
    );

   CREATE TABLE support_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    sender TEXT CHECK(sender IN ('student','admin')) NOT NULL,
    message TEXT NOT NULL,
    seen INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


    """)

    # ---------- SUBJECT DATA ----------
    subjects = [
    
        ("ENGINEERING CHEMISTRY","Civil",1),
        ("ENGINEERING MATHEMATICS-1","Civil",1),
        ("COMMUNICATIVE ENGLISH","Civil",1),
        ("ENGINEERING GRAPHICS AND DESIGN","Civil",1),
        ("ENGINEERING MECHANICS","Civil",1),

        ("ENGINEERING PHYSICS","Civil",2),
        ("ENGINEERING MATHEMATICS-II","Civil",2),
        ("PROGRAMMING FOR PROBLEM SOLVING","Civil",2),
        ("BUILDING MATERIAL & CONSTRUCTION TECHNIQUES","Civil",2),
        ("ENVIRONMENTAL SCIENCE & SANITATION","Civil",2),
        ("ELEMENTS OF CIVIL ENGINEERING","Civil",2),

        ('BASIC ELECTRONICS','Civil',3),
        ('BIOLOGY FOR ENGINEERS','Civil',3),
        ('COMPUTER-AIDED CIVIL ENGINEERING DRAWING','Civil',3),
        ('ENGINEERING MECHANICS','Civil',3),
        ('SURVEYING AND GEOMATICS','Civil',3),
        ('MATHEMATICS-III (PROBABILITY THEORY AND STATISTICS)','Civil',3),
        ('HUMANITIES-1 (EFFECTIVE TECHNICAL COMMUNICATION)','Civil',3),
        ('INTRODUCTION TO CIVIL ENGINEERING','Civil',3),
 
        ('MECHANICAL ENGINEERING','Civil',4),
        ('ENGINEERING GEOLOGY','Civil',4),
        ('DISASTER PREPAREDNESS AND PLANNING','Civil',4),
        ('INTRODUCTION TO FLUID MECHANICS','Civil',4),
        ('INTRODUCTION TO SOLID MECHANICS','Civil',4),
        ('STRUCTURAL ANALYSIS','Civil',4),
        ('MATERIALS TESTING AND EVALUATION','Civil',4),
        ('COMPUTER-AIDED STRUCTURAL ANALYSIS LAB','Civil',4),
        ('MANAGEMENT I (ORGANISATIONAL BEHAVIOUR)','Civil',4),
        ('OPEN ELECTIVE I (HUMANITIES)','Civil',4),
        ('MECHANICS OF MATERIALS','Civil',5),
        ('HYDRAULIC ENGINEERING','Civil',5),
        ('ANALYSIS AND DESIGN OF CONCRETE STRUCTURE','Civil',5),
        ('GEOTECHNICAL ENGINEERING I','Civil',5),
        ('HYDROLOGY AND WATER RESOURCES ENGINEERING','Civil',5),
        ('ENVIRONMENTAL ENGINEERING I','Civil',5),
        ('TRANSPORTATION ENGINEERING','Civil',5),
        ('ENVIRONMENTAL SCIENCE','Civil',5),
        ('SUMMER ENTREPRENEURSHIP II','Civil',5),
        ('CONSTRUCTION ENGINEERING AND MANAGEMENT','Civil',6),
        ('ENGINEERING ECONOMICS ESTIMATION AND COSTING','Civil',6),
        ('DESIGN OF STEEL STRUCTURE','Civil',6),
        ('GEOTECHNICAL ENGINEERING II','Civil',6),
        ('ENVIRONMENTAL ENGINEERING II','Civil',6),
        ('PROGRAM ELECTIVE I','Civil',6),
        ('GRADUATE EMPLOYABILITY SKILLS AND COMPETITIVE COURSES','Civil',7),
        ('PROFESSIONAL PRACTICE LAW AND ETHICS','Civil',7),
        ('PROGRAM ELECTIVE II','Civil',7),
        ('PROGRAM ELECTIVE III','Civil',7),
        ('PROJECT I','Civil',7),
        ('OPEN ELECTIVE','Civil',8),
        ('PROGRAM ELECTIVE IV','Civil',8),
        ('PROGRAM ELECTIVE V','Civil',8),
        ('PROGRAM ELECTIVE VI','Civil',8),
        ('PROJECT II','Civil',8),

        # ========== CSE ==========
        ("ENGINEERING PHYSICS","CSE",1),
        ("ENGINEERING MATHEMATICS-1","CSE",1),
        ("PROGRAMMING FOR PROBLEM SOLVING","CSE",1),
        ("IT WORKSHOP","CSE",1),
        ("BASIC ELECTRONICS ENGINEERING","CSE",1),

        ("ENGINEERING CHEMISTRY","CSE",2),
        ("ENGINEERING MATHEMATICS-II","CSE",2),
        ("COMMUNICATIVE ENGLISH","CSE",2),
        ("PYTHON PROGRAMMING","CSE",2),
        ("INTRODUCTION TO WEB DESIGN","CSE",2),
        ('ANALOG ELECTRONIC CIRCUITS','CSE',3),
        ('DATA STRUCTURES AND ALGORITHMS','CSE',3),
        ('OOP USING C++','CSE',3),
        ('TECHNICAL WRITING','CSE',3),
        ('MATHEMATICS-III','CSE',3),
        ('DISCRETE MATHEMATICS','CSE',4),
        ('COMPUTER ORGANISATION','CSE',4),
        ('OPERATING SYSTEMS','CSE',4),
        ('DESIGN AND ANALYSIS OF ALGORITHMS','CSE',4),
        ('DIGITAL ELECTRONICS','CSE',4),
        ('DATABASE MANAGEMENT SYSTEMS','CSE',5),
        ('COMPILER AND AUTOMATA THEORY','CSE',5),
        ('COMPUTER NETWORK','CSE',5),
        ('CRYPTOGRAPHY AND NETWORK SECURITY','CSE',5),
        ('INTERNET OF THINGS','CSE',5),

        ('MACHINE LEARNING','CSE',6),
        ('WIRELESS NETWORKS','CSE',6),
        ('AI AND ETHICS','CSE',6),
        ('INTERNET AND INTRANET ENGINEERING','CSE',6),
        ('IOT AND ITS APPLICATIONS','CSE',6),
        ('BIOLOGY FOR ENGINEERS','CSE',7),
        ('SOCIAL NETWORKIN MINING','CSE',7),
        ('ROBOTICS AND ROBOT APPLICATION','CSE',7),
        ('PRINCIPLES OF MANAGEMENT','CSE',7),

        # (बाकी ece यहाँ)
        ('ENGINEERING PHYSICS','ECE',1),
        ('ENGINEERING MATHEMATICS-1','ECE',1),
        ('PROGRAMMING FOR PROBLEM SOLVING','ECE',1),
        ('WORKSHOP PRACTICES','ECE',1),
        ('BASIC ELECTRICAL ENGINEERING','ECE',1),
        ('ENGINEERING CHEMISTRY','ECE',2),
        ('ENGINEERING MATHEMATICS-II','ECE',2),
        ('COMMUNICATIVE ENGLISH','ECE',2),
        ('ENGINEERING GRAPHICS AND DESIGN','ECE',2),
        ('BASIC ELECTRONICS','ECE',2),
        ('NETWORK THEORY','ECE',3),
        ('SIGNALS AND SYSTEMS','ECE',3),
        ('MATHEMATICS-III','ECE',3),
        ('OBJECT ORIENTED PROGRAMMING','ECE',3),
        ('BASIC ELECTRONICS','ECE',3),
        ('ELECTRICAL AND ELECTRONICS MATERIAL','ECE',3),
        ('DIGITAL CIRCUITS','ECE',4),
        ('ANALOG CIRCUITS','ECE',4),
        ('SEMICONDUCTOR PHYSICS AND DEVICES','ECE',4),
        ('ANALOG COMMUNICATION','ECE',4),
        ('ELECTROMAGNETIC THEORY','ECE',4),
        ('DIGITAL SIGNAL PROCESSING','ECE',5),
        ('DSP LAB','ECE',5),
        ('MICROPROCESSOR AND MICROCONTROLLERS','ECE',5),
        ('MICROPROCESSOR LAB','ECE',5),
        ('LINEAR CONTROL SYSTEMS','ECE',5),
        ('LINEAR IC AND APPLICATIONS','ECE',5),
        ('COMPUTER NETWORKS AND SECURITY','ECE',5),
        ('ENVIRONMENTAL SCIENCE','ECE',5),
        ('SUMMER ENTREPRENEURSHIP II','ECE',5),
        ('DIGITAL COMMUNICATION','ECE',6),
        ('ELECTRONIC INSTRUMENTS AND MEASUREMENTS','ECE',6),
        ('COMPUTER ORGANISATION AND ARCHITECTURE','ECE',6),
        ('BIOLOGY FOR ENGINEERS','ECE',6),
        ('PROGRAM ELECTIVE I','ECE',6),
        ('DISASTER MANAGEMENT','ECE',6),
        ('BUSINESS ANALYTICS','ECE',7),
        ('COST MANAGEMENT OF ENGINEERING PROJECTS','ECE',7),
        ('GRADUATE EMPLOYABILITY SKILLS','ECE',7),
        ('PROGRAM ELECTIVE II','ECE',7),
        ('PROGRAM ELECTIVE III','ECE',7),
        ('WIRELESS COMMUNICATION','ECE',7),
        ('PROJECT I','ECE',7),
        ('OPEN ELECTIVE I','ECE',8),
        ('OPEN ELECTIVE II','ECE',8),
        ('PROGRAM ELECTIVE IV','ECE',8),
        ('PROGRAM ELECTIVE V','ECE',8),
        #ee subect------
    

       ('ENGINEERING PHYSICS','EE',1),
       ('ENGINEERING MATHEMATICS-1','EE',1),
       ('PROGRAMMING FOR PROBLEM SOLVING','EE',1),
       ('WORKSHOP PRACTICES','EE',1),
       ('BASIC ELECTRICAL ENGINEERING','EE',1),
       
       #-- SEM 2
       ('ENGINEERING CHEMISTRY','EE',2),
       ('ENGINEERING MATHEMATICS-II','EE',2),
       ('COMMUNICATIVE ENGLISH','EE',2),
       ('ENGINEERING GRAPHICS AND DESIGN','EE',2),
       ('BASIC ELECTRONICS','EE',2),
       
      # -- SEM 3
       ('ELECTRICAL CIRCUIT ANALYSIS','EE',3),
       ('ELECTRICAL CIRCUIT LAB','EE',3),
       ('ANALOG ELECTRONICS','EE',3),
       ('ANALOG ELECTRONICS LAB','EE',3),
       ('ELECTRICAL MACHINES I','EE',3),
       ('ELECTROMAGNETIC FIELDS','EE',3),
       
       #-- SEM 4
       ('DIGITAL ELECTRONICS','EE',4),
       ('ELECTRICAL MACHINES II','EE',4),
       ('ELECTRICAL AND ELECTRONIC MEASUREMENT','EE',4),
       ('SIGNALS AND SYSTEMS','EE',4),
       ('MATHEMATICS III','EE',4),
       
       #-- SEM 5
       ('POWER SYSTEM I','EE',5),
       ('CONTROL SYSTEMS','EE',5),
       ('MICROPROCESSORS','EE',5),
       ('POWER ELECTRONICS','EE',5),
       ('PROGRAM ELECTIVE I','EE',5),
       
      # -- SEM 6
       ('POWER SYSTEMS II','EE',6),
       ('DIGITAL SIGNAL PROCESSING','EE',6),
       ('VLSI DESIGN','EE',6),
       ('PROGRAM ELECTIVE II','EE',6),
       ('PROGRAM ELECTIVE III','EE',6),
       
      # -- SEM 7
       ('HUMAN VALUES AND ETHICS','EE',7),
       ('POWER SYSTEM PROTECTION','EE',7),
       ('PROGRAM ELECTIVE IV','EE',7),
       ('PROJECT I','EE',7),
       
      # -- SEM 8
       ('OPEN ELECTIVE III','EE',8),
       ('OPEN ELECTIVE IV','EE',8),
       ('PROGRAM ELECTIVE V','EE',8),
       ('PROGRAM ELECTIVE VI','EE',8),
       # ================= MECHANICAL ENGINEERING =================

# -------- SEMESTER 1 --------
       ("ENGINEERING CHEMISTRY","Mechanical",1),
       ("ENGINEERING MATHEMATICS-1","Mechanical",1),
       ("COMMUNICATIVE ENGLISH","Mechanical",1),
       ("ENGINEERING GRAPHICS AND DESIGN","Mechanical",1),
       ("BASIC ELECTRICAL ENGINEERING","Mechanical",1),       
       
       # -------- SEMESTER 2 --------
       ("ENGINEERING PHYSICS","Mechanical",2),
       ("ENGINEERING MATHEMATICS-II","Mechanical",2),
       ("PROGRAMMING FOR PROBLEM SOLVING","Mechanical",2),
       ("WORKSHOP PRACTICES","Mechanical",2),
       ("ELEMENTS OF MECHANICAL ENGINEERING","Mechanical",2),       
       
       # -------- SEMESTER 3 --------
       ("MACHINE DRAWING","Mechanical",3),
       ("MATHEMATICS-III (PDE, PROBABILITY AND STATISTICS)","Mechanical",3),
       ("BIOLOGY","Mechanical",3),
       ("BASIC ELECTRONICS ENGINEERING","Mechanical",3),
       ("ENGINEERING MECHANICS","Mechanical",3),
       ("THERMODYNAMICS","Mechanical",3),       
       
       # -------- SEMESTER 4 --------
       ("FLUID MECHANICS","Mechanical",4),
       ("APPLIED THERMODYNAMICS","Mechanical",4),
       ("STRENGTH OF MATERIALS","Mechanical",4),
       ("ENGINEERING MATERIALS","Mechanical",4),
       ("INSTRUMENTATION AND CONTROL","Mechanical",4),
       
       # -------- SEMESTER 5 --------
       ("HEAT TRANSFER","Mechanical",5),
       ("FLUID MACHINERY","Mechanical",5),
       ("MANUFACTURING PROCESSES","Mechanical",5),
       ("KINEMATICS OF MACHINES","Mechanical",5),
       ("CONSTITUTION OF INDIA / ESSENCE OF INDIAN KNOWLEDGE TRADITION","Mechanical",5),
       ("SUMMER ENTREPRENEURSHIP II","Mechanical",5),
       ("OPEN ELECTIVE I (MOOCS / SWAYAM / NPTEL)","Mechanical",5),
       ("GRADUATE EMPLOYABILITY SKILLS AND COMPETITIVE COURSES","Mechanical",5),
       
       # -------- SEMESTER 6 --------
       ("DYNAMICS OF MACHINERY","Mechanical",6),
       ("MANUFACTURING TECHNOLOGY","Mechanical",6),
       ("DESIGN OF MACHINE ELEMENTS","Mechanical",6),
       ("AUTOMATION IN MANUFACTURING","Mechanical",6),
       ("OPEN ELECTIVE-II","Mechanical",6),
       ("PROGRAM ELECTIVE-I","Mechanical",6),
       ("PROGRAM ELECTIVE-II","Mechanical",6),
       
       # -------- SEMESTER 7 --------
       ("INDUCTION PROGRAM","Mechanical",7),
       ("INTERNAL COMBUSTION ENGINES","Mechanical",7),
       ("OPEN ELECTIVE-III","Mechanical",7),
       ("PROGRAM ELECTIVE-III","Mechanical",7),
       ("PROGRAM ELECTIVE-IV","Mechanical",7),
       ("PROJECT-I","Mechanical",7),
       
       # -------- SEMESTER 8 --------
       ("OPEN ELECTIVE-IV","Mechanical",8),
       ("OPEN ELECTIVE-V","Mechanical",8),
       ("PROGRAM ELECTIVE-V","Mechanical",8),
       ("PROGRAM ELECTIVE-VI","Mechanical",8),
       ("PROJECT-II","Mechanical",8),
       

    ]

    # ---------- INSERT SUBJECTS ----------
    c.executemany(
        "INSERT INTO subjects (name, department, semester) VALUES (?, ?, ?)",
        subjects
    )

    conn.commit()
    conn.close()
    print("✅ Database + Subjects initialized successfully")

if __name__ == "__main__":
    create_tables()
