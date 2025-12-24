import sqlite3


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """
    """
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)

def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_def_sql: str) -> None:
    if _column_exists(conn, table, column):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def_sql}")

def _get_db_connection(DB_FILE) -> sqlite3.Connection:
    """创建 SQLite 连接，并启用 Row 工厂便于按列名取值。"""
    # 1. 建立连接
    conn = sqlite3.connect(DB_FILE)
    # 2. 关键一步：设置 row_factory
    # 这允许我们通过列名访问数据，并使用 row.keys()
    conn.row_factory = sqlite3.Row
    """
    默认情况：SQLite 返回的数据是元组 (1, "Alice")。你必须记住 1 是 ID，"Alice" 是用户名。
    开启后：SQLite 返回的是 Row 对象。它更像一个字典，你可以通过 row["username"] 来取值。这也是为什么你后续能使用 row_to_dict 函数的前提。
    """
    return conn

def _ensure_db_schema(DB_FILE) -> None:
    """确保数据库表存在；即便没运行 init_db.py 也能启动应用。"""
    with _get_db_connection(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'pending',
                contact TEXT NOT NULL,
                address TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                contact TEXT,
                image TEXT,
                create_time TEXT,
                address TEXT,
                attributes TEXT
            )
            """
        )

        # 兼容旧数据库：users 表
        _ensure_column(conn, "users", "role", "role TEXT DEFAULT 'user'")
        _ensure_column(conn, "users", "status", "status TEXT DEFAULT 'pending'")
        _ensure_column(conn, "users", "contact", "contact TEXT NOT NULL")
        _ensure_column(conn, "users", "address", "address TEXT NOT NULL")

        # 兼容旧数据库：items 表
        _ensure_column(conn, "items", "address", "address TEXT")
        _ensure_column(conn, "items", "attributes", "attributes TEXT")

# ==================== 用户管理功能模块 ====================

def load_users(DB_FILE):
    """
    加载用户密码映射
    """
    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        rows = conn.execute("SELECT username, password FROM users").fetchall()
        return {row["username"]: row["password"] for row in rows}

def get_user_by_username(username: str, DB_FILE) -> dict | None:
    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        row = conn.execute(
            """
            SELECT id, username, password, role, status, contact, address
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()
    return row_to_dict(row)

def authenticate_user(username: str, password: str, DB_FILE, require_approved: bool = True) -> bool:
    """校验用户名和密码；可选要求 status=approved 才允许登录。"""
    user = get_user_by_username(username, DB_FILE)
    if not user:
        return False
    if require_approved and user.get("status") != "approved":
        return False
    return user.get("password") == password

def register_user(username: str, password: str, contact: str, address: str, DB_FILE) -> tuple[bool, str]:
    """注册普通用户，默认状态 pending，等待管理员审批。"""
    _ensure_db_schema(DB_FILE)
    username = (username or "").strip()
    password = (password or "").strip()
    contact = (contact or "").strip()
    address = (address or "").strip()

    if not username or not password:
        return False, "用户名和密码不能为空"
    if len(username) < 3:
        return False, "用户名至少需要 3 个字符"
    if len(password) < 6:
        return False, "密码至少需要 6 个字符"
    if not contact:
        return False, "联系方式不能为空"
    if not address:
        return False, "住址不能为空"

    try:
        with _get_db_connection(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO users (username, password, role, status, contact, address)
                VALUES (?, ?, 'user', 'pending', ?, ?)
                """,
                (username, password, contact, address),
            )
        return True, "注册成功，等待管理员审批"
    except sqlite3.IntegrityError:
        return False, "用户名已存在"

def list_pending_users(DB_FILE) -> list[dict]:
    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT id, username, role, status, contact, address
            FROM users
            WHERE status = 'pending'
            ORDER BY id ASC
            """
        ).fetchall()
    return [row_to_dict(r) for r in rows]

def approve_user(target_username: str, DB_FILE) -> tuple[bool, str]:
    _ensure_db_schema(DB_FILE)
    target_username = (target_username or "").strip()
    if not target_username:
        return False, "请输入要批准的用户名"

    with _get_db_connection(DB_FILE) as conn:
        row = conn.execute(
            "SELECT status FROM users WHERE username = ?",
            (target_username,),
        ).fetchone()
        if not row:
            return False, "用户不存在"
        if row["status"] == "approved":
            return True, "该用户已是 approved 状态"

        conn.execute(
            "UPDATE users SET status = 'approved' WHERE username = ?",
            (target_username,),
        )
    return True, "已批准该用户"

def add_user(username: str, password: str, DB_FILE, *, role: str = "user", status: str = "approved", contact: str = "", address: str = "") -> bool:
    """新增用户（兼容接口）。

    注意：users 表里 contact/address 为 NOT NULL（初始化脚本如此），因此这里也要求传入。
    """
    _ensure_db_schema(DB_FILE)
    if not username:
        raise ValueError("username不能为空")
    elif not password:
        raise ValueError("password不能为空")
    elif not contact:
        raise ValueError("contact不能为空")
    elif not address:
        raise ValueError("address不能为空")

    try:
        with _get_db_connection(DB_FILE) as conn:
            conn.execute(
                """
                INSERT INTO users (username, password, role, status, contact, address)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, password, role, status, contact, address),
            )
        return True
    except sqlite3.IntegrityError:
        return False

# ==================== 数据存储管理模块 ====================

def load_items(DB_FILE):
    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT id, name, category, description, contact, image, create_time, attributes
            FROM items
            ORDER BY id ASC
            """
        ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "description": row["description"],
            "contact": row["contact"],
            "image": row["image"],
            "create_time": row["create_time"],
            "attributes": row["attributes"],
        }
        for row in rows
    ]


def save_items(items, DB_FILE):
    # 为了保持原有“保存整个列表”的接口，这里采用覆盖写入表的方式。
    # 实际业务中更推荐直接 INSERT/UPDATE/DELETE（本项目的 add_item/delete_item 已改为直接操作数据库）。
    _ensure_db_schema(DB_FILE)
    rows = [
        (
            item.get("id"),
            item.get("name"),
            item.get("description"),
            item.get("contact"),
            item.get("create_time"),
            item.get("category"),
            item.get("image"),
            item.get("attributes"),
        )
        for item in items
    ]

    with _get_db_connection(DB_FILE) as conn:
        conn.execute("DELETE FROM items")
        conn.executemany(
            """
            INSERT INTO items (id, name, description, contact, create_time, category, image, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        