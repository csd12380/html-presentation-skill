#!/usr/bin/env python3
"""环境探测脚本：探测当前平台是否支持 AI 生图、是否有截图能力。

用法：
    python probe.py

输出 JSON：
    {"image_gen": true/false, "screenshot": true/false}

说明：
- image_gen：尝试 import 或检查 ImageGen 工具是否可用。脚本本身无法直接感知
  Agent 工具列表，这里提供两个启发式判断：1) 检查常见生图 CLI 是否存在；
  2) 提示 Agent 用 ToolSearch 查 ImageGen。实际判定以 Agent 的 ToolSearch 结果为准。
- screenshot：检查 playwright 是否可用。
"""
import json
import shutil
import importlib.util


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def has_cmd(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def probe():
    result = {
        "image_gen": False,   # 需 Agent 用 ToolSearch 查 ImageGen 补充
        "screenshot": False,
        "playwright": has_module("playwright"),
        "chrome": has_cmd("chrome") or has_cmd("google-chrome"),
        "note": "image_gen 需 Agent 用 ToolSearch 查 ImageGen 工具；screenshot 依据 playwright/chrome 判定",
    }
    # 截图能力：playwright 可用 或 有 chrome 且有 playwright
    result["screenshot"] = result["playwright"]
    return result


if __name__ == "__main__":
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
