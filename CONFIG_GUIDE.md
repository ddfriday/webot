# Webot 微信适配器 - 配置说明

## 📝 完整配置示例

```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    # === 必填配置 ===
    base_url: "http://localhost:8057/api"  # wxhttp 服务地址
    wxid: "wxid_xxxxxxxxx"                 # 机器人微信ID
    
    # === 消息同步配置 ===
    poll_interval_sec: 1.5       # 消息同步轮询间隔（秒），建议 1.0-2.0
    use_client_synckey: false    # 是否使用客户端同步键（高级功能）
    
    # === API 请求控制 ===
    # API 请求队列化延时配置（秒）
    # 格式："最小值,最大值"，例如 "0.5,2.0" 表示每次 API 请求前随机延时 0.5-2.0 秒
    # 留空或设为 "0,0" 则不延时（注：消息同步接口不受此影响）
    api_request_delay_range: "0.5,2.0"
    
    # === 昵称黑名单（过滤消息，不回复）===
    # 私聊：默认屏蔽昵称包含"微信 / wx / wechat"的联系人
    private_nickname_blacklist_keywords: "微信,wx,wechat"
    private_nickname_blacklist_regex: ""
    
    # 群聊：默认不启用（保持原有 @/主动触发逻辑）
    group_nickname_blacklist_keywords: ""
    group_nickname_blacklist_regex: ""
    
    # === 消息发送延时（模拟真人）===
    # 格式："最小值,最大值"，例如 "3.5,6.5" 表示每条消息发送前随机延时 3.5-6.5 秒
    # 留空或设为 "0,0" 则不延时
    send_delay_range: "3.5,6.5"
    
    # === 高级配置 ===
    max_consecutive_errors: 10   # 连续错误重试次数（达到后停止适配器）
```

## 📋 配置项详解

### 必填配置

| 配置项 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `base_url` | string | wxhttp 服务的 API 地址 | `http://localhost:8057/api` |
| `wxid` | string | 机器人的微信 ID | `wxid_xxxxxxxxx` |

### 消息同步配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `poll_interval_sec` | float | 1.5 | 消息同步轮询间隔（秒），建议 1.0-2.0，过快可能被限流 |
| `use_client_synckey` | boolean | false | 是否使用客户端同步键（高级功能，一般不需要） |

### API 请求控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `api_request_delay_range` | string | "" | API 请求延时范围，格式："最小值,最大值"（秒）<br>例如 "0.5,2.0" 表示每次请求前随机延时 0.5-2.0 秒<br>**注意**：消息同步接口不受此影响 |

**用途**：
- 防止 API 请求过快触发微信风控
- 模拟真人操作，降低封号风险
- 建议设置为 0.5-2.0 秒

### 昵称黑名单

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `private_nickname_blacklist_keywords` | string | "微信,wx,wechat" | 私聊黑名单关键词（逗号分隔），不区分大小写 |
| `private_nickname_blacklist_regex` | string | "" | 私聊黑名单正则表达式 |
| `group_nickname_blacklist_keywords` | string | "" | 群聊黑名单关键词（逗号分隔） |
| `group_nickname_blacklist_regex` | string | "" | 群聊黑名单正则表达式 |

**用途**：
- 过滤骚扰消息，不回复黑名单用户
- 私聊默认屏蔽昵称包含"微信"、"wx"、"wechat"的联系人
- 群聊默认不启用（保持原有 @/主动触发逻辑）

**示例**：
```yaml
# 屏蔽昵称包含"微信"、"官方"、"客服"的联系人
private_nickname_blacklist_keywords: "微信,官方,客服"

# 使用正则表达式屏蔽昵称符合特定模式的联系人
private_nickname_blacklist_regex: "^微信.*|.*官方.*|.*客服$"
```

### 消息发送延时

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `send_delay_range` | string | "" | 消息发送延时范围，格式："最小值,最大值"（秒）<br>例如 "3.5,6.5" 表示每条消息发送前随机延时 3.5-6.5 秒 |

**用途**：
- 模拟真人回复速度
- 避免消息发送过快被识别为机器人
- 建议设置为 3.0-6.0 秒

### 高级配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `max_consecutive_errors` | int | 10 | 连续错误重试次数，达到后自动停止适配器 |

## 🎯 推荐配置

### 基础配置（最小化）
```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
```

### 日常使用（推荐）
```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
    api_request_delay_range: "0.5,2.0"
    send_delay_range: "3.5,6.5"
```

### 高频使用（快速响应）
```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
    poll_interval_sec: 1.0
    api_request_delay_range: "0.2,1.0"
    send_delay_range: "1.0,3.0"
```

### 安全优先（降低风控风险）
```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
    poll_interval_sec: 2.0
    api_request_delay_range: "1.0,3.0"
    send_delay_range: "5.0,10.0"
    private_nickname_blacklist_keywords: "微信,wx,wechat,官方,客服"
```

## ⚠️ 注意事项

1. **base_url 和 wxid 必须正确配置**，否则适配器无法启动
2. **延时配置会影响响应速度**，请根据实际场景调整
3. **api_request_delay_range 和 send_delay_range 的区别**：
   - `api_request_delay_range`：控制所有 API 调用（发送消息、下载文件等）的延时
   - `send_delay_range`：额外的消息发送延时，两者会叠加
4. **消息同步不受延时配置影响**，保证消息接收实时性
5. **黑名单功能会在适配器层直接丢弃消息**，不会传递给 LLM 处理

## 🔍 常见问题

### Q: 配置了延时后，机器人响应变慢了？
A: 这是正常的。延时配置的目的就是模拟真人操作，避免被识别为机器人。如需快速响应，可以减小延时范围或设置为 "0,0"。

### Q: 如何关闭黑名单功能？
A: 将对应的配置项设置为空字符串即可：
```yaml
private_nickname_blacklist_keywords: ""
private_nickname_blacklist_regex: ""
```

### Q: 适配器显示连续错误并停止了？
A: 检查 wxhttp 服务是否正常运行，base_url 是否正确。可以增加 `max_consecutive_errors` 的值来提高容错性。

### Q: 消息收取延迟很高？
A: 检查 `poll_interval_sec` 配置，建议设置为 1.0-1.5 秒。
