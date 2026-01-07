# Webot 微信适配器 - 安装和使用指南

## 📋 目录

1. [系统要求](#系统要求)
2. [安装步骤](#安装步骤)
3. [配置说明](#配置说明)
4. [验证安装](#验证安装)
5. [常见问题](#常见问题)

## 🔧 系统要求

- **AstrBot** >= v4.0.0
- **Python** >= 3.10
- **wxhttp 服务** 已运行并可访问

## 📥 安装步骤

### 方法一：通过 AstrBot 插件市场安装（推荐）

1. 在 AstrBot WebUI 中打开"插件管理"
2. 搜索 "webot" 或 "wxhttp_adapter"
3. 点击"安装"按钮
4. 等待安装完成

### 方法二：通过命令行安装

```bash
# 方式1: 使用 astrbot 命令
astrbot plugin install https://github.com/ddfriday/webot

# 方式2: 手动克隆到插件目录
cd AstrBot/data/plugins
git clone https://github.com/ddfriday/webot wxhttp_adapter
```

### 方法三：手动安装

1. 下载插件代码
   ```bash
   cd AstrBot/data/plugins
   git clone https://github.com/ddfriday/webot wxhttp_adapter
   ```

2. 安装依赖（通常会自动安装）
   ```bash
   cd wxhttp_adapter
   pip install -r requirements.txt  # 如果有的话
   ```

3. 重启 AstrBot

## ⚙️ 配置说明

### 1. 获取必要信息

在配置之前，你需要准备以下信息：

- **wxhttp 服务地址**：通常是 `http://localhost:8057/api`
- **机器人微信ID**：你的微信账号的 wxid，例如 `wxid_xxxxxxxxx`

### 2. 编辑配置文件

打开 `data/config/astrbot.yml`，添加或修改以下内容：

```yaml
platform_adapters:
  - type: webot
    base_url: "http://localhost:8057/api"  # 替换为你的 wxhttp 服务地址
    wxid: "wxid_xxxxxxxxx"                 # 替换为你的微信ID
```

### 3. 可选配置

根据需要添加以下配置：

```yaml
platform_adapters:
  - type: webot
    base_url: "http://localhost:8057/api"
    wxid: "wxid_xxxxxxxxx"
    
    # 延时控制（模拟真人，防风控）
    api_request_delay_range: "0.5,2.0"    # API 请求随机延时 0.5-2.0 秒
    send_delay_range: "3.5,6.5"            # 消息发送随机延时 3.5-6.5 秒
    
    # 昵称黑名单（防骚扰）
    private_nickname_blacklist_keywords: "微信,wx,wechat,官方,客服"
    
    # 消息同步间隔
    poll_interval_sec: 1.5                 # 建议 1.0-2.0 秒
```

更多配置选项请参考 [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

### 4. 智谱识图配置（可选）

如果需要使用智谱等多模态 API，需要配置公网回调地址：

```yaml
# 全局配置（在 astrbot.yml 顶层）
callback_api_base: "https://your-domain.com"

# 智谱配置
providers:
  - type: zhipu_chat_completion
    api_key: "your-api-key"
    model: "glm-4v-plus"
```

## ✅ 验证安装

### 1. 检查插件是否加载

1. 打开 AstrBot WebUI
2. 进入"插件管理"页面
3. 查找 "Webot 微信适配器" 或 "wxhttp_adapter"
4. 确认状态为"已启用"

### 2. 检查日志

启动 AstrBot 后，查看日志：

```bash
# 查看日志文件
tail -f data/logs/astrbot.log

# 或在 WebUI 的"日志"页面查看
```

正常情况下，你应该看到类似以下的日志：

```
[INFO] [webot] API 请求延时: 0.5-2.0 秒
[INFO] [wxhttp] 请求队列工作线程启动（延时: 0.5-2.0s）
[INFO] wxhttp adapter started
[INFO] [webot] 消息发送延时: 3.5-6.5 秒
```

### 3. 发送测试消息

1. 使用另一个微信号给机器人发送消息
2. 查看 AstrBot 是否收到消息
3. 观察机器人是否正常回复

如果看到以下日志，说明消息收发正常：

```
[DEBUG] [wxhttp] → Msg/Sync 请求: {...}
[INFO] [wxhttp] ✓ Msg/Sync ← Code=0 (耗时 0.15s)
[INFO] [wxhttp] ✓ Msg/SendTxt ← Code=0 操作成功 (耗时 0.23s)
```

## ❓ 常见问题

### Q1: 插件在 WebUI 中不显示

**可能原因：**
- 插件目录位置不正确
- metadata.yaml 文件缺失或格式错误
- 插件代码有语法错误

**解决方法：**
1. 确认插件目录在 `data/plugins/wxhttp_adapter/`
2. 检查 `metadata.yaml` 文件是否存在
3. 查看 AstrBot 日志中的错误信息
4. 重启 AstrBot

### Q2: 配置项显示为空白或乱码

**可能原因：**
- `default_config_tmpl` 中的配置项没有正确注册
- 平台适配器注册失败

**解决方法：**
1. 检查 `wxhttp_platform_adapter.py` 中的 `@register_platform_adapter` 装饰器
2. 确认所有配置项都在 `default_config_tmpl` 中定义
3. 重新加载插件或重启 AstrBot

### Q3: 适配器无法启动

**可能原因：**
- `base_url` 或 `wxid` 配置错误
- wxhttp 服务未运行或无法访问

**解决方法：**
1. 检查 wxhttp 服务是否运行：
   ```bash
   curl http://localhost:8057/api/Msg/Sync -X POST -H "Content-Type: application/json" -d '{"Wxid":"test","Scene":0}'
   ```
2. 确认 `base_url` 配置正确（注意有没有 `/api` 后缀）
3. 确认 `wxid` 配置正确
4. 查看 AstrBot 日志中的错误信息

### Q4: 连续错误导致适配器停止

**错误信息：**
```
[ERROR] [webot] 连续 10 次轮询异常，插件终止运行
```

**可能原因：**
- wxhttp 服务中断或不稳定
- 网络连接问题

**解决方法：**
1. 检查 wxhttp 服务状态
2. 增加 `max_consecutive_errors` 配置值
3. 检查网络连接
4. 重启 wxhttp 服务和 AstrBot

### Q5: 消息收取延迟很高

**可能原因：**
- `poll_interval_sec` 设置过大

**解决方法：**
1. 减小 `poll_interval_sec`，建议设置为 1.0-1.5 秒
2. 确认 wxhttp 服务响应速度正常

### Q6: Logo 不显示

**可能原因：**
- logo 文件缺失或格式不对
- AstrBot 版本不支持 SVG 格式

**解决方法：**
1. 确认插件目录下有 `logo.svg` 文件
2. 如果 AstrBot 不支持 SVG，可以转换为 PNG：
   ```bash
   # 使用 ImageMagick 转换（如果已安装）
   convert logo.svg -resize 256x256 logo.png
   ```

### Q7: 智谱识图不工作

**可能原因：**
- 未配置 `callback_api_base`
- 公网地址无法访问
- 防火墙阻止访问

**解决方法：**
1. 确认配置了正确的 `callback_api_base`
2. 确保地址使用 HTTPS
3. 检查防火墙设置，开放 443 端口
4. 测试公网地址是否可访问

## 📚 更多资源

- [配置指南](CONFIG_GUIDE.md) - 详细的配置说明
- [更新日志](CHANGELOG.md) - 版本更新记录
- [事件分析](EVENT_ANALYSIS.md) - AstrBot 事件类型对比
- [GitHub 仓库](https://github.com/ddfriday/webot) - 源代码和问题反馈

## 💬 获取帮助

如果遇到问题：

1. 查看本文档的常见问题部分
2. 查看 AstrBot 官方文档
3. 在 GitHub 仓库提交 Issue
4. 加入 AstrBot 开发者 QQ 群：975206796

## 🔄 更新插件

### 通过 WebUI 更新

1. 打开 AstrBot WebUI
2. 进入"插件管理"页面
3. 找到 "Webot 微信适配器"
4. 点击"更新"按钮

### 手动更新

```bash
cd AstrBot/data/plugins/wxhttp_adapter
git pull
```

然后在 WebUI 中重载插件或重启 AstrBot。
