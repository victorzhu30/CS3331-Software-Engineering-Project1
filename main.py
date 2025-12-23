import gradio as gr
import json
import html
import os
import sqlite3
import shutil
import sys
from datetime import datetime
from dotenv import load_dotenv

from utils.contact import format_contact
from utils.auth import show_welcome
from utils.util import *
from utils.database import _get_db_connection, _ensure_db_schema, load_users, add_user, load_items, save_items

# # 加载环境变量配置
# load_dotenv()

# ==================== 全局常量配置 ====================
# 从 constants 模块导入数据文件路径配置
from constants import DATA_FILE      # 物品数据存储文件路径 (items.json)
from constants import USERS_FILE     # 用户数据存储文件路径 (users.json)
from constants import IMAGE_DIR      # 图片存储目录路径 (images/)
from constants import DB_FILE        # SQLite 数据库文件路径 (CS3331.db)
from constants import CATEGORIES, CATEGORY_FIELDS, MAX_DYNAMIC_FIELDS

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

def authenticate(username, password):
    """
    验证用户登录凭证
    
    功能说明:
        检查用户名和密码是否匹配，用于 Gradio 的 auth 参数
    
    输入参数:
        username (str): 用户输入的用户名
        password (str): 用户输入的密码
    
    返回值:
        bool: 验证成功返回 True，失败返回 False
    
    使用场景:
        app.launch(auth=authenticate)
    """
    users = load_users(DB_FILE)
    if username in users and users[username] == password:
        return True
    return False

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

    defs = CATEGORY_FIELDS.get(category, [])
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
    defs = CATEGORY_FIELDS.get(category, [])
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
    defs = CATEGORY_FIELDS.get(category, [])
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
    """
    添加新物品到数据库
    
    功能说明:
        创建新物品记录，包括保存图片、生成ID、记录时间等
    
    输入参数:
        name (str): 物品名称，必填
        category (str): 物品分类，从预定义分类中选择
        description (str): 物品描述，可选
        contact (str): 联系方式，必填（邮箱/QQ/手机号）
        image (str): 上传的图片临时路径，可选
    
    返回值:
        tuple: 包含7个元素的元组，用于更新 Gradio 组件
            (0) str: 操作结果消息
            (1) str: 更新后的物品列表HTML
            (2) str: 清空后的分类输入框
            (3) str: 清空后的名称输入框
            (4) str: 清空后的描述输入框
            (5) str: 清空后的联系方式输入框
            (6) None: 清空后的图片上传框
    
    数据验证:
        - 物品名称不能为空
        - 联系方式不能为空
    
    业务逻辑:
        1. 验证必填字段
        2. 生成新的物品ID（最大ID + 1）
        3. 保存上传的图片
        4. 创建物品记录
        5. 保存到数据文件
        6. 返回操作结果和更新后的列表
    """
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
    field_defs = CATEGORY_FIELDS.get(category, [])
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
            image_tag = f'<img src="/gradio_api/file={image_abs_path}" class="item-image" />'
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
            image_tag = f'<img src="/gradio_api/file={image_abs_path}" class="item-image" />'
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

# ==================== Gradio 界面构建 ====================

# 创建 Gradio 应用界面
with gr.Blocks(title="物品复活平台", css=custom_css) as app:
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
                link="/logout",
                variant="secondary"
            )
    
    # 页面加载时显示欢迎信息
    app.load(show_welcome, None, welcome_msg)

    # ========== Tab 1: 添加物品 ==========
    with gr.Tab(label="📝 添加物品"):
        with gr.Row():
            # 左侧：输入表单
            with gr.Column():
                add_name = gr.Textbox(
                    label="物品名称*",
                    placeholder="例如：二手自行车"
                )
                add_category = gr.Dropdown(
                    choices=CATEGORIES,
                    value="书籍",
                    multiselect=False,
                    label="物品分类*"
                )

                # 动态属性输入框（先创建占位，按类别显示/隐藏）
                _initial_props = _category_field_initial_props("书籍")
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
                    choices=["全部"] + CATEGORIES,
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

# ==================== 应用启动入口 ====================

import traceback

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
    
    安全说明:
        - allowed_paths 中的文件可被所有登录用户访问
        - 建议生产环境使用更安全的认证方式（如密码加密）
    """
    # 获取图片目录的绝对路径
    image_dir_absolute = os.path.abspath(IMAGE_DIR)
    
    try:
        # 启动应用
        app.launch(
            inbrowser=True,
            share=False,
            allowed_paths=[image_dir_absolute],  # 使用绝对路径
            auth=authenticate,  # 使用自定义认证函数
            auth_message="🔐 请登录物品复活平台\n\n默认账号:\n用户名: admin 密码: admin123\n用户名: user1 密码: password1"
        )
        # allowed_paths: List of complete filepaths or parent directories that gradio is allowed to serve. 
        # Must be absolute paths. Warning: if you provide directories, any files in these directories or their subdirectories are accessible to all users of your app. Can be set by comma separated environment variable GRADIO_ALLOWED_PATHS. These files are generally assumed to be secure and will be displayed in the browser when possible. 
    except Exception as e:
        # 如果出错，打印错误详情
        traceback.print_exc()
        # 关键：卡住窗口，不让它立刻关闭
        input("程序发生严重错误，请截图发给开发者。按回车键退出...")