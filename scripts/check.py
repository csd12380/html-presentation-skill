#!/usr/bin/env python3
"""逐页截图自检脚本。

用法：
    python check.py <index.html路径> [页数]

- 用系统 Chrome 无头模式打开 index.html，逐页（#/1...#/N）截图到 _check/pNN.png
- 截图后由 Agent 用 ViewImage 逐张检查：溢出/错位/失衡/图片同化/文字可读性

Agent 看图自检的检查清单（每页必查）：
1. 溢出/错位：文字、图片是否超出容器或相互重叠
2. 失衡：左右/上下留白是否对称，有无大片空白或拥挤
3. 图片同化：图与背景是否"糊成一片"（图白底+页白底）
4. 文字可读性：**任何文字是否偏小/看不清**——图注、标签、页码、SVG 内文字尤其要查；发现"勉强能看清"就判不合格，须放大字号（见 references/视觉规范.md 字号下限）

依赖：playwright + 系统 Chrome。缺失时自动 pip install playwright（浏览器用 channel="chrome" 复用系统 Chrome，无需 playwright install）。
"""
import sys
import os
import subprocess

PY = r"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe"


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa
        return
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=False)


def main():
    html = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    os.makedirs("_check", exist_ok=True)
    abs_path = "file:///" + os.path.abspath(html).replace("\\", "/")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for i in range(1, pages + 1):
            # 先跳空白页强制重载，否则同一 file:// URL 只改 hash 不会重新加载，会一直停在首页
            pg.goto("about:blank")
            pg.goto(abs_path + "#/" + str(i))
            pg.wait_for_timeout(1600)
            pg.screenshot(path=f"_check/p{i:02d}.png")
        b.close()
    print(f"done: {pages} pages -> _check/")


if __name__ == "__main__":
    main()
