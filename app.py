from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ---------------- DB CONNECTION ----------------
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "admin" in session:
        return redirect("/admin-dashboard")
    if "user_id" in session:
        return redirect("/dashboard")
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        hashed_pw = generate_password_hash(password)

        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO users (username,email,password) VALUES (%s,%s,%s)",
                (username, email, hashed_pw)
            )
            db.commit()
            flash("Registration successful! Please log in.", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()
            db.close()

        return redirect("/login")

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")

# ---------------- USER DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM complaints WHERE user_id=%s", (session["user_id"],))
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS pending FROM complaints WHERE user_id=%s AND status='pending'", (session["user_id"],))
    pending = cursor.fetchone()["pending"]

    cursor.execute("SELECT COUNT(*) AS resolved FROM complaints WHERE user_id=%s AND status='resolved'", (session["user_id"],))
    resolved = cursor.fetchone()["resolved"]

    cursor.close()
    db.close()

    return render_template("dashboard.html",
                           username=session["username"],
                           total=total,
                           pending=pending,
                           resolved=resolved)

# ---------------- MY COMPLAINTS ----------------
@app.route("/my-complaints")
def my_complaints():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM complaints WHERE user_id=%s", (session["user_id"],))
    complaints = cursor.fetchall()
    cursor.close()
    db.close()

    return render_template("my_complaints.html", complaints=complaints, username=session["username"])

# ---------------- ADD COMPLAINT ----------------
@app.route("/add-complaint", methods=["GET", "POST"])
def add_complaint():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        title = request.form["title"].strip()
        category = request.form["category"].strip()
        description = request.form["description"].strip()

        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
                "INSERT INTO complaints (user_id, title, category, description, status) VALUES (%s, %s, %s, %s, %s)",
                (session["user_id"], title, category, description, "pending")
            )
            db.commit()
            flash("Complaint added successfully!", "success")
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close()
            db.close()

        return redirect("/my-complaints")

    return render_template("add_complaint.html")

# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if "admin" in session:
        return redirect("/admin-dashboard")

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin WHERE username=%s", (username,))
        admin = cursor.fetchone()
        cursor.close()
        db.close()

        if admin and check_password_hash(admin["password"], password):
            session["admin"] = True
            session["admin_username"] = admin["username"]
            return redirect("/admin-dashboard")
        else:
            flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html")

# ---------------- ADMIN DASHBOARD ----------------
# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin-dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Complaints with user info
    cursor.execute("""
        SELECT complaints.id, users.username, complaints.title, complaints.category, complaints.description, complaints.status, complaints.created_at
        FROM complaints
        JOIN users ON complaints.user_id = users.id
    """)
    data = cursor.fetchall()

    # Pending count
    cursor.execute("SELECT COUNT(*) AS pending FROM complaints WHERE status='pending'")
    pending = cursor.fetchone()["pending"]

    # Resolved count
    cursor.execute("SELECT COUNT(*) AS resolved FROM complaints WHERE status='resolved'")
    resolved = cursor.fetchone()["resolved"]

    cursor.close()
    db.close()

    return render_template("admin_dashboard.html", data=data, pending=pending, resolved=resolved)

# ---------------- UPDATE COMPLAINT STATUS ----------------
@app.route("/update-complaint/<int:complaint_id>/<string:new_status>")
def update_complaint(complaint_id, new_status):
    if "admin" not in session:
        flash("Unauthorized access!", "danger")
        return redirect("/login")

    if new_status not in ["pending", "resolved"]:
        flash("Invalid status value!", "danger")
        return redirect("/admin-dashboard")

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("UPDATE complaints SET status=%s WHERE id=%s", (new_status, complaint_id))
        db.commit()
        flash("Complaint status updated successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect("/admin-dashboard")

# ---------------- DELETE COMPLAINT ----------------
@app.route("/delete-complaint/<int:complaint_id>")
def delete_complaint(complaint_id):
    if "admin" not in session:
        flash("Unauthorized access!", "danger")
        return redirect("/login")

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("DELETE FROM complaints WHERE id=%s", (complaint_id,))
        db.commit()
        flash("Complaint deleted successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        cursor.close()
        db.close()

    return redirect("/admin-dashboard")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)