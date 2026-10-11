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
    check('出发前隐藏下一步且路线保持展开', pg.locator('#nextStep').is_hidden()
          and pg.locator('#stayControls').is_visible() and pg.locator('#routeExpand').is_hidden())
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
    check("已完成状态更新，未来日期不显示部分完成数", pg.locator('#steps [data-done="d:qd-depart-rail:0"]').get_attribute("aria-pressed") == "true"
          and pg.locator('#dateRail [data-day="0"] .day-done').count() == 0)
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
    check('页脚跟随已订数量且保留参考价和隐私说明', '已订 1/9 项为你手动记录' in pg.inner_text('#bookingFoot')
          and '均为参考' in pg.inner_text('footer') and '隐私' in pg.inner_text('footer'))
    pg.keyboard.press('Escape')
    tap(pg, "#adjustToggle")
    check("已订票锁住切换且多入口状态一致", pg.locator('#phaseRail [data-mode="gzqd:hsr"]').is_disabled()
          and pg.locator('#phaseRail [data-book="leg:gzqd:rail"]').first.get_attribute("aria-pressed") == "true")
    tap(pg, '#phaseRail [data-phase="0"]')
    check("展开详情也不能改已订方式", pg.locator('#segPanel0 [data-mode="gzqd:hsr"]').is_disabled())
    check('调整加交通详情同一预订按钮只出现一次', pg.locator('#phaseRail [data-book="leg:gzqd:rail"]:visible').count() == 1)
    shot(pg, '09-adjust-transit-detail')
    tap(pg, '#phaseRail [data-phase="0"]')
    for seg, ids in [(1, ['hotel:qd']), (2, ['leg:c6571', 'leg:ferry']),
                     (3, ['hotel:dl']), (5, ['hotel:nc'])]:
        tap(pg, f'#phaseRail [data-phase="{seg}"]')
        check(f'调整加详情第{seg}段预订按钮无重复', all(
            pg.locator(f'#phaseRail [data-book="{id}"]:visible').count() == 1 for id in ids))
        if seg == 2:
            shot(pg, '10-adjust-ferry-detail')
        tap(pg, f'#phaseRail [data-phase="{seg}"]')
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
    check('取消全部预订恢复页脚草案说明', pg.inner_text('#bookingFoot') == '这是行程草案，不代表已出票或订房。')
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

    # Fixed Beijing clock + explicit user completion flags, never auto-complete by time.
    for label, instant, done, title, countdown, tomorrow in [
        ('11-next-z168-arrival', '2026-10-13T21:00:00+08:00', {}, '抵达青岛北站', '还有 1 小时 45 分', False),
        ('12-next-c6571', '2026-10-16T12:30:00+08:00', {'d:ferry-depart:0': True}, 'C6571', '还有 1 小时 10 分', False),
        ('13-next-on-ferry', '2026-10-16T23:00:00+08:00', {f'd:ferry-depart:{i}': True for i in range(5)}, '抵达旅顺西站', '还有 6 小时', True),
        ('14-next-tomorrow', '2026-10-14T20:00:00+08:00', {}, '大学路', '还有 13 小时 30 分', True),
    ]:
        ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                                  is_mobile=True, has_touch=True, timezone_id='America/New_York')
        clock(ctx, instant)
        ctx.add_init_script("if(!localStorage.getItem('china-trip-v3-progress'))localStorage.setItem('china-trip-v3-progress',%s)" %
                            json.dumps(json.dumps({'done': done, 'booked': {}})))
        pg = ctx.new_page()
        case_errors = []
        pg.on('pageerror', lambda e: case_errors.append(str(e)))
        pg.goto(URL, wait_until='domcontentloaded')
        check(label + ' 页面身份及正常加载', '/travel/' in pg.url and '日行程' in pg.title()
              and pg.locator('#dayTitle').inner_text() != '')
        if label == '14-next-tomorrow':
            for _ in range(pg.locator('#steps [data-done]').count()):
                tap(pg, '#nextComplete')
            check('完成按钮逐步推进并同步日期勾号', pg.inner_text('#dateRail [data-day="2"] .day-done') == '✓'
                  and pg.locator('#overlay.open').count() == 0)
        check(label + ' 下一步及倒计时', title in pg.inner_text('#nextTitle')
              and pg.inner_text('#nextCountdown') == countdown
              and ('明天' in pg.inner_text('#nextWhen')) == tomorrow)
        check(label + ' 行程内默认收起路线且保留统计和时间条', pg.locator('#stayControls').is_hidden()
              and pg.locator('#timeLedger').is_visible() and pg.locator('.stat').count() == 3
              and pg.inner_text('#routeExpand') == '展开全部路线')
        check(label + ' 未来不显示完成数，过去今天显示', pg.evaluate("""()=>{
const current=Number(document.querySelector('#dateRail .today').dataset.day);
return [...document.querySelectorAll('#dateRail [data-day]')].every(e=>{
const count=e.querySelector('.day-done');return +e.dataset.day<=current?!!count:!count||count.textContent==='✓'})} """))
        if label != '14-next-tomorrow':
            text = pg.inner_text('#nextTicket')
            check(label + ' 车票显示出发到达时刻及站名', '→' not in text and pg.locator('#nextTicket .tk').count() == 1
                  and (('10/12' in text and '18:57' in text and '22:45' in text and '青岛北站' in text) if 'z168' in label else
                       ('13:40' in text and '14:54' in text and '烟台站' in text) if 'c6571' in label else
                       ('10/16' in text and '22:00' in text and '10/17' in text and '05:00' in text and '旅顺西站' in text)))
        pg.evaluate('scrollTo({top:0,behavior:"instant"})')
        shot(pg, label)
        if label == '12-next-c6571':
            tap(pg, '#dateRail [data-day="1"]')
            check('查看其他日期不改变今天下一步', 'C6571' in pg.inner_text('#nextTitle'))
            tap(pg, '#nextAll')
            tap(pg, '#routeExpand')
            check('路线展开真实可见', pg.locator('#stayControls').is_visible() and pg.inner_text('#routeExpand') == '收起全部路线')
            pg.reload(wait_until='domcontentloaded')
            check('展开状态刷新后保留', pg.locator('#stayControls').is_visible())
            tap(pg, '#routeExpand')
            tap(pg, '#adjustTop')
            check('收起时进入调整临时展开', pg.locator('#stayControls').is_visible())
            tap(pg, '#adjustTop')
            check('退出调整恢复收起偏好', pg.locator('#stayControls').is_hidden())
            pg.reload(wait_until='domcontentloaded')
            check('收起状态刷新后保留', pg.locator('#stayControls').is_hidden())
            tap(pg, '#nextComplete')
            check('下一步完成后推进且不打开详情', '烟台站休息' in pg.inner_text('#nextTitle')
                  and pg.locator('#steps [data-done="d:ferry-depart:1"]').get_attribute('aria-pressed') == 'true'
                  and pg.locator('#overlay.open').count() == 0)
            pg.reload(wait_until='domcontentloaded')
            check('下一步完成记录刷新不丢失', '烟台站休息' in pg.inner_text('#nextTitle'))
            tap(pg, '#nextAll')
            check('看今天全部跳到今天而非下一步所属日', '10/16' in pg.inner_text('#dayKicker'))
            check('单圈44px触控且竖线连续', pg.locator('#steps').evaluate("""e=>{
const rows=[...e.querySelectorAll('.step-row')];return !e.querySelector('.step-dot')&&rows.every((r,i)=>{
 const b=r.querySelector('.step-check').getBoundingClientRect(),line=getComputedStyle(r,'::before');
 return r.querySelectorAll('.step-check').length===1&&b.width>=44&&b.height>=44&&
 (i===rows.length-1?line.display==='none':line.bottom==='-22px'&&Math.abs(r.getBoundingClientRect().left+parseFloat(line.left)+1-b.x-b.width/2)<1)
})}"""))
            shot(pg, '15-single-circle-timeline')
            tap(pg, '#steps [data-step="1"]')
            check('手指打开详情关闭按钮无光环且焦点保留', pg.locator('#closeSheet').evaluate("e=>e===document.activeElement&&getComputedStyle(e).outlineStyle==='none'"))
            shot(pg, '16-touch-detail')
            pg.keyboard.press('Escape')
            pg.locator('#steps [data-step="1"]').focus()
            pg.keyboard.press('Enter')
            check('键盘打开详情仍有焦点光环与焦点陷阱', pg.locator('#closeSheet').evaluate("e=>getComputedStyle(e).outlineWidth==='3px'"))
            pg.keyboard.press('Shift+Tab')
            check('键盘焦点仍限制在抽屉内', pg.evaluate("sheet.contains(document.activeElement)"))
        if label == '13-next-on-ferry':
            tap(pg, '#dateRail [data-day="5"]')
            tap(pg, '#nextAll')
            check('明天提醒的看今天全部仍回今天', '10/16' in pg.inner_text('#dayKicker'))
        check(label + ' 无横向溢出和运行错误', pg.evaluate('document.documentElement.scrollWidth<=innerWidth') and not case_errors)
        ctx.close()

    ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                              is_mobile=True, has_touch=True)
    clock(ctx, '2026-10-16T23:00:00+08:00')
    ctx.add_init_script("localStorage.setItem('china-trip-v3-progress',JSON.stringify({done:Object.fromEntries([0,1,2,3].map(i=>['d:ferry-depart:'+i,true])),booked:{}}))")
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    check('夜船过时未勾仍提醒已到时间，不自动跳过', pg.inner_text('#nextCountdown') == '已到时间'
          and '烟台北站' in pg.inner_text('#nextTitle') and '22:00' in pg.inner_text('#nextTicket'))
    ctx.close()

    ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                              is_mobile=True, has_touch=True)
    clock(ctx, '2026-10-22T12:00:00+08:00')
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    check('Z168和K441夜车出发日与到达日分开标记', pg.inner_text('#dateRail [data-day="0"] i') == '夜车'
          and pg.inner_text('#dateRail [data-day="1"] i') == '→青岛'
          and pg.inner_text('#dateRail [data-day="10"] i') == '夜车'
          and pg.inner_text('#dateRail [data-day="11"] i') == '→广州')
    tap(pg, '#nextAll')
    shot(pg, '17-1022-date-rail')
    tap(pg, '#adjustTop')
    tap(pg, '#phaseRail [data-mode="xggz:hsr"]')
    check('返程高铁只有当天到达标签', pg.locator('#dateRail [data-day]').count() == 11
          and pg.inner_text('#dateRail [data-day="10"] i') == '→广州')
    ctx.close()

    ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                              is_mobile=True, has_touch=True)
    clock(ctx, '2026-10-23T20:00:00+08:00')
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    for _ in range(pg.locator('#steps [data-done]').count()):
        tap(pg, '#nextComplete')
    check('最后一天完成安全收尾，不越界到明天', '今天的安排已全部完成' in pg.inner_text('#nextTitle')
          and pg.locator('#nextComplete').is_disabled() and pg.inner_text('#nextCountdown') == '')
    ctx.close()

    ctx = browser.new_context(viewport={'width': 428, 'height': 926}, device_scale_factor=3,
                              is_mobile=True, has_touch=True)
    clock(ctx, '2026-10-13T21:00:00+08:00', manual_ticks=True)
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    pg.evaluate('window.__testTime+=60000;window.__testMinuteTick()')
    check('一分钟后倒计时自动刷新', pg.inner_text('#nextCountdown') == '还有 1 小时 44 分')
    pg.evaluate('window.__testTime+=3*3600000;window.__testMinuteTick()')
    check('跨午夜按北京时间换为新一天', '今天 · 10/14' == pg.inner_text('#nextWhen')
          and pg.inner_text('#nextTitle') == '八大关')
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
        else:
            check('行程结束隐藏下一步且展开路线', pg.locator('#nextStep').is_hidden() and pg.locator('#stayControls').is_visible())
        shot(pg, label)
        ctx.close()

    ctx = browser.new_context(viewport={'width': 1440, 'height': 900})
    pg = ctx.new_page()
    pg.goto(URL, wait_until='domcontentloaded')
    check('桌面无横向溢出', pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    shot(pg, '06-desktop')
    pg.locator('#adjustTop').click()
    pg.locator('#phaseRail [data-mode="xggz:hsr"]').click()
    pg.evaluate('scrollTo({top:document.documentElement.scrollHeight,behavior:"instant"})')
    pg.wait_for_timeout(400)
    check('1440宽变化条出现时页脚完整露出', pg.locator('#changeBar').is_visible()
          and pg.locator('footer').bounding_box()['y'] + pg.locator('footer').bounding_box()['height']
          < pg.locator('#changeBar').bounding_box()['y'] - 8)
    shot(pg, '18-desktop-change-footer')
    browser.close()

with open(os.path.join(OUT, 'checks.json'), 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
failures = sum(not x['ok'] for x in results)
print('TOTAL', len(results), 'FAIL', failures)
sys.exit(1 if failures else 0)
