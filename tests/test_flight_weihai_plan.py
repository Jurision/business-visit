"""Run the actual itinerary builder in Node, without adding a browser API."""
import itertools
import json
import pathlib
import re
import subprocess
import unittest

HTML = (pathlib.Path(__file__).resolve().parents[1] / 'travel/index.html').read_text(encoding='utf-8')
JS = re.search(r'<script>(.*?)</script>', HTML, re.S).group(1)
DATA = JS.split('(function(){', 1)[1].split('var plan=buildPlan()', 1)[0]
HELPERS = JS.split('/* progress helpers start */')[1].split('/* progress helpers end */')[0]
ENV = 'var localStorage={getItem(){return null}};\n' + DATA + '''
var stayKeyOf={青岛:'qingdao',威海:'weihai',大连:'dalian',南昌:'nanchang',新干探亲:'xingan'};
var plan=buildPlan(),days=plan.days;
''' + HELPERS


def run(code):
    process = subprocess.run(['node', '-'], input=ENV + code, text=True, encoding='utf-8', capture_output=True)
    if process.returncode:
        raise AssertionError(process.stderr)
    return json.loads(process.stdout)


class FlightWeihaiPlanTests(unittest.TestCase):
    def test_default_dates_hotels_and_paid_flights(self):
        result = run('''console.log(JSON.stringify({
dates:days.map(d=>d.d),nights:plan.segments.filter(x=>x.kind==='stay').map(x=>x.duration.split(' · ')[0]),
booked:bookingItems(plan).filter(bookingFlag).map(x=>[x.id,x.depDate]),
paid:confirmedFlights['leg:gzqd:air'].paid+confirmedFlights['leg:dlnc:air'].paid,
budgets:days.filter(d=>/-air$/.test(d.source)).map(d=>[d.budget,d.basis]),count:bookingItems(plan).length
}));''')
        self.assertEqual(result['dates'], ['10/' + str(d) for d in range(13, 24)])
        self.assertEqual(result['nights'], ['2晚', '1晚', '1晚', '2晚', '2晚'])
        self.assertEqual(result['booked'], [['leg:gzqd:air', '10/13'], ['hotel:qd:2026-10-13', None], ['leg:dlnc:air', '10/18']])
        self.assertEqual(result['paid'], 1279)
        self.assertEqual(result['budgets'][0][0], [785.49, 885.49])
        self.assertEqual(result['budgets'][1][0], [947, 1097])
        self.assertEqual(result['count'], 11)

    def test_confirmed_hotel_is_one_night_and_pending_nights_keep_estimates(self):
        result = run('''console.log(JSON.stringify({
rooms:bookingItems(plan).filter(x=>x.id.startsWith('hotel:qd:')).map(x=>[x.date,bookingFlag(x),x.detail]),
budgets:days.slice(0,2).map(d=>d.budget),basis:days[0].basis,
steps:days[0].steps.map(s=>[s.id,s.t,s.n,s.s,s.detail]),checkout:days[1].steps.find(s=>s.id==='d:qd-hotel:checkout')
}));''')
        self.assertEqual([row[:2] for row in result['rooms']], [['10/13', True], ['10/14', False]])
        self.assertIn('133.49', result['rooms'][0][2])
        self.assertIn('0704', result['rooms'][0][2])
        self.assertEqual(result['budgets'], [[785.49, 885.49], [180, 330]])
        self.assertIn('实付¥133.49', result['basis'])
        self.assertEqual([s[1] for s in result['steps']], ['05:30', '07:25', '10:30', '约12:00', '到市区后', '下午', '15:00后'])
        self.assertIn('3号线', result['steps'][2][3])
        self.assertIn('寄存', result['steps'][4][2])
        self.assertIn('待确认', result['checkout']['tag'])
        self.assertEqual(result['checkout']['t'], '12:00前')

    def test_hotel_dates_do_not_lock_unbooked_extra_nights(self):
        result = run('''progressState.booked={"hotel:qd:2026-10-13":true};
var out=[changeReason('stay','qingdao',2),changeReason('weihai',null,false),!!changeReason('mode','gzqd','rail')];
routePrefs.weihai=false;plan=buildPlan();days=plan.days;
out.push(bookingItems(plan).filter(x=>x.id.startsWith('hotel:qd:')).map(x=>[x.date,bookingFlag(x)]));
console.log(JSON.stringify(out));''')
        self.assertEqual(result, ['', '', True, [['10/13', True], ['10/14', False], ['10/15', False]]])

    def test_no_weihai_preserves_flights_and_two_yantai_tickets(self):
        result = run('''routePrefs.weihai=false;plan=buildPlan();days=plan.days;
console.log(JSON.stringify({n:days.length,qd:plan.segments[1].duration,
items:bookingItems(plan).map(x=>[x.id,x.depDate]),ferry:rawTickets(plan.segments[2]).map(k=>[k.dep,k.arr,k.to])}));''')
        self.assertEqual(result['n'], 11)
        self.assertTrue(result['qd'].startswith('3晚'))
        self.assertIn(['leg:c6571', '10/16'], result['items'])
        self.assertIn(['leg:ferry', '10/16'], result['items'])
        self.assertIn(['leg:dlnc:air', '10/18'], result['items'])
        self.assertEqual(result['ferry'], [['13:40', '14:54', '烟台站'], ['22:00', '约05:00', '旅顺西站']])

    def test_adjustable_full_days_shift_downstream_not_paid_flights(self):
        result = run('''var out=[];for(var n=0;n<=2;n++)for(var x=0;x<=2;x++){
stayPrefs.nanchang=n;stayPrefs.xingan=x;var p=buildPlan();out.push([n,x,p.days.length,p.days[p.days.length-1].d,
bookingItems(p).find(i=>i.id==='leg:dlnc:air').depDate,p.segments.find(s=>s.label==='南昌').duration]);}
console.log(JSON.stringify(out));''')
        for n, x, count, end, flight, nights in result:
            self.assertEqual(count, 9 + n + x)
            self.assertEqual(end, '10/' + str(21 + n + x))
            self.assertEqual(flight, '10/18')
            self.assertTrue(nights.startswith(str(n + 1) + '晚'))

    def test_bookings_protect_dates_and_comparison_does_not_fake_orders(self):
        result = run('''var out=[!!changeReason('mode','gzqd','rail'),!!changeReason('stay','qingdao',2),changeReason('weihai',null,false)];
comparisonMode=true;out.push(changeReason('mode','gzqd','rail'));tripModes.gzqd='rail';plan=buildPlan();days=plan.days;
out.push(bookingItems(plan).filter(bookingFlag).map(x=>x.id));out.push(progressState.booked['leg:dlnc:air']);
console.log(JSON.stringify(out));''')
        self.assertEqual(result, [True, True, '', '', [], True])

    def test_requested_next_steps_use_arrival_and_sailing_tickets(self):
        result = run('''var scenarios=[[0,'2026-10-13T08:00:00+08:00'],[3,'2026-10-16T20:00:00+08:00'],[5,'2026-10-18T12:00:00+08:00']];
console.log(JSON.stringify(scenarios.map(([i,t])=>{var n=nextPending(days,{},i,Date.parse(t)),k=nextStepTicket(n.index,n.step);
return[n.step.t,k.train,countdownText(n.step,n.index,Date.parse(t)),overdueSteps(days,{},i,Date.parse(t)).length]})));''')
        self.assertEqual([x[:3] for x in result], [
            ['10:30', 'AQ1019 · 九元航空', '还有 2 小时 30 分'],
            ['21:30参考', '生生2 · 码头待核', '还有 1 小时 30 分'],
            ['13:35', 'MU6908 · 东方航空', '还有 1 小时 35 分']])
        self.assertTrue(all(x[3] > 0 for x in result))

    def test_all_modes_and_durations_have_complete_nonnegative_time_ledger(self):
        result = run('''var errors=[],count=0;
for(var gz of ['air','rail','hsr'])for(var dl of ['air','rail','hsr'])for(var nc of ['rail','hsr'])for(var ret of ['rail','hsr'])
for(var wh of [true,false])for(var q of [1,3])for(var d of [0,2])for(var n of [0,2])for(var x of [0,2]){
tripModes={gzqd:gz,dlnc:dl,ncxg:nc,xggz:ret};routePrefs.weihai=wh;stayPrefs={qingdao:q,dalian:d,nanchang:n,xingan:x};var p=buildPlan();count++;
var hours=p.ledger.hours.reduce((a,b)=>a+b,0),rounded=p.ledger.before+p.ledger.after+p.ledger.stay+p.ledger.transit;
if(p.ledger.hours.some(h=>h<0)||Math.abs(hours-p.days.length*24)>1e-6||Math.abs(rounded-p.days.length)>1e-6||p.overLimit!==(p.days.length>14))errors.push([tripModes,stayPrefs,wh,hours,rounded]);
var ids=p.days.flatMap(day=>day.steps.map(s=>s.id));if(new Set(ids).size!==ids.length)errors.push([tripModes,stayPrefs,wh,ids.filter((id,i)=>ids.indexOf(id)!==i)]);
}
console.log(JSON.stringify({count,errors:errors.slice(0,8)}));''')
        self.assertEqual(result['count'], 1152)
        self.assertEqual(result['errors'], [])

    def test_packing_and_weather_preserve_existing_storage_and_explicit_uncertainty(self):
        for token in ('笔记本电脑和充电器', '远程办公', '30L背包可能超尺寸', '20×30×40cm',
                      '清晰3C标识', '随身洗漱用品≤100ml', '夜船晕船药和外套', '11/10',
                      'function weatherRows()', '2026-10-11 08:00', '不是威海或海况预报', 'china-trip-v3-pack'):
            self.assertIn(token, HTML)
        self.assertNotIn('10/12', HTML)
        self.assertIn('https://www.weihai.gov.cn/art/2026/4/21/art_58820_6298948.html', HTML)


if __name__ == '__main__':
    unittest.main()
