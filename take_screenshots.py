"""截取 GEO MVP 各页面截图：首页直达，子页通过点击侧边栏导航（URL 直达中文页名会 404）"""
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8501"
NAV = [
    ("01-home", None),
    ("02-testset", "测试集"),
    ("03-collect", "采集"),
    ("04-dashboard", "看板"),
    ("05-advisory", "GEO建议"),
    ("06-report", "报告导出"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1150})
    page.goto(BASE, wait_until="networkidle")
    time.sleep(8)
    for name, link in NAV:
        if link:
            page.get_by_test_id("stSidebar").get_by_text(link, exact=True).click()
            time.sleep(8)  # 切页 + websocket 渲染 + plotly 绘制
        txt_len = page.evaluate(
            "() => (document.querySelector('section.main')||document.body).innerText.length"
        )
        page.screenshot(path=f"docs/screenshots/{name}.png", full_page=False)
        print(f"{name} done, text_len={txt_len}")
    browser.close()
print("ALL_SHOTS_DONE")
