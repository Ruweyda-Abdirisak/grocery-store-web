import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change_this_secret_key_in_production"
DB_NAME = "users.db"
DEFAULT_ADMIN_EMAIL = "shugri@gmail.com"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    columns = [row["name"] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "role" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")

    cursor.execute(
        "UPDATE users SET role = 'admin' WHERE LOWER(email) = ?",
        (DEFAULT_ADMIN_EMAIL.lower(),),
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT COUNT(*) AS count FROM products")
    if cursor.fetchone()["count"] == 0:
        sample_products = [
            ("Bariis (5kg)", 8.50, 25),
            ("Saliid Cunto (3L)", 7.00, 30),
            ("Caano Boore (900g)", 6.25, 20),
            ("Sonkor (2kg)", 3.00, 40),
            ("Khudrad Isku Jira (1kg)", 2.50, 35),
            ("Hilib Geel (1kg)", 9.00, 20),
            ("Hilib Adhi (1kg)", 8.00, 20),
            ("Malay (1kg)", 5.50, 25),
            ("Hilib Doro (1kg)", 6.50, 22),
        ]
        cursor.executemany(
            "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
            sample_products,
        )

    conn.commit()
    conn.close()


def seed_new_products():
    conn = get_db()
    cursor = conn.cursor()

    extra_products = [
        ("Hilib Geel (1kg)", 9.00, 20),
        ("Hilib Adhi (1kg)", 8.00, 20),
        ("Malay (1kg)", 5.50, 25),
        ("Hilib Doro (1kg)", 6.50, 22),
    ]

    for name, price, stock in extra_products:
        exists = cursor.execute(
            "SELECT id FROM products WHERE name = ?",
            (name,),
        ).fetchone()
        if not exists:
            cursor.execute(
                "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                (name, price, stock),
            )

    conn.commit()
    conn.close()


init_db()
seed_new_products()


def is_logged_in():
    return "user" in session


def is_admin():
    return session.get("is_admin") is True


def generate_store_reply(message_text, conn=None):
    text = message_text.lower()

    if "dalab" in text or "order" in text:
        return "Dalabaadkaaga waxaad ka eegi kartaa qaybta My Orders ee Dashboard-ka."
    if "furan" in text or "saacad" in text or "time" in text:
        return "Dukaanku wuxuu shaqeeyaa maalin kasta; fariintaada waa la helay."

    known_items = {
        "bariis": "Bariis",
        "rice": "Bariis",
        "saliid": "Saliid",
        "oil": "Saliid",
        "caano": "Caano",
        "milk": "Caano",
        "sonkor": "Sonkor",
        "sugar": "Sonkor",
        "khudrad": "Khudrad",
        "geel": "Hilib Geel",
        "camel": "Hilib Geel",
        "adhi": "Hilib Adhi",
        "ari": "Hilib Adhi",
        "goat": "Hilib Adhi",
        "malay": "Malay",
        "kalluun": "Malay",
        "fish": "Malay",
        "doro": "Hilib Doro",
        "digaag": "Hilib Doro",
        "chicken": "Hilib Doro",
    }

    for keyword, db_part in known_items.items():
        if keyword in text:
            if conn is not None:
                row = conn.execute(
                    "SELECT name, stock FROM products WHERE name LIKE ?",
                    (f"%{db_part}%",),
                ).fetchone()
                if row and row["stock"] > 0:
                    return f"Haa, waan haynaa ({row['name']})! Waxaa yaalla {row['stock']} xabbo."
                elif row and row["stock"] == 0:
                    return f"Maya, hadda ma yaallo ({row['name']}) — stock-ga waa dhammaaday."
            return f"Haa, {db_part} waa qayb ka mid ah alaabta dukaanka. Fadlan eeg bogga Products."

    return "Maya, shaygaas hadda ma yaallo ama kuma jiro liiska alaabta dukaanka."


@app.route("/", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user"] = user["email"]
            session["is_admin"] = (user["role"] == "admin")
            flash("Si guul leh ayaad u soo gashay!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email ama password-ka waa khalad.", "error")

    return render_template("index.html", logged_in=is_logged_in())


@app.route("/register", methods=["GET", "POST"])
def register():
    if is_logged_in():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if password != confirm_password:
            flash("Password-ka iyo Confirm Password isma laha.", "error")
            return render_template("register.html", logged_in=is_logged_in())

        role = "admin" if email == DEFAULT_ADMIN_EMAIL.lower() else "user"
        hashed_pw = generate_password_hash(password)

        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                (email, hashed_pw, role),
            )
            conn.commit()
            conn.close()
            flash("Akoonka waa la sameeyay! Hadda soo gal.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email-kan horay ayaa loo diiwaangeliyay.", "error")

    return render_template("register.html", logged_in=is_logged_in())


@app.route("/dashboard")
def dashboard():
    if not is_logged_in():
        flash("Fadlan marka hore soo gal si aad u aragto Dashboard-ka.", "error")
        return redirect(url_for("login"))

    user_email = session["user"]
    conn = get_db()
    orders = conn.execute(
        "SELECT * FROM orders WHERE user_email = ? ORDER BY id DESC",
        (user_email,),
    ).fetchall()
    raw_messages = conn.execute(
        "SELECT * FROM messages WHERE email = ? ORDER BY id DESC",
        (user_email,),
    ).fetchall()

    messages = []
    for m in raw_messages:
        messages.append({
            "id": m["id"],
            "name": m["name"],
            "email": m["email"],
            "message": m["message"],
            "created_at": m["created_at"],
            "reply": generate_store_reply(m["message"], conn),
        })

    conn.close()

    grand_total = sum(order["total_price"] for order in orders)

    return render_template(
        "dashboard.html",
        logged_in=True,
        email=user_email,
        orders=orders,
        grand_total=grand_total,
        messages=messages,
    )


@app.route("/cancel-order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    if not is_logged_in():
        flash("Fadlan marka hore soo gal.", "error")
        return redirect(url_for("login"))

    user_email = session["user"]
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND user_email = ?",
        (order_id, user_email),
    ).fetchone()

    if not order:
        conn.close()
        flash("Dalabka lama helin ama ma lihid awoodda aad ku tirtirto.", "error")
        return redirect(url_for("dashboard"))

    conn.execute(
        "UPDATE products SET stock = stock + ? WHERE name = ?",
        (order["quantity"], order["product_name"]),
    )
    conn.execute(
        "DELETE FROM orders WHERE id = ? AND user_email = ?",
        (order_id, user_email),
    )
    conn.commit()
    conn.close()

    flash(f"Dalabkii ({order['product_name']}) waa la joojiyay, stock-giina waa la soo celiyay.", "success")
    return redirect(url_for("dashboard"))


@app.route("/services", methods=["GET", "POST"])
def services():
    if request.method == "POST":
        if not is_logged_in():
            flash("Fadlan marka hore soo gal si aad alaab u dalbato.", "error")
            return redirect(url_for("login"))

        product_id = request.form.get("product_id", type=int)
        quantity = request.form.get("quantity", type=int, default=1)

        if not quantity or quantity < 1:
            flash("Tirada la dalbanayo waa inay ahaato ugu yaraan 1.", "error")
            return redirect(url_for("services"))

        conn = get_db()
        product = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        if not product:
            conn.close()
            flash("Alaabta la doortay lama helin.", "error")
            return redirect(url_for("services"))

        if product["stock"] < quantity:
            conn.close()
            flash(f"Waxaa yaalla kaliya {product['stock']} xabbo oo {product['name']} ah.", "error")
            return redirect(url_for("services"))

        total_price = round(product["price"] * quantity, 2)
        new_stock = product["stock"] - quantity

        conn.execute(
            """
            INSERT INTO orders (user_email, product_name, quantity, total_price)
            VALUES (?, ?, ?, ?)
            """,
            (session["user"], product["name"], quantity, total_price),
        )
        conn.execute(
            "UPDATE products SET stock = ? WHERE id = ?",
            (new_stock, product_id),
        )
        conn.commit()
        conn.close()

        flash(f"Dalabkaaga ({quantity} x {product['name']} - ${total_price:.2f}) waa la gudbiyay!", "success")
        return redirect(url_for("dashboard"))

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    conn.close()

    return render_template(
        "services.html",
        logged_in=is_logged_in(),
        products=products,
    )


@app.route("/about")
def about():
    return render_template("about.html", logged_in=is_logged_in())


@app.route("/contact", methods=["GET", "POST"])
def contact():
    user_email = session.get("user", "")
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        message = request.form.get("message", "").strip()

        if name and email and message:
            conn = get_db()
            conn.execute(
                "INSERT INTO messages (name, email, message) VALUES (?, ?, ?)",
                (name, email, message),
            )
            conn.commit()
            conn.close()
            flash("Fariintaada si guul leh ayaa loo diray dukaanka!", "success")
            return redirect(url_for("contact"))
        else:
            flash("Fadlan buuxi magaca, email-ka, iyo fariintaada.", "error")

    return render_template("contact.html", logged_in=is_logged_in(), email=user_email)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "admin_login":
            email = request.form.get("admin_email", "").strip().lower()
            secret = request.form.get("admin_password", "")

            conn = get_db()
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            conn.close()

            if user and check_password_hash(user["password"], secret) and user["role"] == "admin":
                session["user"] = user["email"]
                session["is_admin"] = True
                flash("Si guul leh ayaad u gashay Admin View!", "success")
            else:
                flash("Email-ka, password-ka, ama ogolaanshaha Admin-ka waa khalad.", "error")
            return redirect(url_for("admin"))

        if action == "admin_logout":
            session.pop("is_admin", None)
            flash("Waad ka baxday Admin View.", "success")
            return redirect(url_for("admin"))

        if not is_admin():
            flash("Fadlan marka hore soo gal Admin View.", "error")
            return redirect(url_for("admin"))

        if action == "create_admin":
            new_email = request.form.get("new_admin_email", "").strip().lower()
            new_password = request.form.get("new_admin_password", "")

            if new_email and len(new_password) >= 4:
                hashed_pw = generate_password_hash(new_password)
                try:
                    conn = get_db()
                    conn.execute(
                        "INSERT INTO users (email, password, role) VALUES (?, ?, 'admin')",
                        (new_email, hashed_pw),
                    )
                    conn.commit()
                    conn.close()
                    flash(f"Admin cusub ({new_email}) waa la sameeyay!", "success")
                except sqlite3.IntegrityError:
                    conn = get_db()
                    conn.execute(
                        "UPDATE users SET role = 'admin' WHERE email = ?",
                        (new_email,),
                    )
                    conn.commit()
                    conn.close()
                    flash(f"Akoonka ({new_email}) waxaa loo dallacsiiyay Admin!", "success")
            else:
                flash("Fadlan geli email sax ah iyo password ugu yaraan 4 xaraf ah.", "error")
            return redirect(url_for("admin"))

        if action == "toggle_role":
            target_id = request.form.get("user_id", type=int)
            if target_id:
                conn = get_db()
                target = conn.execute("SELECT id, email, role FROM users WHERE id = ?", (target_id,)).fetchone()
                if target:
                    new_role = "admin" if target["role"] != "admin" else "user"
                    conn.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_id))
                    conn.commit()
                    flash(f"Doorka {target['email']} waxaa loo beddelay {new_role}.", "success")
                conn.close()
            return redirect(url_for("admin"))

        if action == "add_product":
            name = request.form.get("name", "").strip()
            price = request.form.get("price", type=float)
            stock = request.form.get("stock", type=int)

            if name and price is not None and price > 0 and stock is not None and stock >= 0:
                conn = get_db()
                conn.execute(
                    "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
                    (name, round(price, 2), stock),
                )
                conn.commit()
                conn.close()
                flash(f"Alaab cusub ({name}) waa lagu daray dukaanka!", "success")
            else:
                flash("Fadlan geli magaca alaabta, qiime sax ah, iyo stock sax ah.", "error")
            return redirect(url_for("admin"))

        if action == "update_stock":
            product_id = request.form.get("product_id", type=int)
            new_stock = request.form.get("stock", type=int)
            new_price = request.form.get("price", type=float)

            if product_id and new_stock is not None and new_stock >= 0 and new_price is not None and new_price > 0:
                conn = get_db()
                conn.execute(
                    "UPDATE products SET stock = ?, price = ? WHERE id = ?",
                    (new_stock, round(new_price, 2), product_id),
                )
                conn.commit()
                conn.close()
                flash("Stock-ga iyo qiimaha alaabta waa la cusboonaysiiyay!", "success")
            else:
                flash("Xogta la geliyay ma saxna.", "error")
            return redirect(url_for("admin"))

        if action == "delete_product":
            product_id = request.form.get("product_id", type=int)
            if product_id:
                conn = get_db()
                conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
                conn.commit()
                conn.close()
                flash("Alaabta waa laga saaray liiska.", "success")
            return redirect(url_for("admin"))

    if not is_admin():
        return render_template("admin.html", is_admin=False, logged_in=is_logged_in())

    conn = get_db()
    products = conn.execute("SELECT * FROM products ORDER BY id ASC").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    messages = conn.execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
    users = conn.execute("SELECT id, email, role FROM users ORDER BY id ASC").fetchall()
    conn.close()

    total_revenue = sum(o["total_price"] for o in orders)

    return render_template(
        "admin.html",
        is_admin=True,
        logged_in=is_logged_in(),
        products=products,
        orders=orders,
        messages=messages,
        users=users,
        total_revenue=total_revenue,
    )


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("is_admin", None)
    flash("Waad ka baxday nidaamka.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)