#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动同步 version.py 中的版本信息到 metadata.yaml

运行此脚本后，metadata.yaml 会自动更新为 version.py 中定义的版本号、作者、描述等信息
"""

import os
import sys
from pathlib import Path

# 确保可以导入 version 模块
sys.path.insert(0, str(Path(__file__).parent))

from version import __version__, __author__, __description__, __repo__


def sync_metadata():
    """同步版本信息到 metadata.yaml（仓库根目录和插件目录）"""
    
    # metadata.yaml 内容模板
    metadata_content = f"""# Webot 微信平台适配器元数据
# 基于 wxhttp 协议的 AstrBot 平台适配器

name: wxhttp_adapter
author: {__author__}
version: "{__version__}"
desc: "{__description__}"
repo: "{__repo__}"
"""
    
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent  # 仓库根目录
    
    # 1. 同步到仓库根目录的 metadata.yaml（AstrBot 加载插件时需要）
    root_metadata = repo_root / "metadata.yaml"
    with open(root_metadata, "w", encoding="utf-8") as f:
        f.write(metadata_content)
    print(f"✅ 已同步版本信息到根目录: {root_metadata}")
    
    # 2. 同步到插件目录的 metadata.yaml（备份，保持一致性）
    plugin_metadata = script_dir / "metadata.yaml"
    with open(plugin_metadata, "w", encoding="utf-8") as f:
        f.write(metadata_content)
    print(f"✅ 已同步版本信息到插件目录: {plugin_metadata}")
    
    print(f"\n📦 版本信息:")
    print(f"   版本: {__version__}")
    print(f"   作者: {__author__}")
    print(f"   仓库: {__repo__}")


if __name__ == "__main__":
    sync_metadata()
