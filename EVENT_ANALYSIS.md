# AstrBot 事件类型对比分析

## 📋 事件实现情况

### ✅ 已实现的事件

| 事件类型 | 实现类 | 功能描述 | 实现文件 |
|---------|--------|---------|---------|
| 消息事件 | `WxHttpMessageEvent` | 继承自 `AstrMessageEvent`，处理私聊和群聊消息 | wxhttp_event.py |

#### 消息事件支持的功能：
- ✅ 私聊消息（文本、图片、语音、视频）
- ✅ 群聊消息（文本、图片、语音、视频）
- ✅ @机器人检测和响应
- ✅ 消息发送（文本、图片、语音）
- ✅ 消息引用回复（模拟实现）
- ✅ @提及发送

### ❌ 未实现的潜在事件类型

基于其他平台适配器的经验，以下事件可能对 AstrBot 有价值：

| 事件类型 | 优先级 | 说明 | 可能的实现方式 |
|---------|-------|------|--------------|
| 群成员加入事件 | ⭐⭐⭐⭐ | 检测新成员入群 | 需要 wxhttp 协议支持 MsgType 特定类型 |
| 群成员退出事件 | ⭐⭐⭐ | 检测成员退群 | 需要 wxhttp 协议支持 |
| 好友请求事件 | ⭐⭐⭐⭐ | 接收并处理好友请求 | 需要 wxhttp 提供好友验证接口 |
| 机器人被踢出群事件 | ⭐⭐⭐ | 机器人被管理员移出群聊 | 通过消息同步检测 |
| 管理员变动事件 | ⭐⭐ | 群管理员权限变化 | 需要 wxhttp 协议支持 |
| 消息撤回事件 | ⭐⭐⭐ | 检测消息被撤回 | 需要 wxhttp 提供撤回通知 |
| 群名称修改事件 | ⭐ | 群聊名称变更 | 低优先级 |
| 戳一戳事件 | ⭐⭐ | 接收拍一拍/戳一戳 | 需要协议支持 |
| 红包事件 | ⭐ | 红包消息通知 | 仅通知，不涉及领取 |
| 转账事件 | ⭐ | 转账消息通知 | 仅通知，不涉及收款 |

### 🔍 当前实现的消息类型支持

在 `convert_message` 方法中，我们支持以下 wxhttp MsgType：

```python
supported_types = {
    1,   # 文本消息
    3,   # 图片消息
    34,  # 语音消息
    43,  # 视频消息
    47,  # 表情消息（仅占位）
    49,  # 引用/分享消息（仅占位）
}
```

其他 MsgType（如系统通知、群成员变动等）目前会被忽略。

### 💡 扩展建议

#### 1. 优先实现：好友请求事件

```python
class WxHttpFriendRequestEvent(AstrBotEvent):
    """好友请求事件"""
    def __init__(self, request_wxid: str, verify_msg: str, ...):
        ...
    
    async def accept(self):
        """接受好友请求"""
        ...
    
    async def reject(self):
        """拒绝好友请求"""
        ...
```

#### 2. 次优先实现：群成员变动事件

```python
class WxHttpGroupMemberEvent(AstrBotEvent):
    """群成员变动事件"""
    event_type: str  # "join" | "leave" | "kick"
    group_id: str
    member_id: str
    operator_id: str  # 操作者（踢人场景）
```

#### 3. 消息撤回事件

```python
class WxHttpMessageRecallEvent(AstrBotEvent):
    """消息撤回事件"""
    message_id: str
    group_id: Optional[str]
    sender_id: str
```

### 🚧 实现限制

大多数高级事件的实现依赖于：

1. **wxhttp 协议支持**：需要 wxhttp 服务端提供相应的消息类型和接口
2. **API 文档**：需要了解特定事件对应的 MsgType 和数据结构
3. **测试环境**：需要实际环境测试事件触发和数据格式

### 📝 建议下一步

1. **调研 wxhttp 协议**：
   - 查看 `/Msg/Sync` 返回的完整 MsgType 列表
   - 确认是否有群成员变动、好友请求等系统通知

2. **日志监控**：
   - 启用 DEBUG 日志
   - 观察各类操作（入群、退群、添加好友）产生的 Sync 数据

3. **逐步扩展**：
   - 先实现日志记录，收集原始数据
   - 分析数据格式后再实现事件类

### 🔗 参考资源

- AstrBot 官方文档：https://github.com/Soulter/AstrBot
- wxhttp 协议文档：查看项目中的 `APIs调用日志/swagger.json`
- 其他平台适配器参考：QQ 官方 Bot、Telegram Bot 等

---

**总结**：当前实现专注于核心的消息收发功能，已经覆盖了 80% 的日常使用场景。其他事件类型的实现需要根据实际需求和 wxhttp 协议能力逐步添加。
