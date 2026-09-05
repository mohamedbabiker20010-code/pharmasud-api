#!/usr/bin/env python3
"""Rendered responsive audit; run against a local/rehearsal PharmaSUD server."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.getenv("RESPONSIVE_BASE_URL", "http://127.0.0.1:8765")
ARTIFACTS = Path(os.getenv("RESPONSIVE_ARTIFACTS", "/tmp/pharmasud-responsive-artifacts"))
ARTIFACTS.mkdir(parents=True, exist_ok=True)

VIEWPORTS = {
    "320x568": (320, 568), "360x800": (360, 800), "375x667": (375, 667),
    "390x844": (390, 844), "393x852": (393, 852), "414x896": (414, 896),
    "430x932": (430, 932), "768x1024": (768, 1024), "820x1180": (820, 1180),
    "1024x1366": (1024, 1366), "1280x720": (1280, 720), "1366x768": (1366, 768),
    "1440x900": (1440, 900), "1920x1080": (1920, 1080),
}

PAGES = {
    "dashboard": "/dashboard", "pos": "/pos", "medicines": "/medicines",
    "medicine_form": "/medicine-form", "inventory": "/inventory",
    "batch_receive": "/batch-receive", "sales_history": "/sales-history",
    "reports_sales": "/reports-sales", "reports_profits": "/reports-profits",
    "slow_moving": "/reports-slow-moving", "purchase_forecast": "/reports-purchase-forecast",
    "employees": "/employees", "settings": "/settings", "alerts": "/alerts",
    "stocktake": "/stocktake", "audit_log": "/audit-log",
}

SCREENSHOT_PAGES = {"dashboard", "pos", "medicines", "inventory", "employees", "settings", "reports_sales"}
SCREENSHOT_SIZES = {"390x844", "430x932", "768x1024", "1366x768", "1920x1080"}

def run():
    failures, measurements = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.getenv(
                "PLAYWRIGHT_CHROMIUM_EXECUTABLE",
                "/home/lenovo/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome",
            ),
        )
        context = browser.new_context(locale="ar-SA")
        context.add_init_script("""
          localStorage.setItem('token','responsive-layout-token');
          localStorage.setItem('role','admin');
          localStorage.setItem('userName','اسم مستخدم طويل لاختبار الاستجابة');
        """)
        page = context.new_page()
        page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(BASE) else route.abort())
        for size, (width, height) in VIEWPORTS.items():
            page.set_viewport_size({"width": width, "height": height})
            for name, path in PAGES.items():
                response = page.goto(BASE + path, wait_until="domcontentloaded", timeout=15000)
                if not response or response.status >= 400:
                    failures.append(f"{name}@{size}:HTTP_{response.status if response else 'NONE'}")
                    continue
                measure = page.evaluate("""() => {
                  const root=document.documentElement;
                  const visible=[...document.querySelectorAll('body *')].filter(e=>{
                    const s=getComputedStyle(e),r=e.getBoundingClientRect();
                    return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0;
                  });
                  const offenders=visible.filter(e=>{
                    const r=e.getBoundingClientRect();
                    const localScroll=['auto','scroll'].includes(getComputedStyle(e.parentElement||e).overflowX);
                    return !localScroll && (r.left < -1 || r.right > root.clientWidth + 1);
                  }).slice(0,5).map(e=>e.tagName+'.'+e.className);
                  return {client:root.clientWidth,scroll:root.scrollWidth,offenders};
                }""")
                measurements.append({"page": name, "viewport": size, **measure})
                if measure["scroll"] > measure["client"]:
                    failures.append(f"{name}@{size}:OVERFLOW_{measure['scroll']-measure['client']}:{measure['offenders']}")
                if name == "medicines":
                    add = page.locator("a", has_text="إضافة دواء").first
                    if not add.is_visible():
                        failures.append(f"medicines@{size}:ADD_ACTION_HIDDEN")
                    else:
                        box=add.bounding_box()
                        if not box or box["x"] < -1 or box["x"]+box["width"] > width+1:
                            failures.append(f"medicines@{size}:ADD_ACTION_CLIPPED")
                if size in SCREENSHOT_SIZES and name in SCREENSHOT_PAGES:
                    page.screenshot(path=str(ARTIFACTS/f"{name}-{size}.png"), full_page=True)

        # A realistic long-content medicine card must remain contained on iPhone width.
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE + "/medicines", wait_until="domcontentloaded")
        page.locator(".med-grid").evaluate("""grid => {
          grid.innerHTML = `<article class="med-card"><div class="card-content">
            <div class="med-name">اسم دواء طويل جداً لاختبار عدم تمدد البطاقة خارج شاشة الهاتف</div>
            <div class="med-category">تصنيف دوائي طويل للاختبار</div>
            <button class="btn">تعديل</button></div></article>`;
        }""")
        card = page.locator(".med-card").first.bounding_box()
        edit = page.get_by_role("button", name="تعديل").bounding_box()
        if not card or card["x"] < 0 or card["x"] + card["width"] > 391:
            failures.append("medicines@390x844:STRESS_CARD_CLIPPED")
        if not edit or edit["x"] < 0 or edit["x"] + edit["width"] > 391:
            failures.append("medicines@390x844:EDIT_ACTION_CLIPPED")

        # Direction switching must not introduce page-level overflow.
        for direction in ("rtl", "ltr"):
            for width, height in ((390, 844), (1366, 768)):
                page.set_viewport_size({"width": width, "height": height})
                page.goto(BASE + "/medicines", wait_until="domcontentloaded")
                page.evaluate("d => document.documentElement.dir = d", direction)
                dims = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                if dims[0] > dims[1]:
                    failures.append(f"medicines@{width}x{height}:{direction.upper()}_OVERFLOW")

        # Verify the real mobile drawer opens inside the viewport and fully dismisses.
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(BASE + "/dashboard", wait_until="domcontentloaded")
        page.evaluate("""() => {
          document.querySelector('.sidebar').classList.add('mobile-open');
          document.body.classList.add('mobile-drawer-open');
        }""")
        page.wait_for_timeout(400)
        sidebar = page.locator(".sidebar").bounding_box()
        if not sidebar or sidebar["x"] < 0 or sidebar["x"] + sidebar["width"] > 391:
            failures.append("dashboard@390x844:SIDEBAR_OPEN_CLIPPED")
        page.evaluate("""() => {
          document.querySelector('.sidebar').classList.remove('mobile-open');
          document.body.classList.remove('mobile-drawer-open');
        }""")
        page.wait_for_timeout(400)
        if page.locator(".sidebar").is_visible():
            failures.append("dashboard@390x844:SIDEBAR_NOT_DISMISSED")

        # Modal containment at the narrowest supported viewport.
        page.set_viewport_size({"width": 320, "height": 568})
        page.goto(BASE + "/employees", wait_until="domcontentloaded")
        modal = page.locator(".modal").first
        if modal.count():
            page.evaluate("""() => { const o=document.querySelector('.modal-overlay'); if(o)o.classList.add('open'); }""")
            box=modal.bounding_box()
            if box and (box["x"] < 0 or box["x"]+box["width"] > 320 or box["height"] > 568):
                failures.append("employees@320x568:MODAL_OUTSIDE_VIEWPORT")
        browser.close()
    (ARTIFACTS/"measurements.json").write_text(json.dumps(measurements,ensure_ascii=False,indent=2))
    print(f"RESPONSIVE_ASSERTIONS={len(measurements)}")
    print(f"SCREENSHOTS={len(list(ARTIFACTS.glob('*.png')))}")
    print(f"FAILURES={len(failures)}")
    for failure in failures: print("FAIL="+failure)
    raise SystemExit(1 if failures else 0)

if __name__ == "__main__":
    run()
