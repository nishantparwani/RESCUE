"""
app.py  —  RESCUE Flask Application
Run:  python app.py
"""

from flask import (
    Flask, render_template, request, session,
    redirect, url_for, jsonify, abort
)
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
import os

from db import init_db, query

# ─────────────────────────────────────────
#  APP SETUP
# ─────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rescue-secret-2025-change-in-prod")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ─────────────────────────────────────────
#  AUTH DECORATORS
# ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def staff_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") not in ("staff", "admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def ok(data=None, **kwargs):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(kwargs)
    return jsonify(payload)


def err(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code


# ─────────────────────────────────────────
#  PAGE ROUTES
# ─────────────────────────────────────────
@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    if session.get("role") == "admin":
        return redirect(url_for("admin_page"))
    return redirect(url_for("staff_page"))


@app.route("/login", methods=["GET"])
def login_page():
    if "user_id" in session:
        return redirect(url_for("home"))
    return render_template("login.html")


@app.route("/admin")
@login_required
@admin_required
def admin_page():
    return render_template("admin.html", user=session)


@app.route("/staff")
@login_required
@staff_required
def staff_page():
    return render_template("staff.html", user=session)


@app.route("/dashboard")
@login_required
def dashboard_page():
    return render_template("index.html", user=session)


# ─────────────────────────────────────────
#  AUTH API
# ─────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return err("Username and password are required.")

    user = query(
        "SELECT u.*, h.name AS hospital_name FROM users u "
        "LEFT JOIN hospitals h ON u.hospital_id = h.id "
        "WHERE u.username = %s",
        (username,), fetchone=True
    )

    if not user or not check_password_hash(user["password"], password):
        return err("Invalid credentials.", 401)

    session.clear()
    session["user_id"]       = user["id"]
    session["username"]      = user["username"]
    session["role"]          = user["role"]
    session["hospital_id"]   = user["hospital_id"]
    session["hospital_name"] = user.get("hospital_name", "")

    redirect_url = "/admin" if user["role"] == "admin" else "/staff"
    return ok({"redirect": redirect_url, "role": user["role"], "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return ok({"redirect": "/login"})


@app.route("/api/me", methods=["GET"])
@login_required
def api_me():
    return ok({
        "user_id":       session["user_id"],
        "username":      session["username"],
        "role":          session["role"],
        "hospital_id":   session.get("hospital_id"),
        "hospital_name": session.get("hospital_name"),
    })


# ─────────────────────────────────────────
#  ADMIN  — STATS
# ─────────────────────────────────────────
@app.route("/api/admin/stats", methods=["GET"])
@login_required
@admin_required
def api_admin_stats():
    hospitals  = query("SELECT COUNT(*) AS c FROM hospitals", fetchone=True)["c"]
    resources  = query("SELECT COUNT(*) AS c FROM resources", fetchone=True)["c"]
    transfers  = query("SELECT COUNT(*) AS c FROM transfers", fetchone=True)["c"]
    pending    = query("SELECT COUNT(*) AS c FROM transfers WHERE status='pending'", fetchone=True)["c"]
    users      = query("SELECT COUNT(*) AS c FROM users",    fetchone=True)["c"]
    ambulances = query("SELECT COUNT(*) AS c FROM ambulances WHERE status='active'", fetchone=True)["c"]
    icu_total  = query("SELECT SUM(icu_available) AS c FROM hospitals", fetchone=True)["c"] or 0

    return ok({
        "hospitals":        hospitals,
        "resources":        resources,
        "transfers":        transfers,
        "pending_transfers":pending,
        "users":            users,
        "active_ambulances":ambulances,
        "total_icu":        int(icu_total),
    })


# ─────────────────────────────────────────
#  HOSPITALS  CRUD
# ─────────────────────────────────────────
@app.route("/api/hospitals", methods=["GET"])
@login_required
def api_hospitals_list():
    rows = query(
        "SELECT id, name, location, network, status, icu_capacity, icu_available "
        "FROM hospitals ORDER BY id"
    )
    return ok(rows)


@app.route("/api/hospitals", methods=["POST"])
@login_required
@admin_required
def api_hospitals_create():
    d = request.get_json(force=True) or {}
    name     = (d.get("name") or "").strip()
    location = (d.get("location") or "").strip()
    if not name or not location:
        return err("name and location are required.")

    new_id = query(
        "INSERT INTO hospitals (name, location, network, icu_capacity, icu_available) "
        "VALUES (%s, %s, %s, %s, %s)",
        (name, location, d.get("network","5G"),
         int(d.get("icu_capacity", 0)), int(d.get("icu_available", 0))),
        commit=True
    )
    return ok({"id": new_id}), 201


@app.route("/api/hospitals/<int:hid>", methods=["PUT"])
@login_required
@admin_required
def api_hospitals_update(hid):
    d = request.get_json(force=True) or {}
    fields, vals = [], []
    for col in ("name", "location", "network", "status", "icu_capacity", "icu_available"):
        if col in d:
            fields.append(f"{col}=%s")
            vals.append(d[col])
    if not fields:
        return err("No fields to update.")
    vals.append(hid)
    query(f"UPDATE hospitals SET {', '.join(fields)} WHERE id=%s", tuple(vals), commit=True)
    return ok()


@app.route("/api/hospitals/<int:hid>", methods=["DELETE"])
@login_required
@admin_required
def api_hospitals_delete(hid):
    query("DELETE FROM hospitals WHERE id=%s", (hid,), commit=True)
    return ok()


# ─────────────────────────────────────────
#  RESOURCES  CRUD
# ─────────────────────────────────────────
@app.route("/api/resources", methods=["GET"])
@login_required
def api_resources_list():
    hospital_id = request.args.get("hospital_id")
    # Staff can only see their own hospital
    if session.get("role") == "staff":
        hospital_id = session.get("hospital_id")

    if hospital_id:
        rows = query(
            "SELECT r.*, h.name AS hospital_name FROM resources r "
            "JOIN hospitals h ON r.hospital_id = h.id "
            "WHERE r.hospital_id=%s ORDER BY r.name",
            (hospital_id,)
        )
    else:
        rows = query(
            "SELECT r.*, h.name AS hospital_name FROM resources r "
            "JOIN hospitals h ON r.hospital_id = h.id ORDER BY h.name, r.name"
        )
    return ok(rows)


@app.route("/api/resources", methods=["POST"])
@login_required
@admin_required
def api_resources_create():
    d = request.get_json(force=True) or {}
    required = ("name", "hospital_id", "stock")
    for f in required:
        if not d.get(f) and d.get(f) != 0:
            return err(f"Field '{f}' is required.")

    new_id = query(
        "INSERT INTO resources (name, category, hospital_id, stock, unit, critical_threshold) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (d["name"].strip(), d.get("category","other"),
         int(d["hospital_id"]), int(d["stock"]),
         d.get("unit","units"), int(d.get("critical_threshold", 5))),
        commit=True
    )
    return ok({"id": new_id}), 201


@app.route("/api/resources/<int:rid>", methods=["PUT"])
@login_required
@admin_required
def api_resources_update(rid):
    d = request.get_json(force=True) or {}
    fields, vals = [], []
    for col in ("name", "category", "stock", "unit", "critical_threshold", "hospital_id"):
        if col in d:
            fields.append(f"{col}=%s")
            vals.append(d[col])
    if not fields:
        return err("No fields to update.")
    vals.append(rid)
    query(f"UPDATE resources SET {', '.join(fields)} WHERE id=%s", tuple(vals), commit=True)
    return ok()


@app.route("/api/resources/<int:rid>", methods=["DELETE"])
@login_required
@admin_required
def api_resources_delete(rid):
    query("DELETE FROM resources WHERE id=%s", (rid,), commit=True)
    return ok()


# ─────────────────────────────────────────
#  TRANSFERS
# ─────────────────────────────────────────
@app.route("/api/transfers", methods=["GET"])
@login_required
def api_transfers_list():
    if session.get("role") == "admin":
        rows = query(
            "SELECT t.*, "
            "  fh.name AS from_hospital, th.name AS to_hospital, "
            "  r.name AS resource_name, "
            "  u.username AS requested_by_name "
            "FROM transfers t "
            "JOIN hospitals fh ON t.from_hospital_id = fh.id "
            "JOIN hospitals th ON t.to_hospital_id   = th.id "
            "JOIN resources r  ON t.resource_id       = r.id "
            "JOIN users u      ON t.requested_by      = u.id "
            "ORDER BY t.created_at DESC"
        )
    else:
        hid = session.get("hospital_id")
        rows = query(
            "SELECT t.*, "
            "  fh.name AS from_hospital, th.name AS to_hospital, "
            "  r.name AS resource_name, "
            "  u.username AS requested_by_name "
            "FROM transfers t "
            "JOIN hospitals fh ON t.from_hospital_id = fh.id "
            "JOIN hospitals th ON t.to_hospital_id   = th.id "
            "JOIN resources r  ON t.resource_id       = r.id "
            "JOIN users u      ON t.requested_by      = u.id "
            "WHERE t.from_hospital_id=%s OR t.to_hospital_id=%s "
            "ORDER BY t.created_at DESC",
            (hid, hid)
        )
    # convert datetimes to strings
    for r in rows:
        for k in ("created_at", "updated_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].strftime("%Y-%m-%d %H:%M")
    return ok(rows)


@app.route("/api/transfers", methods=["POST"])
@login_required
@staff_required
def api_transfers_create():
    d = request.get_json(force=True) or {}
    required = ("from_hospital_id", "to_hospital_id", "resource_id", "units")
    for f in required:
        if not d.get(f):
            return err(f"Field '{f}' is required.")

    if session.get("role") == "staff":
        if int(d["from_hospital_id"]) != session.get("hospital_id"):
            return err("You can only request from your own hospital.", 403)

    # check stock
    res = query(
        "SELECT stock FROM resources WHERE id=%s AND hospital_id=%s",
        (int(d["resource_id"]), int(d["from_hospital_id"])),
        fetchone=True
    )
    if not res:
        return err("Resource not found at that hospital.")
    if res["stock"] < int(d["units"]):
        return err(f"Insufficient stock. Available: {res['stock']}")

    new_id = query(
        "INSERT INTO transfers (from_hospital_id, to_hospital_id, resource_id, units, "
        "requested_by, notes) VALUES (%s,%s,%s,%s,%s,%s)",
        (int(d["from_hospital_id"]), int(d["to_hospital_id"]),
         int(d["resource_id"]),      int(d["units"]),
         session["user_id"],         d.get("notes", "")),
        commit=True
    )
    return ok({"id": new_id}), 201


@app.route("/api/transfers/<int:tid>", methods=["PUT"])
@login_required
@admin_required
def api_transfers_update(tid):
    d = request.get_json(force=True) or {}
    status = d.get("status", "").strip()
    if status not in ("approved", "rejected", "completed"):
        return err("status must be approved, rejected, or completed.")

    transfer = query("SELECT * FROM transfers WHERE id=%s", (tid,), fetchone=True)
    if not transfer:
        return err("Transfer not found.", 404)

    query(
        "UPDATE transfers SET status=%s, approved_by=%s WHERE id=%s",
        (status, session["user_id"], tid), commit=True
    )

    # If approved: deduct stock from source hospital
    if status == "approved":
        query(
            "UPDATE resources SET stock = stock - %s "
            "WHERE id=%s AND hospital_id=%s AND stock >= %s",
            (transfer["units"], transfer["resource_id"],
             transfer["from_hospital_id"], transfer["units"]),
            commit=True
        )

    return ok()


# ─────────────────────────────────────────
#  MESSAGES
# ─────────────────────────────────────────
@app.route("/api/messages", methods=["GET"])
@login_required
def api_messages_list():
    rows = query(
        "SELECT m.*, u.username AS sender_name, "
        "  h.name AS hospital_name "
        "FROM messages m "
        "JOIN users u ON m.sender_id = u.id "
        "LEFT JOIN hospitals h ON u.hospital_id = h.id "
        "ORDER BY m.timestamp DESC LIMIT 50"
    )
    for r in rows:
        if isinstance(r.get("timestamp"), datetime):
            r["timestamp"] = r["timestamp"].strftime("%H:%M")
    return ok(rows)


@app.route("/api/messages", methods=["POST"])
@login_required
def api_messages_create():
    d = request.get_json(force=True) or {}
    content = (d.get("content") or "").strip()
    if not content:
        return err("Message content cannot be empty.")

    new_id = query(
        "INSERT INTO messages (sender_id, content, broadcast, to_hospital) VALUES (%s,%s,%s,%s)",
        (session["user_id"], content,
         int(d.get("broadcast", 1)), d.get("to_hospital") or None),
        commit=True
    )
    return ok({"id": new_id}), 201


# ─────────────────────────────────────────
#  AMBULANCES
# ─────────────────────────────────────────
@app.route("/api/ambulances", methods=["GET"])
@login_required
def api_ambulances_list():
    rows = query(
        "SELECT a.*, h.name AS hospital_name FROM ambulances a "
        "LEFT JOIN hospitals h ON a.hospital_id = h.id ORDER BY a.code"
    )
    return ok(rows)


@app.route("/api/ambulances", methods=["POST"])
@login_required
@admin_required
def api_ambulances_create():
    d = request.get_json(force=True) or {}
    code = (d.get("code") or "").strip()
    if not code:
        return err("Ambulance code is required.")
    new_id = query(
        "INSERT INTO ambulances (code, hospital_id, status, location, eta) "
        "VALUES (%s,%s,%s,%s,%s)",
        (code, d.get("hospital_id") or None,
         d.get("status","active"), d.get("location","Base"), d.get("eta","--")),
        commit=True
    )
    return ok({"id": new_id}), 201


@app.route("/api/ambulances/<int:aid>", methods=["PUT"])
@login_required
@admin_required
def api_ambulances_update(aid):
    d = request.get_json(force=True) or {}
    fields, vals = [], []
    for col in ("code", "hospital_id", "status", "location", "eta"):
        if col in d:
            fields.append(f"{col}=%s")
            vals.append(d[col])
    if not fields:
        return err("No fields to update.")
    vals.append(aid)
    query(f"UPDATE ambulances SET {', '.join(fields)} WHERE id=%s", tuple(vals), commit=True)
    return ok()


# ─────────────────────────────────────────
#  USER MANAGEMENT (admin only)
# ─────────────────────────────────────────
@app.route("/api/users", methods=["GET"])
@login_required
@admin_required
def api_users_list():
    rows = query(
        "SELECT u.id, u.username, u.email, u.role, u.hospital_id, "
        "  h.name AS hospital_name, u.created_at "
        "FROM users u LEFT JOIN hospitals h ON u.hospital_id = h.id "
        "ORDER BY u.id"
    )
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d")
    return ok(rows)


@app.route("/api/users", methods=["POST"])
@login_required
@admin_required
def api_users_create():
    d = request.get_json(force=True) or {}
    username = (d.get("username") or "").strip()
    email    = (d.get("email")    or "").strip()
    password = (d.get("password") or "").strip()
    role     = d.get("role", "staff")

    if not username or not email or not password:
        return err("username, email and password are required.")
    if role not in ("admin", "staff"):
        return err("role must be admin or staff.")

    existing = query("SELECT id FROM users WHERE username=%s OR email=%s",
                     (username, email), fetchone=True)
    if existing:
        return err("Username or email already exists.")

    new_id = query(
        "INSERT INTO users (username, email, password, role, hospital_id) "
        "VALUES (%s,%s,%s,%s,%s)",
        (username, email, generate_password_hash(password),
         role, d.get("hospital_id") or None),
        commit=True
    )
    return ok({"id": new_id}), 201


@app.route("/api/users/<int:uid>", methods=["DELETE"])
@login_required
@admin_required
def api_users_delete(uid):
    if uid == session["user_id"]:
        return err("Cannot delete your own account.")
    query("DELETE FROM users WHERE id=%s", (uid,), commit=True)
    return ok()


# ─────────────────────────────────────────
#  TRIAGE
# ─────────────────────────────────────────
@app.route("/api/triage", methods=["GET"])
@login_required
def api_triage_list():
    if session.get("role") == "staff":
        rows = query(
            "SELECT t.*, h.name AS hospital_name FROM triage t "
            "JOIN hospitals h ON t.hospital_id = h.id "
            "WHERE t.hospital_id=%s ORDER BY t.priority, t.created_at DESC",
            (session["hospital_id"],)
        )
    else:
        rows = query(
            "SELECT t.*, h.name AS hospital_name FROM triage t "
            "JOIN hospitals h ON t.hospital_id = h.id "
            "ORDER BY t.priority, t.created_at DESC"
        )
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M")
    return ok(rows)


@app.route("/api/triage", methods=["POST"])
@login_required
def api_triage_create():
    d = request.get_json(force=True) or {}
    hid = session.get("hospital_id") if session["role"] == "staff" else d.get("hospital_id")
    if not hid:
        return err("hospital_id required.")
    import random
    case_code = "C-" + str(random.randint(1000, 9999))
    new_id = query(
        "INSERT INTO triage (case_code, hospital_id, patient_anon, condition_name, priority) "
        "VALUES (%s,%s,%s,%s,%s)",
        (case_code, int(hid), d.get("patient_anon","Unknown"),
         d.get("condition_name","—"), d.get("priority","P2")),
        commit=True
    )
    return ok({"id": new_id, "case_code": case_code}), 201


# ─────────────────────────────────────────
#  ERROR HANDLERS
# ─────────────────────────────────────────
@app.errorhandler(403)
def forbidden(e):
    return render_template("login.html", error="Access denied."), 403


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


# ─────────────────────────────────────────
#  ENTRYPOINT
# ─────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
