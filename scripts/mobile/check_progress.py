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


def clock(ctx, iso):
    ctx.add_init_script("""(()=>{const T=new Date(%s).getTime(),D=Date;
class F extends D {constructor(...a){super(...(a.length?a:[T]))}static now(){return T}}window.Date=F})()""" % json.dumps(iso))


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome")
    ctx = browser.new_context(viewport={"width": 428, "height": 926},
                              device_scale_factor=3, is_mobile=True, has_touch=True)
    clock(ctx, "2026-10-11T09:00:00+08:00")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL, wait_until="domcontentloaded")
    check("出发前倒计时、仅本机与默认9项预订", "还有 1 天" in pg.inner_text("#tripProgressText")
          and pg.inner_text("#syncState") == "仅本机" and "0 / 9" in pg.inner_text("#bookingSummary"))
    check("普通模式隐藏独立预订按钮及锁定提示", pg.locator('#phaseRail > .booking-actions:visible, #phaseRail > .lock-note:visible, #dayCard .book-toggle:visible').count() == 0)
    check("未订顶部文案与城市晚数小标记", pg.inner_text('#planStatus') == '12天 · 候选未订票'
          and pg.locator('#phaseRail .hotel-badge').count() == 3
          and pg.locator('#phaseRail .hotel-badge.booked').count() == 0)
    check("进度卡删除手动说明，车船小时不折行", '不连接购票' not in pg.inner_text('.trip-progress')
          and '67–68h' in pg.inner_text('#statTransitSub')
          and pg.locator('.transit-hours').evaluate("e=>getComputedStyle(e).whiteSpace==='nowrap'&&e.scrollWidth<=e.clientWidth"))
    check("待订票面小字为灰色", pg.locator('#phaseRail .book-badge').first.evaluate("e=>getComputedStyle(e).color==='rgb(140, 146, 141)'"))
    tap(pg, '#phaseRail [data-phase="0"]')
    check("非调整模式点开详情可改预订", pg.locator('#segPanel0 [data-book="leg:gzqd:rail"]').is_visible())
    tap(pg, '#phaseRail [data-phase="0"]')
    pg.evaluate("scrollTo({top:0,behavior:'instant'})")
    shot(pg, "01-before-trip")
    check("所有步骤ID唯一且符合48字符白名单", pg.evaluate("""()=>{
const ids=[...document.querySelectorAll('#steps [data-done]')].map(e=>e.dataset.done);
return new Set(ids).size===ids.length&&ids.every(id=>/^[a-z0-9:_-]{1,48}$/.test(id))} """))
    tap(pg, '#steps [data-done="d:qd-depart-rail:0"]')
    check("勾选不误开详情", pg.locator("#overlay.open").count() == 0)
    check("已完成与日期计数更新", pg.locator('#steps [data-done="d:qd-depart-rail:0"]').get_attribute("aria-pressed") == "true"
          and "1/" in pg.inner_text('#dateRail [data-day="0"] .day-done'))
    tap(pg, '#steps [data-step="0"]')
    check("正文仍打开详情并可取消完成", pg.locator("#overlay.open").count() == 1)
    tap(pg, '#sheetContent [data-done="d:qd-depart-rail:0"]')
    check("详情取消同步到当天步骤", pg.locator('#steps [data-done="d:qd-depart-rail:0"]').get_attribute("aria-pressed") == "false")
    pg.keyboard.press("Escape")
    check("抽屉关闭后焦点返回原步骤", pg.evaluate("document.activeElement.dataset.step==='0'"))
    tap(pg, '#steps [data-done="d:qd-depart-rail:0"]')
    pg.reload(wait_until="domcontentloaded")
    check("刷新保留完成状态", pg.locator('#steps [data-done="d:qd-depart-rail:0"]').get_attribute("aria-pressed") == "true")
    for id in pg.locator('#steps [data-done]').evaluate_all('es=>es.map(e=>e.dataset.done)'):
        if pg.locator(f'#steps [data-done="{id}"]').get_attribute('aria-pressed') != 'true':
            tap(pg, f'#steps [data-done="{id}"]')
    check('当天全部完成显示勾号且44px触控目标达标', pg.inner_text('#dateRail [data-day="0"] .day-done') == '✓'
          and pg.locator('#steps [data-done]').first.bounding_box()['width'] >= 44
          and pg.locator('#steps [data-done]').first.bounding_box()['height'] >= 44)
    shot(pg, '07-completed-steps')
    tap(pg, '#bookingSummary')
    check('手动记录说明保留在抽屉', '手动记录' in pg.inner_text('#sheetContent') and '不代表已出票或订房' in pg.inner_text('#sheetContent'))
    tap(pg, '#sheetContent [data-book="leg:gzqd:rail"]')
    check('部分预订顶部文案与绿色票面', pg.inner_text('#planStatus') == '12天 · 已订 1/9'
          and pg.locator('#phaseRail .book-badge.booked').first.evaluate("e=>getComputedStyle(e).color==='rgb(53, 127, 82)'"))
    pg.keyboard.press('Escape')
    tap(pg, "#adjustToggle")
    check("已订票锁住切换且多入口状态一致", pg.locator('#phaseRail [data-mode="gzqd:hsr"]').is_disabled()
          and pg.locator('#phaseRail [data-book="leg:gzqd:rail"]').first.get_attribute("aria-pressed") == "true")
    tap(pg, '#phaseRail [data-phase="0"]')
    check("展开详情也不能改已订方式", pg.locator('#segPanel0 [data-mode="gzqd:hsr"]').is_disabled())
    tap(pg, '#phaseRail [data-phase="0"]')
    tap(pg, '#phaseRail [data-book="hotel:qd"]')
    check("酒店已订锁住加减", pg.locator('[data-adjust="qingdao"][data-delta="1"]').is_disabled()
          and pg.locator('[data-adjust="qingdao"][data-delta="-1"]').is_disabled())
    shot(pg, "02-booked-locks")
    tap(pg, '#adjustToggle')
    check('退出调整隐藏独立按钮并保留酒店已订标记', pg.locator('#phaseRail > .booking-actions:visible, #phaseRail > .lock-note:visible').count() == 0
          and pg.locator('#phaseRail .hotel-badge.booked').count() == 1
          and pg.inner_text('#planStatus') == '12天 · 已订 2/9')
    pg.evaluate('scrollTo(0,0)')
    shot(pg, '08-compact-overview')
    tap(pg, '#adjustToggle')
    tap(pg, "#bookingSummary")
    check("集中预订抽屉显示手动记录与待选定酒店", "待订 · 7" in pg.inner_text("#sheetContent")
          and "已订 · 2" in pg.inner_text("#sheetContent") and "酒店待选定" in pg.inner_text("#sheetContent"))
    shot(pg, "03-booking-drawer")
    tap(pg, '#sheetContent [data-book="hotel:qd"]')
    check("取消酒店后解锁，抽屉不关闭", not pg.locator('[data-adjust="qingdao"][data-delta="1"]').is_disabled()
          and pg.locator("#overlay.open").count() == 1)
    tap(pg, '#sheetContent [data-book="leg:gzqd:rail"]')
    all_ids = pg.locator('#sheetContent [data-book]').evaluate_all('es=>es.map(e=>e.dataset.book)')
    for id in all_ids:
        tap(pg, f'#sheetContent [data-book="{id}"]')
    check('全部订好顶部写全部已订', pg.inner_text('#planStatus') == '12天 · 全部已订' and '9 / 9' in pg.inner_text('#bookingSummary'))
    for id in all_ids:
        tap(pg, f'#sheetContent [data-book="{id}"]')
    check('取消全部预订恢复候选未订票', pg.inner_text('#planStatus') == '12天 · 候选未订票')
    pg.keyboard.press("Escape")
    tap(pg, '#phaseRail [data-mode="gzqd:hsr"]')
    check("取消车票后可切换高铁", pg.locator('#phaseRail [data-mode="gzqd:hsr"]').get_attribute("aria-pressed") == "true")
    tap(pg, '#phaseRail [data-book="leg:gzqd:hsr"]')
    check("恢复默认不能绕过已订锁", pg.locator("#resetStays").is_disabled())
    # Programmatic event also cannot bypass the data-level guard.
    pg.locator('#phaseRail [data-mode="gzqd:rail"]').evaluate("e=>e.dispatchEvent(new MouseEvent('click',{bubbles:true}))")
    check("事件层也拦截已订修改", pg.locator('#phaseRail [data-mode="gzqd:hsr"]').get_attribute("aria-pressed") == "true")
    pg.reload(wait_until="domcontentloaded")
    check("刷新保留已订及锁定", pg.locator('#phaseRail [data-book="leg:gzqd:hsr"]').first.get_attribute("aria-pressed") == "true"
          and pg.locator('#phaseRail [data-mode="gzqd:rail"]').is_disabled())
    tap(pg, '#adjustToggle')
    tap(pg, '#phaseRail [data-book="leg:gzqd:hsr"]')
    # Retain bookings of inactive transport modes without displaying them.
    pg.evaluate("""()=>{const state=JSON.parse(localStorage.getItem('china-trip-v3-progress'));
state.booked['leg:gzqd:rail']=true;localStorage.setItem('china-trip-v3-progress',JSON.stringify(state))}""")
    pg.reload(wait_until="domcontentloaded")
    check("旧方式预订保留但不显示、不计数", pg.locator('[data-book="leg:gzqd:rail"]').count() == 0
          and "已订 0 / 9" in pg.inner_text("#bookingSummary"))
    tap(pg, "#adjustToggle")
    tap(pg, '#phaseRail [data-mode="gzqd:rail"]')
    check("回到旧方式恢复已订记录", pg.locator('#phaseRail [data-book="leg:gzqd:rail"]').first.get_attribute("aria-pressed") == "true")
    tap(pg, '#phaseRail [data-book="leg:gzqd:rail"]')
    tap(pg, '#phaseRail [data-book="leg:ferry"]')
    check("已订夜船锁住会顺延船期的上游停留", pg.locator('[data-adjust="qingdao"][data-delta="1"]').is_disabled())
    tap(pg, '#phaseRail [data-book="leg:ferry"]')
    # Stable source IDs survive changes before a completed day.
    tap(pg, '#dateRail [data-day="6"]')
    first_id = pg.locator('#steps [data-done]').first.get_attribute('data-done')
    tap(pg, '#steps [data-done]')
    tap(pg, '[data-adjust="qingdao"][data-delta="1"]')
    tap(pg, '#dateRail [data-day="7"]')
    check("加青岛一天后大连完成状态不串日", pg.locator('#steps [data-done]').first.get_attribute('data-done') == first_id
          and pg.locator('#steps [data-done]').first.get_attribute('aria-pressed') == 'true')
    tap(pg, '[data-adjust="xingan"][data-delta="1"]')
    # The added family day must not inherit the first family day's flags.
    family_ids = []
    for index in range(pg.locator('#dateRail [data-day]').count()):
        pg.locator(f'#dateRail [data-day="{index}"]').evaluate("e=>e.click()")
        ids = pg.locator('#steps [data-done]').evaluate_all("es=>es.map(e=>e.dataset.done)")
        family_ids.extend(x for x in ids if x.startswith('d:family-'))
    check("复制探亲日ID互不重复", len(family_ids) >= 6 and len(set(family_ids)) == len(family_ids))
    check("清单与天气功能完整保留", pg.locator('#packBtn').count() == 1)
    tap(pg, '#packBtn')
    check("打包清单仍可操作", pg.locator('[data-pack]').count() > 15 and '天气' in pg.inner_text('#sheetContent'))
    pg.keyboard.press('Escape')
    check("手机无横向溢出与运行错误", pg.evaluate('document.documentElement.scrollWidth<=innerWidth') and not errors)
    ctx.close()

    # China calendar day does not depend on the device's timezone.
    for label, instant, expected, timezone in [
        ('04-during-trip', '2026-10-15T09:00:00+08:00', '第 4 / 12 天', 'America/New_York'),
        ('05-after-trip', '2026-10-24T09:00:00+08:00', '行程已结束', 'Asia/Shanghai'),
    ]:
        ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                                  is_mobile=True, has_touch=True, timezone_id=timezone)
        clock(ctx, instant)
        pg = ctx.new_page()
        pg.goto(URL, wait_until='domcontentloaded')
        check(label + ' 按北京时间判断进度', expected in pg.inner_text('#tripProgressText'))
        if 'during' in label:
            check('过去日期变浅且今天可跳转', pg.locator('#dateRail .past').count() == 3
                  and pg.locator('#todayBtn').is_visible() and '10/15' in pg.inner_text('#dayKicker'))
            pg.evaluate('scrollTo(0,0)')
        shot(pg, label)
        ctx.close()

    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    check('桌面无横向溢出', pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    shot(pg, '06-desktop')
    browser.close()

with open(os.path.join(OUT, 'checks.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
failures = sum(not x['ok'] for x in results)
print('TOTAL', len(results), 'FAIL', failures)
sys.exit(1 if failures else 0)
