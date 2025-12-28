# WxHttp Adapter for AstrBot

基于 wxhttp 协议的 AstrBot 平台适配器，支持微信消息收发和多模态识图。

## 快速开始

### 安装

```bash
astrbot plugin install https://github.com/你的用户名/astrbot-wxhttp-adapter
```

### 配置

编辑 `data/config/astrbot.yml`:

```yaml
# 全局配置（智谱识图必需）
callback_api_base: "https://your-domain.com"

# 平台配置
platform_adapters:
  - type: wechatpadpro
    base_url: "http://wxhttp-server:8057/api"
    wxid: "wxid_your_bot_id"
```

## 功能特性

- ✅ 私聊/群聊文本收发
- ✅ 图片/语音/视频自动下载
- ✅ 智谱等识图 API 支持（自动生成公网 URL）
- ✅ 昵称黑名单（防骚扰）
- ✅ Docker 友好（无需修改核心代码）

## 智谱识图配置

```yaml
callback_api_base: "https://your-domain.com"  # 必须配置

providers:
  - type: zhipu_chat_completion
    api_key: "your-api-key"
    model: "glm-4v-plus"
```

**工作原理:** 下载图片 → 注册到 AstrBot 文件服务 → 生成 `https://domain.com/api/file/{token}` → 智谱 API 访问该 URL

## 高级配置

### 昵称黑名单

```yaml
platform_adapters:
  - type: wechatpadpro
    # 私聊黑名单（可选）
    private_nickname_blacklist_keywords: ["微信", "wx"]
    private_nickname_blacklist_regex: ""
    
    # 群聊黑名单（默认不启用）
    group_nickname_blacklist_keywords: []
```

### 媒体文件

- 存储路径: `data/temp/wxhttp_media/<wxid>/<YYYYMMDD>/<类型>/`
- 清理旧文件: `find data/temp/wxhttp_media -mtime +7 -delete`

## 常见问题

**识图失败？**
- 确保 `callback_api_base` 配置为公网 HTTPS 地址
- 检查防火墙开放 443 端口

**为什么要用 URL 而不是 base64？**
- 智谱 API 仅支持 URL 输入，OpenAI 两种都支持

## License

MIT


