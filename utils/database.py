import sqlite3

def _get_db_connection(DB_FILE) -> sqlite3.Connection:
    """创建 SQLite 连接，并启用 Row 工厂便于按列名取值。"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def _ensure_db_schema(DB_FILE) -> None:
    """确保数据库表存在；即便没运行 init_db.py 也能启动应用。"""
    with _get_db_connection(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                contact TEXT,
                create_time TEXT,
                category TEXT NOT NULL,
                image TEXT
            )
            """
        )

# ==================== 用户管理功能模块 ====================

def load_users(DB_FILE):
    """
    从 JSON 文件加载用户数据
    
    功能说明:
        读取 users.json 文件中的用户信息，如果文件不存在则创建默认用户
    
    输入参数:
        无
    
    返回值:
        dict: 用户字典，格式为 {username: password}
              例如: {"admin": "admin123", "user1": "password1"}
    
    异常处理:
        文件不存在时自动创建默认用户并保存
    """
    with _get_db_connection(DB_FILE) as conn:
        rows = conn.execute("SELECT username, password FROM users").fetchall()
        if rows:
            return {row["username"]: row["password"] for row in rows}

    # 数据库为空时插入默认用户（保持原行为）
    default_users = {
        "admin": "admin123",
        "user1": "password1",
    }
    save_users(default_users)
    return default_users

def add_user(username: str, password: str, DB_FILE) -> bool:
    """新增用户。

    返回值:
        True  - 插入成功
        False - 用户名已存在
    """
    _ensure_db_schema(DB_FILE)
    if not username or not password:
        raise ValueError("username/password 不能为空")

    try:
        with _get_db_connection(DB_FILE) as conn:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password),
            )
        return True
    except sqlite3.IntegrityError:
        return False

def save_users(users, DB_FILE):
    _ensure_db_schema(DB_FILE)
    user_list = [(username, password) for username, password in users.items()]
    with _get_db_connection(DB_FILE) as conn:
        conn.execute("DELETE FROM users")
        conn.executemany(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            user_list,
        )

# ==================== 数据存储管理模块 ====================

def load_items(DB_FILE):
    """
    返回值:
        list: 物品列表，每个物品是一个字典，包含以下字段:
              - id (int): 物品唯一标识
              - name (str): 物品名称
              - category (str): 物品分类
              - description (str): 物品描述
              - contact (str): 联系方式
              - image (str): 图片路径
              - create_time (str): 创建时间
    
    异常处理:
        文件不存在时返回空列表
    """
    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        rows = conn.execute(
            """
            SELECT id, name, category, description, contact, image, create_time
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
        )
        for item in items
    ]

    with _get_db_connection(DB_FILE) as conn:
        conn.execute("DELETE FROM items")
        conn.executemany(
            """
            INSERT INTO items (id, name, description, contact, create_time, category, image)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        