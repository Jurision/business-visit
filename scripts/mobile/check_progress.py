"""Phase-one progress acceptance at 428x926. No live writes or cloud service."""
import json
import os
import sys
from playwright.sync_api import sync_playwright

URL, OUT = sys.argv[1:3]
os.makedirs(OUT, exist_ok=True)
results = []


def check(label, condition):
    results.append({"check": label, "ok": bool(condition)})
    print(("PASS " if condition else "FAIL ") + label, flush=True)


def tap(pg, selector):
    target = pg.locator(selector).first
    target.evaluate("e=>e.scrollIntoView({block:'center'})")
    target.tap()


def shot(pg, label):
    # Capture the settled UI, not an intermediate drawer/scroll animation.
    pg.wait_for_timeout(400)
    pg.screenshot(path=os.path.join(OUT, label + ".png"))


def clock(ctx, iso, manual_ticks=False):
    # Compatible with the installed Playwright: only test contexts get this clock.
    ctx.add_init_script("""(()=>{const T=new Date(%s).getTime(),D=Date;
window.__testTime=T;
class F extends D {constructor(...a){super(...(a.length?a:[window.__testTime]))}static now(){return window.__testTime}}window.Date=F;
if(%s){const interval=window.setInterval;window.setInterval=function(fn,ms,...args){
 if(ms===60000)window.__testMinuteTick=()=>fn(...args);return interval(fn,ms,...args)};}
})()""" % (json.dumps(iso), json.dumps(manual_ticks)))



with sync_playwright() as p:
    browser=p.chromium.launch(channel="chrome")
    errors=[]
    def context(iso,reduced=False,desktop=False):
        ctx=browser.new_context(viewport={"width":1440 if desktop else 428,"height":900 if desktop else 926},device_scale_factor=1 if desktop else 3,is_mobile=not desktop,has_touch=not desktop,reduced_motion="reduce" if reduced else "no-preference")
        clock(ctx,iso,True)
        return ctx
    def page(ctx):
        pg=ctx.new_page()
        pg.on("pageerror",lambda e:errors.append(str(e)))
        pg.on("console",lambda m:m.type=="error" and errors.append(m.text))
        pg.goto(URL,wait_until="domcontentloaded")
        return pg
    def close_sheet(pg):
        pg.keyboard.press("Escape")
    ctx=context("2026-10-11T09:00:00+08:00")
    pg=page(ctx)
    check("出发前2天、AQ1019和默认已订2/10","还有 2 天" in pg.inner_text("#tripProgressText") and "AQ1019" in pg.inner_text("#tripProgressText") and "2 / 10" in pg.inner_text("#bookingSummary"))
    check("出发前下一步隐藏、路线展开",pg.locator("#nextStep").is_hidden() and pg.locator("#stayControls").is_visible())
    check("普通模式没有额外预订入口",pg.locator("#phaseRail > .booking-actions:visible,#dayCard .book-toggle:visible").count()==0)
    check("未来日期无部分完成数",pg.locator("#dateRail .day-done").count()==0)
    check("默认4城市酒店待订小标记",pg.locator(".hotel-badge").count()==4 and pg.locator(".hotel-badge.booked").count()==0)
    tap(pg,'#steps [data-done="d:qd-arrive-air:0"]')
    check("勾选不误开详情",pg.locator("#overlay.open").count()==0)
    check("单圈按钮44px触控",pg.locator("#steps .step-check").first.bounding_box()["width"]>=44 and pg.locator("#steps .step-check").first.bounding_box()["height"]>=44 and pg.locator("#steps .step-dot").count()==0)
    pg.reload(wait_until="domcontentloaded")
    check("刷新保留完成记录",pg.locator('#steps [data-done="d:qd-arrive-air:0"]').get_attribute("aria-pressed")=="true")
    tap(pg,"#bookingSummary")
    check("酒店仍待选定，预订抽屉保留手动说明","酒店待选定" in pg.inner_text("#sheetContent") and "取消勾选不会替你退票" in pg.inner_text("#sheetContent"))
    tap(pg,'#sheetContent [data-book="hotel:nc"]')
    close_sheet(pg)
    tap(pg,"#adjustToggle")
    check("已订酒店锁住南昌完整日",pg.locator('[data-adjust="nanchang"][data-delta="1"]').is_disabled() and pg.locator('[data-adjust="nanchang"][data-delta="-1"]').is_disabled())
    tap(pg,"#bookingSummary")
    tap(pg,'#sheetContent [data-book="hotel:nc"]')
    close_sheet(pg)
    check("取消酒店恢复0–2调整",not pg.locator('[data-adjust="nanchang"][data-delta="1"]').is_disabled() and not pg.locator('[data-adjust="nanchang"][data-delta="-1"]').is_disabled())
    tap(pg,'#phaseRail [data-book="leg:shengsheng"]')
    check("已订生生2锁住威海开关",pg.locator("#weihaiToggle").is_disabled())
    pg.locator("#weihaiToggle").evaluate("e=>e.dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    check("事件层也保护已订船班",pg.locator("#weihaiToggle").get_attribute("aria-pressed")=="true")
    tap(pg,'#phaseRail [data-book="leg:shengsheng"]')
    check("取消船票解锁威海开关",not pg.locator("#weihaiToggle").is_disabled())
    # Mark all visible route bookings, then cancel only those added in this check.
    tap(pg,"#bookingSummary")
    ids=pg.locator('#sheetContent [data-book][aria-pressed="false"]').evaluate_all("es=>es.map(e=>e.dataset.book)")
    for id in ids:
        tap(pg,f'#sheetContent [data-book="{id}"]')
    check("全部已订文案动态","全部已订" in pg.inner_text("#planStatus") and "10 / 10" in pg.inner_text("#bookingSummary"))
    for id in ids:
        tap(pg,f'#sheetContent [data-book="{id}"]')
    check("已订机票恢复保留2项","2 / 10" in pg.inner_text("#bookingSummary"))
    close_sheet(pg)
    ctx.close()

    scenarios=[
        ("2026-10-13T08:00:00+08:00","next-10-13-0800","AQ1019","10:30","还有 2 小时 30 分",0),
        ("2026-10-16T20:00:00+08:00","next-10-16-2000","生生2","21:30","还有 1 小时 30 分",3),
        ("2026-10-18T12:00:00+08:00","next-10-18-1200","MU6908","13:35","还有 1 小时 35 分",5),
        ("2026-10-16T23:00:00+08:00","next-night-on-ship","生生2","约05:00","还有 6 小时",4)
    ]
    for iso,label,train,time,countdown,idx in scenarios:
        ctx=context(iso)
        pg=page(ctx)
        check(label+"显示对应交通票",pg.locator("#nextStep").is_visible() and train in pg.inner_text("#nextTicket") and time in pg.inner_text("#nextTicket") and pg.inner_text("#nextCountdown")==countdown)
        check(label+"车票不重复事项和地点",pg.locator("#nextTitle").is_hidden() and pg.locator("#nextTime").is_hidden() and pg.locator("#nextPlace").is_hidden())
        check(label+"自动选今天、日期条今天替代星期","今天" in pg.locator("#dateRail .today span").inner_text() and "周" not in pg.locator("#dateRail .today span").inner_text())
        check(label+"行程中总览默认收起",pg.locator("#stayControls").is_hidden() and pg.locator("#routeExpand").is_visible())
        check(label+"未勾过时项只提醒，不挡下一步",pg.locator("#nextOverdue").is_visible())
        if train=="生生2":
            check(label+"参考为小字",pg.locator("#nextTicket .tk-ref").first.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)<parseFloat(getComputedStyle(e.parentElement).fontSize)"))
        else:
            check(label+"已付机票不标参考",pg.locator("#nextTicket .tk-ref").count()==0 and pg.locator("#nextTicket .book-badge.booked").count()==1)
        pg.evaluate("scrollTo({top:0,behavior:'instant'})")
        shot(pg,label)
        if idx==4:
            check("船上23点显示明天到港","明天" in pg.inner_text("#nextWhen"))
        if idx==3:
            tap(pg,"#nextOverdue")
            before=pg.locator("#sheetContent [data-done]").count()
            tap(pg,"#sheetContent [data-done]")
            check("补勾抽屉更新未完成数",pg.locator("#sheetContent [data-done]").count()==before-1)
            check("补勾不改变下一班船","生生2" in pg.inner_text("#nextTicket"))
            shot(pg,"missed-step-drawer")
            close_sheet(pg)
        if idx==5:
            tap(pg,"#routeExpand")
            pg.reload(wait_until="domcontentloaded")
            check("行程路线展开状态刷新保留",pg.locator("#stayControls").is_visible() and pg.locator("#routeExpand").get_attribute("aria-expanded")=="true")
            tap(pg,"#routeExpand")
            tap(pg,"#nextAll")
            check("看今天全部跳至10/18","10/18" in pg.inner_text("#dayKicker"))
        if idx==0:
            before=pg.locator('#nextComplete').get_attribute("data-done")
            tap(pg,"#nextComplete")
            check("完成即切换下一步",pg.locator("#nextComplete").get_attribute("data-done")!=before and pg.evaluate("JSON.parse(localStorage.getItem('china-trip-v4-progress')).done['d:qd-arrive-air:2']===true"))
            pg.evaluate("window.__testTime=Date.parse('2026-10-13T12:59:00+08:00');window.__testMinuteTick()")
            check("分钟刷新倒计时","还有 1 分" in pg.inner_text("#nextCountdown"))
            pg.evaluate("window.__testTime=Date.parse('2026-10-14T00:01:00+08:00');document.dispatchEvent(new Event('visibilitychange'))")
            check("跨午夜更新今天和进度","第 2 / 11 天" in pg.inner_text("#tripProgressText"))
        ctx.close()

    ctx=context("2026-10-14T20:00:00+08:00")
    pg=page(ctx)
    for id in pg.locator("#steps [data-done]").evaluate_all("es=>es.map(e=>e.dataset.done)"):
        tap(pg,f'#steps [data-done="{id}"]')
    check("10/14全部完成显示明天第一步","明天 · 10/15" in pg.inner_text("#nextWhen") and "07:40" in pg.inner_text("#nextTime"))
    check("全部完成日期条显示勾号",pg.locator('#dateRail [data-day="1"] .day-done').inner_text()=="✓")
    pg.evaluate("scrollTo({top:0,behavior:'instant'})")
    shot(pg,"tomorrow-after-complete")
    tap(pg,"#nextAll")
    tap(pg,'#steps [data-step="0"]')
    check("手指开抽屉无蓝绿焦点圈",pg.locator("#closeSheet").evaluate("e=>getComputedStyle(e).boxShadow==='none'"))
    close_sheet(pg)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(400)
    check("键盘开抽屉保留焦点样式",pg.locator("#overlay.open").count()==1 and pg.locator("#closeSheet").evaluate("e=>getComputedStyle(e).outlineStyle==='solid'&&parseFloat(getComputedStyle(e).outlineWidth)>=3"))
    close_sheet(pg)
    ctx.close()

    ctx=context("2026-10-23T08:00:00+08:00",reduced=True)
    pg=page(ctx)
    check("最后一天进度11/11","第 11 / 11 天" in pg.inner_text("#tripProgressText"))
    check("reduced-motion保留","reduce"==pg.evaluate("matchMedia('(prefers-reduced-motion:reduce)').matches?'reduce':'no'"))
    ctx.close()
    ctx=context("2026-10-24T09:00:00+08:00")
    pg=page(ctx)
    check("行程后隐藏下一步","行程已结束" in pg.inner_text("#tripProgressText") and pg.locator("#nextStep").is_hidden())
    ctx.close()

    # New itinerary must not inherit an old route; packing storage stays separate.
    ctx=context("2026-10-11T09:00:00+08:00")
    ctx.add_init_script("""localStorage.setItem('china-trip-v3-modes','{"gzqd":"rail","dlnc":"hsr"}');localStorage.setItem('china-trip-v3-pack','{"0-0":1}');""")
    pg=page(ctx)
    check("旧路线记录不会覆盖新已订飞机",pg.locator("#phaseRail .book-badge.booked").count()==2 and "11日行程" in pg.inner_text("#heroTitle"))
    tap(pg,"#packBtn")
    check("已有打包勾选继承",pg.locator('[data-pack="0-0"]').is_checked())
    ctx.close()
    ctx=context("2026-10-11T09:00:00+08:00")
    ctx.add_init_script("Storage.prototype.setItem=function(){throw Error('test quota')}")
    pg=page(ctx)
    check("存储失败有清楚提示","存储失败" in pg.inner_text("#syncState") and "可能丢失" in pg.inner_text("#progressNotice"))
    ctx.close()
    check("所有模拟场景控制台0错误",not errors)
    browser.close()

with open(os.path.join(OUT,"progress-checks.json"),"w",encoding="utf-8") as f:
    json.dump(results,f,ensure_ascii=False,indent=1)
print("TOTAL",len(results),"FAIL",sum(not x["ok"] for x in results))
sys.exit(1 if any(not x["ok"] for x in results) else 0)
