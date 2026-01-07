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
    """同步版本信息到 metadata.yaml"""
    
    # metadata.yaml 内容模板
    metadata_content = f"""# 本文件的版本信息由 version.py 自动生成，请勿手动修改
# 若需更新版本号，请修改 version.py 文件后运行 sync_version.py

name: wxhttp_adapter
author: {__author__}
version: "{__version__}"
desc: "{__description__}"
repo: "{__repo__}"
"""
    
    # 写入 metadata.yaml
    script_dir = Path(__file__).parent
    metadata_file = script_dir / "metadata.yaml"
    
    with open(metadata_file, "w", encoding="utf-8") as f:
        f.write(metadata_content)
    
    print(f"✅ 已同步版本信息到 metadata.yaml")
    print(f"   版本: {__version__}")
    print(f"   作者: {__author__}")
    print(f"   仓库: {__repo__}")


if __name__ == "__main__":
    sync_metadata()
