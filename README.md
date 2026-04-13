# RESCUE
## Rapid Emergency Services Coordination & Unified Engine

A mini project built for the Web Programming and Database Management System lab courses.
The system lets hospitals see each other's resource stock in real time, send transfer requests,
get admin approval, and communicate through a shared messaging board.

---

## How to Run

Step 1 — Make sure you have Python 3 and MySQL installed and running.

Step 2 — Install the Python libraries:
    pip install -r requirements.txt

Step 3 — Start the server:
    python app.py

Open your browser and go to: http://localhost:5000

The app creates the database, all tables, and sample data automatically on the first run.
You do not need to run schema.sql manually unless you want to reset everything.

---

## Login Credentials (Sample Data)

Username   Password   Role    Hospital
admin      admin123   Admin   All hospitals
staff1     staff123   Staff   KEM Hospital
staff2     staff123   Staff   Hinduja Hospital

---

## Project Structure

rescue_project/
    app.py              — Flask server, all routes and API logic
    db.py               — Database connection, table creation, sample data
    schema.sql          — Raw SQL to set up the database manually
    requirements.txt    — Python libraries needed
    README.md           — This file
    templates/
        login.html      — Login page with role selector
        admin.html      — Admin panel (full CRUD)
        staff.html      — Staff panel (hospital-scoped view)
        index.html      — Redirect page
    static/
        js/
            rescue_api.js   — JavaScript helper functions for API calls

app.py contains all the Flask routes. Each route handles one API endpoint.
Routes are grouped into: auth, hospitals, resources, transfers, messages, ambulances, triage, users.

db.py handles the MySQL connection. The init_db() function runs on startup.
It creates rescue_db if it does not exist, creates all the tables, and inserts sample data
if the tables are empty. This means the project works out of the box with no manual SQL needed.

schema.sql is the standalone SQL file for MySQL Workbench or phpMyAdmin.
Useful for showing CREATE TABLE statements, foreign keys, and constraints in the DBMS evaluation.

login.html has a role selector and a form. JavaScript sends credentials to the server
using fetch() and redirects the user to the correct panel based on their role.

admin.html loads all content dynamically without page reloads. The admin manages hospitals,
resources, users, transfers, ambulances, and messages. Each section is a table loaded from JSON.

staff.html shows only the logged-in user's own hospital's resources. Staff can submit
transfer requests, check request status, send messages, and view ambulance information.
The hospital restriction is enforced by the server using the session, not just the browser.

rescue_api.js wraps fetch calls into named functions like RescueAPI.resources.list()
so any HTML page can use them without rewriting the full fetch code each time.

---

## Database Tables

Seven tables, all in third normal form.

users — login details and roles. Passwords are hashed with PBKDF2-SHA256.
        hospital_id is a foreign key linking each staff user to their hospital.

hospitals — name, location, network type, ICU capacity, and available ICU beds.

resources — medicines, equipment, beds, and blood products stored per hospital.
            critical_threshold is compared against stock to flag low items.

transfers — the main workflow table. Records every request from submission to completion.
            status ENUM has four values: pending, approved, rejected, completed.
            When approved, the server automatically reduces stock in the resources table.
            from_hospital_id, to_hospital_id, resource_id, requested_by are all foreign keys.

messages — broadcast and direct messages between hospitals.
           sender_id is a foreign key to users. to_hospital is nullable for broadcasts.

ambulances — vehicle code, hospital assignment, status, location text, and ETA.
             hospital_id is a foreign key to hospitals.

triage — active patient cases with priority P1, P2, or P3.
         hospital_id is a foreign key to hospitals.

---

## SQL Concepts Covered in This Project

DDL (Lab 2):
  CREATE DATABASE rescue_db
  CREATE TABLE with PRIMARY KEY, NOT NULL, UNIQUE, FOREIGN KEY, CHECK constraints
  All five constraint types are present in schema.sql

DML (Lab 3 and 5):
  INSERT INTO with multiple rows for sample hospitals, users, resources, and ambulances
  SELECT with WHERE clause filtering by hospital_id, status, and role
  UPDATE to change transfer status and reduce stock count
  DELETE to remove hospitals, resources, and users from the admin panel

Joins (Lab 8):
  All transfer and resource queries use INNER JOIN to pull hospital names and resource names
  rather than returning raw IDs to the browser

GROUP BY and aggregates (Lab 6):
  Admin stats endpoint uses COUNT(*) for hospitals, resources, transfers, users
  and SUM(icu_available) to total available ICU beds across all hospitals

Subqueries (Lab 9):
  Stock check before a transfer is submitted uses a SELECT inside the validation logic
  to confirm the requested units do not exceed what the source hospital currently holds

Normalization (Lab 10):
  Hospital names are stored once in the hospitals table and referenced by ID everywhere else
  No column group repeats across any table
  All non-key columns depend only on the primary key in their table (3NF)

---

## API Endpoints

All responses: { "success": true, "data": [...] }  or  { "success": false, "error": "message" }

POST   /api/login               Anyone        Login
POST   /api/logout              Logged in     Logout
GET    /api/me                  Logged in     Current user info
GET    /api/admin/stats         Admin only    Dashboard counts
GET    /api/hospitals           Logged in     List hospitals
POST   /api/hospitals           Admin only    Add hospital
PUT    /api/hospitals/<id>      Admin only    Edit hospital
DELETE /api/hospitals/<id>      Admin only    Remove hospital
GET    /api/resources           Logged in     List resources (staff sees own hospital only)
POST   /api/resources           Admin only    Add resource
PUT    /api/resources/<id>      Admin only    Edit resource
DELETE /api/resources/<id>      Admin only    Remove resource
GET    /api/transfers           Logged in     List transfers (staff sees own hospital only)
POST   /api/transfers           Staff/Admin   Submit transfer request
PUT    /api/transfers/<id>      Admin only    Approve, reject, or complete
GET    /api/messages            Logged in     Get message log
POST   /api/messages            Logged in     Send message
GET    /api/ambulances          Logged in     List ambulances
POST   /api/ambulances          Admin only    Add ambulance
PUT    /api/ambulances/<id>     Admin only    Update ambulance
GET    /api/users               Admin only    List users
POST   /api/users               Admin only    Create user
DELETE /api/users/<id>          Admin only    Remove user
GET    /api/triage              Logged in     List triage cases
POST   /api/triage              Logged in     Add triage case

---

## Security Notes

Passwords are hashed before storage using generate_password_hash from Werkzeug.
The hash method is PBKDF2-SHA256. The plain text password is never stored anywhere.

Sessions use Flask cookies with HttpOnly set so JavaScript cannot read the cookie.
The SECRET_KEY in app.py should be changed to a random string before deployment.

Role restrictions are enforced server side using Python decorators.
Changing something in the browser cannot bypass them because the check happens
on the server before any data is returned or written.

---

## Changing the Database Settings

Edit the top of db.py:

    DB_CONFIG = {
        "host":     "localhost",
        "user":     "root",
        "password": "root",
        "database": "rescue_db",
    }

Or set environment variables before running:
    DB_PASSWORD=yourpassword
    SECRET_KEY=anyrandomstring

---

## Lab Mapping

Web Programming labs covered:
  Lab 2-4   HTML forms, tags, CSS styling across login, admin, and staff pages
  Lab 5-6   JavaScript operators, conditions, and form validation
  Lab 7-9   JavaScript fetch calls, dynamic page updates without reload

DBMS labs covered:
  Lab 2     DDL with all five constraint types in schema.sql
  Lab 3     INSERT, SELECT, UPDATE, DELETE used throughout app.py
  Lab 4     ER model with seven entities (see the report for the diagram description)
  Lab 5-6   WHERE, ORDER BY, GROUP BY, HAVING, aggregate functions
  Lab 8     JOIN queries across hospitals, resources, transfers, and users tables
  Lab 9     Subqueries for stock validation before transfer approval
  Lab 10    3NF normalization across all seven tables

---

Nishant Parwani  |  Team Onrique  |  NMIMS Mumbai  |  2024-25
