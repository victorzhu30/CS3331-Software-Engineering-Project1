import json
import html
import os
import shutil
from datetime import datetime
from dotenv import load_dotenv
import traceback

import gradio as gr
from fastapi import FastAPI
import uvicorn

from utils.contact import format_contact
from utils.auth import show_welcome
from utils.util import *
from utils.database import (
    _get_db_connection,
    _ensure_db_schema,
    load_users,
    add_user,
    load_items,
    save_items,
    authenticate_user,
    register_user,
    list_pending_users,
    approve_user,
    get_user_by_username,
)

# # 加载环境变量配置
# load_dotenv()

# ==================== 全局常量配置 ====================
# 从 constants 模块导入数据文件路径配置
from constants import DATA_FILE      # 物品数据存储文件路径 (items.json)
from constants import USERS_FILE     # 用户数据存储文件路径 (users.json)
from constants import IMAGE_DIR      # 图片存储目录路径 (images/)
from constants import DB_FILE        # SQLite 数据库文件路径 (CS3331.db)
from constants import MAX_DYNAMIC_FIELDS

from utils import category_config

# 绝对路径配置（兼容开发和打包环境）
IMAGE_DIR = get_path_for_write(IMAGE_DIR)
DB_FILE = get_path_for_write(DB_FILE)

# 创建图片存储目录（如果不存在）
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# 从文件中读取自定义 CSS 样式
with open(get_path_for_read("style.css"), "r", encoding="utf-8") as f:
    custom_css = f.read()

_ensure_db_schema(DB_FILE)

# https://www.gradio.app/guides/sharing-your-app#mounting-within-another-fast-api-app
MAIN_PATH = "/home"      # 主应用（需要登录）
REGISTER_PATH = "/register"  # 注册页（无需登录）

app = FastAPI()

from fastapi.responses import HTMLResponse

# @app.get("/")
# def read_main():
#     return {
#         "message": "This is your main app. Open /home for the main UI and /register for registration.",
#         "main_ui": MAIN_PATH,
#         "register": REGISTER_PATH,
#     }

@app.get("/", response_class=HTMLResponse)
def read_main():
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>系统入口</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f7f9; }}
                .container {{ text-align: center; background: white; padding: 2rem; border-radius: 12px; shadow: 0 4px 6px rgba(0,0,0,0.1); box-shadow: 0 10px 25px rgba(0,0,0,0.05); }}
                h1 {{ color: #2d3748; margin-bottom: 1.5rem; }}
                .btn-group {{ display: flex; gap: 1rem; justify-content: center; }}
                .btn {{ padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; transition: all 0.2s; }}
                .btn-main {{ background-color: #4299e1; color: white; }}
                .btn-main:hover {{ background-color: #3182ce; }}
                .btn-reg {{ background-color: #edf2f7; color: #4a5568; }}
                .btn-reg:hover {{ background-color: #e2e8f0; }}
                p {{ color: #718096; margin-bottom: 2rem; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>欢迎使用系统</h1>
                <p>请根据您的需求选择进入的页面</p>
                <div class="btn-group">
                    <a href="{MAIN_PATH}" class="btn btn-main">进入主应用 (需要登录)</a>
                    <a href="{REGISTER_PATH}" class="btn btn-reg">新用户注册</a>
                </div>
            </div>
        </body>
    </html>
    """

def authenticate(username, password):
    """
    验证用户登录凭证

    输入参数:
        username (str): 用户输入的用户名
        password (str): 用户输入的密码
    
    返回值:
        bool: 验证成功返回 True，失败返回 False
    """
    # 仅允许已通过管理员审批 (status=approved) 的用户登录
    if not username or not password:
        return False
    return authenticate_user(username, password, DB_FILE, require_approved=True)

def _is_admin_request(request: gr.Request | None) -> bool:
    """
    Note: if your function is called directly instead of through the UI (this happens, for example, when examples are cached, or when the Gradio app is called via API), then request will be None. 
    You should handle this case explicitly to ensure that your app does not throw any errors. That is why we have the explicit check if request.
    """
    if not request:
        return False
    username = getattr(request, "username", None)
    if not username:
        return False
    me = get_user_by_username(username, DB_FILE)
    return bool(me and me.get("role") == "admin")

def _render_pending_users_html():
    pending = list_pending_users(DB_FILE)
    if not pending:
        return "<div style='padding: 12px; color: #666;'>暂无待审批用户</div>"

    rows_html = "".join(
        f"""
        <tr>
            <td>{html.escape(str(u.get('id', '')))}</td>
            <td>{html.escape(str(u.get('username', '')))}</td>
            <td>{html.escape(str(u.get('contact', '') or ''))}</td>
            <td>{html.escape(str(u.get('address', '') or ''))}</td>
            <td>{html.escape(str(u.get('status', '') or ''))}</td>
        </tr>
        """
        for u in pending
    )

    return (
        "<div style='padding: 8px 0;'><b>待审批用户列表</b></div>"
        "<table style='width: 100%; border-collapse: collapse;'>"
        "<thead><tr>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>ID</th>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>用户名</th>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>联系方式</th>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>住址</th>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>状态</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
    )

def admin_approve_user(target_username, request: gr.Request):
    # 仅管理员可审批（并处理 request 可能为 None）
    if not _is_admin_request(request):
        return "❌ 仅管理员可审批用户", _render_pending_users_html(), target_username

    ok, msg = approve_user(target_username, DB_FILE)
    prefix = "✅ " if ok else "❌ "
    return prefix + msg, _render_pending_users_html(), ""

def do_register(username, password, confirm_password, contact, address):
    if password != confirm_password:
        return "❌ 两次输入的密码不一致", username, password, confirm_password, contact, address

    ok, msg = register_user(username, password, contact, address, DB_FILE)
    if ok:
        return (
            f"✅ {msg}\n\n请等待管理员审批后再登录。",
            "",
            "",
            "",
            "",
            "",
        )
    return "❌ " + msg, username, password, confirm_password, contact, address

def _init_admin_tab(request: gr.Request | None):
    visible = _is_admin_request(request)
    # Tab 默认隐藏；仅管理员在加载后显示
    return gr.update(visible=visible), _render_pending_users_html()

def save_image(image, item_id):
    """
    保存上传的图片到指定目录
    
    功能说明:
        将用户上传的图片复制到 images/ 目录，并按规则命名
    
    输入参数:
        image (str): 上传图片的临时文件路径
        item_id (int): 物品ID，用于生成唯一文件名
    
    返回值:
        str: 保存后的图片相对路径
             格式: "images/item_{id}_{timestamp}{ext}"
             例如: "images/item_5_20251021_143025.jpg"
    
    文件命名规则:
        item_{物品ID}_{时间戳}.{原始扩展名}
        时间戳格式: YYYYMMDD_HHMMSS
    
    异常处理:
        如果图片没有扩展名，默认使用 .jpg
    """
    # 生成时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(image)[1] or '.jpg'
    # 将文件路径分割成文件名和扩展名两部分，返回元组 (文件名, 扩展名)。没有扩展名时返回空字符串
    # 取元组的第二个元素（索引为1），即扩展名部分。如果扩展名为空字符串（布尔值为 False），则使用默认值 .jpg
    filename = f"item_{item_id}_{timestamp}{ext}"
    filepath = os.path.join(IMAGE_DIR, filename)
    
    # 复制图片到存储目录
    shutil.copy(image, filepath)
    # shutil (shell utilities) 是 Python 的高级文件操作模块，专门用于文件和目录的复制、移动、删除等操作。
    # shutil.copy() 的功能
    # 复制文件内容和权限
    # 自动处理文件打开/关闭
    # 跨平台兼容（Windows/Linux/Mac）
    return filepath

def delete_image(image_path):
    """
    删除指定路径的图片文件
    
    功能说明:
        安全地删除物品关联的图片文件
    
    输入参数:
        image_path (str): 图片文件路径
                         例如: "images/item_1_20251021_143025.jpg"
    
    返回值:
        无
    
    异常处理:
        使用 try-except 捕获删除失败的情况，确保程序不会因此中断
        可能的失败原因: 文件不存在、权限不足等
    """
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except Exception:
            pass


def _parse_attributes(attributes_text):
    if not attributes_text:
        return {}
    try:
        value = json.loads(attributes_text)
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _render_attributes_html(category, attributes_text):
    attrs = _parse_attributes(attributes_text)
    if not attrs:
        return ""

    defs = category_config.get_category_fields().get(category, [])
    label_by_key = {d.get("key"): d.get("label", d.get("key")) for d in defs}

    parts = []
    for k, v in attrs.items():
        if v is None or str(v).strip() == "":
            continue
        label = label_by_key.get(k, k)
        parts.append(
            f"<span><b>{html.escape(str(label))}</b>: {html.escape(str(v))}</span>"
        )

    if not parts:
        return ""

    return "<div>" + " &nbsp; ".join(parts) + "</div>"


def _category_field_updates(category):
    defs = category_config.get_category_fields().get(category, [])
    updates = []
    for i in range(MAX_DYNAMIC_FIELDS):
        if i < len(defs):
            d = defs[i]
            label = d.get("label", d.get("key", "属性"))
            required = d.get("required", False)
            updates.append(
                gr.update(
                    visible=True,
                    label=f"{label}{'*' if required else ''}",
                    value="",
                )
            )
        else:
            updates.append(gr.update(visible=False, label="属性", value=""))
    return updates


def _category_field_initial_props(category):
    defs = category_config.get_category_fields().get(category, [])
    props = []
    for i in range(MAX_DYNAMIC_FIELDS):
        if i < len(defs):
            d = defs[i]
            label = d.get("label", d.get("key", "属性"))
            required = d.get("required", False)
            props.append({"label": f"{label}{'*' if required else ''}", "visible": True})
        else:
            props.append({"label": "属性", "visible": False})
    return props

# 在 click 事件中返回空值来清空输入框。
def add_item(name, category, description, address, contact, image, *dynamic_values):
    print(f"Adding item: {name}, {category}, {description}, {address}, {contact}, {image}")

    # 规范化动态字段输出长度（用于 UI 回填/清空）
    dynamic_values = list(dynamic_values)
    if len(dynamic_values) < MAX_DYNAMIC_FIELDS:
        dynamic_values.extend([""] * (MAX_DYNAMIC_FIELDS - len(dynamic_values)))
    else:
        dynamic_values = dynamic_values[:MAX_DYNAMIC_FIELDS]
    
    # 验证必填字段
    if not name or not contact:
        return (
            "❌ 物品名称和联系方式不能为空！",
            get_items_list(),
            name,
            category,
            description,
            address,
            contact,
            image,
            *dynamic_values,
        )

    # 打包动态属性（写死配置驱动）
    field_defs = category_config.get_category_fields().get(category, [])
    attributes = {}
    missing_required = []
    for idx, d in enumerate(field_defs):
        key = d.get("key")
        if not key:
            continue
        value = (dynamic_values[idx] if idx < len(dynamic_values) else "")
        value = "" if value is None else str(value).strip()
        if d.get("required") and not value:
            missing_required.append(d.get("label", key))
        attributes[key] = value

    if missing_required:
        return (
            "❌ 请填写必填属性：" + "、".join(missing_required),
            get_items_list(),
            name,
            category,
            description,
            address,
            contact,
            image,
            *dynamic_values,
        )
    
    _ensure_db_schema(DB_FILE)

    with _get_db_connection(DB_FILE) as conn:
        # 生成新物品ID（保持与原 JSON 版本一致的“max + 1”策略）
        new_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM items").fetchone()[
            "next_id"
        ]

        # 保存图片（如果有）
        image_path = save_image(image, new_id) if image else None

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            INSERT INTO items (id, name, description, address, contact, create_time, category, image, attributes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id,
                name,
                description,
                address,
                contact,
                now_str,
                category,
                image_path,
                json.dumps(attributes, ensure_ascii=False),
            ),
        )
    
    # 返回成功消息和清空的输入框
    return (
        f"✅ 成功添加物品：{name}",
        get_items_list(),
        "",
        None,
        "",
        "",
        "",
        None,
        *([""] * MAX_DYNAMIC_FIELDS),
    )

def delete_item(item_id):
    """
    删除指定ID的物品
    
    功能说明:
        根据物品ID删除物品记录及关联图片
    
    输入参数:
        item_id (str): 要删除的物品ID（字符串格式）
    
    返回值:
        tuple: 包含3个元素的元组
            (0) str: 操作结果消息
            (1) str: 更新后的物品列表HTML
            (2) str: 清空后的ID输入框
    
    数据验证:
        - ID不能为空
        - ID必须是数字
        - ID必须存在于数据库中
    
    业务逻辑:
        1. 验证输入的ID格式
        2. 查找对应的物品记录
        3. 删除关联的图片文件
        4. 从数据库删除记录
        5. 返回操作结果
    
    异常处理:
        - 捕获 ValueError（ID不是数字）
        - 未找到ID时返回错误消息
    """
    # 验证ID不为空
    if not item_id:
        return (
            "❌ 请输入要删除的物品ID！",
            get_items_list(),
            item_id
        )
    
    try:
        # 转换为整数
        item_id = int(item_id)

        _ensure_db_schema(DB_FILE)
        with _get_db_connection(DB_FILE) as conn:
            row = conn.execute("SELECT image FROM items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return (
                    "❌ 物品ID不存在！",
                    get_items_list(),
                    item_id,
                )

            # 删除关联图片
            image_path = row["image"]
            if image_path:
                delete_image(image_path)

            conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        
        return (
            f"✅ 成功删除ID为 {item_id} 的物品",
            get_items_list(),
            ""
        )
        
    except ValueError:
        return (
            "❌ 物品ID必须是数字！",
            get_items_list(),
            item_id
        )

# ==================== 界面显示与渲染模块 ====================

def get_items_list():
    """
    生成物品列表的 HTML 卡片视图
    
    功能说明:
        将物品数据渲染为响应式卡片布局的 HTML
    
    输入参数:
        无（从数据文件读取）
    
    返回值:
        str: HTML 格式的物品列表，包含:
             - 物品图片
             - 分类标签
             - ID 和名称
             - 描述信息
             - 格式化的联系方式
             - 创建时间
        
        空列表时返回提示信息
    
    渲染逻辑:
        1. 加载所有物品数据
        2. 为每个物品生成 HTML 卡片
        3. 处理图片显示（存在/不存在）
        4. 调用 format_contact() 格式化联系方式
        5. 组装完整的 HTML 字符串
    
    图片处理:
        使用 Gradio 的文件访问 API: /gradio_api/file={绝对路径}
        需配合 app.launch(allowed_paths=[...]) 使用
    """
    items = load_items(DB_FILE)
    
    # 处理空列表情况
    if not items:
        return "<div style='text-align: center; padding: 50px; color: #999;'>暂无物品信息</div>"
    
    # 开始构建 HTML
    display_cards_html = '<div class="items-container">'

    for item in items:
        # 处理物品图片
        image_tag = ""
        if item.get('image') and os.path.exists(item['image']):
            # print(item['image']) 
            # images\item_4_20251016_212755.jpeg

            image_path = item['image'].replace('\\', '/')
            # 把字符串中的所有反斜杠 \ 替换成正斜杠 /
            # 在 Python 字符串中，\ 是转义字符，需要用 \\ 表示一个真正的反斜杠
            # print(image_path)
            # images/item_4_20251016_212755.jpeg

            # /gradio_api/file= + allowed_paths 配合使用
            # https://blog.gitcode.com/5eaed1170a48c79c5c3391f182927f5a.html
            # https://gradio.org.cn/guides/file-access
            image_abs_path = os.path.abspath(item['image']).replace('\\', '/')
            image_tag = f'<img src="gradio_api/file={image_abs_path}" class="item-image" />'
        else:
            # 无图片时显示占位符
            image_tag = '<div class="item-image" style="background: #f5f5f5; display: flex; align-items: center; justify-content: center; color: #999;">暂无图片</div>'
        
        # 格式化联系方式（支持邮箱、QQ、电话等）
        contact_html = format_contact(item['contact'])

        # 渲染动态属性（不同类别不同字段）
        attrs_html = _render_attributes_html(item.get('category', ''), item.get('attributes'))

        # 构建单个物品卡片
        display_cards_html += f"""
        <div class="item-card">
            {image_tag}
            <div class="item-category">🏷️ {item.get('category', '未分类')}</div>
            <div class="item-id">ID: {item['id']}</div>
            <div class="item-name">{item['name']}</div>
            <div class="item-desc">{item.get('description', '无描述')}</div>
            {attrs_html}
            {contact_html}
            <div class="item-time">⏰ {item['create_time']}</div>
        </div>
        """
    
    display_cards_html += "</div>"
    return display_cards_html


def search_items(keyword, category_filter):
    """
    搜索物品并返回结果
    
    功能说明:
        根据关键词和分类筛选物品，返回匹配结果
    
    输入参数:
        keyword (str): 搜索关键词，在名称和描述中查找（不区分大小写）
        category_filter (str|list): 分类筛选条件
                                   - str: 单个分类或"全部"
                                   - list: 多个分类的列表
    
    返回值:
        tuple: 包含2个元素的元组
            (0) str: 搜索结果的 HTML（卡片格式）
            (1) str: 空字符串（用于清空搜索框）
    
    搜索逻辑:
        1. 加载所有物品
        2. 按分类筛选（支持单选和多选）
        3. 按关键词过滤（名称或描述包含关键词）
        4. 生成结果 HTML
    
    特殊处理:
        - "全部"分类不进行筛选
        - 关键词为空时只按分类筛选
        - 未找到结果时返回提示信息
    """
    items = load_items(DB_FILE)
    
    # 默认值处理
    if not category_filter:
        category_filter = "全部"
    
    # 分类筛选逻辑
    if isinstance(category_filter, str):
        # 单个分类
        if category_filter != "全部":
            items = [
                item for item in items 
                if item.get('category') == category_filter
            ]
    elif isinstance(category_filter, list):
        # 多个分类
        if "全部" not in category_filter:
            items = [
                item for item in items 
                if item.get('category') in category_filter
            ]
    
    # 关键词搜索（不区分大小写）
    if keyword:
        items = [
            item for item in items 
            if keyword.lower() in item['name'].lower() 
            or keyword.lower() in item.get('description', '').lower()
        ]
    
    # 未找到结果
    if not items:
        return (
            "<div style='text-align: center; padding: 50px; color: #999;'>未找到相关物品</div>",
            ""
        )
    
    # 构建搜索结果 HTML（复用卡片样式）
    search_cards_html = f'<div class="search-header">找到 {len(items)} 个相关物品</div>'
    search_cards_html += '<div class="items-container">'
    
    for item in items:
        # 处理图片
        image_tag = ""
        if item.get('image') and os.path.exists(item['image']):
            image_abs_path = os.path.abspath(item['image']).replace('\\', '/')
            image_tag = f'<img src="gradio_api/file={image_abs_path}" class="item-image" />'
        else:
            image_tag = '<div class="item-image" style="background: #f5f5f5; display: flex; align-items: center; justify-content: center; color: #999;">暂无图片</div>'
        
        # 格式化联系方式
        contact_html = format_contact(item['contact'])

        attrs_html = _render_attributes_html(item.get('category', ''), item.get('attributes'))

        search_cards_html += f"""
        <div class="item-card">
            {image_tag}
            <div class="item-category">🏷️ {item.get('category', '未分类')}</div>
            <div class="item-id">ID: {item['id']}</div>
            <div class="item-name">{item['name']}</div>
            <div class="item-desc">{item.get('description', '无描述')}</div>
            {attrs_html}
            {contact_html}
            <div class="item-time">⏰ {item['create_time']}</div>
        </div>
        """
    
    search_cards_html += "</div>"
    return search_cards_html, ""


# ==================== 管理员：物品类型管理 ====================

def _render_category_config_html() -> str:
    categories = category_config.get_categories()
    fields_map = category_config.get_category_fields()

    if not categories:
        return "<div style='padding: 12px; color: #666;'>暂无物品类型</div>"

    rows_html = "".join(
        f"""
        <tr>
            <td style='border-bottom:1px solid #eee;padding:6px;'>{html.escape(str(c))}</td>
            <td style='border-bottom:1px solid #eee;padding:6px;'>{len(fields_map.get(c, []))}</td>
        </tr>
        """
        for c in categories
    )

    return (
        "<div style='padding: 8px 0;'><b>当前物品类型</b></div>"
        "<table style='width: 100%; border-collapse: collapse;'>"
        "<thead><tr>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>类型名称</th>"
        "<th style='text-align:left;border-bottom:1px solid #ddd;padding:6px;'>属性数量</th>"
        "</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
        f"<div style='padding-top:6px;color:#666;'>字段上限：{MAX_DYNAMIC_FIELDS}（可在 constants.py 调整）</div>"
    )


def _dropdown_updates_after_category_change():
    cats = category_config.get_categories()
    return (
        gr.update(choices=cats),
        gr.update(choices=["全部"] + cats),
    )

def _init_category_tab(request: gr.Request | None):
    visible = _is_admin_request(request)
    cats = category_config.get_categories()
    return gr.update(visible=visible), _render_category_config_html(), gr.update(choices=cats, value=None)

def admin_category_load(selected_category: str, request: gr.Request | None):
    if not _is_admin_request(request):
        return "❌ 仅管理员可操作", gr.update(), "", "[]"

    cats = category_config.get_categories()
    selected_category = (selected_category or "").strip()
    if not selected_category or selected_category not in cats:
        return "", gr.update(choices=cats, value=None), "", "[]"

    return (
        "",
        gr.update(choices=cats, value=selected_category),
        selected_category,
        category_config.get_fields_json_for_category(selected_category),
    )

def admin_category_save(selected_category: str, new_name: str, fields_json: str, request: gr.Request | None):
    if not _is_admin_request(request):
        add_upd, search_upd = _dropdown_updates_after_category_change()
        return (
            "❌ 仅管理员可操作",
            _render_category_config_html(),
            gr.update(),
            gr.update(),
            gr.update(),
            add_upd,
            search_upd,
        )

    ok, msg = category_config.upsert_category(
        old_name = selected_category,
        new_name = new_name,
        fields_json = fields_json,
    )
    prefix = "✅ " if ok else "❌ "

    cats = category_config.get_categories()
    final_name = (new_name or "").strip()
    cat_select_upd = gr.update(choices=cats, value=(final_name if ok else (selected_category or None)))
    add_upd, search_upd = _dropdown_updates_after_category_change()
    # 保存成功后刷新 JSON（按规范化后的格式回填）
    fields_back = category_config.get_fields_json_for_category(final_name) if ok else (fields_json or "[]")

    return (
        prefix + msg,
        _render_category_config_html(),
        cat_select_upd,
        (final_name if ok else (new_name or "")),
        fields_back,
        add_upd,
        search_upd,
    )


def admin_category_delete(selected_category: str, request: gr.Request | None):
    if not _is_admin_request(request):
        add_upd, search_upd = _dropdown_updates_after_category_change()
        return (
            "❌ 仅管理员可操作",
            _render_category_config_html(),
            gr.update(),
            gr.update(),
            gr.update(),
            add_upd,
            search_upd,
        )

    selected_category = (selected_category or "").strip()
    if not selected_category:
        add_upd, search_upd = _dropdown_updates_after_category_change()
        return (
            "❌ 请选择要删除的类型",
            _render_category_config_html(),
            gr.update(),
            gr.update(),
            gr.update(),
            add_upd,
            search_upd,
        )

    _ensure_db_schema(DB_FILE)
    with _get_db_connection(DB_FILE) as conn:
        cnt = conn.execute(
            "SELECT COUNT(1) AS c FROM items WHERE category = ?",
            (selected_category,),
        ).fetchone()["c"]

    if cnt and int(cnt) > 0:
        add_upd, search_upd = _dropdown_updates_after_category_change()
        return (
            f"❌ 该类型下已有 {cnt} 条物品记录，不能删除",
            _render_category_config_html(),
            gr.update(),
            gr.update(),
            gr.update(),
            add_upd,
            search_upd,
        )

    ok, msg = category_config.delete_category(selected_category)
    prefix = "✅ " if ok else "❌ "
    cats = category_config.get_categories()
    cat_select_upd = gr.update(choices=cats, value=None)
    add_upd, search_upd = _dropdown_updates_after_category_change()

    return (
        prefix + msg,
        _render_category_config_html(),
        cat_select_upd,
        "",
        "[]",
        add_upd,
        search_upd,
    )

# ==================== Gradio 界面构建 ====================

# 创建 Gradio 应用界面
with gr.Blocks(title="物品复活平台 - 首页", css=custom_css) as main_ui:
    # 页面标题
    gr.Markdown(value="# 🔄 物品复活平台")
    gr.Markdown(value="## 让闲置物品找到新主人！")

    # 顶部用户信息栏
    with gr.Row():
        with gr.Column(scale=4):
            welcome_msg = gr.Markdown()
        with gr.Column(scale=1):
            logout_button = gr.Button(
                "🚪 退出登录",
                # 相对链接，挂载到 /gradio 时会变成 /gradio/logout
                link="logout",
                variant="secondary"
            )
    
    # 页面加载时显示欢迎信息
    main_ui.load(show_welcome, None, welcome_msg)

    # ========== Tab 1: 添加物品 ==========
    with gr.Tab(label="📝 添加物品"):
        with gr.Row():
            # 左侧：输入表单
            with gr.Column():
                add_name = gr.Textbox(
                    label="物品名称*",
                    placeholder="例如：二手自行车"
                )
                _cats = category_config.get_categories()
                _default_cat = "书籍" if "书籍" in _cats else (_cats[0] if _cats else None)
                add_category = gr.Dropdown(
                    choices=_cats,
                    value=_default_cat,
                    multiselect=False,
                    label="物品分类*"
                )

                # 动态属性输入框（先创建占位，按类别显示/隐藏）
                _initial_props = _category_field_initial_props(_default_cat)
                dynamic_fields = [
                    gr.Textbox(
                        label=_initial_props[i]["label"],
                        visible=_initial_props[i]["visible"],
                    )
                    for i in range(MAX_DYNAMIC_FIELDS)
                ]

                add_desc = gr.Textbox(label="物品描述", placeholder="描述物品的状态、价格等", lines=3)
                add_address = gr.Textbox(label="物品地址", placeholder="例如：某某市某某区某某街道")
                add_contact = gr.Textbox(label="联系方式*", placeholder="例如：微信号、QQ号、手机号")
                add_image = gr.Image(label="物品图片（可选）", type="filepath")
                # C:\Users\Victor\AppData\Local\Temp\gradio\9276db2d12094d403b50fa0616889f4c0344535778c973500e676acfe2344928\1.jpeg
                add_btn = gr.Button(value="添加物品", variant="primary")
            
            # 右侧：操作结果和列表预览
            with gr.Column():
                add_output = gr.Textbox(label="操作结果", lines=2)
                gr.Markdown(value="**当前物品列表**")
                add_list = gr.HTML(value=get_items_list())
        
        # 绑定添加按钮事件
        add_btn.click(
            add_item,
            inputs=[add_name, add_category, add_desc, add_address, add_contact, add_image, *dynamic_fields],
            outputs=[
                add_output,
                add_list,
                add_name,
                add_category,
                add_desc,
                add_address,
                add_contact,
                add_image,
                *dynamic_fields,
            ]
        )

        # 类别变化时动态显示对应属性字段
        add_category.change(
            fn=_category_field_updates,
            inputs=[add_category],
            outputs=dynamic_fields,
        )
    
    # ========== Tab 2: 删除物品 ==========
    with gr.Tab(label="🗑️ 删除物品"):
        with gr.Row():
            # 左侧：删除操作
            with gr.Column():
                del_id = gr.Textbox(
                    label="物品ID",
                    placeholder="输入要删除的物品ID"
                )
                del_btn = gr.Button(value="删除物品", variant="stop")
            
            # 右侧：操作结果和列表
            with gr.Column():
                del_output = gr.Textbox(label="操作结果", lines=2)
                del_list = gr.HTML(
                    label="当前物品列表",
                    value=get_items_list()
                )
        
        # 绑定删除按钮事件
        del_btn.click(
            delete_item,
            inputs=[del_id],
            outputs=[del_output, del_list, del_id]
        )
    
    # ========== Tab 3: 物品列表 ==========
    with gr.Tab(label="📋 物品列表"):
        list_output = gr.HTML(value=get_items_list())
        refresh_btn = gr.Button("🔄 刷新列表")
        
        # 绑定刷新按钮事件
        refresh_btn.click(
            lambda: get_items_list(),
            outputs=[list_output]
        )
    
    # ========== Tab 4: 查找物品 ==========
    with gr.Tab(label="🔍 查找物品"):
        with gr.Row():
            # 左侧：搜索条件
            with gr.Column():
                search_keyword = gr.Textbox(
                    label="搜索关键词",
                    placeholder="输入物品名称或描述"
                )
                search_category = gr.Dropdown(
                    choices=["全部"] + category_config.get_categories(),
                    value="全部",
                    multiselect=True,
                    label="筛选分类"
                )
                search_btn = gr.Button(value="搜索", variant="primary")
            
            # 右侧：搜索结果
            with gr.Column():
                search_output = gr.HTML(value="搜索结果")

        # 绑定搜索按钮事件
        search_btn.click(
            search_items,
            inputs=[search_keyword, search_category],
            outputs=[search_output, search_keyword]
        )

    # ========== Tab 5: 用户审批（管理员） ==========
    with gr.Tab(label="✅ 用户审批 (管理员)", visible=False) as admin_tab:
        gr.Markdown("仅管理员可见：批准 pending 用户后才能登录主应用。")
        with gr.Row():
            with gr.Column(scale=1):
                approve_username = gr.Textbox(label="待批准用户名", placeholder="例如：new_user")
                approve_btn = gr.Button(value="批准用户", variant="primary")
                approve_msg = gr.Textbox(label="操作结果", lines=2)
            with gr.Column(scale=2):
                pending_list_html = gr.HTML(value=_render_pending_users_html())

        approve_btn.click(
            admin_approve_user,
            inputs=[approve_username],
            outputs=[approve_msg, pending_list_html, approve_username],
        )

    # ========== Tab 6: 物品类型管理（管理员） ==========
    with gr.Tab(label="🛠️ 物品类型管理 (管理员)", visible=False) as category_admin_tab:
        gr.Markdown("仅管理员可见：新增/修改物品类型（名称 + 属性定义）。默认读取 constants.py；保存后写入 category_config.json。")

        category_config_html = gr.HTML(value=_render_category_config_html())

        with gr.Row():
            with gr.Column(scale=1):
                cat_select = gr.Dropdown(
                    choices=category_config.get_categories(),
                    value=None,
                    label="选择要编辑的类型",
                )
                cat_name = gr.Textbox(label="修改类型名称", placeholder="例如：家具")
            with gr.Column(scale=2):
                cat_fields = gr.Textbox(
                    label="属性定义（JSON 数组）",
                    lines=10,
                    # value="[]",
                    placeholder='例如：[{"key":"brand","label":"品牌","required":false}]',
                )

        with gr.Row():
            cat_load_btn = gr.Button(value="加载选中类型", variant="secondary")
            cat_save_btn = gr.Button(value="保存（新增/更新）", variant="primary")
            cat_del_btn = gr.Button(value="删除类型", variant="stop")

        cat_msg = gr.Textbox(label="操作结果", lines=2)

        cat_load_btn.click(
            admin_category_load,
            inputs=[cat_select],
            outputs=[cat_msg, cat_select, cat_name, cat_fields],
        )

        cat_save_btn.click(
            admin_category_save,
            inputs=[cat_select, cat_name, cat_fields],
            outputs=[cat_msg, category_config_html, cat_select, cat_name, cat_fields, add_category, search_category],
        )

        cat_del_btn.click(
            admin_category_delete,
            inputs=[cat_select],
            outputs=[cat_msg, category_config_html, cat_select, cat_name, cat_fields, add_category, search_category],
        )

    # 页面加载后根据当前登录用户角色，决定是否显示管理员 Tab
    main_ui.load(
        _init_admin_tab,
        inputs=None,
        outputs=[admin_tab, pending_list_html],
    )

    # 页面加载后根据当前登录用户角色，决定是否显示物品类型管理 Tab
    main_ui.load(
        _init_category_tab,
        inputs=None,
        outputs=[category_admin_tab, category_config_html, cat_select],
    )

# 注册页面（无需登录），与主应用同进程同端口，通过 FastAPI 挂载在 /register
with gr.Blocks(title="物品复活平台 - 用户注册", css=custom_css) as register_page:
    gr.Markdown(value="# 📝 新用户注册")
    gr.Markdown(value="注册后默认进入待审批 (pending) 状态，管理员批准后才能登录主应用。")
    with gr.Row():
        with gr.Column():
            reg_username = gr.Textbox(label="用户名*", placeholder="至少 3 个字符")
            reg_password = gr.Textbox(label="密码*", type="password", placeholder="至少 6 个字符")
            reg_confirm = gr.Textbox(label="确认密码*", type="password", placeholder="再次输入密码")
            reg_contact = gr.Textbox(label="联系方式*", placeholder="手机号/QQ/微信等")
            reg_address = gr.Textbox(label="住址*", placeholder="例如：某某市某某区")
            reg_btn = gr.Button(value="注册", variant="primary")
        with gr.Column():
            reg_out = gr.Textbox(label="结果", lines=6)

    reg_btn.click(
        do_register,
        inputs=[reg_username, reg_password, reg_confirm, reg_contact, reg_address],
        outputs=[reg_out, reg_username, reg_password, reg_confirm, reg_contact, reg_address],
    )

# ==================== 应用启动入口 ====================

if __name__ == "__main__":
    """
    主程序入口
    
    功能说明:
        启动 Gradio Web 应用，配置服务器参数和认证方式
    
    配置说明:
        - share: 是否生成公网分享链接（False=仅本地访问）
        - allowed_paths: 允许访问的文件路径列表（用于图片显示）
        - auth: 用户认证函数
        - auth_message: 登录页面显示的提示信息
    
    访问地址:
        本地: http://127.0.0.1:7860
        公网: 需设置 share=True
    """
    try:
        # 挂载注册页（无需登录）
        gr.mount_gradio_app(
            app,
            register_page,
            path=REGISTER_PATH,
        )

        # 挂载主应用（需要登录）
        gr.mount_gradio_app(
            app,
            main_ui,
            path=MAIN_PATH,
            auth=authenticate,
            auth_message=(
                "🔐 请登录物品复活平台\n\n"
                "默认账号:\n用户名: admin 密码: admin123\n用户名: user1 密码: password1\n\n"
                "新用户请先打开 /register 进行注册；注册后需管理员批准才能登录。"
            ),
            # auth: If provided, username and password (or list of username-password tuples) required to access the gradio app. Can also provide function that takes username and password and returns True if valid login.
            # auth_message: If provided, HTML message provided on login page for this gradio app.
            allowed_paths=[IMAGE_DIR],
        )

        uvicorn.run(app, host="127.0.0.1", port=7861)
    except Exception:
        traceback.print_exc()
        input("程序发生严重错误，请截图发给开发者。按回车键退出...")