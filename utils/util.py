import sys
import os


def get_resource_path(relative_path):
    """获取资源的绝对路径，兼容开发环境和打包后的环境"""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller 打包后的临时目录
        return os.path.join(sys._MEIPASS, relative_path)
    # 开发环境下的当前目录
    return os.path.join(os.path.abspath("."), relative_path)


def get_path_for_read(relative_path):
    """
    【读资源专用】
    获取资源文件的目录（兼容开发环境和打包后的临时目录）
    用来读：CSS, 图片, 默认配置
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    # print("__file__:", __file__) D:\数据库原理\物品复活\CS3331-Software-Engineering-Project1\utils\util.py
    # print("os.path.abspath(__file__):", os.path.abspath(__file__)) D:\数据库原理\物品复活\CS3331-Software-Engineering-Project1\utils\util.py
    # print(os.path.dirname(os.path.abspath("."))) D:\数据库原理\物品复活
    # print(os.path.abspath(".")) D:\数据库原理\物品复活\CS3331-Software-Engineering-Project1
    return os.path.join(os.path.abspath("."), relative_path)


def get_path_for_write(relative_path):
    """
    【写数据专用】
    获取 exe 所在的真实目录（用户能看到的目录）
    用来读写：数据库(.db), 日志(.log), 用户保存的文件
    """
    if getattr(sys, "frozen", False):
        # 如果是打包后的 exe，返回 exe 所在的文件夹
        return os.path.join(os.path.dirname(sys.executable), relative_path)
    # 如果是 py 代码运行，返回 main.py 所在的文件夹
    return os.path.join(os.path.abspath("."), relative_path)
