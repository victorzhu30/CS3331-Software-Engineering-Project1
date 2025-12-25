"""
文件目的: 用户认证与欢迎信息显示模块
作者: victorzhu30
创建日期: 2025-10-16

功能描述:
    处理用户登录后的欢迎信息显示
    从 Gradio Request 对象中提取用户信息
    配合 app.load() 实现页面加载时的个性化欢迎
"""

import gradio as gr


# ==================== 用户界面功能 ====================


def show_welcome(request: gr.Request):
    """
    在页面加载时显示欢迎信息

    功能说明:
        从 Gradio 的 Request 对象中提取当前登录用户名
        生成个性化的欢迎消息（Markdown 格式）

    输入参数:
        request (gr.Request): Gradio 自动传递的请求对象，包含:
                             - username: 登录用户名（需启用 auth）
                             - client: 客户端信息（IP等）
                             - headers: HTTP 请求头

    返回值:
        str: Markdown 格式的欢迎消息

    使用场景:
        配合 app.load() 使用，在页面加载时自动执行:

    注意事项:
        - 只有在 app.launch(auth=...) 启用认证后，request.username 才有值
        - 使用 hasattr() 检查属性存在，避免未启用认证时报错
    """
    # 安全获取用户名（如果未启用认证则显示"游客"）
    username = request.username if hasattr(request, "username") else "游客"

    # 返回 Markdown 格式的欢迎消息
    return f"### 👋 欢迎回来，{username}！"
