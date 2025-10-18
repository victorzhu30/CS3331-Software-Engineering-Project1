import gradio as gr
import json
import os
import shutil
from datetime import datetime
from dotenv import load_dotenv

from utils.contact import format_contact

load_dotenv()

# 数据存储文件
DATA_FILE = "items.json"
IMAGE_DIR = "images"

# 创建图片存储目录
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

# 物品分类
from constants import CATEGORIES

# 从文件中读取 CSS 内容
# 确保 style.css 和 app.py 文件在同一个目录下
with open("style.css", "r", encoding="utf-8") as f:
    custom_css = f.read()

# 初始化数据
def load_items():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) # 返回 list 或 dict 
    return []

def save_items(items):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        # ensure_ascii=False - 允许中文字符
        # indent=2 - 格式化缩进，便于阅读

# 保存图片
def save_image(image, item_id):
    """保存上传的图片，返回保存路径"""
    # 生成文件名：item_id_timestamp.jpg
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

# 删除图片
def delete_image(image_path):
    """删除物品对应的图片"""
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except:
            pass

# 添加物品
# 在 click 事件中返回空值来清空输入框。
def add_item(name, category, description, contact, image):
    print(f"Adding item: {name}, {category}, {description}, {contact}, {image}")
    if not name or not contact:
        return "❌ 物品名称和联系方式不能为空！", get_items_list(), name, category, description, contact, image
    
    items = load_items()
    new_id = max([item['id'] for item in items], default=0) + 1

    # 保存图片
    image_path = save_image(image, new_id) if image else None

    new_item = {
        "id": new_id,
        "name": name,
        "category": category,
        "description": description,
        "contact": contact,
        "image": image_path,
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    items.append(new_item)
    save_items(items)
    # 返回空字符串来清空输入框
    return f"✅ 成功添加物品：{name}", get_items_list(), "", None, "", "", None

# 删除物品
def delete_item(item_id):
    if not item_id:
        return "❌ 请输入要删除的物品ID！", get_items_list(), item_id
    
    items = load_items()
    try:
        item_id = int(item_id)
        # 查找要删除的物品
        item_to_delete = next((item for item in items if item['id'] == item_id), None)
        
        if not item_to_delete:
            return "❌ 物品ID不存在！", get_items_list(), item_id
        
        # 删除图片
        if item_to_delete.get('image'):
            delete_image(item_to_delete['image'])

        # 删除物品记录
        items = [item for item in items if item['id'] != item_id]
        save_items(items)
        
        return f"✅ 成功删除ID为 {item_id} 的物品", get_items_list(), ""
    except ValueError:
        return "❌ 物品ID必须是数字！", get_items_list(), item_id

# 显示物品列表 - 卡片式
def get_items_list():
    items = load_items()
    if not items:
        return "<div style='text-align: center; padding: 50px; color: #999;'>暂无物品信息</div>"
    
    display_cards_html = '<div class="items-container">'

    for item in items:
        # 图片处理
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
            image_tag = '<div class="item-image" style="background: #f5f5f5; display: flex; align-items: center; justify-content: center; color: #999;">暂无图片</div>'
        
        # 格式化联系方式
        contact_html = format_contact(item['contact'])

        display_cards_html += f"""
        <div class="item-card">
            {image_tag}
            <div class="item-category">🏷️ {item.get('category', '未分类')}</div>
            <div class="item-id">ID: {item['id']}</div>
            <div class="item-name">{item['name']}</div>
            <div class="item-desc">{item.get('description', '无描述')}</div>
            {contact_html}
            <div class="item-time">⏰ {item['create_time']}</div>
        </div>
        """
    
    display_cards_html += "</div>"
    return display_cards_html

# 查找物品 - 卡片式
def search_items(keyword, category_filter):
    items = load_items()
    if not category_filter:
        category_filter = "全部"
    
    # 分类筛选
    if isinstance(category_filter, str):
        if category_filter != "全部":
            items = [item for item in items if item.get('category') == category_filter]
    elif isinstance(category_filter, list):
        if "全部" not in category_filter:
            items = [item for item in items if item.get('category') in category_filter]
    
    # 关键词搜索
    if keyword:
        items = [item for item in items if keyword.lower() in item['name'].lower() 
                 or keyword.lower() in item.get('description', '').lower()]
    
    if not items:
        return "<div style='text-align: center; padding: 50px; color: #999;'>未找到相关物品</div>", ""
    
    # 复用卡片样式
    search_cards_html = f'<div class="search-header">找到 {len(items)} 个相关物品</div>' + '<div class="items-container">'
    
    for item in items:
        image_tag = ""
        if item.get('image') and os.path.exists(item['image']):
            image_abs_path = os.path.abspath(item['image'])
            image_tag = f'<img src="/gradio_api/file={image_abs_path}" class="item-image" />'
        else:
            image_tag = '<div class="item-image" style="background: #f5f5f5; display: flex; align-items: center; justify-content: center; color: #999;">暂无图片</div>'
        
        # 格式化联系方式
        contact_html = format_contact(item['contact'])

        search_cards_html += f"""
        <div class="item-card">
            {image_tag}
            <div class="item-category">🏷️ {item.get('category', '未分类')}</div>
            <div class="item-id">ID: {item['id']}</div>
            <div class="item-name">{item['name']}</div>
            <div class="item-desc">{item.get('description', '无描述')}</div>
            {contact_html}
            <div class="item-time">⏰ {item['create_time']}</div>
        </div>
        """
    
    search_cards_html += "</div>"
    return search_cards_html, ""

# 创建Gradio界面
with gr.Blocks(title="物品复活平台", css=custom_css) as app:
    gr.Markdown(value="# 🔄 物品复活平台")
    gr.Markdown(value="让闲置物品找到新主人！")
    
    with gr.Tab(label="📝 添加物品"):
        with gr.Row():
            with gr.Column():
                add_name = gr.Textbox(label="物品名称*", placeholder="例如：二手自行车")
                add_category = gr.Dropdown(
                    choices=CATEGORIES,
                    value="书籍",
                    multiselect=False,
                    label="物品分类*"
                )
                add_desc = gr.Textbox(label="物品描述", placeholder="描述物品的状态、价格等", lines=3)
                add_contact = gr.Textbox(label="联系方式*", placeholder="例如：微信号、QQ号、手机号")
                add_image = gr.Image(label="物品图片（可选）", type="filepath")
                # C:\Users\Victor\AppData\Local\Temp\gradio\9276db2d12094d403b50fa0616889f4c0344535778c973500e676acfe2344928\1.jpeg
                add_btn = gr.Button(value="添加物品", variant="primary")
            with gr.Column():
                add_output = gr.Textbox(label="操作结果", lines=2)
                gr.Markdown(value="**当前物品列表**")
                add_list = gr.HTML(value=get_items_list())
        
        add_btn.click(
            add_item, 
            inputs=[add_name, add_category, add_desc, add_contact, add_image], 
            outputs=[add_output, add_list, add_category, add_name, add_desc, add_contact, add_image]
        )
    
    with gr.Tab(label="🗑️ 删除物品"):
        with gr.Row():
            with gr.Column():
                del_id = gr.Textbox(label="物品ID", placeholder="输入要删除的物品ID")
                del_btn = gr.Button(value="删除物品", variant="stop")
            with gr.Column():
                del_output = gr.Textbox(label="操作结果", lines=2)
                del_list = gr.HTML(label="当前物品列表", value=get_items_list())
        
        del_btn.click(delete_item, inputs=[del_id], outputs=[del_output, del_list, del_id])
    
    with gr.Tab(label="📋 物品列表"):
        list_output = gr.HTML(value=get_items_list())
        refresh_btn = gr.Button("🔄 刷新列表")
        refresh_btn.click(lambda: get_items_list(), outputs=[list_output])
        # 匿名函数，点击时执行
        # - 无参数输入
        # - 调用 get_items_list() 获取最新物品列表
    
    with gr.Tab(label="🔍 查找物品"):
        with gr.Row():
            with gr.Column():
                search_keyword = gr.Textbox(label="搜索关键词", placeholder="输入物品名称或描述")
                search_category = gr.Dropdown(
                    choices=["全部"] + CATEGORIES,
                    value="全部",
                    multiselect=True,
                    label="筛选分类"
                )
                search_btn = gr.Button(value="搜索", variant="primary")
            with gr.Column():
                search_output = gr.HTML(value="搜索结果")

        search_btn.click(
            search_items, 
            inputs=[search_keyword, search_category], 
            outputs=[search_output, search_keyword]
        )

if __name__ == "__main__":
    image_dir_absolute = os.path.abspath(IMAGE_DIR)
    app.launch(
        share=False,
        allowed_paths=[image_dir_absolute]  # 使用绝对路径    
    )
    # allowed_paths: List of complete filepaths or parent directories that gradio is allowed to serve. 
    # Must be absolute paths. Warning: if you provide directories, any files in these directories or their subdirectories are accessible to all users of your app. Can be set by comma separated environment variable GRADIO_ALLOWED_PATHS. These files are generally assumed to be secure and will be displayed in the browser when possible. 