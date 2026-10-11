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
    ctx = b.new_context(viewport={"width": 428, "height": 926}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=UA)
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.evaluate("localStorage.clear()")
    pg.reload(wait_until="domcontentloaded")
    time.sleep(2.5)

    # 1 default
    i = info(pg)
    rec("默认 12 天", i["days"] == 12 and "12日行程" in i["title"] and "10月23日" in i["dates"], json.dumps(i, ensure_ascii=False))
    rec("默认无横向溢出", overflow(pg) <= 0, "overflow=%s" % overflow(pg))
    shot(pg, "01-首屏")
    shot(pg, "00-整页-默认", full=True)
    ferry_tickets = pg.locator('#phaseRail [data-phase="2"] .tk')
    rec("总览夜船段分为动车和夜船两张带日期的票", ferry_tickets.count() == 2 and "10/1613:40" in ferry_tickets.nth(0).inner_text().replace("\n", "") and "10/1614:54" in ferry_tickets.nth(0).inner_text().replace("\n", "") and "10/1622:00" in ferry_tickets.nth(1).inner_text().replace("\n", "") and "10/17约05:00" in ferry_tickets.nth(1).inner_text().replace("\n", ""))

    # tap target audit
    small = pg.evaluate("""()=>[...document.querySelectorAll('button,a')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return [e.className||e.id||e.tagName,Math.round(r.width),Math.round(r.height)]}).filter(x=>x[1]<40||x[2]<32)""")
    rec("可见触控目标尺寸（宽≥40/高≥32）", not small, json.dumps(small, ensure_ascii=False))

    # 2 adjust each city +1 / -1
    click(pg, "#adjustToggle")
    shot(pg, "02-调整模式")
    base = info(pg)
    for k, label in [("qingdao", "青岛"), ("dalian", "大连"), ("xingan", "新干探亲"), ("nanchang", "南昌")]:
        click(pg, f'[data-adjust="{k}"][data-delta="1"]')
        a = info(pg)
        others_same = all(s1 == s2 for s1, s2 in zip(base["segs"], a["segs"]) if not s1.startswith(label + " "))
        rec(f"{label} +1 天 → 13 天，其余城市不变", a["days"] == 13 and others_same and "13日行程" in a["title"], " | ".join(a["segs"]) + " | " + a["dates"] + " | " + a["budget"])
        if k == "qingdao":
            texts = pg.locator('#phaseRail [data-phase="2"] .tk').all_inner_texts()
            rec("青岛加一天后两张车船票日期顺延", "10/17" in texts[0] and "10/1722:00" in texts[1].replace("\n", "") and "10/18约05:00" in texts[1].replace("\n", ""))
        if k == "nanchang":
            shot(pg, "03-南昌加一天")
        click(pg, f'[data-adjust="{k}"][data-delta="-1"]')
        rec(f"{label} −1 天 → 恢复 12 天", info(pg)["days"] == 12)
    # min bound: dalian / xingan can go down to 1 night, never removed
    for k, label, nxt in (("dalian", "大连", "大连 → 南昌"), ("xingan", "新干探亲", "新干县 → 广州")):
        click(pg, f'[data-adjust="{k}"][data-delta="-1"]')
        a = info(pg)
        seg = [x for x in a["segs"] if x.startswith(label + " ")]
        dis = pg.locator(f'[data-adjust="{k}"][data-delta="-1"]').is_disabled()
        rec(f"{label} 可减到 1 晚（11 天），再减按钮禁用，{label}不会被删掉", a["days"] == 11 and seg == [label + " 1晚"] and dis, " | ".join(a["segs"]) + " | " + a["dates"] + " | " + a["budget"])
        if k == "dalian":
            shot(pg, "02b-大连减到1晚")
        click(pg, f'[data-adjust="{k}"][data-delta="1"]')
    rec("减到 1 晚再加回 → 12 天", info(pg)["days"] == 12)

    # 3 14-day boundary
    click(pg, '[data-adjust="qingdao"][data-delta="1"]')
    click(pg, '[data-adjust="nanchang"][data-delta="1"]')
    a = info(pg)
    rec("14 天边界", a["days"] == 14 and "已到上限" in pg.inner_text("#statDaysSub") and "还可增加 0 天" in a["limit"], a["limit"] + " | " + a["dates"])
    shot(pg, "04-14天边界")
    rec("14 天无横向溢出", overflow(pg) <= 0)

    # 4 over limit
    click(pg, '[data-adjust="dalian"][data-delta="1"]')
    a = info(pg)
    rec("超限提示（15 天）", a["days"] == 15 and "超过14天上限 1 天" in a["limit"] and "已超14天上限" in a["status"], a["limit"] + " | " + a["status"])
    shot(pg, "05-超限提示")
    # leave editing mode -> over-limit note must stay visible
    click(pg, "#adjustToggle")
    rec("退出调整后超限提示仍可见", not pg.locator("#limitNote").is_hidden())
    # restore default
    click(pg, "#adjustToggle")
    click(pg, "#resetStays")
    rec("恢复默认 → 12 天", info(pg)["days"] == 12)
    click(pg, "#adjustToggle")

    # 5 overview segments expand in place
    labels = pg.evaluate("[...document.querySelectorAll('#phaseRail .seg-text b')].map(b=>b.textContent)")
    rec("路线顺序：大连→南昌→新干→返穗卧铺（无南昌中转/回南昌）", labels == ["去青岛火车","青岛","烟台夜船","大连","大连→南昌","南昌","南昌→新干","新干探亲","返穗卧铺"], " / ".join(labels))
    k0 = info(pg)["kicker"]; y0 = pg.evaluate("scrollY")
    click(pg, '#phaseRail [data-phase="1"]')
    panel = pg.locator("#segPanel1")
    ptxt = panel.inner_text() if panel.count() else ""
    rec("点“青岛”→ 原地展开详情，不跳转", panel.count() == 1 and "这几天预算合计" in ptxt and "每晚 ≤¥150" in ptxt and pg.locator("#segPanel1 [data-goto]").count() == 4 and info(pg)["kicker"] == k0, ptxt.replace(chr(10), " | ")[:200])
    shot(pg, "06-展开青岛")
    click(pg, '#phaseRail [data-phase="1"]')
    rec("再点“青岛”→ 收起", pg.locator("#segPanel1").count() == 0)
    click(pg, '#phaseRail [data-phase="8"]')
    ptxt = pg.inner_text("#segPanel8") if pg.locator("#segPanel8").count() else ""
    rec("展开“返穗卧铺”显示 K441 车次、时刻与票价", "K441 新干 → 广州白云" in ptxt and "16:29" in ptxt and "硬卧" in ptxt, ptxt.replace(chr(10), " | ")[:200])
    shot(pg, "06b-展开返穗卧铺")
    rec("同一时间只展开一段", pg.locator(".seg-panel").count() == 1)
    click(pg, '#phaseRail [data-phase="7"]')
    ptxt = pg.inner_text("#segPanel7")
    rec("展开“新干探亲”显示住家中、逐日 3 天（到达日＋完整日＋离开日）", "住家中" in ptxt and pg.locator("#segPanel7 [data-goto]").count() == 3, ptxt.replace(chr(10), " | ")[:160])
    click(pg, '#phaseRail [data-phase="3"]')
    click(pg, '#segPanel3 [data-goto]')
    pg.wait_for_function("()=>{const top=dayCard.getBoundingClientRect().top,h=railWrap.getBoundingClientRect().height;return top>=h&&top<=h+30}")
    a = info(pg)
    top = pg.evaluate("document.getElementById('dayCard').getBoundingClientRect().top")
    rail_height = pg.locator("#railWrap").bounding_box()["height"]
    rec("展开“大连”后点第一天 → 跳到大连抵达日并滚动到卡片", "旅顺 → 大连" in a["kicker"] and rail_height <= top <= rail_height + 30, a["kicker"] + " cardTop=%d railHeight=%d" % (top, rail_height))
    shot(pg, "06c-展开后跳转大连")

    # Jiangxi days
    for idx, want in ((7, "大连 → 南昌"), (8, "南昌 → 新干县"), (10, "新干县 → 广州"), (11, "车上 → 广州")):
        pg.evaluate("document.querySelector('#dateRail [data-day=\"%d\"]').click()" % idx); time.sleep(0.4)
        k = info(pg)["kicker"]
        rec("第 %d 天是 %s" % (idx + 1, want), want in k, k)
        if idx == 8:
            shot(pg, "06d-南昌到新干日")
    pg.evaluate("document.querySelector('#dateRail [data-day=\"0\"]').click()"); time.sleep(0.3)

    # Transport mode switching
    def labels():
        return pg.evaluate("[...document.querySelectorAll('#phaseRail .seg-text b')].map(b=>b.textContent)")
    def kick(i):
        pg.evaluate("document.querySelector('#dateRail [data-day=\"%d\"]').click()" % i); time.sleep(0.3)
        return info(pg)["kicker"] + " · " + pg.inner_text("#dayTitle")
    def route_of(i):
        pg.evaluate("document.querySelector('#dateRail [data-day=\"%d\"]').click()" % i); time.sleep(0.3)
        return pg.inner_text("#routeChain").replace(chr(10), "")
    def first_time(i):
        pg.evaluate("document.querySelector('#dateRail [data-day=\"%d\"]').click()" % i); time.sleep(0.3)
        return pg.inner_text("#steps .step-time").replace(chr(10), "")
    def find_day(sub):
        return pg.evaluate("[...document.querySelectorAll('#dateRail .date')].findIndex(b=>b.getAttribute('aria-label').indexOf(%r)>=0)" % sub)
    def modes():
        return pg.evaluate("localStorage.getItem('china-trip-v3-modes')")
    pg.evaluate("scrollTo(0,0)"); time.sleep(0.2)
    click(pg, "#adjustToggle")
    rec("调整模式显示 4 段交通切换（烟台夜船固定）", pg.locator("#phaseRail .modes").count() == 4)
    base_b = info(pg)["budget"]
    click(pg, '#phaseRail .modes [data-mode="xggz:hsr"]')
    a = info(pg)
    rec("返程改高铁 → 11 天、当晚到广州东", a["days"] == 11 and labels()[-1] == "返穗高铁" and "广州东" in route_of(a["days"] - 1), a["dates"] + " | " + a["budget"] + " (原 " + base_b + ")")
    shot(pg, "07a-返程改高铁")
    bar = pg.inner_text("#changeBar").replace(chr(10), " | ") if pg.locator("#changeBar").is_visible() else ""
    rec("变化条：返程改高铁 → 天数 12→11、交通少10小时28分、预算变化", "新干→广州 改为高铁（G3065）" in bar and "12→11天" in bar and "少1天" in bar and "少10小时28分" in bar and ("约多花" in bar or "约省" in bar), bar[:220])
    rec("统计格显示“比默认”", "比默认少1天" in pg.inner_text("#dDays") and "比默认少10小时28分" in pg.inner_text("#dTransit"), pg.inner_text("#dDays") + " / " + pg.inner_text("#dTransit") + " / " + pg.inner_text("#dBudget"))
    shot(pg, "07a2-变化条")
    click(pg, '#phaseRail .modes [data-mode="gzqd:hsr"]')
    a = info(pg)
    rec("去程也改高铁 → 10 天、第一天当晚入住青岛", a["days"] == 10 and "坐高铁去青岛" in kick(0), a["dates"] + " | " + a["budget"])
    click(pg, '#phaseRail .modes [data-mode="dlnc:rail"]')
    a = info(pg)
    rec("大连→南昌改普速经北京 → 多 1 天（11 天），路线含北京", a["days"] == 11 and "大连→北京→南昌" in labels(), " / ".join(labels()) + " | " + a["budget"])
    bar = pg.inner_text("#changeBar").replace(chr(10), " | ")
    rec("变化条：大连→南昌改普速 → 交通多14小时52分、多1天、车上过夜增加", "多14小时52分" in bar and "多1天" in bar and "车上过夜" in bar and "比默认方案" in bar, bar[:240])
    ncx = find_day("南昌 → 新干县")
    nc = kick(ncx)
    rec("普速经北京时，南昌那天从 07:26 到站开始、不住南昌酒店", "清晨到南昌" in nc and first_time(ncx).startswith("07:26"), nc)
    click(pg, '#phaseRail .modes [data-mode="ncxg:hsr"]')
    a = info(pg)
    ncx = find_day("南昌 → 新干县")
    nc = kick(ncx)
    rec("南昌→新干改高铁 → 天数不变、改从南昌西到新干东", a["days"] == 11 and "南昌西站" in route_of(ncx) and "新干东站" in route_of(ncx), nc)
    shot(pg, "07b-四段都切换后")
    # comparison panel
    pg.evaluate("scrollTo(0,0)"); time.sleep(0.2)
    idx = labels().index("返穗高铁")
    click(pg, '#phaseRail [data-phase="%d"]' % idx)
    ptxt = pg.inner_text("#segPanel%d" % idx)
    rec("展开交通段显示两种方式对比和“改选后”天数与预算", pg.locator("#segPanel%d .mode-opt" % idx).count() == 2 and "改选后：坐车船多10小时28分" in ptxt and "多1天" in ptxt, ptxt.replace(chr(10), " | ")[:220])
    shot(pg, "07c-交通方式对比")
    click(pg, '#segPanel%d [data-mode="xggz:rail"]' % idx)
    rec("在对比卡里点普速卧铺 → 切回 12 天", info(pg)["days"] == 12 and labels()[-1] == "返穗卧铺")
    # nanchang +1 with rail via Beijing
    click(pg, '[data-adjust="nanchang"][data-delta="1"]')
    fn = pg.evaluate("[...document.querySelectorAll('#dateRail .date')].findIndex(b=>/周. 南昌(?:，|$)/.test(b.getAttribute('aria-label')))")
    t8 = first_time(fn); title8 = pg.inner_text("#dayTitle")
    rec("普速到南昌再加南昌 1 天 → 第一个南昌日从 07:26 到站开始", title8.startswith("南昌完整游玩日") and t8.startswith("07:26") and info(pg)["days"] == 13, "第 8 天：" + title8 + " " + t8)
    # persistence
    pg.reload(wait_until="domcontentloaded"); time.sleep(2.5)
    rec("刷新后交通方式和天数保留", modes() == '{"gzqd":"hsr","dlnc":"rail","ncxg":"hsr","xggz":"rail"}' and info(pg)["days"] == 13)
    click(pg, "#adjustToggle")
    click(pg, "#resetStays")
    rec("恢复默认 → 12 天、默认交通方式", info(pg)["days"] == 12 and modes() == '{"gzqd":"rail","dlnc":"hsr","ncxg":"rail","xggz":"rail"}', info(pg)["budget"])
    click(pg, "#adjustToggle")
    pg.evaluate("document.querySelector('#dateRail [data-day=\"0\"]').click()"); time.sleep(0.3)
    rec("切换交通后无横向溢出", overflow(pg) <= 0)
    pg.evaluate("document.getElementById('dayCard').scrollIntoView()"); time.sleep(0.3)

    # 6 date rail tap + sticky
    click(pg, '#dateRail [data-day="4"]')
    a = info(pg)
    rail_top = pg.evaluate("document.getElementById('railWrap').getBoundingClientRect().top")
    rec("日期条点选第 5 天（烟台夜船）且日期条吸顶", "海上" in a["kicker"] and abs(rail_top) < 1, a["kicker"] + " railTop=%s cardTop=%s" % (rail_top, pg.evaluate("dayCard.getBoundingClientRect().top")))
    shot(pg, "07-夜船日")
    tk = pg.locator("#dayLegs .tk")
    rec("夜船当天的车船显示两张票和22:00烟台北上船", tk.count() == 2 and "C6571" in tk.nth(0).inner_text() and "烟台站" in tk.nth(0).inner_text() and "22:00" in tk.nth(1).inner_text() and "烟台北站" in tk.nth(1).inner_text() and "约7小时0分" in tk.nth(1).inner_text())

    # 7 date rail horizontal scroll does not move page vertically
    y0 = pg.evaluate("scrollY")
    box = pg.locator("#dateRail").bounding_box()
    pg.mouse.move(box["x"] + 300, box["y"] + 30)
    pg.evaluate("document.getElementById('dateRail').scrollBy(200,0)")
    time.sleep(0.3)
    y1 = pg.evaluate("scrollY")
    rec("日期条横向滚动不带动纵向滚动", y0 == y1, "scrollY %s→%s, railScroll=%s" % (y0, y1, pg.evaluate("dateRail.scrollLeft")))

    # 8 swipe on card (touch)
    cdp = ctx.new_cdp_session(pg)
    def swipe(x0, x1, y):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y}]})
        for k in range(1, 9):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * k / 8, "y": y + k}]})
            time.sleep(0.015)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        time.sleep(0.5)
    before = info(pg)["kicker"]
    print("at400:", pg.evaluate("(()=>{const e=document.elementFromPoint(214,400);return e.className+'|'+e.tagName})()"), "scrollY", pg.evaluate("scrollY"))
    swipe(330, 90, 400)
    print("url after swipe", pg.url)
    after = info(pg)["kicker"]
    rec("卡片左滑 → 后一天", before != after and "第 6" in after, before + " → " + after)
    swipe(90, 330, 400)
    rec("卡片右滑 → 前一天", "第 5" in info(pg)["kicker"])
    # vertical swipe should scroll, not change day
    y0 = pg.evaluate("scrollY")
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": 200, "y": 700}]})
    for k in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": 200 + k * 3, "y": 700 - k * 30}]})
        time.sleep(0.015)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    time.sleep(0.5)
    rec("卡片纵向滑动 → 只滚动页面、不切换日期", "第 5" in info(pg)["kicker"] and pg.evaluate("scrollY") > y0, "scrollY %s→%s" % (y0, pg.evaluate("scrollY")))

    # 9 step sheet
    click(pg, '#steps [data-step="4"]')
    rec("步骤抽屉打开（夜船）", pg.locator("#overlay.open").count() == 1 and "烟台北站 → 旅顺西站" in pg.inner_text("#sheetContent"))
    shot(pg, "08-步骤抽屉")
    # drag-to-close
    gb = pg.locator("#sheetGrip").bounding_box()
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": gb["x"] + 200, "y": gb["y"] + 10}]})
    for k in range(1, 9):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": gb["x"] + 200, "y": gb["y"] + 10 + k * 25}]})
        time.sleep(0.02)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    time.sleep(0.5)
    rec("下拉把手关闭抽屉", pg.locator("#overlay.open").count() == 0)

    # 10 budget sheet + goto
    pg.evaluate("scrollTo(0,0)"); time.sleep(0.3)
    click(pg, "#budgetBtn")
    txt = pg.inner_text("#sheetContent")
    rec("预算抽屉打开且总额与概览一致", info(pg)["budget"].replace(",", "") in txt.replace(",", ""), info(pg)["budget"])
    shot(pg, "09-预算抽屉")
    pg.locator("#sheetContent").evaluate("e=>e.closest('.sheet').scrollTop=400"); time.sleep(0.2)
    shot(pg, "09b-预算抽屉-下滑")
    click(pg, '#sheetContent [data-goto="9"]')
    rec("预算行点按 → 关闭抽屉并跳到对应日期", pg.locator("#overlay.open").count() == 0 and "第 10" in info(pg)["kicker"], info(pg)["kicker"])

    # 12 map
    pg.evaluate("scrollTo(0,0)"); time.sleep(0.3)
    click(pg, "#mapBtn")
    print("after map", pg.evaluate("[overlay.className, sheetLabel.textContent]"))
    rec("路线图抽屉打开", "固定顺序" in pg.inner_text("#sheetContent"))
    shot(pg, "12-路线图")
    click(pg, "#closeSheet")

    rec("全程无横向溢出", overflow(pg) <= 0)
    rec("控制台无错误", not errs, "; ".join(errs))
    ctx.close()

    # 14 during-trip "today" (fake clock 2026-10-15)
    ctx = b.new_context(viewport={"width": 428, "height": 926}, device_scale_factor=3, is_mobile=True, has_touch=True, user_agent=UA)
    ctx.add_init_script("""(()=>{const T=new Date(2026,9,15,9,0).getTime();const D=Date;class F extends D{constructor(...a){super(...(a.length?a:[T]))}static now(){return T}};window.Date=F})()""")
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded"); time.sleep(2.5)
    rec("行程期间（模拟 10/15）自动选中今天并显示“查看今天”", "10/15" in info(pg)["kicker"] and pg.locator("#todayBtn").is_visible(), pg.inner_text("#todayBtn"))
    shot(pg, "14-行程中-今天")
    click(pg, "#todayBtn")
    shot(pg, "15-行程中-跳到今天")
    ctx.close()

    # 15 desktop
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded"); time.sleep(2.5)
    rec("桌面 1440 无横向溢出", overflow(pg) <= 0)
    shot(pg, "16-桌面")
    click(pg, '#steps [data-step="0"]')
    shot(pg, "17-桌面-抽屉")
    ctx.close()
    b.close()

json.dump(log, open(os.path.join(OUT, "check-log.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("TOTAL", len(log), "FAIL", sum(not x["ok"] for x in log))
sys.exit(1 if any(not x["ok"] for x in log) else 0)
