#!/usr/bin/env python3
"""逐页截图自检 + 动效「可见性」验活。

用法：
    python check.py <index.html路径> [页数] [--no-motion]

- 用系统 Chrome 无头模式打开 index.html，逐页（#/1...#/N）截图到 _check/pNN.png
- 每页在入场动画结束后隔 2.0s 截两帧，比对像素差异
- 扫描每页 .ib-* 元素数量、种类、动画周期，找出「周期过长的假动效」
- 截图后由 Agent 用 ViewImage 逐张检查：溢出/错位/失衡/图片同化/文字可读性

三档判定（旧版只有「在动 / 静止」两档，会放过几乎看不见的微动）：
    ratio < 0.002          静止 ⚠        页面根本没动
    0.002 <= ratio < 0.012  微动不可见 ⚠   测得出但肉眼看不出，按不合格处理
    ratio >= 0.012          明显可见 ✅    通过

Agent 看图自检清单（每页必查）：
1. 溢出/错位：文字、图片是否超出容器或相互重叠
2. 失衡：左右/上下留白是否对称，有无大片空白或拥挤
3. 图片同化：图与背景是否糊成一片
4. 文字可读性：图注、标签、页码、SVG 内文字尤其要查
5. 动效观感：主运动是否明显到一眼能看见；只有装饰环 / 淡网格在动 = 不合格

依赖：playwright + pillow + 系统 Chrome。缺失时自动 pip install。
"""
import sys
import os
import io
import subprocess

PY = r"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe"
MOTION_DEAD = 0.002       # 低于此判静止
MOTION_WEAK = 0.012       # 低于此判「测得到但看不见」，仍不合格
SLOW_LIMIT = 30.0         # 动画周期上限（秒），超过就是假动效
GAP_MS = 2000             # 两帧间隔，贴近人眼观察窗


def ensure_deps():
    try:
        from playwright.sync_api import sync_playwright  # noqa
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=False)
    try:
        from PIL import Image  # noqa
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "-q"], check=False)


def diff_ratio(b1, b2):
    """两张 PNG 字节流的差异像素占比。"""
    from PIL import Image, ImageChops
    a = Image.open(io.BytesIO(b1)).convert("L")
    b = Image.open(io.BytesIO(b2)).convert("L")
    diff = ImageChops.difference(a, b)
    hist = diff.histogram()
    changed = sum(hist[7:])          # 灰度差 > 6 的像素才算"真的变了"
    return changed / float(a.width * a.height)


def scan_motion(pg):
    """读取当前页环境态元素数量、种类、最长周期。"""
    return pg.evaluate("""() => {
      const on = document.querySelector('.slide.on') || document.body;
      const els = [...on.querySelectorAll('[class*="ib-"]')];
      const kinds = new Set(), durations = [];
      for (const el of els) {
        for (const c of el.classList) if (c.startsWith('ib-')) kinds.add(c);
        const s = getComputedStyle(el);
        if (s.animationName && s.animationName !== 'none') {
          const d = parseFloat(s.animationDuration);
          if (!isNaN(d) && d > 0) durations.push(d);
        }
      }
      return {
        count: els.length,
        kinds: [...kinds],
        maxDur: durations.length ? Math.max(...durations) : 0,
        slow: durations.filter(d => d > 30).length
      };
    }""")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    motion = "--no-motion" not in sys.argv

    html = args[0] if args else "index.html"
    pages = int(args[1]) if len(args) > 1 else 12

    ensure_deps()
    from playwright.sync_api import sync_playwright

    os.makedirs("_check", exist_ok=True)
    abs_path = "file:///" + os.path.abspath(html).replace("\\", "/")
    results = []

    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        for i in range(1, pages + 1):
            # 先跳空白页强制重载，否则同一 file:// URL 只改 hash 不会重新加载
            pg.goto("about:blank")
            pg.goto(abs_path + "#/" + str(i))
            # 1900ms：入场动画跑完、环境态刚开始，此时两帧差异只来自环境态
            pg.wait_for_timeout(1900)
            first = pg.screenshot(path=f"_check/p{i:02d}.png")
            info = scan_motion(pg)
            if motion:
                pg.wait_for_timeout(GAP_MS)
                second = pg.screenshot()
                results.append((i, diff_ratio(first, second), info))
            else:
                results.append((i, None, info))
        b.close()

    print(f"done: {pages} pages -> _check/")
    if motion and results:
        print("\n页   ratio     判定            动效数/种类  最长周期")
        print("-" * 62)
        bad = []
        all_kinds = set()
        for i, r, info in results:
            all_kinds.update(info["kinds"])
            if r is None:
                flag = "(未验活)"
            elif r < MOTION_DEAD:
                flag = "静止 ⚠"
                bad.append((i, "静止"))
            elif r < MOTION_WEAK:
                flag = "微动不可见 ⚠"
                bad.append((i, "肉眼看不见"))
            else:
                flag = "明显可见 ✅"
            ratio_s = f"{r:.4f}" if r is not None else "  --  "
            slow_s = f"  ⚠ {info['slow']} 个周期>30s" if info["slow"] else ""
            print(f"p{i:02d}  {ratio_s}   {flag:<14}  {info['count']:>2}/{len(info['kinds']):<2}      {info['maxDur']:>5.1f}s{slow_s}")
            if info["count"] == 0:
                bad.append((i, "没有 .ib-* 元素"))
        print("-" * 62)
        print(f"全篇用到 {len(all_kinds)} 种环境态动效：{', '.join(sorted(all_kinds))}")
        if bad:
            print(f"\n{len(bad)} 项不合格：")
            for i, why in bad:
                print(f"  p{i:02d}  {why}")
            print("处理：每页配 3–4 个、其中至少一个 F 层强可见动效（.ib-beam / .ib-particles / "
                  ".ib-maskflow / .ib-edge / .ib-wave / .ib-orbit），并把周期压到 5–28s。")
            print("详见 references/环境态动效库.md")
        else:
            print("\n全部页面动效明显可见 ✅")


if __name__ == "__main__":
    main()
