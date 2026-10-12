"""428x926 local booking/progress regression after presentation redesign."""
import json
import os
import sys
from playwright.sync_api import sync_playwright
from ui_tabs import tab, adjust, close_adjust

URL, OUT = sys.argv[1:3]
os.makedirs(OUT,exist_ok=True)
results=[]


def check(label,ok):
    results.append({'check':label,'ok':bool(ok)})
    print(('PASS ' if ok else 'FAIL ')+label,flush=True)


with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome')
    errors=[]
    def page(iso,seed=None,reduce=False):
        ctx=browser.new_context(viewport={'width':428,'height':926},device_scale_factor=3,is_mobile=True,has_touch=True,reduced_motion='reduce' if reduce else 'no-preference')
        ctx.add_init_script("""(()=>{const D=Date;window.__testTime=new D(%s).getTime();window.Date=class extends D {
          constructor(...a){super(...(a.length?a:[window.__testTime]))}static now(){return window.__testTime}};
          const interval=setInterval;window.setInterval=(fn,ms,...a)=>{if(ms===60000)window.__testMinuteTick=()=>fn(...a);return interval(fn,ms,...a)}})()""" % json.dumps(iso))
        if seed:
            ctx.add_init_script(seed)
        pg=ctx.new_page()
        pg.on('pageerror',lambda e:errors.append(str(e)))
        pg.on('console',lambda m:m.type=='error' and errors.append(m.text))
        pg.goto(URL,wait_until='domcontentloaded')
        return ctx,pg
    def tap(pg,sel):
        pg.locator(sel).first.tap()
    ctx,pg=page('2026-10-12T09:00:00+08:00')
    check('出发前今天页写明天出发',pg.locator('#page-today').is_visible() and '明天出发' in pg.inner_text('#dayKicker'))
    check('出发前不编倒计时',pg.locator('#nextStep').is_hidden() and pg.locator('#departureNote').is_visible())
    check('未来日没有0完成数',pg.locator('#dateRail .day-done').count()==0)
    tap(pg,'#steps [data-done="d:qd-arrive-air:0"]')
    check('勾选不误开详情且44px',pg.locator('#overlay.open').count()==0 and pg.locator('#steps .step-check').first.bounding_box()['width']>=44)
    pg.reload(wait_until='domcontentloaded')
    check('刷新保留步骤',pg.locator('#steps [data-done="d:qd-arrive-air:0"]').get_attribute('aria-pressed')=='true')
    tab(pg,'booking')
    check('预订3/11且青岛按晚独立','3 / 11' in pg.inner_text('#bookingCount') and pg.locator('#bookingList [data-book="hotel:qd:2026-10-13"]').get_attribute('aria-pressed')=='true' and pg.locator('#bookingList [data-book="hotel:qd:2026-10-14"]').get_attribute('aria-pressed')=='false')
    check('已付订单及九元任务可见',all(x in pg.inner_text('#page-booking') for x in ('133.49','10/12 12:00前免费取消','入住离店后即完成')))
    tap(pg,'#bookingList [data-book="hotel:nc"]')
    adjust(pg)
    check('已订酒店锁南昌',pg.locator('[data-adjust="nanchang"][data-delta="1"]').is_disabled())
    close_adjust(pg);tab(pg,'booking');tap(pg,'#bookingList [data-book="hotel:nc"]');adjust(pg)
    check('取消后解锁南昌',not pg.locator('[data-adjust="nanchang"][data-delta="1"]').is_disabled())
    check('已订航班锁方式和日期',pg.locator('#phaseRail .modes [data-mode="gzqd:rail"]').is_disabled() and pg.locator('[data-adjust="qingdao"][data-delta="1"]').is_disabled())
    close_adjust(pg);tab(pg,'booking');tap(pg,'#bookingList [data-book="leg:shengsheng"]');adjust(pg)
    check('已订船锁威海',pg.locator('#weihaiToggle').is_disabled())
    close_adjust(pg);tab(pg,'booking');tap(pg,'#bookingList [data-book="leg:shengsheng"]')
    ids=pg.locator('#bookingList [data-book][aria-pressed="false"]').evaluate_all('es=>es.map(e=>e.dataset.book)')
    for id in ids:
        tap(pg,f'#bookingList [data-book="{id}"]')
    check('全部已订进度',pg.inner_text('#bookingCount')=='已订 11 / 11' and pg.locator('#bookingTrack').get_attribute('aria-valuenow')=='11')
    for id in ids:
        tap(pg,f'#bookingList [data-book="{id}"]')
    check('恢复3/11且实付预算不变',pg.inner_text('#bookingCount')=='已订 3 / 11' and pg.inner_text('#statBudget')=='¥3,665.49–5,189.49')
    tab(pg,'packing');pg.locator('[data-pack="0-4"]').check();pg.reload(wait_until='domcontentloaded')
    check('清单和页签刷新保留',pg.locator('#page-packing').is_visible() and pg.locator('[data-pack="0-4"]').is_checked())
    ctx.close()
    ctx,pg=page('2026-10-12T09:00:00+08:00',"""if(!localStorage.getItem('migration-test')){
      localStorage.setItem('china-trip-v4-progress',JSON.stringify({done:{'d:qd-arrive-air:0':true},booked:{'leg:gzqd:air':true,'leg:dlnc:air':true,'hotel:qd':true}}));
      localStorage.setItem('china-trip-v3-pack','{"0-4":1}');localStorage.setItem('migration-test','1')}""")
    tab(pg,'booking')
    check('旧v4迁移不误订第二晚','3 / 11' in pg.inner_text('#bookingCount') and pg.locator('#bookingList [data-book="hotel:qd:2026-10-14"]').get_attribute('aria-pressed')=='false')
    tap(pg,'#bookingList [data-book="hotel:qd:2026-10-13"]');pg.reload(wait_until='domcontentloaded')
    check('取消后刷新不重勾','2 / 11' in pg.inner_text('#bookingCount'))
    tab(pg,'today')
    check('旧完成记录不丢',pg.locator('#steps [data-done="d:qd-arrive-air:0"]').get_attribute('aria-pressed')=='true')
    tab(pg,'packing')
    check('旧清单不丢',pg.locator('[data-pack="0-4"]').is_checked());ctx.close()
    for iso,code,when,count in [('2026-10-13T08:00:00+08:00','AQ1019','10:30','还有 2 小时 30 分'),('2026-10-16T20:00:00+08:00','生生2','21:30','还有 1 小时 30 分'),('2026-10-18T12:00:00+08:00','MU6908','13:35','还有 1 小时 35 分'),('2026-10-16T23:00:00+08:00','生生2','约05:00','还有 6 小时')]:
        ctx,pg=page(iso)
        check(code+when+'下一步倒计时不变',code in pg.inner_text('#nextTicket') and when in pg.inner_text('#nextTicket') and pg.inner_text('#nextCountdown')==count)
        check(code+'不重复交通事项',pg.locator('#nextTitle').is_hidden() and pg.locator('#nextPlace').is_hidden())
        check(code+'同票默认折叠可展开',not pg.locator('#todayTickets').evaluate('e=>e.open'))
        check(code+'过时未勾仅提醒',pg.locator('#nextOverdue').is_visible())
        tap(pg,'#nextOverdue');before=pg.locator('#sheetContent [data-done]').count();tap(pg,'#sheetContent [data-done]')
        check(code+'補勾更新',pg.locator('#sheetContent [data-done]').count()==before-1);pg.keyboard.press('Escape')
        if code=='AQ1019':
            tap(pg,'#nextComplete')
            check('完成切下一步',pg.evaluate("JSON.parse(localStorage.getItem('china-trip-v4-progress')).done['d:qd-arrive-air:2']===true"))
            pg.evaluate("window.__testTime=Date.parse('2026-10-13T14:59:00+08:00');window.__testMinuteTick()")
            check('分钟刷新',pg.inner_text('#nextCountdown')=='还有 1 分')
            pg.evaluate("window.__testTime=Date.parse('2026-10-14T00:01:00+08:00');window.__testMinuteTick()")
            check('午夜进度和今天页一起刷新','第 2 / 11 天' in pg.inner_text('#tripProgressText') and '10/14' in pg.inner_text('#dayKicker') and pg.locator('#nextStep').is_visible())
        ctx.close()
    ctx,pg=page('2026-10-14T20:00:00+08:00')
    for id in pg.locator('#steps [data-done]').evaluate_all('es=>es.map(e=>e.dataset.done)'):
        tap(pg,f'#steps [data-done="{id}"]')
    check('全完成显示明天','明天 · 10/15' in pg.inner_text('#nextWhen') and '07:40' in pg.inner_text('#nextTime'))
    check('日期全完成✓',pg.locator('#dateRail [data-day="1"] .day-done').text_content()=='✓')
    tap(pg,'#steps [data-step="0"]')
    check('触屏无焦点光环',pg.locator('#closeSheet').evaluate("e=>getComputedStyle(e).boxShadow==='none'"));pg.keyboard.press('Escape');pg.keyboard.press('Enter')
    check('键盘保留焦点',pg.locator('#overlay.open').count()==1 and pg.locator('#closeSheet').evaluate("e=>getComputedStyle(e).outlineStyle==='solid'"));ctx.close()
    ctx,pg=page('2026-10-24T09:00:00+08:00',reduce=True)
    check('结束默认行程且reduced-motion',pg.locator('#page-route').is_visible() and pg.evaluate("matchMedia('(prefers-reduced-motion:reduce)').matches"));ctx.close()
    ctx,pg=page('2026-10-12T09:00:00+08:00',"Storage.prototype.setItem=function(){throw Error('quota')}")
    check('存储失败提示可见',pg.locator('#localNotice').is_visible() and '可能丢失' in pg.inner_text('#localNotice'));ctx.close()
    check('所有场景控制台0错误',not errors);browser.close()
with open(os.path.join(OUT,'progress-checks.json'),'w',encoding='utf-8') as f:
    json.dump(results,f,ensure_ascii=False,indent=1)
print('TOTAL',len(results),'FAIL',sum(not x['ok'] for x in results))
sys.exit(1 if any(not x['ok'] for x in results) else 0)
