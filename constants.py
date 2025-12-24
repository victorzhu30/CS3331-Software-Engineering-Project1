CATEGORIES = [
    "书籍", "数码", "居家", "食品", "美妆", 
    "票券", "衣饰", "鞋包", "运动", "文具", 
    "玩具", "乐器", "其他"
]

# 不同类别的“额外属性”配置（写死在代码里）
# 说明:
# - key: 类别名（需与 CATEGORIES 一致）
# - value: 字段列表；每个字段包含:
#   - key: 存储用字段名（写入 items.attributes 的 JSON）
#   - label: 页面展示名
#   - required: 是否必填（MVP 先做前端校验）
#
# 你可以按需继续扩展字段（例如 data_type/enum_options 等）。
CATEGORY_FIELDS = {
    "书籍": [
        {"key": "author", "label": "作者", "required": True},
        {"key": "publisher", "label": "出版社", "required": False},
    ],
    "数码": [
        {"key": "brand", "label": "品牌", "required": False},
        {"key": "model", "label": "型号", "required": False},
    ],
    "居家": [
        {"key": "material", "label": "材质", "required": False},
        {"key": "quantity", "label": "数量", "required": False},
    ],
    "食品": [
        {"key": "expiry_date", "label": "保质期", "required": True},
        {"key": "quantity", "label": "数量", "required": True},
    ],
    "美妆": [
        {"key": "brand", "label": "品牌", "required": False},
        {"key": "expiry_date", "label": "保质期", "required": False},
    ],
    "票券": [
        {"key": "valid_until", "label": "有效期", "required": False},
    ],
    "衣饰": [
        {"key": "size", "label": "尺码", "required": False},
    ],
    "鞋包": [
        {"key": "size", "label": "尺码", "required": False},
        {"key": "brand", "label": "品牌", "required": False},
    ],
    "运动": [
        {"key": "brand", "label": "品牌", "required": False},
    ],
    "文具": [
        {"key": "brand", "label": "品牌", "required": False},
    ],
    "玩具": [
        {"key": "age_range", "label": "适用年龄", "required": False},
    ],
    "乐器": [
        {"key": "brand", "label": "品牌", "required": False},
        {"key": "model", "label": "型号", "required": False},
    ],
    "其他": [],
}

# 动态属性输入框最多显示几个（管理员可配置类别字段；为避免 UI 字段不够用，这里设定一个固定上限）
# 注意：如果你希望允许更多字段，只需要调大这个值即可。
MAX_DYNAMIC_FIELDS = 10

DATA_FILE = "items.json"
USERS_FILE = "users.json" 
IMAGE_DIR = "images"
DB_FILE = "CS3331.db"