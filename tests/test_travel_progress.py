"""Local progress contracts; cloud sync is deliberately not enabled in phase one."""
import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "travel/index.html").read_text(encoding="utf-8")
JS = re.search(r"<script>(.*?)</script>", HTML, re.S).group(1)
HELPERS = JS.split("/* progress helpers start */")[1].split("/* progress helpers end */")[0]


def node(source):
    result = subprocess.run(["node", "-"], input=source, text=True,
                            encoding="utf-8", capture_output=True, check=True)
    return json.loads(result.stdout)


class TravelProgressTests(unittest.TestCase):
    def test_complete_script_compiles(self):
        self.assertTrue(node("new Function(" + json.dumps(JS) + ");console.log(true)"))

    def test_local_map_allows_only_bounded_true_flags(self):
        result = node(HELPERS + """
console.log(JSON.stringify([
 cleanProgressMap({'d:qd-arrive:1':true,'bad space':true,'leg:ferry':false,'hotel:qd':1},200),
 cleanProgressMap(['not-a-map'],200),
 Object.keys(cleanProgressMap(Object.fromEntries(Array.from({length:250},(_,i)=>['d:'+i,true])),200)).length,
 Object.keys(cleanProgressMap(Object.fromEntries(Array.from({length:50},(_,i)=>['leg:'+i,true])),40)).length,
 Object.keys(cleanProgressMap({['x'.repeat(49)]:true},200)).length
]));""")
        self.assertEqual(result, [{"d:qd-arrive:1": True}, {}, 200, 40, 0])

    def test_progress_is_separate_from_packing_and_no_cloud_requests(self):
        self.assertIn('"china-trip-v3-progress"', JS)
        self.assertIn('"china-trip-v3-pack"', JS)
        self.assertNotIn("fetch(", JS)
        self.assertNotIn("/travel/api/", JS)
        for token in ("仅本机", 'id="tripProgressBar"', 'id="bookingSummary"',
                      'data-done=', 'data-book=', "改方式前先退票", "取消勾选不会替你退票或退房"):
            self.assertIn(token, HTML)

    def test_stable_source_ids_and_reset_guard(self):
        for token in ('s.id="d:"+source+":"+i', '"family-"+(i+1)',
                      '"leg:c6571"', '"leg:ferry"', '"hotel:qd"',
                      'changeReason("reset")', "item.signature!==x.signature"):
            self.assertIn(token, JS)

    def test_storage_failure_is_visible(self):
        result = node(HELPERS + """
var progressState={done:{},booked:{}},progressStorageOk=true;
var localStorage={setItem(){throw Error('quota')}};
saveProgress();console.log(progressStorageOk);
""")
        self.assertFalse(result)

    def test_next_step_uses_manual_completion_and_stops_at_tomorrow(self):
        result = node(HELPERS + """
var ds=[{steps:[{id:'a',t:'09:30'},{id:'b',t:'13:30'}]},
        {steps:[{id:'c',t:'09:30'}]},{steps:[{id:'d',t:'09:30'}]}];
console.log(JSON.stringify([
 nextPending(ds,{},-1),nextPending(ds,{},3),nextPending(ds,{},0),
 nextPending(ds,{a:true},0),nextPending(ds,{a:true,b:true},0),
 nextPending(ds,{a:true,b:true,c:true},0),nextPending(ds,{d:true},2)
]));""")
        self.assertEqual(result[:2], [None, None])
        self.assertEqual([x['step']['id'] for x in result[2:5]], ['a', 'b', 'c'])
        self.assertEqual(result[4]['index'], 1)
        self.assertEqual(result[5:], [None, None])

    def test_countdown_uses_china_dates_and_does_not_guess_fuzzy_times(self):
        result = node(HELPERS + """
console.log(JSON.stringify([
 countdownText({t:'22:45'},1,Date.parse('2026-10-13T21:00:00+08:00')),
 countdownText({t:'13:40参考'},4,Date.parse('2026-10-16T12:30:00+08:00')),
 countdownText({t:'约05:00'},5,Date.parse('2026-10-16T23:00:00+08:00')),
 countdownText({t:'09:30'},3,Date.parse('2026-10-14T20:00:00+08:00')),
 countdownText({t:'13:40'},4,Date.parse('2026-10-16T13:50:00+08:00')),
 countdownText({t:'上午'},5,Date.now()),stepInstant({t:'25:00'},5),
 countdownText({t:'13:40'},4,Date.parse('2026-10-16T12:40:00+08:00'))
]));""")
        self.assertEqual(result, ['还有 1 小时 45 分', '还有 1 小时 10 分',
                                  '还有 6 小时', '还有 13 小时 30 分',
                                  '已到时间', '', None, '还有 1 小时'])

    def test_next_ticket_matches_arrivals_but_not_port_checkin(self):
        result = node(HELPERS + """
var plan={segments:[{kind:'transit',start:4,end:5}]};
function ticketsOf(){return [
 {dep:'13:40',arr:'14:54',from:'青岛北站',to:'烟台站',plus:0,train:'C6571'},
 {dep:'22:00',arr:'约05:00',from:'烟台北站',to:'旅顺西站',plus:1,train:'夜船'}]}
console.log(JSON.stringify([
 nextStepTicket(4,{kind:'火车',t:'13:40参考',n:'C6571 青岛北→烟台'}).train,
 nextStepTicket(4,{kind:'轮渡',t:'20:30前',n:'抵达中铁轮渡烟台北站'}),
 nextStepTicket(4,{kind:'轮渡',t:'22:00参考',n:'烟台北站→旅顺西站'}).train,
 nextStepTicket(5,{kind:'轮渡',t:'约05:00',n:'抵达旅顺西站'}).train
]));""")
        self.assertEqual(result, ['C6571', None, '夜船', '夜船'])

    def test_next_ui_and_keyboard_focus_preserve_old_features(self):
        for token in ('id="nextStep"', 'id="nextComplete"', 'id="nextAll"',
                      'id="bookingFoot"', 'id="routeExpand"',
                      '"china-trip-v3-route-open"', 'all||i<=todayIndex',
                      'html.keyboard-input #closeSheet:focus',
                      'html:not(.keyboard-input) #closeSheet:focus',
                      'document.addEventListener("pointerdown"', 'renderNextStep(true)'):
            self.assertIn(token, HTML)
        step_render = JS.split('steps.innerHTML=')[1].split('var prev=')[0]
        self.assertNotIn('step-dot', step_render)
        self.assertIn('grid-template-columns:50px 44px minmax(0,1fr)', HTML)
        self.assertIn('top:22px;bottom:-22px', HTML)

    def test_expanded_panels_omit_duplicate_booking_actions_and_clear_footer(self):
        segment_render = JS.split('function segHtml(')[1].split('function render(')[0]
        self.assertEqual(segment_render.count("(open?'':bookingActions(x))"), 2)
        self.assertIn('function updateBarSpace()', JS)
        self.assertIn('new ResizeObserver(updateBarSpace)', JS)
        self.assertIn('padding-bottom:max(150px,var(--bar-clearance,150px))', HTML)
        self.assertIn('/火车过夜/.test(s)', JS.split('function chipCity(')[1].split('function cnDate')[0])


if __name__ == "__main__":
    unittest.main()
