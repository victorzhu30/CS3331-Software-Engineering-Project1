# 物品复活平台 🔄

## 项目简介

物品复活平台是一个帮助大学生处理闲置物品的 Web 应用。许多大学生拥有一些觉得扔掉可惜、不处理又占地方的物品，通过这个平台，用户可以方便地发布、查找和交易闲置物品，让它们"复活"并找到新主人。

## 功能特性

### ✅ 已实现功能

1. **📝 添加物品**
   - 支持输入物品名称、分类、描述和联系方式
   - 支持上传物品图片
   - 自动生成物品 ID 和创建时间
   - 13 种物品分类：书籍、数码、居家、食品、美妆、票券、衣饰、鞋包、运动、文具、玩具、乐器、其他

2. **🗑️ 删除物品**
   - 通过物品 ID 删除物品信息
   - 自动删除关联的物品图片
   - 删除操作带有验证和错误提示

3. **📋 显示物品列表**
   - 卡片式展示所有物品
   - 显示物品图片、分类、描述、联系方式等完整信息
   - 响应式布局，自适应不同屏幕尺寸
   - 支持实时刷新

4. **🔍 查找物品**
   - 支持关键词搜索（物品名称和描述）
   - 支持按分类筛选
   - 支持组合查询（关键词 + 分类）
   - 搜索结果以卡片形式展示

5. **🎨 用户界面**
   - 基于 Gradio 框架的现代化 Web 界面
   - 响应式卡片布局
   - 自定义 CSS 样式
   - Tab 页面分离不同功能
   - 友好的交互提示

## 技术栈

- **后端框架**: Gradio
- **数据存储**: JSON 文件
- **图片处理**: shutil, os
- **样式**: 自定义 CSS (style.css)
- **配置管理**: python-dotenv

## 项目结构

```
CS3331-Software-Engineering-Project1/
├── main.py              # 主程序入口
├── constants.py         # 常量定义（物品分类等）
├── items.json           # 物品数据存储
├── style.css            # 自定义样式表
├── images/              # 物品图片存储目录
├── utils/               # 工具模块
│   └── database.py      # 数据库操作（待开发）
├── __pycache__/         # Python 缓存文件
├── .env                 # 环境变量配置
├── .gitignore           # Git 忽略文件
├── grammar.md           # Python 语法笔记
├── todo.md              # 待办事项
├── filepath_test.py     # 文件路径测试
├── display_test.py      # 显示功能测试
├── LICENSE              # 开源协议
└── README.md            # 项目说明文档
```

## 安装与运行

### 环境要求

- Python 3.13
- pip

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/victorzhu30/CS3331-Software-Engineering-Project1.git
cd CS3331-Software-Engineering-Project1
```

2. **安装依赖**

```bash
conda create -n item_revival python=3.13.5 -y
conda activate item_revival
pip install -r requirements.txt
```

3. **运行程序**

```bash
python main.py
```

4. **访问应用**

程序启动后，手动访问控制台显示的本地地址（通常是 `http://127.0.0.1:7860`）。如果启用了 `share=True`，还会生成一个公网分享链接。

## 使用指南

### 添加物品

1. 切换到"📝 添加物品"标签页
2. 填写物品名称（必填）
3. 选择物品分类
4. 填写物品描述
5. 填写联系方式（必填）
6. 上传物品图片（可选）
7. 点击"添加物品"按钮

### 删除物品

1. 切换到"🗑️ 删除物品"标签页
2. 在物品列表中找到要删除的物品 ID
3. 输入物品 ID
4. 点击"删除物品"按钮

### 查看物品列表

1. 切换到"📋 物品列表"标签页
2. 查看所有已发布的物品
3. 点击"🔄 刷新列表"获取最新数据

### 搜索物品

1. 切换到"🔍 查找物品"标签页
2. 输入搜索关键词（可选）
3. 选择物品分类（可选）
4. 点击"搜索"按钮

## 核心实现

### 数据存储

使用 JSON 文件存储物品信息，每个物品包含以下字段：

```json
{
    "id": 1,
    "name": "二手自行车",
    "category": "运动",
    "description": "Specialized 品牌",
    "contact": "18952050888",
    "image": "images/item_1_20251016_201104.jpg",
    "create_time": "2025-10-16 20:11:04"
}
```

### 图片管理

- 上传的图片自动保存到 `images/` 目录
- 文件名格式：`item_{id}_{timestamp}{ext}`
- 删除物品时自动清理关联图片
- 使用 Gradio 的文件访问机制展示图片

### 主要函数

- `load_items()`: 从 JSON 文件加载物品数据
- `save_items(items)`: 保存物品数据到 JSON 文件
- `add_item(name, category, description, contact, image)`: 添加新物品
- `delete_item(item_id)`: 删除指定物品
- `get_items_list()`: 生成物品列表 HTML
- `search_items(keyword, category_filter)`: 搜索物品

## 待实现功能

- [✅] 多标签检索 
- [ ] 用户身份认证(查看自己上传的物品)
- [ ] 迁移到 Flask/FastAPI 框架
- [ ] 使用 MySQL 数据库替代 JSON 文件
- [ ] 电话/邮箱自动识别并生成链接
- [ ] 物品编辑功能
- [ ] 物品状态管理（已售出/已赠送）

## 项目亮点

1. **现代化 UI**: 采用卡片式布局，视觉美观，用户体验好
2. **完整功能**: 实现了添加、删除、查看、搜索的完整闭环
3. **图片支持**: 支持物品图片上传和展示
4. **易于部署**: 单文件运行，无需复杂配置
5. **可扩展性**: 代码结构清晰，便于后续功能扩展

## 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发建议

1. Fork 本仓库
2. 创建新的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 许可证

本项目采用 Apache License 2.0 开源协议。详见 [LICENSE](LICENSE) 文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- GitHub Issues: [项目 Issues 页面](https://github.com/victorzhu30/CS3331-Software-Engineering-Project1/issues)
- GitHub: [@victorzhu30](https://github.com/victorzhu30)

**让闲置物品找到新主人，让资源得到更好的利用！** 🌟