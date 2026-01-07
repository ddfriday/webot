# 更新日志

## 2026-01-07 - 核心优化

### ✨ 新功能

1. **统一请求日志记录**
   - 所有 API 请求现在都有详细的日志记录
   - 记录内容：请求开始、结束、耗时、参数、返回值
   - 日志级别：DEBUG（请求详情）、INFO（结果摘要）、ERROR（错误信息）
   
   示例日志输出：
   ```
   [wxhttp] → Msg/SendTxt 请求: {"Content": "你好", "ToWxid": "xxx"...}
   [wxhttp] ✓ Msg/SendTxt ← Code=0 操作成功 (耗时 0.23s)
   ```

2. **API 请求队列化机制**
   - 除消息同步接口外，所有 API 请求进入队列顺序处理
   - 支持随机延时配置，模拟真人操作
   - 防止请求过快触发微信风控

3. **独立的消息同步间隔**
   - `poll_interval_sec`：控制消息同步接口的轮询间隔
   - `api_request_delay_range`：控制其他 API 请求的延时范围
   - 两者互不干扰，保证消息接收实时性

### 🔧 配置说明

```yaml
# 在 astrbot.yml 的 platform_adapters 中配置:
  - type: wxhttp_webot
    base_url: "http://wxhttp-server:8057/api"
    wxid: "wxid_your_bot_id"
    
    # 消息同步轮询间隔（秒）
    poll_interval_sec: 1.5
    
    # API 请求队列延时范围（秒）
    # 格式："最小值,最大值"，例如 "0.5,2.0" 表示每次 API 请求前随机延时 0.5-2.0 秒
    # 留空或设为 "0,0" 则不延时
    # 注：消息同步接口 (sync) 不受此配置影响
    api_request_delay_range: "0.5,2.0"
    
    # 消息发送延时范围（秒）- 保持原有功能
    send_delay_range: "3.5,6.5"
    
    # 连续错误重试次数（可选，默认 10）
    max_consecutive_errors: 10
```

### 📊 架构改进

**改进前：**
```
所有 API 请求 → 直接调用
├─ 无统一日志
├─ 无延时控制
└─ sync 和其他 API 混在一起
```

**改进后：**
```
消息同步 (sync)
  ↓ poll_interval_sec
直接调用（保证实时性）
  ↓
统一日志记录

其他 API 请求
  ↓
进入队列
  ↓ api_request_delay_range
随机延时
  ↓
顺序执行
  ↓
统一日志记录
```

### 🎯 优势

1. **可观测性提升**：详细的请求日志便于排查问题
2. **风控友好**：随机延时模拟真人操作，降低封号风险
3. **性能监控**：每个请求都记录耗时，便于性能优化
4. **灵活配置**：消息接收和API调用延时独立控制

### ⚠️ 注意事项

- `api_request_delay_range` 仅影响发送消息、下载文件等主动 API 调用
- `poll_interval_sec` 仅影响消息同步轮询频率
- 设置过大的延时会影响消息发送速度，建议根据实际场景调整
- 建议 `api_request_delay_range` 设置为 0.5-2.0 秒，`send_delay_range` 设置为 3.0-6.0 秒

### 🔍 调试建议

启用 DEBUG 日志查看详细的 API 调用信息：
```yaml
# astrbot.yml
log_level: DEBUG
```

查看日志示例：
```
[wxhttp] → Msg/SendTxt 请求: {"Content": "测试消息", ...}
[wxhttp] 队列延时 1.23s 后发送 Msg/SendTxt
[wxhttp] ✓ Msg/SendTxt ← Code=0 操作成功 (耗时 0.45s)
```
