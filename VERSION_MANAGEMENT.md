# 版本管理说明

## 📌 版本信息集中管理

为了避免多处维护版本号，本插件采用**集中式版本管理**：

### 核心文件：`version.py`

所有版本相关的常量都定义在 [version.py](version.py) 中：

```python
__version__ = "0.1.3"
__author__ = "zq"
__description__ = "基于 wxhttp 协议的微信平台适配器..."
__repo__ = "https://github.com/zq/wxhttp_adapter"
ADAPTER_DISPLAY_NAME = "Webot 微信适配器"
LOGO_FILE = "logo.svg"
```

### 自动同步机制

1. **手动更新版本**：
   ```bash
   # 1. 编辑 version.py，修改 __version__ 等常量
   # 2. 运行同步脚本
   python3 sync_version.py
   ```

2. **自动读取版本**：
   - `wxhttp_platform_adapter.py` - 从 `version.py` 导入常量用于 `meta()` 方法
   - `main.py` - 从 `version.py` 导入版本信息用于文档
   - `metadata.yaml` - 通过 `sync_version.py` 自动生成

### 版本更新流程

```
┌─────────────┐
│ 修改        │
│ version.py  │
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ 运行             │
│ sync_version.py  │
└──────┬───────────┘
       │
       ▼
┌──────────────────────────┐
│ 自动更新 metadata.yaml   │
│ (AstrBot 插件系统识别)    │
└──────────────────────────┘
```

## 🔧 配置项统一管理

### UI 配置界面：`_conf_schema.json`

定义插件在 AstrBot WebUI 中的配置界面，包含：
- 配置项标题（中文）
- 输入提示（placeholder）
- 类型验证
- 默认值

### 运行时配置：`wxhttp_platform_adapter.py`

在 `@register_platform_adapter()` 装饰器中定义 `default_config_tmpl`，提供：
- YAML 格式的默认配置
- 详细的中文注释
- 配置项说明

## 📋 需要修改版本时

**只需两步**：

1. 编辑 [version.py](version.py)
   ```python
   __version__ = "0.2.0"  # 修改这里
   ```

2. 运行同步脚本
   ```bash
   python3 sync_version.py
   ```

**✅ 完成！** 所有文件的版本信息都会自动同步。

## ⚠️ 注意事项

- **不要手动编辑** `metadata.yaml` 的版本字段，它会被 `sync_version.py` 覆盖
- **版本号格式**：建议使用语义化版本 `major.minor.patch`（如 `0.1.3`, `1.0.0`）
- **更新后重启**：修改版本后需重启 AstrBot 才能在 WebUI 中看到新版本号
