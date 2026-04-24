import json
import sqlite3
import sys
import uuid
import argparse
import os
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

LOCAL_DEPS = Path(__file__).with_name(".pydeps")
if LOCAL_DEPS.exists():
    sys.path.insert(0, str(LOCAL_DEPS))

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename


APP_TITLE = "云点餐"
DB_PATH = Path(os.getenv("APP_DB_PATH", str(Path(__file__).with_suffix(".db"))))
UPLOAD_DIR = Path(os.getenv("APP_UPLOAD_DIR", str(Path(__file__).with_name("uploads"))))
UPLOAD_DIR.mkdir(exist_ok=True)

ORDER_STATUS_NEW = "new"
ORDER_STATUS_MAKING = "making"
ORDER_STATUS_DONE = "done"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUS_USER_CANCELLED = "user_cancelled"
ACTIVE_ORDER_STATUSES = (ORDER_STATUS_NEW, ORDER_STATUS_MAKING)

PLATFORM_REVIEW_USERNAME = "Chenny"
PLATFORM_REVIEW_PASSWORD = "CHENSONGTAO1.cst"
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY", "replace-with-a-strong-secret-in-production")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


BASE_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{ title }} - {{ app_title }}</title>
  <style>
    :root {
      --bg: #f6f8fc;
      --text: #1d2433;
      --muted: #64708a;
      --primary: #ff6b35;
      --primary-strong: #e95a28;
      --card: #ffffff;
      --line: #e8edf5;
      --ok: #17a34a;
      --warn: #e29c18;
      --danger: #c43b28;
      --shadow: 0 8px 24px rgba(20, 38, 70, 0.08);
      --radius: 16px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 10% -20%, #ffe7de 0%, transparent 45%),
        radial-gradient(circle at 90% -10%, #e6f6ff 0%, transparent 40%),
        var(--bg);
      min-height: 100vh;
    }
    a { color: inherit; text-decoration: none; }
    .topbar {
      position: sticky;
      top: 0;
      backdrop-filter: blur(8px);
      background: rgba(255, 255, 255, 0.92);
      border-bottom: 1px solid var(--line);
      z-index: 10;
    }
    .topbar-inner {
      max-width: 1120px;
      margin: 0 auto;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      font-size: 18px;
    }
    .brand-badge {
      width: 34px;
      height: 34px;
      border-radius: 10px;
      background: linear-gradient(140deg, #ff7a45, #ff3d6e);
      box-shadow: var(--shadow);
    }
    .nav {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 7px 13px;
      font-size: 14px;
      background: #fff;
      transition: all .2s;
    }
    .pill:hover { border-color: #d7dfed; transform: translateY(-1px); }
    .pill.primary {
      background: var(--primary);
      color: #fff;
      border-color: transparent;
    }
    .pill.primary:hover { background: var(--primary-strong); }
    .container {
      max-width: 1120px;
      margin: 20px auto;
      padding: 0 16px 40px;
    }
    .hero {
      background: linear-gradient(130deg, #fff6f2, #ffffff 45%, #f2faff);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 20px;
      margin-bottom: 16px;
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(22px, 3.5vw, 30px);
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 14px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 16px;
    }
    .card h3 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    .muted {
      color: var(--muted);
      font-size: 13px;
    }
    .row {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }
    .space-between { justify-content: space-between; }
    .btn {
      border: none;
      border-radius: 10px;
      padding: 10px 14px;
      background: var(--primary);
      color: #fff;
      font-size: 14px;
      cursor: pointer;
      transition: all .2s;
    }
    .btn:hover { background: var(--primary-strong); transform: translateY(-1px); }
    .btn.secondary {
      background: #f2f5fb;
      color: #30405f;
      border: 1px solid #dee6f3;
    }
    .btn.secondary:hover { background: #e9eff9; }
    .btn.ok { background: var(--ok); }
    .btn.ok:hover { background: #11853c; }
    .btn.danger { background: var(--danger); }
    .btn.danger:hover { background: #a62f1f; }
    input, textarea, select {
      width: 100%;
      border: 1px solid #dbe3f2;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
      outline: none;
      transition: border-color .2s;
      background: #fff;
    }
    input:focus, textarea:focus, select:focus { border-color: #f7a27b; }
    label {
      font-size: 13px;
      margin-bottom: 6px;
      display: block;
      color: #3f4b66;
    }
    .field { margin-bottom: 12px; }
    .price { color: #e23d0f; font-weight: 700; }
    .table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    .table th, .table td {
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: middle;
    }
    .flash-wrap {
      display: grid;
      gap: 8px;
      margin-bottom: 14px;
    }
    .flash {
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 13px;
      border: 1px solid;
    }
    .flash.success { background: #edfff3; border-color: #b7efc6; color: #1d7d39; }
    .flash.warning { background: #fff8eb; border-color: #ffe1ac; color: #8e5a06; }
    .flash.error { background: #fff1f0; border-color: #ffc8c2; color: #a12f20; }
    .tag {
      display: inline-flex;
      align-items: center;
      padding: 4px 8px;
      border-radius: 999px;
      background: #f2f6ff;
      color: #3c5ba5;
      font-size: 12px;
    }
    .tag.pending { background: #fff3df; color: #a5670a; }
    .tag.approved { background: #e9fff1; color: #14733a; }
    .tag.rejected { background: #fff1f0; color: #9d2f21; }
    .tag.pickup { background: #eef5ff; color: #2458b8; }
    .notice {
      border: 1px dashed #ffc796;
      background: #fff7ef;
      color: #a6581d;
      border-radius: 12px;
      padding: 10px 12px;
      font-size: 13px;
    }
    .stars {
      display: inline-flex;
      flex-direction: row-reverse;
      gap: 4px;
    }
    .stars input { display: none; }
    .stars label {
      margin: 0;
      font-size: 22px;
      color: #d0d6e2;
      cursor: pointer;
      line-height: 1;
    }
    .stars input:checked ~ label,
    .stars label:hover,
    .stars label:hover ~ label {
      color: #ff9f1c;
    }
    .footer-note {
      text-align: center;
      color: var(--muted);
      font-size: 12px;
      margin-top: 26px;
    }
    @media (max-width: 720px) {
      .topbar-inner { align-items: flex-start; flex-direction: column; }
      .nav { justify-content: flex-start; }
      .card { padding: 14px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <div class="brand-badge"></div>
        <a href="{{ url_for('home') }}">{{ app_title }}</a>
      </div>
      <nav class="nav">
        <a class="pill" href="{{ url_for('home') }}">首页</a>
        <a class="pill" href="{{ url_for('cart') }}">购物车({{ cart_count }})</a>
        {% if current_user %}
          <a class="pill" href="{{ url_for('my_orders') }}">我的订单</a>
          <a class="pill" href="{{ url_for('support_center') }}">用户支持</a>
          {% if current_user['is_merchant'] %}
            <a class="pill" href="{{ url_for('merchant_dashboard') }}">商家后台</a>
            <a class="pill" href="{{ url_for('merchant_orders') }}">门店订单</a>
          {% else %}
            <a class="pill" href="{{ url_for('merchant_join') }}">商家入驻</a>
          {% endif %}
          <span class="pill">{{ current_user['phone'] }}</span>
          <a class="pill" href="{{ url_for('logout') }}">退出</a>
        {% else %}
          <a class="pill primary" href="{{ url_for('login') }}">登录 / 注册</a>
        {% endif %}

        {% if is_platform_admin %}
          <a class="pill primary" href="{{ url_for('platform_review') }}">审核后台</a>
          <a class="pill" href="{{ url_for('platform_logout') }}">退出审核</a>
        {% else %}
          <a class="pill" href="{{ url_for('platform_login') }}">审核入口</a>
        {% endif %}
      </nav>
    </div>
  </header>

  <main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="flash-wrap">
          {% for category, message in messages %}
            <div class="flash {{ category }}">{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    {{ content | safe }}

    <div class="footer-note">初代演示版：商家入驻、菜品发布、用户留言均需审核通过后生效</div>
  </main>
</body>
</html>
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_column(cur, table, column_name, definition):
    columns = {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {definition}")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_json_list(raw_value):
    if not raw_value:
        return []
    try:
        value = json.loads(raw_value)
        if isinstance(value, list):
            return [str(x) for x in value if x]
    except Exception:
        pass
    return []


def dump_json_list(values):
    return json.dumps([str(v) for v in values if v], ensure_ascii=False)


def order_status_text(status):
    mapping = {
        ORDER_STATUS_NEW: "待接单",
        ORDER_STATUS_MAKING: "制作中",
        ORDER_STATUS_DONE: "商家已完成",
        ORDER_STATUS_CANCELLED: "商家取消接单",
        ORDER_STATUS_USER_CANCELLED: "用户取消订单",
    }
    return mapping.get(status, status)


def auto_down_shelf_empty_stores():
    conn = get_db()
    cur = conn.cursor()
    threshold = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    target_stores = cur.execute(
        """
        SELECT s.id
        FROM stores s
        WHERE s.is_active = 1
          AND s.created_at <= ?
          AND NOT EXISTS (SELECT 1 FROM dishes d WHERE d.store_id = s.id)
        """,
        (threshold,),
    ).fetchall()

    if target_stores:
        now = now_str()
        for row in target_stores:
            cur.execute(
                """
                UPDATE stores
                SET is_active = 0, down_shelf_reason = ?, down_shelf_at = ?
                WHERE id = ?
                """,
                ("系统自动下架：超过3天无商品", now, row["id"]),
            )
        conn.commit()
    conn.close()


@app.before_request
def before_request_tasks():
    auto_down_shelf_empty_stores()


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT UNIQUE,
            wx_openid TEXT UNIQUE,
            username TEXT,
            is_merchant INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS stores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            address TEXT,
            contact_phone TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            down_shelf_reason TEXT,
            down_shelf_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS dishes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT,
            image_url TEXT,
            tags TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT,
            is_available INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(store_id) REFERENCES stores(id)
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            total_price REAL NOT NULL,
            status TEXT NOT NULL,
            fulfillment_type TEXT NOT NULL DEFAULT 'delivery',
            contact_phone TEXT,
            delivery_address TEXT,
            note TEXT,
            merchant_cancel_reason TEXT,
            reminder_stage INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(store_id) REFERENCES stores(id)
        );

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            dish_id INTEGER,
            dish_name TEXT NOT NULL,
            dish_price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS merchant_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            store_name TEXT NOT NULL,
            description TEXT,
            address TEXT,
            contact_phone TEXT,
            qualification_urls TEXT,
            qualification_note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            contact_info TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT,
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );

        CREATE TABLE IF NOT EXISTS order_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            opinion TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(store_id) REFERENCES stores(id)
        );

        CREATE TABLE IF NOT EXISTS dish_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dish_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            opinion TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(dish_id) REFERENCES dishes(id),
            FOREIGN KEY(order_id) REFERENCES orders(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )

    # schema migrations for older databases
    ensure_column(cur, "dishes", "tags", "TEXT")
    ensure_column(cur, "dishes", "status", "TEXT NOT NULL DEFAULT 'approved'")
    ensure_column(cur, "dishes", "review_note", "TEXT")
    ensure_column(cur, "orders", "fulfillment_type", "TEXT NOT NULL DEFAULT 'delivery'")
    ensure_column(cur, "orders", "merchant_cancel_reason", "TEXT")
    ensure_column(cur, "orders", "reminder_stage", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(cur, "stores", "is_active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(cur, "stores", "down_shelf_reason", "TEXT")
    ensure_column(cur, "stores", "down_shelf_at", "TEXT")
    ensure_column(cur, "merchant_applications", "qualification_urls", "TEXT")
    ensure_column(cur, "merchant_applications", "qualification_note", "TEXT")
    ensure_column(cur, "support_tickets", "contact_info", "TEXT")

    cur.execute("UPDATE dishes SET status = 'approved' WHERE status IS NULL OR status = ''")
    cur.execute("UPDATE dishes SET is_available = 1 WHERE is_available IS NULL")
    cur.execute(
        "UPDATE orders SET fulfillment_type = 'delivery' WHERE fulfillment_type IS NULL OR fulfillment_type = ''"
    )
    cur.execute("UPDATE orders SET reminder_stage = 0 WHERE reminder_stage IS NULL")
    cur.execute("UPDATE orders SET status = ? WHERE status IS NULL OR status = ''", (ORDER_STATUS_NEW,))
    cur.execute("UPDATE orders SET status = ? WHERE status IN ('pending', '待接单')", (ORDER_STATUS_NEW,))
    cur.execute("UPDATE orders SET status = ? WHERE status IN ('accepted', '制作中')", (ORDER_STATUS_MAKING,))
    cur.execute("UPDATE orders SET status = ? WHERE status IN ('completed', '商家已完成')", (ORDER_STATUS_DONE,))
    cur.execute("UPDATE orders SET status = ? WHERE status IN ('cancelled', '商家取消接单')", (ORDER_STATUS_CANCELLED,))
    cur.execute(
        "UPDATE orders SET status = ? WHERE status IN ('user_cancelled', '用户取消订单')",
        (ORDER_STATUS_USER_CANCELLED,),
    )

    existing = cur.execute("SELECT COUNT(*) AS c FROM stores").fetchone()["c"]
    if existing == 0:
        now = now_str()
        cur.execute(
            "INSERT INTO users(phone, username, is_merchant, created_at) VALUES (?, ?, 1, ?)",
            ("13800000000", "演示商家", now),
        )
        user_id = cur.lastrowid
        cur.execute(
            """
            INSERT INTO stores(user_id, name, description, address, contact_phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                "暖胃小馆",
                "现炒家常菜，30分钟极速送达",
                "科技园一路 88 号",
                "13800000000",
                now,
            ),
        )
        store_id = cur.lastrowid
        seed_dishes = [
            ("招牌红烧肉饭", 26.0, "热销", "饭类,午餐", "https://picsum.photos/seed/meal1/480/320"),
            ("番茄牛腩面", 24.0, "面食", "汤面,推荐", "https://picsum.photos/seed/meal2/480/320"),
            ("香煎鸡胸沙拉", 22.0, "轻食", "减脂,低卡", "https://picsum.photos/seed/meal3/480/320"),
        ]
        cur.executemany(
            """
            INSERT INTO dishes(store_id, name, price, category, tags, image_url, status, is_available, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'approved', 1, ?)
            """,
            [(store_id, n, p, c, tags, img, now) for (n, p, c, tags, img) in seed_dishes],
        )

    conn.commit()
    conn.close()


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def is_platform_admin():
    return bool(session.get("platform_admin"))


def get_user_merchant_application(user_id):
    conn = get_db()
    app_row = conn.execute(
        "SELECT * FROM merchant_applications WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return app_row


def login_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("请先登录后再继续操作", "warning")
            return redirect(url_for("login", next=request.path))
        return view_fn(*args, **kwargs)

    return wrapper


def merchant_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            flash("请先登录", "warning")
            return redirect(url_for("login", next=request.path))
        if not user["is_merchant"]:
            app_row = get_user_merchant_application(user["id"])
            if app_row and app_row["status"] == "pending":
                flash("你的商家入驻申请正在审核中", "warning")
            else:
                flash("你当前不是商家账号，请先完成商家入驻并通过审核", "warning")
            return redirect(url_for("merchant_join"))
        return view_fn(*args, **kwargs)

    return wrapper


def platform_admin_required(view_fn):
    @wraps(view_fn)
    def wrapper(*args, **kwargs):
        if not is_platform_admin():
            flash("请先登录审核账号", "warning")
            return redirect(url_for("platform_login", next=request.path))
        return view_fn(*args, **kwargs)

    return wrapper


def get_cart():
    cart = session.get("cart")
    if not cart:
        return {"store_id": None, "items": {}}
    return cart


def set_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_item_count():
    cart = get_cart()
    return sum(int(v) for v in cart.get("items", {}).values())


def render_page(title, body_template, **context):
    inner_context = dict(context)
    inner_context.setdefault("current_user", current_user())
    inner_context.setdefault("is_platform_admin", is_platform_admin())
    inner_context.setdefault("order_status_text", order_status_text)
    body = render_template_string(body_template, **inner_context)
    return render_template_string(
        BASE_HTML,
        title=title,
        content=body,
        app_title=APP_TITLE,
        current_user=current_user(),
        cart_count=cart_item_count(),
        is_platform_admin=is_platform_admin(),
        order_status_text=order_status_text,
    )


def save_uploaded_image(upload_file):
    if not upload_file or not upload_file.filename:
        return None
    filename = secure_filename(upload_file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None
    final_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}{ext}"
    save_path = UPLOAD_DIR / final_name
    upload_file.save(save_path)
    return url_for("uploaded_file", filename=final_name)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "app": APP_TITLE, "time": now_str()})


@app.route("/")
def home():
    keyword = (request.args.get("q") or "").strip()
    conn = get_db()
    sql = f"""
        SELECT s.*,
               (SELECT COUNT(*) FROM dishes d
                WHERE d.store_id = s.id AND d.is_available = 1 AND d.status = 'approved') AS dish_count,
               (SELECT COUNT(*) FROM orders o
                WHERE o.store_id = s.id
                  AND o.status NOT IN ('{ORDER_STATUS_DONE}', '{ORDER_STATUS_CANCELLED}', '{ORDER_STATUS_USER_CANCELLED}')) AS active_order_count
        FROM stores s
        WHERE s.is_active = 1
    """
    params = []
    if keyword:
        sql += " AND (s.name LIKE ? OR s.description LIKE ? OR s.address LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like])
    sql += " ORDER BY s.id DESC"
    stores = conn.execute(sql, params).fetchall()
    conn.close()

    body = """
    <section class="hero">
      <h1>线上选店订餐</h1>
      <p>支持外卖配送 + 到店自提，有任何问题请留言</p>
    </section>

    <form class="card row" method="get" action="{{ url_for('home') }}" style="margin-bottom: 14px;">
      <input name="q" placeholder="搜索店铺/地址/关键词" value="{{ keyword }}" style="flex: 1; min-width: 220px;" />
      <button class="btn" type="submit">搜索店铺</button>
    </form>

    {% if stores %}
      <section class="grid">
        {% for store in stores %}
          <article class="card">
            <div class="row space-between">
              <h3>{{ store['name'] }}</h3>
              <span class="tag">在售 {{ store['dish_count'] }} 道</span>
            </div>
            <div class="muted">目前订单：{{ store['active_order_count'] }}</div>
            <div class="muted" style="margin-bottom: 8px;">{{ store['description'] or '这个店铺还没有填写简介' }}</div>
            <div class="muted">地址：{{ store['address'] or '-' }}</div>
            <div class="muted">联系电话：{{ store['contact_phone'] or '-' }}</div>
            <div class="row" style="margin-top: 12px;">
              <a class="btn" href="{{ url_for('store_detail', store_id=store['id']) }}">进入店铺点餐</a>
            </div>
          </article>
        {% endfor %}
      </section>
    {% else %}
      <div class="card">
        <h3>暂无店铺</h3>
        <p class="muted">你可以先登录后申请商家入驻，审核通过后即可开店。</p>
      </div>
    {% endif %}
    """
    return render_page("首页", body, stores=stores, keyword=keyword)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_type = request.form.get("login_type", "phone")
        next_url = request.args.get("next") or url_for("home")

        conn = get_db()
        cur = conn.cursor()

        if login_type == "wx":
            wx_openid = (request.form.get("wx_openid") or "").strip()
            if not wx_openid:
                flash("请输入微信标识（演示可随便填）", "error")
                conn.close()
                return redirect(url_for("login", next=next_url))

            user = cur.execute("SELECT * FROM users WHERE wx_openid = ?", (wx_openid,)).fetchone()
            if not user:
                phone = f"wx_{wx_openid[-6:].rjust(6, '0')}"
                cur.execute(
                    "INSERT INTO users(phone, wx_openid, username, created_at) VALUES (?, ?, ?, ?)",
                    (phone, wx_openid, f"微信用户{wx_openid[-4:]}", now_str()),
                )
                conn.commit()
                user_id = cur.lastrowid
            else:
                user_id = user["id"]

            session["user_id"] = user_id
            flash("微信快捷登录成功", "success")
            conn.close()
            return redirect(next_url)

        phone = (request.form.get("phone") or "").strip()
        code = (request.form.get("code") or "").strip()
        if len(phone) < 6:
            flash("请输入正确的手机号", "error")
            conn.close()
            return redirect(url_for("login", next=next_url))
        if code != "123456":
            flash("验证码错误，演示环境请使用 123456", "error")
            conn.close()
            return redirect(url_for("login", next=next_url))

        user = cur.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if not user:
            cur.execute(
                "INSERT INTO users(phone, username, created_at) VALUES (?, ?, ?)",
                (phone, f"用户{phone[-4:]}", now_str()),
            )
            conn.commit()
            user_id = cur.lastrowid
        else:
            user_id = user["id"]

        session["user_id"] = user_id
        conn.close()
        flash("登录成功", "success")
        return redirect(next_url)

    body = """
    <section class="hero">
      <h1>登录 / 注册</h1>
      <p>初代演示：手机号验证码固定为 <b>123456</b>，并提供微信快捷登录入口。</p>
    </section>

    <section class="grid" style="align-items: start;">
      <form method="post" class="card">
        <input type="hidden" name="login_type" value="phone" />
        <h3>手机号登录</h3>
        <div class="field">
          <label>手机号</label>
          <input name="phone" placeholder="例如 13800138000" required />
        </div>
        <div class="field">
          <label>验证码（演示固定码）</label>
          <input name="code" placeholder="请输入 123456" required />
        </div>
        <button class="btn" type="submit">登录 / 自动注册</button>
      </form>

      <form method="post" class="card">
        <input type="hidden" name="login_type" value="wx" />
        <h3>微信快捷登录（演示）</h3>
        <div class="field">
          <label>微信唯一标识</label>
          <input name="wx_openid" placeholder="例如 wx_demo_001" required />
        </div>
        <p class="muted">生产环境中替换为微信授权接口回调数据。</p>
        <button class="btn ok" type="submit">一键微信登录</button>
      </form>

      <section class="card">
        <h3>平台审核登录</h3>
        <p class="muted">审核账号单独入口，用于审核商家入驻、菜品发布和用户留言。</p>
        <a class="btn secondary" href="{{ url_for('platform_login') }}">进入审核登录页</a>
      </section>
    </section>
    """
    return render_page("登录", body)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("cart", None)
    flash("已退出登录", "success")
    return redirect(url_for("home"))


@app.route("/platform/login", methods=["GET", "POST"])
def platform_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        next_url = request.args.get("next") or url_for("platform_review")
        if username == PLATFORM_REVIEW_USERNAME and password == PLATFORM_REVIEW_PASSWORD:
            session["platform_admin"] = True
            flash("审核账号登录成功", "success")
            return redirect(next_url)
        flash("审核账号或密码错误", "error")
        return redirect(url_for("platform_login"))

    body = """
    <section class="hero">
      <h1>审核账号登录</h1>
      <p>仅平台审核人员使用，用于处理入驻、菜品和用户支持留言。</p>
    </section>

    <form method="post" class="card" style="max-width: 540px; margin: 0 auto;">
      <div class="field">
        <label>审核账号</label>
        <input name="username" required />
      </div>
      <div class="field">
        <label>审核密码</label>
        <input type="password" name="password" required />
      </div>
      <button class="btn" type="submit">登录审核后台</button>
    </form>
    """
    return render_page("审核登录", body)


@app.route("/platform/logout")
def platform_logout():
    session.pop("platform_admin", None)
    flash("已退出审核账号", "success")
    return redirect(url_for("home"))


@app.route("/platform/review")
@platform_admin_required
def platform_review():
    conn = get_db()
    merchant_apps = conn.execute(
        """
        SELECT a.*, u.phone AS user_phone
        FROM merchant_applications a
        JOIN users u ON u.id = a.user_id
        ORDER BY
            CASE a.status WHEN 'pending' THEN 0 ELSE 1 END,
            a.id DESC
        """
    ).fetchall()

    dishes = conn.execute(
        """
        SELECT d.*, s.name AS store_name, u.phone AS merchant_phone
        FROM dishes d
        JOIN stores s ON s.id = d.store_id
        JOIN users u ON u.id = s.user_id
        ORDER BY
            CASE d.status WHEN 'pending' THEN 0 ELSE 1 END,
            d.id DESC
        """
    ).fetchall()

    tickets = conn.execute(
        """
        SELECT t.*, u.phone AS user_phone, s.name AS store_name
        FROM support_tickets t
        JOIN users u ON u.id = t.user_id
        JOIN orders o ON o.id = t.order_id
        JOIN stores s ON s.id = o.store_id
        ORDER BY
            CASE t.status WHEN 'pending' THEN 0 ELSE 1 END,
            t.id DESC
        """
    ).fetchall()

    stores = conn.execute(
        """
        SELECT s.*, u.phone AS owner_phone
        FROM stores s
        JOIN users u ON u.id = s.user_id
        ORDER BY s.id DESC
        """
    ).fetchall()
    conn.close()

    merchant_qualifications = {
        row["id"]: parse_json_list(row["qualification_urls"]) for row in merchant_apps
    }

    body = """
    <section class="hero">
      <h1>平台审核后台</h1>
      <p>审核商家入驻、菜品发布、用户留言。当前登录账号：{{ review_user }}</p>
    </section>

    <section style="display:grid; gap: 14px;">
      <article class="card">
        <h3>门店上下架管理</h3>
        {% if stores %}
          <table class="table">
            <thead>
              <tr>
                <th>ID</th><th>店铺</th><th>商家</th><th>状态</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {% for s in stores %}
                <tr>
                  <td>#{{ s['id'] }}</td>
                  <td>{{ s['name'] }}</td>
                  <td>{{ s['owner_phone'] }}</td>
                  <td>
                    {% if s['is_active'] %}
                      <span class="tag approved">上架中</span>
                    {% else %}
                      <span class="tag rejected">已下架</span>
                      <div class="muted">{{ s['down_shelf_reason'] or '-' }}</div>
                    {% endif %}
                  </td>
                  <td>
                    <form method="post" action="{{ url_for('platform_store_status', store_id=s['id']) }}" class="row">
                      {% if s['is_active'] %}
                        <input name="reason" placeholder="下架原因（可选）" style="max-width: 220px;" />
                        <button class="btn danger" type="submit" name="action" value="down">平台下架</button>
                      {% else %}
                        <button class="btn ok" type="submit" name="action" value="up">恢复上架</button>
                      {% endif %}
                    </form>
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <p class="muted">暂无门店。</p>
        {% endif %}
      </article>

      <article class="card">
        <h3>商家入驻审核</h3>
        {% if merchant_apps %}
          <table class="table">
            <thead>
              <tr>
                <th>ID</th><th>用户</th><th>店名</th><th>状态</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {% for row in merchant_apps %}
                <tr>
                  <td>#{{ row['id'] }}</td>
                  <td>{{ row['user_phone'] }}</td>
                  <td>{{ row['store_name'] }}</td>
                  <td>
                    <span class="tag {{ row['status'] }}">{{ row['status'] }}</span>
                  </td>
                  <td>
                    {% if row['status'] == 'pending' %}
                      <form method="post" action="{{ url_for('review_merchant_application', app_id=row['id']) }}" class="row">
                        <input name="review_note" placeholder="审核备注（可选）" style="max-width: 220px;" />
                        <button class="btn ok" type="submit" name="decision" value="approve">通过</button>
                        <button class="btn danger" type="submit" name="decision" value="reject">驳回</button>
                      </form>
                    {% else %}
                      <div class="muted">{{ row['review_note'] or '-' }}</div>
                      <form method="post" action="{{ url_for('platform_delete_record', kind='merchant', record_id=row['id']) }}">
                        <button class="btn secondary" type="submit">删除记录</button>
                      </form>
                    {% endif %}
                  </td>
                </tr>
                <tr>
                  <td colspan="5" class="muted">
                    资质备注：{{ row['qualification_note'] or '未填写' }}<br />
                    {% set imgs = merchant_qualifications.get(row['id'], []) %}
                    资质图片：
                    {% if imgs %}
                      {% for img in imgs %}
                        <a href="{{ img }}" target="_blank">查看{{ loop.index }}</a>{% if not loop.last %} | {% endif %}
                      {% endfor %}
                    {% else %}
                      无
                    {% endif %}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
          <form method="post" action="{{ url_for('platform_batch_delete_records') }}" class="row" style="margin-top: 10px;">
            <input type="hidden" name="kind" value="merchant" />
            <input name="ids" placeholder="批量删除ID，逗号分隔（仅已处理）" style="flex:1; min-width:260px;" />
            <button class="btn secondary" type="submit">批量删除</button>
          </form>
        {% else %}
          <p class="muted">暂无入驻申请。</p>
        {% endif %}
      </article>

      <article class="card">
        <h3>菜品审核</h3>
        {% if dishes %}
          <table class="table">
            <thead>
              <tr>
                <th>ID</th><th>店铺</th><th>菜品</th><th>状态</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {% for row in dishes %}
                <tr>
                  <td>#{{ row['id'] }}</td>
                  <td>{{ row['store_name'] }}</td>
                  <td>{{ row['name'] }}（¥{{ '%.2f'|format(row['price']) }}）</td>
                  <td><span class="tag {{ row['status'] }}">{{ row['status'] }}</span></td>
                  <td>
                    {% if row['status'] == 'pending' %}
                      <form method="post" action="{{ url_for('review_dish', dish_id=row['id']) }}" class="row">
                        <input name="review_note" placeholder="审核备注（可选）" style="max-width: 220px;" />
                        <button class="btn ok" type="submit" name="decision" value="approve">通过</button>
                        <button class="btn danger" type="submit" name="decision" value="reject">驳回</button>
                      </form>
                    {% else %}
                      <div class="muted">{{ row['review_note'] or '-' }}</div>
                      <form method="post" action="{{ url_for('platform_delete_record', kind='dish', record_id=row['id']) }}">
                        <button class="btn secondary" type="submit">删除记录</button>
                      </form>
                    {% endif %}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
          <form method="post" action="{{ url_for('platform_batch_delete_records') }}" class="row" style="margin-top: 10px;">
            <input type="hidden" name="kind" value="dish" />
            <input name="ids" placeholder="批量删除ID，逗号分隔（仅已处理）" style="flex:1; min-width:260px;" />
            <button class="btn secondary" type="submit">批量删除</button>
          </form>
        {% else %}
          <p class="muted">暂无菜品记录。</p>
        {% endif %}
      </article>

      <article class="card">
        <h3>用户支持留言审核</h3>
        {% if tickets %}
          <table class="table">
            <thead>
              <tr>
                <th>ID</th><th>订单</th><th>用户</th><th>状态</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              {% for row in tickets %}
                <tr>
                  <td>#{{ row['id'] }}</td>
                  <td>#{{ row['order_id'] }} / {{ row['store_name'] }}</td>
                  <td>{{ row['user_phone'] }}</td>
                  <td><span class="tag {{ row['status'] }}">{{ row['status'] }}</span></td>
                  <td>
                    {% if row['status'] == 'pending' %}
                      <form method="post" action="{{ url_for('review_support_ticket', ticket_id=row['id']) }}" class="row">
                        <input name="review_note" placeholder="审核备注（可选）" style="max-width: 220px;" />
                        <button class="btn ok" type="submit" name="decision" value="approve">通过</button>
                        <button class="btn danger" type="submit" name="decision" value="reject">驳回</button>
                      </form>
                    {% else %}
                      <div class="muted">{{ row['review_note'] or '-' }}</div>
                      <form method="post" action="{{ url_for('platform_delete_record', kind='support', record_id=row['id']) }}">
                        <button class="btn secondary" type="submit">删除记录</button>
                      </form>
                    {% endif %}
                  </td>
                </tr>
                <tr>
                  <td colspan="5" class="muted">
                    留言：{{ row['message'] }}<br />
                    联系方式：{{ row['contact_info'] or '未填写' }}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
          <form method="post" action="{{ url_for('platform_batch_delete_records') }}" class="row" style="margin-top: 10px;">
            <input type="hidden" name="kind" value="support" />
            <input name="ids" placeholder="批量删除ID，逗号分隔（仅已处理）" style="flex:1; min-width:260px;" />
            <button class="btn secondary" type="submit">批量删除</button>
          </form>
        {% else %}
          <p class="muted">暂无用户留言。</p>
        {% endif %}
      </article>
    </section>
    """
    return render_page(
        "审核后台",
        body,
        merchant_apps=merchant_apps,
        dishes=dishes,
        tickets=tickets,
        stores=stores,
        merchant_qualifications=merchant_qualifications,
        review_user=PLATFORM_REVIEW_USERNAME,
    )


@app.route("/platform/review/merchant/<int:app_id>", methods=["POST"])
@platform_admin_required
def review_merchant_application(app_id):
    decision = (request.form.get("decision") or "").strip()
    review_note = (request.form.get("review_note") or "").strip()
    if decision not in {"approve", "reject"}:
        flash("无效审核操作", "error")
        return redirect(url_for("platform_review"))

    conn = get_db()
    app_row = conn.execute(
        "SELECT * FROM merchant_applications WHERE id = ?",
        (app_id,),
    ).fetchone()
    if not app_row:
        conn.close()
        flash("申请不存在", "error")
        return redirect(url_for("platform_review"))

    status = "approved" if decision == "approve" else "rejected"
    conn.execute(
        """
        UPDATE merchant_applications
        SET status = ?, review_note = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (status, review_note, now_str(), app_id),
    )

    if decision == "approve":
        existing_store = conn.execute(
            "SELECT * FROM stores WHERE user_id = ?",
            (app_row["user_id"],),
        ).fetchone()
        if existing_store:
            conn.execute(
                """
                UPDATE stores
                SET name = ?, description = ?, address = ?, contact_phone = ?
                WHERE id = ?
                """,
                (
                    app_row["store_name"],
                    app_row["description"],
                    app_row["address"],
                    app_row["contact_phone"],
                    existing_store["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO stores(user_id, name, description, address, contact_phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    app_row["user_id"],
                    app_row["store_name"],
                    app_row["description"],
                    app_row["address"],
                    app_row["contact_phone"],
                    now_str(),
                ),
            )
        conn.execute("UPDATE users SET is_merchant = 1 WHERE id = ?", (app_row["user_id"],))
    else:
        conn.execute("UPDATE users SET is_merchant = 0 WHERE id = ?", (app_row["user_id"],))

    conn.commit()
    conn.close()
    flash("商家申请审核完成", "success")
    return redirect(url_for("platform_review"))


@app.route("/platform/review/dish/<int:dish_id>", methods=["POST"])
@platform_admin_required
def review_dish(dish_id):
    decision = (request.form.get("decision") or "").strip()
    review_note = (request.form.get("review_note") or "").strip()
    if decision not in {"approve", "reject"}:
        flash("无效审核操作", "error")
        return redirect(url_for("platform_review"))

    conn = get_db()
    dish = conn.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,)).fetchone()
    if not dish:
        conn.close()
        flash("菜品不存在", "error")
        return redirect(url_for("platform_review"))

    if decision == "approve":
        conn.execute(
            "UPDATE dishes SET status = 'approved', review_note = ?, is_available = 1 WHERE id = ?",
            (review_note, dish_id),
        )
    else:
        conn.execute(
            "UPDATE dishes SET status = 'rejected', review_note = ?, is_available = 0 WHERE id = ?",
            (review_note, dish_id),
        )
    conn.commit()
    conn.close()
    flash("菜品审核完成", "success")
    return redirect(url_for("platform_review"))


@app.route("/platform/review/support/<int:ticket_id>", methods=["POST"])
@platform_admin_required
def review_support_ticket(ticket_id):
    decision = (request.form.get("decision") or "").strip()
    review_note = (request.form.get("review_note") or "").strip()
    if decision not in {"approve", "reject"}:
        flash("无效审核操作", "error")
        return redirect(url_for("platform_review"))

    status = "approved" if decision == "approve" else "rejected"
    conn = get_db()
    conn.execute(
        """
        UPDATE support_tickets
        SET status = ?, review_note = ?, reviewed_at = ?
        WHERE id = ?
        """,
        (status, review_note, now_str(), ticket_id),
    )
    conn.commit()
    conn.close()
    flash("用户留言审核完成", "success")
    return redirect(url_for("platform_review"))


@app.route("/platform/store/<int:store_id>/status", methods=["POST"])
@platform_admin_required
def platform_store_status(store_id):
    action = (request.form.get("action") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if action not in {"down", "up"}:
        flash("无效操作", "error")
        return redirect(url_for("platform_review"))

    conn = get_db()
    store = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    if not store:
        conn.close()
        flash("门店不存在", "error")
        return redirect(url_for("platform_review"))

    if action == "down":
        conn.execute(
            """
            UPDATE stores
            SET is_active = 0, down_shelf_reason = ?, down_shelf_at = ?
            WHERE id = ?
            """,
            (reason or "平台手动下架", now_str(), store_id),
        )
        flash("门店已下架", "success")
    else:
        conn.execute(
            "UPDATE stores SET is_active = 1, down_shelf_reason = NULL, down_shelf_at = NULL WHERE id = ?",
            (store_id,),
        )
        flash("门店已恢复上架", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("platform_review"))


def delete_review_record(conn, kind, record_id):
    if kind == "merchant":
        row = conn.execute("SELECT status FROM merchant_applications WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return False, "商家申请不存在"
        if row["status"] == "pending":
            return False, "待审核商家申请不能删除"
        conn.execute("DELETE FROM merchant_applications WHERE id = ?", (record_id,))
        return True, ""

    if kind == "dish":
        row = conn.execute("SELECT status FROM dishes WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return False, "菜品记录不存在"
        if row["status"] == "pending":
            return False, "待审核菜品不能删除"
        conn.execute("DELETE FROM dish_feedback WHERE dish_id = ?", (record_id,))
        conn.execute("DELETE FROM dishes WHERE id = ?", (record_id,))
        return True, ""

    if kind == "support":
        row = conn.execute("SELECT status FROM support_tickets WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return False, "留言记录不存在"
        if row["status"] == "pending":
            return False, "待审核留言不能删除"
        conn.execute("DELETE FROM support_tickets WHERE id = ?", (record_id,))
        return True, ""

    return False, "未知类型"


@app.route("/platform/review/delete/<kind>/<int:record_id>", methods=["POST"])
@platform_admin_required
def platform_delete_record(kind, record_id):
    if kind not in {"merchant", "dish", "support"}:
        flash("无效类型", "error")
        return redirect(url_for("platform_review"))
    conn = get_db()
    ok, msg = delete_review_record(conn, kind, record_id)
    if ok:
        conn.commit()
        flash("记录已删除", "success")
    else:
        flash(msg, "warning")
    conn.close()
    return redirect(url_for("platform_review"))


@app.route("/platform/review/batch-delete", methods=["POST"])
@platform_admin_required
def platform_batch_delete_records():
    kind = (request.form.get("kind") or "").strip()
    ids_text = (request.form.get("ids") or "").strip()
    if kind not in {"merchant", "dish", "support"}:
        flash("无效类型", "error")
        return redirect(url_for("platform_review"))
    if not ids_text:
        flash("请填写要删除的ID列表", "warning")
        return redirect(url_for("platform_review"))

    ids = []
    for p in ids_text.replace("，", ",").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            ids.append(int(p))
        except ValueError:
            pass
    if not ids:
        flash("ID格式不正确", "error")
        return redirect(url_for("platform_review"))

    conn = get_db()
    ok_count = 0
    for rid in ids:
        ok, _ = delete_review_record(conn, kind, rid)
        if ok:
            ok_count += 1
    conn.commit()
    conn.close()
    flash(f"批量删除完成，成功 {ok_count} 条", "success")
    return redirect(url_for("platform_review"))


@app.route("/merchant/join", methods=["GET", "POST"])
@login_required
def merchant_join():
    user = current_user()
    conn = get_db()
    existing_store = conn.execute("SELECT * FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    app_row = conn.execute(
        "SELECT * FROM merchant_applications WHERE user_id = ?",
        (user["id"],),
    ).fetchone()
    app_qualification_urls = parse_json_list(app_row["qualification_urls"]) if app_row else []

    if request.method == "POST":
        store_name = (request.form.get("store_name") or "").strip()
        description = (request.form.get("description") or "").strip()
        address = (request.form.get("address") or "").strip()
        contact_phone = (request.form.get("contact_phone") or "").strip()
        qualification_note = (request.form.get("qualification_note") or "").strip()
        qualification_files = request.files.getlist("qualification_files")

        if not store_name:
            conn.close()
            flash("店铺名称不能为空", "error")
            return redirect(url_for("merchant_join"))

        new_qualification_urls = []
        for upload_file in qualification_files:
            if not upload_file or not upload_file.filename:
                continue
            saved_url = save_uploaded_image(upload_file)
            if not saved_url:
                conn.close()
                flash("资质图片格式不支持，仅支持 png/jpg/jpeg/gif/webp", "error")
                return redirect(url_for("merchant_join"))
            new_qualification_urls.append(saved_url)

        if user["is_merchant"] and existing_store:
            conn.execute(
                """
                UPDATE stores
                SET name = ?, description = ?, address = ?, contact_phone = ?
                WHERE id = ?
                """,
                (store_name, description, address, contact_phone, existing_store["id"]),
            )
            conn.commit()
            conn.close()
            flash("店铺信息已更新", "success")
            return redirect(url_for("merchant_dashboard"))

        merged_qualification_urls = app_qualification_urls + new_qualification_urls
        if merged_qualification_urls:
            merged_qualification_urls = list(dict.fromkeys(merged_qualification_urls))

        if app_row:
            conn.execute(
                """
                UPDATE merchant_applications
                SET store_name = ?, description = ?, address = ?, contact_phone = ?,
                    qualification_urls = ?, qualification_note = ?,
                    status = 'pending', review_note = NULL, created_at = ?, reviewed_at = NULL
                WHERE user_id = ?
                """,
                (
                    store_name,
                    description,
                    address,
                    contact_phone,
                    dump_json_list(merged_qualification_urls),
                    qualification_note,
                    now_str(),
                    user["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO merchant_applications(
                    user_id, store_name, description, address, contact_phone,
                    qualification_urls, qualification_note, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    user["id"],
                    store_name,
                    description,
                    address,
                    contact_phone,
                    dump_json_list(merged_qualification_urls),
                    qualification_note,
                    now_str(),
                ),
            )
        conn.commit()
        conn.close()
        flash("入驻申请已提交，等待平台审核", "success")
        return redirect(url_for("merchant_join"))

    body = """
    <section class="hero">
      <h1>商家入驻</h1>
      <p>提交后会进入平台审核，审核通过后才可以进入商家后台发布菜品。</p>
    </section>

    {% if app_row %}
      <div class="card" style="margin-bottom:12px;">
        <div class="row space-between">
          <strong>当前申请状态</strong>
          <span class="tag {{ app_row['status'] }}">{{ app_row['status'] }}</span>
        </div>
        <div class="muted" style="margin-top:6px;">审核备注：{{ app_row['review_note'] or '暂无' }}</div>
      </div>
    {% endif %}

    {% if current_user['is_merchant'] %}
      <div class="notice" style="margin-bottom:12px;">你已通过商家审核，提交将直接更新店铺资料。</div>
    {% endif %}

    <form method="post" class="card" style="max-width: 680px; margin: 0 auto;" enctype="multipart/form-data">
      <div class="field">
        <label>店铺名称</label>
        <input name="store_name" value="{{ pref_name }}" placeholder="例如：江南家常菜" required />
      </div>
      <div class="field">
        <label>店铺简介</label>
        <textarea name="description" rows="3" placeholder="一句话介绍你的店铺特色">{{ pref_desc }}</textarea>
      </div>
      <div class="field">
        <label>地址</label>
        <input name="address" value="{{ pref_addr }}" placeholder="例如：浦东新区 XX 路 XX 号" />
      </div>
      <div class="field">
        <label>联系电话</label>
        <div class="muted" style="margin-bottom:6px;">后续会进行审核回访，请确认手机号可用</div>
        <input name="contact_phone" value="{{ pref_phone }}" />
      </div>
      {% if not current_user['is_merchant'] %}
        <div class="field">
          <label>店铺资质上传（可选，可多张）</label>
          <div class="muted" style="margin-bottom:6px;">上传有效资质更快成功入驻</div>
          <input type="file" name="qualification_files" multiple accept=".png,.jpg,.jpeg,.gif,.webp" />
        </div>
        <div class="field">
          <label>资质备注（可选）</label>
          <textarea name="qualification_note" rows="2" placeholder="例如：营业执照、食品经营许可证已上传">{{ pref_qualification_note }}</textarea>
        </div>
        {% if app_qualification_urls %}
          <div class="field">
            <label>已上传资质</label>
            <div class="row">
              {% for q in app_qualification_urls %}
                <a class="pill" href="{{ q }}" target="_blank">资质图{{ loop.index }}</a>
              {% endfor %}
            </div>
          </div>
        {% endif %}
      {% endif %}
      <button class="btn" type="submit">{{ '保存店铺信息' if current_user['is_merchant'] else '提交入驻审核' }}</button>
    </form>
    """
    html = render_page(
        "商家入驻",
        body,
        app_row=app_row,
        current_user=user,
        pref_name=(existing_store["name"] if existing_store else (app_row["store_name"] if app_row else "")),
        pref_desc=(existing_store["description"] if existing_store else (app_row["description"] if app_row else "")),
        pref_addr=(existing_store["address"] if existing_store else (app_row["address"] if app_row else "")),
        pref_phone=(
            (existing_store["contact_phone"] if existing_store else (app_row["contact_phone"] if app_row else ""))
            or user["phone"]
        ),
        pref_qualification_note=(app_row["qualification_note"] if app_row else ""),
        app_qualification_urls=app_qualification_urls,
    )
    conn.close()
    return html


@app.route("/merchant/dashboard")
@merchant_required
def merchant_dashboard():
    user = current_user()
    conn = get_db()
    store = conn.execute("SELECT * FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("未找到店铺，请联系平台处理", "error")
        return redirect(url_for("merchant_join"))

    dishes = conn.execute(
        "SELECT * FROM dishes WHERE store_id = ? ORDER BY id DESC",
        (store["id"],),
    ).fetchall()
    dish_ids = [d["id"] for d in dishes]
    feedback_meta = {}
    if dish_ids:
        placeholders = ",".join("?" for _ in dish_ids)
        feedback_rows = conn.execute(
            f"""
            SELECT dish_id, COUNT(*) AS c, AVG(stars) AS avg_stars
            FROM dish_feedback
            WHERE dish_id IN ({placeholders})
            GROUP BY dish_id
            """,
            dish_ids,
        ).fetchall()
        for r in feedback_rows:
            feedback_meta[r["dish_id"]] = {
                "count": r["c"],
                "avg_stars": round(float(r["avg_stars"]), 2) if r["avg_stars"] is not None else 0,
            }
    conn.close()

    body = """
    <section class="hero">
      <h1>商家后台</h1>
      <p>{{ store['name'] }} | 新菜品发布后进入审核，通过后自动上架。</p>
    </section>

    <section class="grid" style="grid-template-columns: 1.15fr 1.8fr;">
      <form class="card" method="post" action="{{ url_for('merchant_add_dish') }}" enctype="multipart/form-data">
        <h3>发布新菜品</h3>
        <div class="field">
          <label>菜品名称</label>
          <input name="name" placeholder="例如：椒盐鸡翅" required />
        </div>
        <div class="field">
          <label>价格（元）</label>
          <input name="price" type="number" min="0" step="0.01" placeholder="例如：28.00" required />
        </div>
        <div class="field">
          <label>分类</label>
          <input name="category" placeholder="例如：热销 / 主食 / 小吃" />
        </div>
        <div class="field">
          <label>备注标签（可输入多个，逗号分隔）</label>
          <input name="tags" placeholder="例如：招牌,微辣,推荐" />
        </div>
        <div class="field">
          <label>图片上传（优先）</label>
          <input type="file" name="image_file" accept=".png,.jpg,.jpeg,.gif,.webp" />
        </div>
        <button class="btn" type="submit">提交菜品审核</button>
      </form>

      <section class="card">
        <div class="row space-between" style="margin-bottom: 8px;">
          <h3 style="margin: 0;">菜品列表</h3>
          <a class="pill" href="{{ url_for('store_detail', store_id=store['id']) }}">预览店铺</a>
        </div>

        {% if dishes %}
          <form method="post" action="{{ url_for('merchant_batch_delete_dishes') }}" id="dish-batch-delete-form" class="row" style="margin-bottom: 10px;">
            <button class="btn secondary" type="submit">批量删除未上架/已下架记录</button>
            <span class="muted">仅删除未上架或已下架的菜品记录</span>
          </form>
          <table class="table">
            <thead>
              <tr>
                <th>批量</th>
                <th>菜品</th>
                <th>标签</th>
                <th>价格</th>
                <th>审核</th>
                <th>上/下架</th>
              </tr>
            </thead>
            <tbody>
              {% for dish in dishes %}
                <tr>
                  <td>
                    {% if dish['status'] != 'approved' or not dish['is_available'] %}
                      <input type="checkbox" name="dish_ids" value="{{ dish['id'] }}" form="dish-batch-delete-form" />
                    {% endif %}
                  </td>
                  <td>{{ dish['name'] }}<div class="muted">{{ dish['category'] or '-' }}</div></td>
                  <td>{{ dish['tags'] or '-' }}</td>
                  <td class="price">¥{{ '%.2f'|format(dish['price']) }}</td>
                  <td>
                    <span class="tag {{ dish['status'] }}">{{ dish['status'] }}</span>
                    <div class="muted">{{ dish['review_note'] or '-' }}</div>
                  </td>
                  <td>
                    {% if dish['status'] == 'approved' and dish['is_available'] %}
                      <div class="row">
                        <form method="post" action="{{ url_for('merchant_toggle_dish', dish_id=dish['id']) }}">
                          <button class="btn secondary" type="submit">下架</button>
                        </form>
                        <a class="pill" href="{{ url_for('merchant_dish_feedback', dish_id=dish['id']) }}">
                          评价 {{ feedback_meta.get(dish['id'], {}).get('count', 0) }}
                        </a>
                      </div>
                    {% elif dish['status'] == 'approved' and not dish['is_available'] %}
                      <div class="row">
                        <form method="post" action="{{ url_for('merchant_toggle_dish', dish_id=dish['id']) }}">
                          <button class="btn secondary" type="submit">上架</button>
                        </form>
                        <form method="post" action="{{ url_for('merchant_delete_dish', dish_id=dish['id']) }}">
                          <button class="btn secondary" type="submit">删除记录</button>
                        </form>
                      </div>
                    {% else %}
                      <div class="row">
                        <span class="muted">待审核后可操作</span>
                        <form method="post" action="{{ url_for('merchant_delete_dish', dish_id=dish['id']) }}">
                          <button class="btn secondary" type="submit">删除记录</button>
                        </form>
                      </div>
                    {% endif %}
                  </td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <p class="muted">你还没有发布菜品，先在左侧提交第一个商品吧。</p>
        {% endif %}
      </section>
    </section>
    """
    return render_page("商家后台", body, store=store, dishes=dishes, feedback_meta=feedback_meta)


@app.route("/merchant/dish/add", methods=["POST"])
@merchant_required
def merchant_add_dish():
    user = current_user()
    name = (request.form.get("name") or "").strip()
    category = (request.form.get("category") or "").strip()
    tags = (request.form.get("tags") or "").strip()

    try:
        price = float(request.form.get("price") or "")
    except ValueError:
        flash("价格格式不正确", "error")
        return redirect(url_for("merchant_dashboard"))

    if not name or price < 0:
        flash("请填写正确的菜品名称和价格", "error")
        return redirect(url_for("merchant_dashboard"))

    image_file = request.files.get("image_file")
    uploaded_url = save_uploaded_image(image_file)
    if image_file and image_file.filename and not uploaded_url:
        flash("图片格式不支持，仅支持 png/jpg/jpeg/gif/webp", "error")
        return redirect(url_for("merchant_dashboard"))

    conn = get_db()
    store = conn.execute("SELECT * FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("未找到店铺，请先完成商家入驻审核", "error")
        return redirect(url_for("merchant_join"))

    conn.execute(
        """
        INSERT INTO dishes(store_id, name, price, category, image_url, tags, status, review_note, is_available, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL, 0, ?)
        """,
        (store["id"], name, price, category, uploaded_url, tags, now_str()),
    )
    conn.commit()
    conn.close()
    flash("菜品已提交审核，审核通过后自动上架", "success")
    return redirect(url_for("merchant_dashboard"))


@app.route("/merchant/dish/<int:dish_id>/toggle", methods=["POST"])
@merchant_required
def merchant_toggle_dish(dish_id):
    user = current_user()
    conn = get_db()
    dish = conn.execute(
        """
        SELECT d.* FROM dishes d
        JOIN stores s ON s.id = d.store_id
        WHERE d.id = ? AND s.user_id = ?
        """,
        (dish_id, user["id"]),
    ).fetchone()
    if not dish:
        conn.close()
        flash("菜品不存在或没有权限", "error")
        return redirect(url_for("merchant_dashboard"))

    if dish["status"] != "approved":
        conn.close()
        flash("该菜品尚未审核通过，不能上/下架", "warning")
        return redirect(url_for("merchant_dashboard"))

    new_status = 0 if dish["is_available"] else 1
    conn.execute("UPDATE dishes SET is_available = ? WHERE id = ?", (new_status, dish_id))
    conn.commit()
    conn.close()
    flash("菜品上架状态已更新", "success")
    return redirect(url_for("merchant_dashboard"))


@app.route("/merchant/dish/<int:dish_id>/delete", methods=["POST"])
@merchant_required
def merchant_delete_dish(dish_id):
    user = current_user()
    conn = get_db()
    dish = conn.execute(
        """
        SELECT d.* FROM dishes d
        JOIN stores s ON s.id = d.store_id
        WHERE d.id = ? AND s.user_id = ?
        """,
        (dish_id, user["id"]),
    ).fetchone()
    if not dish:
        conn.close()
        flash("菜品不存在或没有权限", "error")
        return redirect(url_for("merchant_dashboard"))

    if dish["status"] == "approved" and dish["is_available"]:
        conn.close()
        flash("上架中菜品不能直接删除，请先下架", "warning")
        return redirect(url_for("merchant_dashboard"))

    conn.execute("DELETE FROM dish_feedback WHERE dish_id = ?", (dish_id,))
    conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
    conn.commit()
    conn.close()
    flash("菜品记录已删除", "success")
    return redirect(url_for("merchant_dashboard"))


@app.route("/merchant/dishes/batch-delete", methods=["POST"])
@merchant_required
def merchant_batch_delete_dishes():
    user = current_user()
    raw_ids = request.form.getlist("dish_ids")
    try:
        dish_ids = [int(x) for x in raw_ids]
    except ValueError:
        dish_ids = []
    if not dish_ids:
        flash("请先勾选要删除的菜品", "warning")
        return redirect(url_for("merchant_dashboard"))

    conn = get_db()
    store = conn.execute("SELECT id FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("门店不存在", "error")
        return redirect(url_for("merchant_join"))

    ok_count = 0
    for dish_id in dish_ids:
        dish = conn.execute(
            "SELECT * FROM dishes WHERE id = ? AND store_id = ?",
            (dish_id, store["id"]),
        ).fetchone()
        if not dish:
            continue
        if dish["status"] == "approved" and dish["is_available"]:
            continue
        conn.execute("DELETE FROM dish_feedback WHERE dish_id = ?", (dish_id,))
        conn.execute("DELETE FROM dishes WHERE id = ?", (dish_id,))
        ok_count += 1

    conn.commit()
    conn.close()
    flash(f"批量删除完成，成功 {ok_count} 条", "success")
    return redirect(url_for("merchant_dashboard"))


@app.route("/merchant/dish/<int:dish_id>/feedback")
@merchant_required
def merchant_dish_feedback(dish_id):
    user = current_user()
    conn = get_db()
    dish = conn.execute(
        """
        SELECT d.*, s.name AS store_name
        FROM dishes d
        JOIN stores s ON s.id = d.store_id
        WHERE d.id = ? AND s.user_id = ?
        """,
        (dish_id, user["id"]),
    ).fetchone()
    if not dish:
        conn.close()
        flash("菜品不存在或没有权限", "error")
        return redirect(url_for("merchant_dashboard"))

    feedbacks = conn.execute(
        """
        SELECT f.*, u.phone AS user_phone
        FROM dish_feedback f
        JOIN users u ON u.id = f.user_id
        WHERE f.dish_id = ?
        ORDER BY f.id DESC
        """,
        (dish_id,),
    ).fetchall()
    conn.close()

    body = """
    <section class="hero">
      <h1>菜品意见箱</h1>
      <p>{{ dish['store_name'] }} / {{ dish['name'] }}</p>
    </section>
    <div class="card" style="margin-bottom:12px;">
      <a class="btn secondary" href="{{ url_for('merchant_dashboard') }}">返回商家后台</a>
    </div>

    <section class="card">
      {% if feedbacks %}
        <table class="table">
          <thead>
            <tr><th>用户</th><th>评分</th><th>意见</th><th>时间</th></tr>
          </thead>
          <tbody>
            {% for f in feedbacks %}
              <tr>
                <td>{{ f['user_phone'] }}</td>
                <td>{{ f['stars'] }} 星</td>
                <td>{{ f['opinion'] or '-' }}</td>
                <td>{{ f['created_at'] }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <p class="muted">该菜品暂时没有用户评价。</p>
      {% endif %}
    </section>
    """
    return render_page("菜品意见箱", body, dish=dish, feedbacks=feedbacks)


@app.route("/store/<int:store_id>")
def store_detail(store_id):
    conn = get_db()
    store = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    if not store:
        conn.close()
        flash("店铺不存在", "error")
        return redirect(url_for("home"))
    if not store["is_active"]:
        conn.close()
        flash("该门店当前已下架，暂不可点餐", "warning")
        return redirect(url_for("home"))

    dishes = conn.execute(
        """
        SELECT * FROM dishes
        WHERE store_id = ? AND status = 'approved' AND is_available = 1
        ORDER BY id DESC
        """,
        (store_id,),
    ).fetchall()
    conn.close()

    body = """
    <section class="hero">
      <h1>{{ store['name'] }}</h1>
      <p>{{ store['description'] or '这家店铺暂时没有简介' }}</p>
      <p class="muted">地址：{{ store['address'] or '-' }} | 联系电话：{{ store['contact_phone'] or '-' }}</p>
    </section>

    {% if dishes %}
      <section class="grid">
        {% for dish in dishes %}
          <article class="card">
            {% if dish['image_url'] %}
              <img src="{{ dish['image_url'] }}" alt="{{ dish['name'] }}" style="width:100%;height:140px;object-fit:cover;border-radius:12px;border:1px solid #eef2fb;margin-bottom:10px;" />
            {% endif %}
            <h3>{{ dish['name'] }}</h3>
            <div class="row space-between">
              <div class="muted">{{ dish['category'] or '未分类' }}</div>
              <div class="price">¥{{ '%.2f'|format(dish['price']) }}</div>
            </div>
            {% if dish['tags'] %}
              <div class="muted" style="margin-top:8px;">标签：{{ dish['tags'] }}</div>
            {% endif %}
            <form method="post" action="{{ url_for('add_to_cart', dish_id=dish['id']) }}" class="row" style="margin-top: 12px;">
              <input name="quantity" type="number" min="1" value="1" style="max-width: 86px;" />
              <button class="btn" type="submit">加入购物车</button>
            </form>
          </article>
        {% endfor %}
      </section>
    {% else %}
      <div class="card"><p class="muted">这家店暂时还没有在售菜品。</p></div>
    {% endif %}
    """
    return render_page("店铺详情", body, store=store, dishes=dishes)


@app.route("/cart/add/<int:dish_id>", methods=["POST"])
def add_to_cart(dish_id):
    try:
        quantity = int(request.form.get("quantity") or "1")
    except ValueError:
        quantity = 1
    quantity = max(quantity, 1)

    conn = get_db()
    dish = conn.execute(
        "SELECT * FROM dishes WHERE id = ? AND status = 'approved' AND is_available = 1",
        (dish_id,),
    ).fetchone()
    conn.close()
    if not dish:
        flash("菜品不存在或暂不可购买", "error")
        return redirect(url_for("home"))

    cart = get_cart()
    store_id = dish["store_id"]
    if cart["store_id"] and cart["store_id"] != store_id:
        cart = {"store_id": store_id, "items": {}}
        flash("购物车已切换到新的店铺，原内容已清空", "warning")

    cart["store_id"] = store_id
    items = cart.get("items", {})
    key = str(dish_id)
    items[key] = int(items.get(key, 0)) + quantity
    cart["items"] = items
    set_cart(cart)
    flash("已加入购物车", "success")
    return redirect(url_for("store_detail", store_id=store_id))


@app.route("/cart")
def cart():
    cart_data = get_cart()
    item_map = cart_data.get("items", {})
    if not item_map:
        body = """
        <section class="hero">
          <h1>购物车</h1>
          <p>还没有添加商品，先去店铺逛逛吧。</p>
        </section>
        <div class="card"><a class="btn" href="{{ url_for('home') }}">去选店</a></div>
        """
        return render_page("购物车", body)

    ids = [int(x) for x in item_map.keys()]
    placeholders = ",".join("?" for _ in ids)
    conn = get_db()
    dishes = conn.execute(
        f"SELECT * FROM dishes WHERE id IN ({placeholders}) AND status = 'approved'",
        ids,
    ).fetchall()
    store = None
    if cart_data.get("store_id"):
        store = conn.execute("SELECT * FROM stores WHERE id = ?", (cart_data["store_id"],)).fetchone()
    conn.close()

    dish_by_id = {str(d["id"]): d for d in dishes}
    rows = []
    total = 0.0
    for dish_id, qty in item_map.items():
        dish = dish_by_id.get(dish_id)
        if not dish:
            continue
        qty = int(qty)
        subtotal = dish["price"] * qty
        total += subtotal
        rows.append({"dish": dish, "qty": qty, "subtotal": subtotal})

    body = """
    <section class="hero">
      <h1>购物车</h1>
      <p>{{ store['name'] if store else '未绑定店铺' }}</p>
    </section>

    <section class="card" style="margin-bottom: 12px;">
      <table class="table">
        <thead>
          <tr>
            <th>菜品</th>
            <th>单价</th>
            <th>数量</th>
            <th>小计</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {% for row in rows %}
            <tr>
              <td>{{ row['dish']['name'] }}</td>
              <td class="price">¥{{ '%.2f'|format(row['dish']['price']) }}</td>
              <td>{{ row['qty'] }}</td>
              <td>¥{{ '%.2f'|format(row['subtotal']) }}</td>
              <td>
                <form method="post" action="{{ url_for('cart_remove', dish_id=row['dish']['id']) }}">
                  <button class="btn secondary" type="submit">移除</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section class="card row space-between">
      <div>
        <div class="muted">合计</div>
        <div class="price" style="font-size: 24px;">¥{{ '%.2f'|format(total) }}</div>
      </div>
      <div class="row">
        <form method="post" action="{{ url_for('cart_clear') }}">
          <button class="btn secondary" type="submit">清空购物车</button>
        </form>
        <a class="btn" href="{{ url_for('checkout') }}">去结算</a>
      </div>
    </section>
    """
    return render_page("购物车", body, rows=rows, total=total, store=store)


@app.route("/cart/remove/<int:dish_id>", methods=["POST"])
def cart_remove(dish_id):
    cart = get_cart()
    items = cart.get("items", {})
    items.pop(str(dish_id), None)
    if not items:
        cart = {"store_id": None, "items": {}}
    else:
        cart["items"] = items
    set_cart(cart)
    flash("已从购物车移除", "success")
    return redirect(url_for("cart"))


@app.route("/cart/clear", methods=["POST"])
def cart_clear():
    set_cart({"store_id": None, "items": {}})
    flash("购物车已清空", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart_data = get_cart()
    item_map = cart_data.get("items", {})
    if not item_map:
        flash("购物车为空，无法结算", "warning")
        return redirect(url_for("cart"))

    ids = [int(x) for x in item_map.keys()]
    placeholders = ",".join("?" for _ in ids)
    conn = get_db()
    dishes = conn.execute(
        f"SELECT * FROM dishes WHERE id IN ({placeholders}) AND status = 'approved'",
        ids,
    ).fetchall()
    store = conn.execute("SELECT * FROM stores WHERE id = ?", (cart_data["store_id"],)).fetchone()
    if not store:
        conn.close()
        flash("店铺不存在，无法下单", "error")
        return redirect(url_for("cart"))
    if not store["is_active"]:
        conn.close()
        flash("该门店已下架，暂不能下单", "warning")
        return redirect(url_for("cart"))

    total = 0.0
    valid_rows = []
    for d in dishes:
        qty = int(item_map.get(str(d["id"]), 0))
        if qty <= 0:
            continue
        subtotal = d["price"] * qty
        total += subtotal
        valid_rows.append((d, qty, subtotal))

    if request.method == "POST":
        contact_phone = (request.form.get("contact_phone") or "").strip()
        delivery_address = (request.form.get("delivery_address") or "").strip()
        note = (request.form.get("note") or "").strip()
        fulfillment_type = (request.form.get("fulfillment_type") or "delivery").strip()
        if fulfillment_type not in {"delivery", "pickup"}:
            fulfillment_type = "delivery"

        if not contact_phone:
            conn.close()
            flash("请填写联系人手机号", "error")
            return redirect(url_for("checkout"))

        if fulfillment_type == "delivery" and not delivery_address:
            conn.close()
            flash("配送模式下请填写配送地址", "error")
            return redirect(url_for("checkout"))

        if fulfillment_type == "pickup":
            delivery_address = f"门店自提（{store['name']}）"

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orders(user_id, store_id, total_price, status, fulfillment_type, contact_phone, delivery_address, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                current_user()["id"],
                store["id"],
                total,
                ORDER_STATUS_NEW,
                fulfillment_type,
                contact_phone,
                delivery_address,
                note,
                now_str(),
            ),
        )
        order_id = cur.lastrowid

        for dish, qty, _ in valid_rows:
            cur.execute(
                "INSERT INTO order_items(order_id, dish_id, dish_name, dish_price, quantity) VALUES (?, ?, ?, ?, ?)",
                (order_id, dish["id"], dish["name"], dish["price"], qty),
            )

        conn.commit()
        conn.close()
        set_cart({"store_id": None, "items": {}})
        flash(f"下单成功，订单号 #{order_id}", "success")
        return redirect(url_for("my_orders"))

    conn.close()
    user = current_user()
    body = """
    <section class="hero">
      <h1>确认下单</h1>
      <p>{{ store['name'] }} | 共 {{ rows|length }} 款商品，合计 <span class="price">¥{{ '%.2f'|format(total) }}</span></p>
    </section>

    <div class="notice" style="margin-bottom:12px;">请仔细确认商品无误后再下单，有任何问题请留言！</div>

    <section class="grid" style="grid-template-columns: 1.5fr 1fr; align-items: start;">
      <section class="card">
        <h3>商品明细</h3>
        <table class="table">
          <thead>
            <tr><th>菜品</th><th>数量</th><th>小计</th></tr>
          </thead>
          <tbody>
            {% for dish, qty, subtotal in rows %}
              <tr>
                <td>{{ dish['name'] }}</td>
                <td>x {{ qty }}</td>
                <td>¥{{ '%.2f'|format(subtotal) }}</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </section>

      <form class="card" method="post" id="checkout-form">
        <h3>履约信息</h3>
        <div class="field">
          <label>取餐方式</label>
          <div class="row">
            <label style="margin:0;"><input type="radio" name="fulfillment_type" value="delivery" checked> 外卖配送</label>
            <label style="margin:0;"><input type="radio" name="fulfillment_type" value="pickup"> 到店自提</label>
          </div>
        </div>
        <div class="field">
          <label>联系人手机号</label>
          <input name="contact_phone" value="{{ user['phone'] }}" required />
        </div>
        <div class="field" id="address-field">
          <label>配送地址（自提可不填）</label>
          <textarea name="delivery_address" rows="3" placeholder="请填写详细地址"></textarea>
        </div>
        <div class="field">
          <label>备注（可选）</label>
          <textarea name="note" rows="2" placeholder="例如：少辣、不要香菜"></textarea>
        </div>
        <button class="btn" type="submit">确认下单</button>
      </form>
    </section>

    <script>
      (function () {
        const radios = document.querySelectorAll('input[name="fulfillment_type"]');
        const addressField = document.getElementById('address-field');
        function toggleAddress() {
          const mode = document.querySelector('input[name="fulfillment_type"]:checked')?.value;
          addressField.style.display = mode === 'pickup' ? 'none' : 'block';
        }
        radios.forEach(r => r.addEventListener('change', toggleAddress));
        toggleAddress();
      })();
    </script>
    """
    return render_page("结算", body, store=store, rows=valid_rows, total=total, user=user)


@app.route("/orders")
@login_required
def my_orders():
    user = current_user()
    conn = get_db()
    orders = conn.execute(
        """
        SELECT o.*, s.name AS store_name
        FROM orders o
        JOIN stores s ON s.id = o.store_id
        WHERE o.user_id = ?
        ORDER BY o.id DESC
        """,
        (user["id"],),
    ).fetchall()

    order_ids = [str(o["id"]) for o in orders]
    items_by_order = {}
    if order_ids:
        placeholders = ",".join("?" for _ in order_ids)
        items = conn.execute(
            f"SELECT * FROM order_items WHERE order_id IN ({placeholders}) ORDER BY id DESC",
            order_ids,
        ).fetchall()
        for item in items:
            items_by_order.setdefault(item["order_id"], []).append(item)

    reviews = conn.execute(
        "SELECT * FROM order_reviews WHERE user_id = ? ORDER BY id DESC",
        (user["id"],),
    ).fetchall()
    review_by_order = {r["order_id"]: r for r in reviews}
    conn.close()

    body = """
    <section class="hero">
      <h1>我的订单</h1>
      <p>可在下方进入“用户支持”留言，留言会提交到审核账号处理。</p>
    </section>
    <div class="card" style="margin-bottom:12px;">
      <a class="btn secondary" href="{{ url_for('support_center') }}">去用户支持留言</a>
    </div>

    {% if orders %}
      <section style="display:grid; gap: 12px;">
        {% for order in orders %}
          <article class="card">
            <div class="row space-between" style="margin-bottom: 8px;">
              <div>
                <h3 style="margin:0;">订单 #{{ order['id'] }}</h3>
                <div class="muted">{{ order['created_at'] }} | {{ order['store_name'] }}</div>
              </div>
              <div class="tag">{{ order_status_text(order['status']) }}</div>
            </div>

            <div class="row" style="margin-bottom:6px;">
              {% if order['fulfillment_type'] == 'pickup' %}
                <span class="tag pickup">到店自提</span>
              {% else %}
                <span class="tag">外卖配送</span>
              {% endif %}
              {% if order['status'] == ORDER_STATUS_NEW %}
                <form method="post" action="{{ url_for('consumer_cancel_order', order_id=order['id']) }}">
                  <button class="btn secondary" type="submit">取消订单</button>
                </form>
              {% endif %}
            </div>
            <div class="muted" style="margin-bottom: 6px;">地址：{{ order['delivery_address'] }}</div>
            <div class="muted" style="margin-bottom: 8px;">联系方式：{{ order['contact_phone'] }}</div>
            {% if order['status'] == ORDER_STATUS_CANCELLED %}
              <div class="muted" style="margin-bottom: 8px; color:#b24b1f;">
                商家取消原因：{{ order['merchant_cancel_reason'] or '无' }}
              </div>
            {% endif %}
            <div class="row" style="gap: 8px; flex-wrap: wrap;">
              {% for item in items_by_order.get(order['id'], []) %}
                <span class="tag" style="background:#fff4ec;color:#b24b1f;">{{ item['dish_name'] }} x{{ item['quantity'] }}</span>
              {% endfor %}
            </div>
            <div style="margin-top:10px;font-weight:700;">合计：<span class="price">¥{{ '%.2f'|format(order['total_price']) }}</span></div>

            {% if order['status'] == ORDER_STATUS_DONE %}
              {% if review_by_order.get(order['id']) %}
                <div class="notice" style="margin-top:10px;">
                  已评价：{{ review_by_order[order['id']]['stars'] }} 星<br />
                  菜品意见：{{ review_by_order[order['id']]['opinion'] or '无' }}
                </div>
              {% else %}
                <form method="post" action="{{ url_for('submit_order_review', order_id=order['id']) }}" class="card" style="margin-top:10px;">
                  <h3 style="font-size:16px; margin-bottom:8px;">订单评价</h3>
                  <div class="field">
                    <label>星级评分（1-5）</label>
                    <div class="stars">
                      <input id="star5_{{ order['id'] }}" type="radio" name="stars" value="5" checked />
                      <label for="star5_{{ order['id'] }}">★</label>
                      <input id="star4_{{ order['id'] }}" type="radio" name="stars" value="4" />
                      <label for="star4_{{ order['id'] }}">★</label>
                      <input id="star3_{{ order['id'] }}" type="radio" name="stars" value="3" />
                      <label for="star3_{{ order['id'] }}">★</label>
                      <input id="star2_{{ order['id'] }}" type="radio" name="stars" value="2" />
                      <label for="star2_{{ order['id'] }}">★</label>
                      <input id="star1_{{ order['id'] }}" type="radio" name="stars" value="1" />
                      <label for="star1_{{ order['id'] }}">★</label>
                    </div>
                  </div>
                  <div class="field">
                    <label>菜品意见</label>
                    <textarea name="opinion" rows="2" placeholder="请输入本次菜品体验意见"></textarea>
                  </div>
                  <button class="btn" type="submit">提交评价</button>
                </form>
              {% endif %}
            {% endif %}
          </article>
        {% endfor %}
      </section>
    {% else %}
      <div class="card"><p class="muted">你还没有下单记录。</p></div>
    {% endif %}
    """
    return render_page(
        "我的订单",
        body,
        orders=orders,
        items_by_order=items_by_order,
        ORDER_STATUS_CANCELLED=ORDER_STATUS_CANCELLED,
        ORDER_STATUS_NEW=ORDER_STATUS_NEW,
        ORDER_STATUS_DONE=ORDER_STATUS_DONE,
        review_by_order=review_by_order,
    )


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def consumer_cancel_order(order_id):
    user = current_user()
    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, user["id"]),
    ).fetchone()
    if not order:
        conn.close()
        flash("订单不存在", "error")
        return redirect(url_for("my_orders"))
    if order["status"] != ORDER_STATUS_NEW:
        conn.close()
        flash("只有待接单订单可取消", "warning")
        return redirect(url_for("my_orders"))
    conn.execute(
        "UPDATE orders SET status = ?, reminder_stage = 2 WHERE id = ?",
        (ORDER_STATUS_USER_CANCELLED, order_id),
    )
    conn.commit()
    conn.close()
    flash("订单已取消", "success")
    return redirect(url_for("my_orders"))


@app.route("/orders/<int:order_id>/review", methods=["POST"])
@login_required
def submit_order_review(order_id):
    user = current_user()
    opinion = (request.form.get("opinion") or "").strip()
    try:
        stars = int(request.form.get("stars") or "0")
    except ValueError:
        stars = 0
    if stars < 1 or stars > 5:
        flash("评分必须在1到5星之间", "error")
        return redirect(url_for("my_orders"))

    conn = get_db()
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, user["id"]),
    ).fetchone()
    if not order:
        conn.close()
        flash("订单不存在", "error")
        return redirect(url_for("my_orders"))
    if order["status"] != ORDER_STATUS_DONE:
        conn.close()
        flash("仅已完成订单可评价", "warning")
        return redirect(url_for("my_orders"))

    exists = conn.execute("SELECT id FROM order_reviews WHERE order_id = ?", (order_id,)).fetchone()
    if exists:
        conn.close()
        flash("该订单已评价", "warning")
        return redirect(url_for("my_orders"))

    conn.execute(
        """
        INSERT INTO order_reviews(order_id, user_id, store_id, stars, opinion, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (order_id, user["id"], order["store_id"], stars, opinion, now_str()),
    )

    items = conn.execute("SELECT dish_id FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
    for item in items:
        if item["dish_id"] is None:
            continue
        conn.execute(
            """
            INSERT INTO dish_feedback(dish_id, order_id, user_id, stars, opinion, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item["dish_id"], order_id, user["id"], stars, opinion, now_str()),
        )

    conn.commit()
    conn.close()
    flash("评价已提交，感谢反馈", "success")
    return redirect(url_for("my_orders"))


def apply_merchant_order_action(conn, store_id, order_id, action, reason):
    order = conn.execute(
        "SELECT * FROM orders WHERE id = ? AND store_id = ?",
        (order_id, store_id),
    ).fetchone()
    if not order:
        return False, "订单不存在或无权限"

    reason = (reason or "").strip()
    current_status = order["status"]

    if action == "accept":
        if current_status != ORDER_STATUS_NEW:
            return False, f"订单#{order_id} 当前不是待接单"
        conn.execute(
            """
            UPDATE orders
            SET status = ?, merchant_cancel_reason = NULL, reminder_stage = 2
            WHERE id = ?
            """,
            (ORDER_STATUS_MAKING, order_id),
        )
        return True, ""

    if action == "cancel":
        if current_status not in {ORDER_STATUS_NEW, ORDER_STATUS_MAKING}:
            return False, f"订单#{order_id} 当前状态不可取消"
        conn.execute(
            """
            UPDATE orders
            SET status = ?, merchant_cancel_reason = ?, reminder_stage = 2
            WHERE id = ?
            """,
            (ORDER_STATUS_CANCELLED, reason or None, order_id),
        )
        return True, ""

    if action == "complete":
        if current_status != ORDER_STATUS_MAKING:
            return False, f"订单#{order_id} 未处于制作中，不能完成"
        conn.execute(
            """
            UPDATE orders
            SET status = ?, merchant_cancel_reason = NULL, reminder_stage = 2
            WHERE id = ?
            """,
            (ORDER_STATUS_DONE, order_id),
        )
        return True, ""

    return False, "未知操作"


@app.route("/merchant/order/<int:order_id>/action", methods=["POST"])
@merchant_required
def merchant_order_action(order_id):
    action = (request.form.get("action") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if action not in {"accept", "cancel", "complete"}:
        flash("无效操作", "error")
        return redirect(url_for("merchant_orders"))

    conn = get_db()
    user = current_user()
    store = conn.execute("SELECT id FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("未找到门店", "error")
        return redirect(url_for("merchant_join"))

    ok, msg = apply_merchant_order_action(conn, store["id"], order_id, action, reason)
    if ok:
        conn.commit()
        flash("订单状态已更新", "success")
    else:
        flash(msg, "warning")
    conn.close()
    return redirect(url_for("merchant_orders"))


@app.route("/merchant/orders/batch-action", methods=["POST"])
@merchant_required
def merchant_orders_batch_action():
    action = (request.form.get("action") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    raw_ids = request.form.getlist("order_ids")
    try:
        order_ids = [int(x) for x in raw_ids]
    except ValueError:
        order_ids = []

    if action not in {"accept", "cancel", "complete"}:
        flash("请选择有效批量操作", "error")
        return redirect(url_for("merchant_orders"))
    if not order_ids:
        flash("请先勾选要处理的订单", "warning")
        return redirect(url_for("merchant_orders"))

    conn = get_db()
    user = current_user()
    store = conn.execute("SELECT id FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("未找到门店", "error")
        return redirect(url_for("merchant_join"))

    success_count = 0
    failed_messages = []
    for order_id in order_ids:
        ok, msg = apply_merchant_order_action(conn, store["id"], order_id, action, reason)
        if ok:
            success_count += 1
        else:
            failed_messages.append(msg)

    conn.commit()
    conn.close()

    if success_count:
        flash(f"批量处理完成，成功 {success_count} 单", "success")
    if failed_messages:
        flash("；".join(failed_messages[:3]), "warning")
    return redirect(url_for("merchant_orders"))


@app.route("/merchant/orders")
@merchant_required
def merchant_orders():
    user = current_user()
    conn = get_db()
    store = conn.execute("SELECT * FROM stores WHERE user_id = ?", (user["id"],)).fetchone()
    if not store:
        conn.close()
        flash("未找到店铺", "error")
        return redirect(url_for("merchant_join"))

    pending_orders = conn.execute(
        "SELECT id, created_at, reminder_stage FROM orders WHERE store_id = ? AND status = ?",
        (store["id"], ORDER_STATUS_NEW),
    ).fetchall()

    reminder_messages = []
    now_dt = datetime.now()
    for p in pending_orders:
        try:
            created_dt = datetime.strptime(p["created_at"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        elapsed_minutes = (now_dt - created_dt).total_seconds() / 60
        if elapsed_minutes >= 30 and int(p["reminder_stage"] or 0) < 2:
            conn.execute("UPDATE orders SET reminder_stage = 2 WHERE id = ?", (p["id"],))
            reminder_messages.append(f"订单#{p['id']} 已超过30分钟未响应，请尽快处理。")
        elif elapsed_minutes >= 15 and int(p["reminder_stage"] or 0) < 1:
            conn.execute("UPDATE orders SET reminder_stage = 1 WHERE id = ?", (p["id"],))
            reminder_messages.append(f"订单#{p['id']} 已超过15分钟未响应，请尽快处理。")

    if reminder_messages:
        conn.commit()

    pending_count = len(pending_orders)
    pending_key = f"merchant_pending_seen_{store['id']}"
    prev_pending_count = int(session.get(pending_key, 0))
    has_new_pending = pending_count > prev_pending_count
    session[pending_key] = pending_count
    session.modified = True

    orders = conn.execute("SELECT * FROM orders WHERE store_id = ? ORDER BY id DESC", (store["id"],)).fetchall()
    order_ids = [str(o["id"]) for o in orders]
    items_by_order = {}
    if order_ids:
        placeholders = ",".join("?" for _ in order_ids)
        items = conn.execute(
            f"SELECT * FROM order_items WHERE order_id IN ({placeholders}) ORDER BY id DESC",
            order_ids,
        ).fetchall()
        for item in items:
            items_by_order.setdefault(item["order_id"], []).append(item)
    conn.close()

    body = """
    <section class="hero">
      <h1>门店订单</h1>
      <p>{{ store['name'] }} | 支持接单、取消接单、已完成，以及批量处理。</p>
    </section>

    <section class="card" style="margin-bottom: 12px;">
      <form id="batch-form" method="post" action="{{ url_for('merchant_orders_batch_action') }}" class="row">
        <select name="action" style="max-width: 180px;" required>
          <option value="">批量操作</option>
          <option value="accept">批量接单</option>
          <option value="cancel">批量取消接单</option>
          <option value="complete">批量标记已完成</option>
        </select>
        <input name="reason" placeholder="取消原因（批量取消时可选）" style="flex:1; min-width:220px;" />
        <button class="btn" type="submit">执行批量操作</button>
      </form>
      <div class="muted" style="margin-top:8px;">勾选下方订单后可批量操作。</div>
    </section>

    {% if orders %}
      <section class="card">
        <table class="table">
          <thead>
            <tr>
              <th>批量</th>
              <th>订单</th>
              <th>状态</th>
              <th>信息</th>
              <th>商品</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {% for order in orders %}
              <tr>
                <td>
                  {% if order['status'] in [ORDER_STATUS_NEW, ORDER_STATUS_MAKING] %}
                    <input type="checkbox" name="order_ids" value="{{ order['id'] }}" form="batch-form" />
                  {% endif %}
                </td>
                <td>
                  #{{ order['id'] }}<br />
                  <span class="muted">{{ order['created_at'] }}</span>
                </td>
                <td>
                  <span class="tag">{{ order_status_text(order['status']) }}</span>
                  {% if order['fulfillment_type'] == 'pickup' %}
                    <div><span class="tag pickup">到店自提</span></div>
                  {% else %}
                    <div><span class="tag">外卖配送</span></div>
                  {% endif %}
                </td>
                <td>
                  <div class="muted">电话：{{ order['contact_phone'] }}</div>
                  <div class="muted">地址：{{ order['delivery_address'] }}</div>
                  {% if order['merchant_cancel_reason'] %}
                    <div class="muted">取消原因：{{ order['merchant_cancel_reason'] }}</div>
                  {% endif %}
                  <div>金额：<span class="price">¥{{ '%.2f'|format(order['total_price']) }}</span></div>
                </td>
                <td>
                  <div class="row" style="gap: 6px;">
                    {% for item in items_by_order.get(order['id'], []) %}
                      <span class="tag" style="background:#f2f8ff;color:#2458b8;">{{ item['dish_name'] }} x{{ item['quantity'] }}</span>
                    {% endfor %}
                  </div>
                </td>
                <td>
                  {% if order['status'] == ORDER_STATUS_NEW %}
                    <form method="post" action="{{ url_for('merchant_order_action', order_id=order['id']) }}" class="row">
                      <button class="btn ok" type="submit" name="action" value="accept">接单</button>
                      <input name="reason" placeholder="取消原因（可选）" style="max-width: 160px;" />
                      <button class="btn danger" type="submit" name="action" value="cancel">取消接单</button>
                    </form>
                  {% elif order['status'] == ORDER_STATUS_MAKING %}
                    <form method="post" action="{{ url_for('merchant_order_action', order_id=order['id']) }}" class="row">
                      <button class="btn" type="submit" name="action" value="complete">已完成</button>
                    </form>
                  {% else %}
                    <span class="muted">已处理</span>
                  {% endif %}
                </td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </section>
    {% else %}
      <div class="card"><p class="muted">暂时没有订单。</p></div>
    {% endif %}

    <script>
      (function () {
        {% if has_new_pending %}
          alert("你有 {{ pending_count }} 个待接单订单，请及时处理。");
        {% endif %}
        {% if reminder_messages %}
          const reminderText = {{ reminder_messages|join('\\n')|tojson }};
          alert(reminderText);
        {% endif %}
      })();
    </script>
    """
    return render_page(
        "门店订单",
        body,
        store=store,
        orders=orders,
        items_by_order=items_by_order,
        reminder_messages=reminder_messages,
        pending_count=pending_count,
        has_new_pending=has_new_pending,
        ORDER_STATUS_NEW=ORDER_STATUS_NEW,
        ORDER_STATUS_MAKING=ORDER_STATUS_MAKING,
    )


@app.route("/support", methods=["GET", "POST"])
@login_required
def support_center():
    user = current_user()
    conn = get_db()

    orders = conn.execute(
        """
        SELECT o.*, s.name AS store_name
        FROM orders o
        JOIN stores s ON s.id = o.store_id
        WHERE o.user_id = ?
        ORDER BY o.id DESC
        """,
        (user["id"],),
    ).fetchall()

    if request.method == "POST":
        order_id_raw = request.form.get("order_id") or ""
        message = (request.form.get("message") or "").strip()
        contact_info = (request.form.get("contact_info") or "").strip()
        try:
            order_id = int(order_id_raw)
        except ValueError:
            order_id = 0

        owned_order = conn.execute(
            "SELECT id FROM orders WHERE id = ? AND user_id = ?",
            (order_id, user["id"]),
        ).fetchone()

        if not owned_order:
            conn.close()
            flash("请选择你自己的订单", "error")
            return redirect(url_for("support_center"))
        if not message:
            conn.close()
            flash("留言内容不能为空", "error")
            return redirect(url_for("support_center"))
        if not contact_info:
            conn.close()
            flash("请填写联系方式，支持手机号或微信", "error")
            return redirect(url_for("support_center"))

        conn.execute(
            """
            INSERT INTO support_tickets(user_id, order_id, message, contact_info, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (user["id"], order_id, message, contact_info, now_str()),
        )
        conn.commit()
        conn.close()
        flash("留言已提交审核账号处理", "success")
        return redirect(url_for("support_center"))

    tickets = conn.execute(
        """
        SELECT t.*, s.name AS store_name
        FROM support_tickets t
        JOIN orders o ON o.id = t.order_id
        JOIN stores s ON s.id = o.store_id
        WHERE t.user_id = ?
        ORDER BY t.id DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()

    body = """
    <section class="hero">
      <h1>用户支持</h1>
      <p>选择订单后留言，内容将提交到审核账号进行审核处理。</p>
    </section>

    <section class="grid" style="grid-template-columns: 1.15fr 1.85fr; align-items:start;">
      <form method="post" class="card">
        <h3>提交留言</h3>
        <div class="field">
          <label>关联订单</label>
          <select name="order_id" required>
            <option value="">请选择订单</option>
            {% for o in orders %}
              <option value="{{ o['id'] }}">#{{ o['id'] }} - {{ o['store_name'] }} - ¥{{ '%.2f'|format(o['total_price']) }}</option>
            {% endfor %}
          </select>
        </div>
        <div class="field">
          <label>留言内容</label>
          <textarea name="message" rows="5" placeholder="请输入你的问题或诉求" required></textarea>
        </div>
        <div class="field">
          <label>联系方式</label>
          <div class="muted" style="margin-bottom:6px;">支持手机号和微信，便于后续确认</div>
          <input name="contact_info" placeholder="例如：13800138000 / wechat_id" required />
        </div>
        <button class="btn" type="submit">提交审核</button>
      </form>

      <section class="card">
        <h3>我的留言记录</h3>
        {% if tickets %}
          <table class="table">
            <thead>
              <tr><th>ID</th><th>订单</th><th>状态</th><th>审核备注</th></tr>
            </thead>
            <tbody>
              {% for t in tickets %}
                <tr>
                  <td>#{{ t['id'] }}</td>
                  <td>#{{ t['order_id'] }} / {{ t['store_name'] }}</td>
                  <td><span class="tag {{ t['status'] }}">{{ t['status'] }}</span></td>
                  <td>{{ t['review_note'] or '-' }}</td>
                </tr>
                <tr>
                  <td colspan="4" class="muted">留言：{{ t['message'] }} | 联系方式：{{ t['contact_info'] or '-' }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <p class="muted">你还没有提交过留言。</p>
        {% endif %}
      </section>
    </section>
    """
    return render_page("用户支持", body, orders=orders, tickets=tickets)


@app.errorhandler(404)
def page_not_found(_):
    body = """
    <section class="hero">
      <h1>页面未找到</h1>
      <p>你访问的页面不存在，返回首页继续浏览。</p>
    </section>
    <div class="card"><a class="btn" href="{{ url_for('home') }}">返回首页</a></div>
    """
    return render_page("404", body), 404


def create_app():
    init_db()
    return app


def deployment_guide():
    return f"""
[公网部署快速步骤 - Ubuntu 示例]
1) 上传本文件到服务器目录，例如 /opt/takeout
2) 安装 Python 依赖：
   python3 -m venv .venv
   source .venv/bin/activate
   pip install flask waitress
3) 生产启动（监听 127.0.0.1:5000，交给 Nginx 反代）：
   APP_SECRET_KEY='请替换为强密钥' .venv/bin/python single_file_takeout_app.py --prod --host 127.0.0.1 --port 5000
4) 健康检查地址：
   http://127.0.0.1:5000/healthz
5) Nginx 反向代理到 127.0.0.1:5000，并配置 HTTPS 证书后即可让其他用户通过域名访问。

[当前机器局域网访问]
- 同一网络可访问：http://你的局域网IP:5000
"""


def run_server(host, port, prod_mode):
    init_db()
    if prod_mode:
        try:
            from waitress import serve
        except Exception:
            print("waitress 未安装，已回退到 Flask 内置服务（不建议生产使用）")
            app.run(host=host, port=port, debug=False)
            return
        serve(app, host=host, port=port, threads=8)
        return
    app.run(host=host, port=port, debug=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="云点餐单文件应用")
    parser.add_argument("--host", default=os.getenv("APP_HOST", "0.0.0.0"), help="监听地址")
    parser.add_argument("--port", type=int, default=int(os.getenv("APP_PORT", "5000")), help="监听端口")
    parser.add_argument("--prod", action="store_true", help="生产模式（优先 waitress）")
    parser.add_argument("--show-deploy-guide", action="store_true", help="打印部署指南后退出")
    args = parser.parse_args()

    if args.show_deploy_guide:
        print(deployment_guide())
        raise SystemExit(0)

    run_server(host=args.host, port=args.port, prod_mode=args.prod)
