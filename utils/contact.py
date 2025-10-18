import re

# 识别联系方式类型并生成对应的 HTML
def format_contact(contact):
    """识别联系方式类型并返回格式化的 HTML"""
    contact = contact.strip()
    
    # 判断是否为邮箱
    # 协议: mailto:
    # 原理: 当一个 <a> 标签的 href 属性以 mailto: 开头时，浏览器会调用操作系统默认的邮件客户端（如 Windows 的邮件、Outlook 或 Foxmail），并自动将 mailto: 后面的地址填入收件人。
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.match(email_pattern, contact):
        return f'''
        <div class="contact-info">
            <a href="mailto:{contact}" class="contact-link email" title="发送邮件">
                📧 {contact}
            </a>
            <span class="copy-hint">(推荐使用Outlook)</span>
        </div>
        '''
    
    # 判断是否为手机号（11位数字）
    # 协议: tel:
    # 原理: tel: 协议主要用于移动设备。在手机上点击一个 tel: 链接，会直接跳转到拨号界面，并将号码预填写好。在桌面上，行为则不统一，可能会提示用 Skype 或其他网络电话应用打开。
    phone_pattern = r'^1[3-9]\d{9}$'
    if re.match(phone_pattern, contact):
        return f'''
        <div class="contact-info">
            <a href="tel:{contact}" class="contact-link phone" title="拨打电话">
                📞 {contact}
            </a>
        </div>
        '''
    
    # 判断是否为QQ号（5-11位数字）
    # 协议: tencent:// (这是 QQ 的私有协议)
    # 原理: 如果用户的电脑上安装了 QQ，点击这个链接就会唤起 QQ 客户端，并打开与指定 QQ 号码的临时聊天窗口。如果没安装，则无反应。
    # HTML 示例: <a href="tencent://message/?uin=123456789&Site=item_revival&Menu=yes">点击与 QQ:123456789 聊天</a>
    # uin 后面跟的是 QQ 号。Site 和 Menu 是附加参数，可以保留。
    qq_pattern = r'^\d{5,11}$'
    if re.match(qq_pattern, contact):
        return f'''
        <div class="contact-info">
            <a href="tencent://message/?uin={contact}&Site=&Menu=yes" class="contact-link qq" title="通过QQ联系">
                💬 QQ: {contact}
            </a>
            <span class="copy-hint">(点击打开QQ，需安装客户端)</span>
        </div>
        '''
    
    # 其他情况（微信号等）
    return f'''
    <div class="contact-info">
        <span class="contact-text">
            📱 {contact}
        </span>
    </div>
    '''