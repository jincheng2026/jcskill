"""发布后建档和抓数据的脚本：建档案、认平台作品、用 TikHub 抓 12 小时和 7 天的数据和评论、写复盘、列出到点没抓的。

只用 Python 3.8 以上自带的模块，不用 pip 装任何东西。入口是 scripts/stats.py。
tikhub.py、platforms.py、text.py 来自同一作者的 jincheng2026/jincheng-workbench 仓库（MIT 许可），
在 skills/jincheng-workbench-research/scripts/research_kit/ 里，那边已经对着真实返回测过；这里只改了提示文字和测试用的环境变量。
"""


class UserError(Exception):
    """能直接说给用户听的错误：原因和怎么办都写在消息里，命令行只打印消息、不打印报错堆栈。"""

    exit_code = 2


class NeedsAgreement(UserError):
    """要先问用户、用户在对话里明确同意才能继续（花钱超过默认上限、小红书接口）。"""

    exit_code = 3
