"""First-stage redesign: responsive tabs, today screens and adjustment drawer."""
import json
import os
from playwright.sync_api import sync_playwright
from ui_tabs import tab, adjust

O = os.environ['O']
URL = os.environ.get('URL', 'http://127.0.0.1:8731/travel/')
os.makedirs(O, exist_ok=True)
results = []


def check(label, ok):
    results.append({'check': label, 'ok': bool(ok)})
    print(('PASS ' if ok else 'FAIL ') + label, flush=True)


def shot(pg, label):
    pg.evaluate("scrollTo({top:0,behavior:'instant'})")
    pg.wait_for_timeout(300)
    pg.screenshot(path=os.path.join(O, label + '.png'))


def audit(pg, label):
    check(label + '没有横向溢出', pg.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    tiny = pg.evaluate("""()=>[...document.querySelectorAll('body *')].filter(e=>e.getClientRects().length &&
      [...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize)<12)
      .map(e=>e.className+':'+getComputedStyle(e).fontSize)""")
    check(label + '可见文字不小于12px', not tiny)
    if tiny:
        print('FONT', tiny, flush=True)
    check(label + '车次航司不截断', pg.locator('.tk-mid small:visible').evaluate_all(
        "es=>es.every(e=>getComputedStyle(e).textOverflow!=='ellipsis'&&e.scrollWidth<=e.clientWidth+1)"))


with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    errors = []
    for desktop in (False, True):
        size = 'desktop' if desktop else 'mobile'
        for iso, label in [('2026-10-13T08:00:00+08:00', '10-13-0800'),
                           ('2026-10-13T13:00:00+08:00', '10-13-1300'),
                           ('2026-10-16T20:00:00+08:00', '10-16-2000'),
                           ('2026-10-18T12:00:00+08:00', '10-18-1200')]:
            ctx = b.new_context(viewport={'width':1440 if desktop else 428,'height':900 if desktop else 926},
                                device_scale_factor=1 if desktop else 3,is_mobile=not desktop,has_touch=not desktop)
            ctx.add_init_script("""{const D=Date,T=new D(%s).getTime();window.Date=class extends D {
              constructor(...a){super(...(a.length?a:[T]))}static now(){return T}};}""" % json.dumps(iso))
            pg = ctx.new_page()
            pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
            pg.goto(URL,wait_until='domcontentloaded')
            check(size+label+'正确页面且非空', '/travel/' in pg.url and '行程' in pg.title() and pg.locator('#dayKicker').is_visible())
            check(size+label+'默认今天且只显示一个面板',pg.locator('#tab-today').get_attribute('aria-selected')=='true' and pg.locator('.tab-panel:visible').count()==1)
            check(size+label+'日期正确',label[:5].replace('-','/') in pg.inner_text('#dayKicker'))
            check(size+label+'四个页签',pg.locator('#appTabs [data-tab]').count()==4)
            check(size+label+'今天没有路线统计和小标签',pg.locator('#page-today .stat:visible,#page-today .ledger:visible,#steps em:visible').count()==0)
            audit(pg,size+label)
            shot(pg,size+'-today-'+label)
            if label=='10-13-1300':
                check(size+'13点下一步15点入住','15:00' in pg.inner_text('#nextTime') and '入住一然' in pg.inner_text('#nextTitle'))
                check(size+'民宿和免费取消截止完整',all(x in pg.inner_text('#dayNightSub') for x in ('1单元0704','133.49','15:00','12:00','10/12 12:00前可免费取消')))
                for name in ('booking','route','packing'):
                    tab(pg,name)
                    check(size+name+'切换',pg.locator('#page-'+name).is_visible() and pg.locator('.tab-panel:visible').count()==1)
                    audit(pg,size+name)
                    shot(pg,size+'-'+name)
                    pg.reload(wait_until='domcontentloaded')
                    check(size+name+'刷新记住页签',pg.locator('#tab-'+name).get_attribute('aria-selected')=='true')
                tab(pg,'route')
                check(size+'行程没有重复统计和外露调整',pg.locator('#allocationSummary:visible,#stayControls:visible,#weihaiToggle:visible').count()==0)
                adjust(pg)
                check(size+'调整控件集中抽屉',pg.locator('#adjustOverlay').is_visible() and pg.locator('#weihaiToggle').is_visible())
                audit(pg,size+'adjust')
                shot(pg,size+'-adjust')
                pg.locator('[data-adjust="nanchang"][data-delta="1"]').click()
                check(size+'变化提示在抽屉内',pg.locator('#changeBar').is_visible() and pg.locator('#changeBar').evaluate("e=>!!e.closest('#adjustPanel')"))
                pg.locator('#changeBar').scroll_into_view_if_needed()
                check(size+'抽屉滚到底仍可关闭',pg.locator('#closeAdjust').evaluate("e=>{let r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return !!h&&(h===e||e.contains(h))}"))
                shot(pg,size+'-adjust-change')
                pg.keyboard.press('Escape')
                check(size+'Esc关闭且恢复焦点',pg.locator('#adjustOverlay').is_hidden() and pg.evaluate("document.activeElement.id==='adjustTop'"))
                pg.locator('[data-route-detail="3"]').click()
                pg.locator('#sheetContent [data-goto]').first.click()
                check(size+'路线日期切今天且可回今天',pg.locator('#page-today').is_visible() and '10/15' in pg.inner_text('#dayKicker') and pg.locator('#backToday').is_visible())
                pg.locator('#backToday').click()
                check(size+'回到实际今天','10/13' in pg.inner_text('#dayKicker'))
            ctx.close()
    check('所有场景控制台无错误',not errors)
    b.close()
with open(os.path.join(O,'nav-checks.json'),'w',encoding='utf-8') as f:
    json.dump(results,f,ensure_ascii=False,indent=1)
print('TOTAL',len(results),'FAIL',sum(not x['ok'] for x in results))
raise SystemExit(1 if any(not x['ok'] for x in results) else 0)
