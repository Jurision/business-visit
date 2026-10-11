import sys, time, json, os
from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = sys.argv[2]
os.makedirs(OUT, exist_ok=True)
log = []
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"


def rec(state, ok, note=""):
    log.append({"state": state, "ok": bool(ok), "note": note})
    print(("PASS " if ok else "FAIL ") + state + (" — " + note if note else ""))


def overflow(pg):
    return pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def info(pg):
    return pg.evaluate("""()=>({
      days:document.querySelectorAll('#dateRail .date').length,
      first:document.querySelector('#dateRail .date b').textContent,
      title:document.getElementById('heroTitle').textContent,
      dates:document.getElementById('heroDates').textContent,
      status:document.getElementById('planStatus').textContent,
      budget:document.getElementById('statBudget').textContent,
      limit:document.getElementById('limitNote').hidden?'(hidden)':document.getElementById('limitNote').textContent,
      kicker:document.getElementById('dayKicker').textContent,
      segs:[...document.querySelectorAll('#phaseRail .seg.stay')].map(s=>s.querySelector('b').textContent+' '+s.querySelector('.seg-nights').firstChild.textContent)
    })""")


def click(pg, sel):
    loc = pg.locator(sel).first
    vp = pg.viewport_size
    box = loc.bounding_box()
    covered = bool(box) and not loc.evaluate("e=>{const r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return !!h&&(e===h||e.contains(h))}")
    if covered:
        loc.evaluate("e=>e.scrollIntoView({block:'center'})")
        time.sleep(0.3)
        box = loc.bounding_box()
    if not box or box["y"] < 0 or box["y"] + box["height"] > vp["height"]:
        loc.scroll_into_view_if_needed()
        time.sleep(0.2)
        box = loc.bounding_box()
    if pg.context._impl_obj._options.get("hasTouch"):
        pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    else:
        pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    time.sleep(0.5)


def shot(pg, name, full=False):
    pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full)



with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width":428,"height":926},device_scale_factor=3,is_mobile=True,has_touch=True,user_agent=UA)
    pg = ctx.new_page()
    errs=[]
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:m.type=="error" and errs.append(m.text))
    pg.goto(URL,wait_until="domcontentloaded")
    pg.evaluate("localStorage.clear()")
    pg.reload(wait_until="domcontentloaded")
    time.sleep(.5)
    def select_day(i):
        # Exercise the date strip through its actual touch target.
        loc=pg.locator(f'#dateRail [data-day="{i}"]')
        loc.evaluate("e=>e.scrollIntoView({inline:'center',block:'nearest'})")
        time.sleep(.3)
        box=loc.bounding_box()
        pg.touchscreen.tap(box["x"]+box["width"]/2,box["y"]+box["height"]/2)
        time.sleep(.3)
        pg.locator("#dayCard").evaluate("e=>e.scrollIntoView({block:'start'})")
        time.sleep(.3)
    def close_bar():
        if pg.locator("#changeBar").is_visible():
            click(pg,"#closeBar")

    i=info(pg)
    rec("默认11天、10/13周二—10/23周五",i["days"]==11 and "威海" in i["title"] and "10月13日 周二" in i["dates"] and "10月23日" in i["dates"])
    rec("两张飞机及青岛第一晚已订，预算上限200", "3 / 11" in pg.inner_text("#bookingSummary") and pg.locator("#phaseRail .book-badge.booked").count()==2)
    rec("默认无横向溢出",overflow(pg)<=0)
    rec("统计交通小时不折行",pg.locator(".transit-hours").evaluate("e=>getComputedStyle(e).whiteSpace==='nowrap'&&e.scrollWidth<=e.clientWidth"))
    shot(pg,"01-overview",True)
    for idx,label,ticket in [(0,"10-13","AQ1019"),(2,"10-15","C6587"),(3,"10-16","生生2"),(5,"10-18","MU6908")]:
        select_day(idx)
        text=pg.inner_text("#dayCard")
        rec(label+"卡片日期与交通","10/"+str(13+idx) in pg.inner_text("#dayKicker") and ticket in text and "待核" in text)
        rec(label+"无横向溢出",overflow(pg)<=0)
        shot(pg,label+"-card")
        shot(pg,label+"-full",True)
    rec("机票实付747与参考费用分开","实付¥747" in pg.inner_text("#budgetBasis") or "实付 ¥747" in pg.inner_text("#budgetBasis"))
    select_day(0)
    rec("民宿第一晚已订且按实付计价",pg.inner_text("#dayBudget")=="¥785.49–885.49" and "已订" in pg.inner_text("#dayNight") and "海景精致投影一居室" in pg.inner_text("#dayNightSub"))
    rec("默认总预算准确到分",pg.inner_text("#statBudget")=="¥3,665.49–5,189.49")
    rec("含分预算完整且当天金额不折行",pg.locator("#dayBudget").evaluate("e=>getComputedStyle(e).whiteSpace==='nowrap'&&e.scrollWidth<=e.clientWidth") and pg.locator("#statBudget").evaluate("e=>e.scrollWidth<=e.clientWidth&&getComputedStyle(e).textOverflow!=='ellipsis'"))
    rec("10/13地铁寄存栈桥与15点后入住",all(s in pg.inner_text("#steps") for s in ["8号线","3号线","寄存行李","栈桥","15:00"]))
    rec("九元联订任务更新为入住离店后完成","已通过飞猪订青岛酒店，入住离店后即完成" in pg.inner_text(".flight-task"))
    click(pg,'#steps [data-step="6"]')
    rec("民宿详情有精确地址房型入住离店和待核项",all(s in pg.inner_text("#sheetContent") for s in ["北京路38号","1单元0704","15:00后","12:00前","133.49","钥匙","取消政策"]))
    shot(pg,"hotel-confirmed-detail")
    pg.keyboard.press("Escape")
    select_day(1)
    rec("10/14第二晚仍待订、不沿用实付价",pg.inner_text("#dayBudget")=="¥180–330" and "待订" in pg.inner_text("#dayNight") and "12:00前" in pg.inner_text("#steps"))
    shot(pg,"10-14-pending-night")
    click(pg,'#steps [data-step="1"]')
    rec("退房详情指向10/13订单而非第二晚",pg.locator('#sheetContent [data-book="hotel:qd:2026-10-13"]').count()==1 and pg.locator('#sheetContent [data-book="hotel:qd:2026-10-14"]').count()==0)
    pg.keyboard.press("Escape")
    click(pg,"#bookingSummary")
    rec("抽屉青岛两晚独立状态",pg.locator('#sheetContent [data-book="hotel:qd:2026-10-13"]').get_attribute("aria-pressed")=="true" and pg.locator('#sheetContent [data-book="hotel:qd:2026-10-14"]').get_attribute("aria-pressed")=="false")
    shot(pg,"hotel-night-bookings")
    pg.keyboard.press("Escape")
    select_day(9)
    rec("10/22夜车出发，不提前写到广州",pg.locator('#dateRail [data-day="9"] i').inner_text()=="夜车" and "10/23" in pg.inner_text("#dayLegs"))
    shot(pg,"10-22-date-strip")
    select_day(10)
    rec("10/23才标到广州",pg.locator('#dateRail [data-day="10"] i').inner_text()=="→广州")

    click(pg,"#adjustToggle")
    rec("已订飞机锁住方式和会移动航班的停留",pg.locator('#phaseRail .modes [data-mode="gzqd:rail"]').is_disabled() and pg.locator('[data-adjust="qingdao"][data-delta="1"]').is_disabled() and pg.locator('[data-adjust="dalian"][data-delta="1"]').is_disabled())
    for seg,ids in [(0,["leg:gzqd:air"]),(1,["hotel:qd:2026-10-13","hotel:qd:2026-10-14"]),(2,["leg:qdwh"]),(3,["hotel:wh"]),(4,["leg:shengsheng"]),(5,["hotel:dl"]),(6,["leg:dlnc:air"]),(7,["hotel:nc"])]:
        click(pg,f'#phaseRail [data-phase="{seg}"]')
        for id in ids:
            rec("调整加详情预订入口唯一："+id,pg.locator(f'#phaseRail [data-book="{id}"]:visible').count()==1)
        if seg==0:
            rec("退票提示只出现一次",pg.inner_text("#phaseRail").count("已订票，改方式前先退票并取消已订标记")==2) # one per paid flight, not twice per flight
            shot(pg,"adjust-flight-detail")
        click(pg,f'#phaseRail [data-phase="{seg}"]')
    for key in ["nanchang","xingan"]:
        base=info(pg)
        for delta,want in [(-1,10),(1,11),(1,12),(-1,11)]:
            click(pg,f'[data-adjust="{key}"][data-delta="{delta}"]')
            rec(key+f"调整至{want}天",info(pg)["days"]==want)
            rec(key+"费用与日期联动",info(pg)["dates"]!=base["dates"] if want!=11 else info(pg)["dates"]==base["dates"])
            close_bar()
        for delta in [-1,1]:
            click(pg,f'[data-adjust="{key}"][data-delta="{delta}"]')
            shot(pg,key+("-zero-full-day" if delta<0 else "-restored"))
            close_bar()

    click(pg,"#weihaiToggle")
    rec("不去威海仍11天、青岛3晚",info(pg)["days"]==11 and "威海" not in info(pg)["title"] and info(pg)["segs"][0].startswith("青岛 3晚"))
    ts=pg.locator('#phaseRail [data-phase="2"] .tk')
    rec("烟台两票显示13:40与22:00",ts.count()==2 and "13:40" in ts.nth(0).inner_text() and "14:54" in ts.nth(0).inner_text() and "22:00" in ts.nth(1).inner_text() and "10/17" in ts.nth(1).inner_text())
    shot(pg,"no-weihai-route",True)
    close_bar()
    select_day(3)
    rec("不去威海当日也显示两票",pg.locator("#dayLegs .tk").count()==2)
    shot(pg,"no-weihai-day")
    for id in ["leg:c6571","leg:ferry"]:
        click(pg,'#phaseRail [data-phase="2"]')
        rec("烟台调整加详情单入口："+id,pg.locator(f'#phaseRail [data-book="{id}"]:visible').count()==1)
        click(pg,'#phaseRail [data-phase="2"]')
    click(pg,"#weihaiToggle")
    close_bar()

    # Only comparison can bypass the paid-flight date locks; actual flags survive.
    click(pg,"#compareToggle")
    click(pg,'#phaseRail .modes [data-mode="gzqd:rail"]')
    rec("保留Z168比较，10/13为夜车出发",pg.locator('#dateRail [data-day="0"] i').inner_text()=="夜车" and "Z168" in pg.inner_text("#phaseRail"))
    rec("比较不把10/19误标成已订MU6908","3 / 11" not in pg.inner_text("#bookingSummary") and "实际已订仍是10/13 AQ1019" in pg.inner_text("#compareNote"))
    rec("原始机票已订标记未丢",pg.evaluate("JSON.parse(localStorage.getItem('china-trip-v4-progress')).booked['leg:dlnc:air']===true"))
    close_bar()
    click(pg,'#phaseRail .modes [data-mode="gzqd:hsr"]')
    click(pg,'#phaseRail .modes [data-mode="dlnc:rail"]')
    rec("大连普速比较保留北京换乘","北京" in pg.inner_text("#phaseRail"))
    close_bar()
    click(pg,'#phaseRail .modes [data-mode="ncxg:hsr"]')
    click(pg,'#phaseRail .modes [data-mode="xggz:hsr"]')
    rec("高铁比较当天到广州",pg.locator("#dateRail .date").last.locator("i").inner_text()=="→广州")
    close_bar()
    click(pg,'[data-adjust="qingdao"][data-delta="1"]')
    click(pg,'[data-adjust="qingdao"][data-delta="1"]')
    click(pg,'[data-adjust="dalian"][data-delta="1"]')
    click(pg,'[data-adjust="dalian"][data-delta="1"]')
    click(pg,'[data-adjust="nanchang"][data-delta="1"]')
    click(pg,'[data-adjust="xingan"][data-delta="1"]')
    rec("超14天不偷偷压缩交通",info(pg)["days"]>14 and "超过14天上限" in info(pg)["limit"])
    shot(pg,"over-limit-comparison")
    close_bar()
    click(pg,"#compareToggle")
    rec("结束比较恢复真实已订路线及预算",info(pg)["days"]==11 and "3 / 11" in pg.inner_text("#bookingSummary") and info(pg)["budget"]==i["budget"])
    close_bar()
    click(pg,"#adjustToggle")

    select_day(0)
    click(pg,'#steps [data-step="1"]')
    rec("航班详情显示实付和机场T2","¥532" in pg.inner_text("#sheetContent") and "T2" in pg.inner_text("#sheetContent"))
    shot(pg,"flight-detail")
    pg.keyboard.press("Escape")
    rec("抽屉关闭焦点恢复",pg.evaluate("document.activeElement.dataset.step==='1'"))
    click(pg,"#budgetBtn")
    rec("预算抽屉11天逐日加总",pg.locator(".budget-row").count()==11 and pg.inner_text(".budget-total")==i["budget"])
    shot(pg,"budget")
    pg.keyboard.press("Escape")
    click(pg,"#mapBtn")
    rec("路线图随威海方案","威海" in pg.inner_text("#sheetContent") and "南昌" in pg.inner_text("#sheetContent"))
    shot(pg,"map")
    pg.keyboard.press("Escape")
    click(pg,"#packBtn")
    rec("原清单保留并补笔记本航空夜船","笔记本电脑和充电器" in pg.inner_text("#sheetContent") and "3C" in pg.inner_text("#sheetContent") and "100ml" in pg.inner_text("#sheetContent"))
    rec("天气日期地点随新路线","10/15" in pg.inner_text(".wx") and "威海" in pg.inner_text(".wx") and "10/18" in pg.inner_text(".wx") and "2026-10-11 08:00" in pg.inner_text(".wx-note"))
    pg.locator('[data-pack="0-4"]').check()
    rec("笔记本清单勾选保存",pg.evaluate("JSON.parse(localStorage.getItem('china-trip-v3-pack'))['0-4']===1"))
    shot(pg,"packing",True)
    pg.keyboard.press("Escape")
    pg.reload(wait_until="domcontentloaded")
    click(pg,"#packBtn")
    rec("刷新保留已有清单状态",pg.locator('[data-pack="0-4"]').is_checked())
    pg.keyboard.press("Escape")
    rec("全程控制台0错误",not errs,str(errs))
    ctx.close()

    ctx=b.new_context(viewport={"width":1440,"height":900})
    pg=ctx.new_page()
    pg.goto(URL,wait_until="domcontentloaded")
    click(pg,"#adjustToggle")
    click(pg,'[data-adjust="nanchang"][data-delta="1"]')
    pg.locator("footer").evaluate("e=>e.scrollIntoView({block:'end'})")
    time.sleep(.4)
    last_line=pg.locator("footer p").last.bounding_box()
    rec("1440宽屏变化条不盖页脚文字",last_line["y"]+last_line["height"]<=pg.locator("#changeBar").bounding_box()["y"])
    rec("1440宽屏无溢出",overflow(pg)<=0)
    shot(pg,"desktop-footer-change")
    shot(pg,"desktop-full",True)
    ctx.close()
    b.close()

with open(os.path.join(OUT,"check-log.json"),"w",encoding="utf-8") as f:
    json.dump(log,f,ensure_ascii=False,indent=1)
print("TOTAL",len(log),"FAIL",sum(not x["ok"] for x in log))
sys.exit(1 if any(not x["ok"] for x in log) else 0)
