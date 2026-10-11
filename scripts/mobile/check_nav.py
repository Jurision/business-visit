import time, os
from playwright.sync_api import sync_playwright
O=os.environ["O"]; URL=os.environ.get("URL","http://127.0.0.1:8731/travel/")
os.makedirs(O, exist_ok=True)
UA="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
res=[]
def rec(n,ok,note=""): res.append(ok); print(("PASS " if ok else "FAIL ")+n+(" — "+note if note else ""))
def tap_visible(pg, selector):
    loc=pg.locator(selector)
    loc.wait_for(state="visible", timeout=3000)
    if selector == "#jumpPill":
        box = loc.bounding_box()
        pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    else:
        loc.tap()
    time.sleep(1)
with sync_playwright() as p:
    b=p.chromium.launch(channel="chrome")
    pg=b.new_context(viewport={"width":428,"height":926},device_scale_factor=3,is_mobile=True,has_touch=True,user_agent=UA).new_page()
    pg.goto(URL,wait_until="domcontentloaded"); pg.evaluate("localStorage.clear()"); pg.reload(wait_until="load"); time.sleep(1)
    rec("10/13新路线首屏为11天，页面顶部不显示跳转按钮", pg.locator("#jumpPill").is_hidden() and "11日行程" in pg.inner_text("#heroTitle") and "10月13日" in pg.inner_text("#heroDates"))
    pg.screenshot(path=O+"/p-fold.png")
    pg.evaluate("window.scrollTo({top:document.getElementById('timeLedger').getBoundingClientRect().top+scrollY-20,behavior:'instant'})"); time.sleep(.4)
    pg.wait_for_function("()=>{const e=document.getElementById('jumpPill'),r=e.getBoundingClientRect();return !e.hidden&&r.width>0&&r.height>0}")
    rec("滚到总览后出现“↓ 每日安排”", pg.locator("#jumpPill").is_visible() and "每日" in pg.inner_text("#jumpPill"))
    tap_visible(pg, "#jumpPill")
    pg.wait_for_function("()=>{const top=dayCard.getBoundingClientRect().top,h=railWrap.getBoundingClientRect().height;return top>=h&&top<=h+30}")
    top=pg.evaluate("dayCard.getBoundingClientRect().top")
    rail_height=pg.locator("#railWrap").bounding_box()["height"]
    rec("点“↓ 每日安排”滚到当天卡片，按钮变成“↑ 总览”", rail_height<=top<=rail_height+30 and "总览" in pg.inner_text("#jumpPill"), "cardTop=%d"%top)
    pg.screenshot(path=O+"/p-day.png")
    tap_visible(pg, "#jumpPill")
    rec("点“↑ 总览”回到总览", 0<=pg.evaluate("overview.getBoundingClientRect().top")<120)
    pg.screenshot(path=O+"/p-overview.png")
    pg.evaluate("scrollTo(0,0)"); time.sleep(.3)
    tap_visible(pg, "#adjustTop")
    rec("顶部“调整”进入调整模式并滚到时间条，变化条未改动时不出现", pg.evaluate("overview.classList.contains('editing')") and pg.inner_text("#adjustTop")=="完成" and pg.locator("#changeBar").is_hidden())
    pg.evaluate("document.querySelector('[data-mode=\"xggz:hsr\"]').scrollIntoView({block:'center'})"); time.sleep(.3)
    tap_visible(pg, '#phaseRail .modes [data-mode="xggz:hsr"]')
    rec("切换后出现变化条，跳转按钮让到变化条上方", pg.locator("#changeBar").is_visible() and pg.locator("#jumpPill").bounding_box()["y"]+42 < pg.locator("#changeBar").bounding_box()["y"]+2)
    pg.screenshot(path=O+"/p-edit-change.png")
    pg.evaluate("localStorage.clear()")
    b.close()
print("TOTAL",len(res),"FAIL",res.count(False))
raise SystemExit(1 if not all(res) else 0)
