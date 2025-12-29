from astrbot.api.star import Context, Star


class WebotAdapterPlugin(Star):
    """Webot 微信平台适配器
    
    基于 wxhttp 协议的 AstrBot 微信平台适配器，支持消息收发和多模态功能。
    
    ## 使用说明
    
    请在 AstrBot 的平台配置中添加：
    
    ```yaml
    platform_adapters:
      - type: webot
        base_url: "http://your-wxhttp-server:8057/api"
        wxid: "wxid_your_bot_id"
        send_delay_range: "3.5,6.5"  # 可选：消息发送延时
    ```
    
    ## 功能特性
    
    - 支持私聊/群聊消息收发
    - 自动下载图片/语音/视频
    - 支持智谱等多模态大模型（自动生成图片公网 URL）
    - 明称黑名单功能（防止骚扰）
    - 消息发送延时（模拟真人回复）
    
    ## 注意事项
    
    - 请确保 wxhttp 服务器已正常运行
    - 如需使用多模态功能，请配置 `callback_api_base`
    
    ---
    
    **作者:** ddfriday  
    **版本:** 0.1.2  
    **仓库:** https://github.com/ddfriday/webot
    """
    
    def __init__(self, context: Context):
        # 导入以触发 @register_platform_adapter 装饰器注册
        from .wxhttp_platform_adapter import WxHttpPlatformAdapter  # noqa: F401
