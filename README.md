# Webot - 微信平台适配器

<div align="center">

![Logo](logo.svg)

**基于 wxhttp 协议的 AstrBot 微信平台适配器**

[![Version](https://img.shields.io/badge/version-0.1.3-blue.svg)](https://github.com/ddfriday/webot)
[![AstrBot](https://img.shields.io/badge/AstrBot-v4.0+-green.svg)](https://github.com/Soulter/AstrBot)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](LICENSE)

</div>

## ✨ 功能特性

- 🚀 **消息收发** - 支持私聊/群聊文本、图片、语音、视频
- 🤖 **智能唤醒** - 群聊 @机器人自动响应
- 🖼️ **多模态支持** - 自动下载媒体文件，支持智谱等识图 API
- 🛡️ **黑名单过滤** - 昵称黑名单，防止骚扰消息
- ⏱️ **延时控制** - 模拟真人操作，降低风控风险
- 📊 **完整日志** - 详细的 API 调用日志，便于调试
- 🔄 **队列化请求** - 自动控制请求频率，避免触发限流

## 📦 快速开始

### 安装

```bash
# 通过 AstrBot 插件市场安装
astrbot plugin install https://github.com/ddfriday/webot

# 或手动安装
cd AstrBot/data/plugins
git clone https://github.com/ddfriday/webot wxhttp_adapter
```

### 基础配置

编辑 `data/config/astrbot.yml`：

```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"  # wxhttp 服务地址
    wxid: "wxid_xxxxxxxxx"                 # 机器人微信ID
```

### 完整配置示例

```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    # === 必填配置 ===
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
    
    # === 延时控制（模拟真人，防风控）===
    api_request_delay_range: "0.5,2.0"    # API 请求延时
    send_delay_range: "3.5,6.5"            # 消息发送延时
    
    # === 昵称黑名单（防骚扰）===
    private_nickname_blacklist_keywords: "微信,wx,wechat,官方"
    
    # === 高级配置 ===
    poll_interval_sec: 1.5                 # 消息同步间隔
    max_consecutive_errors: 10             # 最大连续错误次数
```

详细配置说明请参考 [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

## 🖼️ 智谱识图配置

如需使用智谱等多模态 API，需配置公网回调地址：

```yaml
# 全局配置
callback_api_base: "https://your-domain.com"

# 平台配置
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"

# 智谱配置
providers:
  - type: zhipu_chat_completion
    api_key: "your-api-key"
    model: "glm-4v-plus"
```

**工作原理：**
```
下载图片 → 注册到 AstrBot 文件服务 
→ 生成公网 URL (https://domain.com/api/file/{token})
→ 智谱 API 访问该 URL 进行识图
```

## 高级配置

### 昵称黑名单

```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
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

## 📚 更多文档

- [配置指南](CONFIG_GUIDE.md) - 详细的配置说明
- [安装指南](INSTALL_GUIDE.md) - 安装方法和故障排除
- [更新日志](CHANGELOG.md) - 版本更新记录
- [事件分析](EVENT_ANALYSIS.md) - 事件类型对比分析
- [版本管理](VERSION_MANAGEMENT.md) - 版本号统一管理说明

## License

MIT


