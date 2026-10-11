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


if __name__ == "__main__":
    unittest.main()
