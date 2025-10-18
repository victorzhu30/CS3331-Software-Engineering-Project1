import gradio as gr

# 页面加载时显示欢迎信息
def show_welcome(request: gr.Request):
    username = request.username if hasattr(request, 'username') else "游客"
    return f"### 👋 欢迎回来，{username}！"