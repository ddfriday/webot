from astrbot.api.star import Context, Star


class WebotAdapterPlugin(Star):
    """webot 平台适配器 - 基于 wxhttp 协议的微信适配器
    
    作者: ddfriday
    版本: 0.1.1
    """
    
    def __init__(self, context: Context):
        # 导入以触发 @register_platform_adapter 装饰器注册
        from .wxhttp_platform_adapter import WxHttpPlatformAdapter  # noqa: F401
