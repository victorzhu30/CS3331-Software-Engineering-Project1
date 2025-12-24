import sqlite3
import json
import os

# 定义数据库文件名
DB_FILE = 'CS3331.db'

# # 如果数据库文件已存在，先删除，确保每次运行都是全新的
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

# 1. 连接数据库（会自动创建文件）
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# ---------------------------------------------------------
# 2. 创建表结构 (SQL 语句)
# ---------------------------------------------------------

# 创建 users 表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        status TEXT DEFAULT 'pending',
        contact TEXT NOT NULL,
        address TEXT NOT NULL
    )
''')

# 创建 items 表
# 注意：image 没有设为 NOT NULL，因为有的数据里没有
cursor.execute('''
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
''')

# ---------------------------------------------------------
# 3. 读取 users.json 并写入数据库
# ---------------------------------------------------------
try:
    with open('users.json', 'r', encoding='utf-8') as f:
        users_data = json.load(f)
        # print(users_data)
        # [{'id': 1, 'username': 'admin', 'password': 'admin123', 'role': 'admin', 'status': 'approved'}, {'id': 2, 'username': 'user1', 'password': 'password1', 'role': 'user', 'status': 'approved'}, {'id': 3, 'username': 'user2', 'password': 'password2', 'role': 'user', 'status': 'pending'}]

        user_rows = []
        for user in users_data:
            row = (
                user.get('id'),
                user.get('username'),
                user.get('password'),
                user.get('role', 'user'),    # 默认值 'user'
                user.get('status', 'pending'), # 默认值 'pending'
                user.get('contact'),
                user.get('address')
            )
            user_rows.append(row)
            
        # 批量插入
        cursor.executemany('INSERT INTO users (id, username, password, role, status, contact, address) VALUES (?, ?, ?, ?, ?, ?, ?)', user_rows)
        print(f"成功插入 {len(user_rows)} 条用户数据。")

except FileNotFoundError:
    print("未找到 users.json，跳过用户数据导入。")

# ---------------------------------------------------------
# 4. 读取 items.json 并写入数据库
# ---------------------------------------------------------
try:
    with open('items.json', 'r', encoding='utf-8') as f:
        items_data = json.load(f) #这是一个列表 [{}, {}, ...]
        
        item_rows = []
        for item in items_data:
            # 使用 .get() 方法，因为 image 可能不存在
            # 如果不存在，这就返回 None，数据库里会存为 NULL
            row = (
                item.get('id'),
                item.get('name'),
                item.get('category'), 
                item.get('description'),
                item.get('contact'),
                item.get('image', None),     # 默认值为 None
                item.get('create_time'),
                item.get('address'),
                item.get('attributes', None),
            )
            item_rows.append(row)
            
        # 批量插入
        cursor.executemany('''
            INSERT INTO items (id, name, category, description, contact, image, create_time, address, attributes) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', item_rows)
        print(f"成功插入 {len(item_rows)} 条物品数据。")

except FileNotFoundError:
    print("未找到 items.json，跳过物品数据导入。")

# ---------------------------------------------------------
# 5. 提交保存并关闭
# ---------------------------------------------------------
conn.commit()
conn.close()

print(f"数据库初始化完成：{DB_FILE}")