import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SiteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "travel" / "index.html").read_text(encoding="utf-8")

    def test_trip_stays_out_of_search_indexes(self):
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', self.html)
        self.assertIn("Disallow: /nate/", (ROOT / "robots.txt").read_text(encoding="utf-8"))
        self.assertIn("Disallow: /travel/", (ROOT / "robots.txt").read_text(encoding="utf-8"))
        self.assertNotIn("/nate/", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn('href="https://trip.arielzhu.space/travel/"', self.html)

    def test_share_metadata_is_personal_travel_not_nate(self):
        for token in (
            'property="og:title" content="广州—青岛—大连—江西 12日行程"',
            'property="og:url" content="https://trip.arielzhu.space/travel/"',
            'property="og:image" content="https://trip.arielzhu.space/travel/img/personal-trip-watercolor.png"',
        ):
            self.assertIn(token, self.html)

    def test_local_art_and_favicon_exist(self):
        self.assertIn('href="favicon.svg"', self.html)
        self.assertTrue((ROOT / "travel" / "favicon.svg").is_file())
        self.assertTrue((ROOT / "travel" / "img" / "personal-trip-watercolor.png").is_file())

    def test_legacy_nate_page_redirects_to_travel(self):
        legacy = (ROOT / "nate" / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="0;url=/travel/"', legacy)
        self.assertIn('location.replace("/travel/"', legacy)

    def test_default_is_single_twelve_day_dalian_route(self):
        self.assertIn("广州—青岛—大连—江西 12日行程", self.html)
        self.assertIn("var stayPrefs={qingdao:2,dalian:1,xingan:1,nanchang:0}", self.html)
        self.assertIn("return{key:\"dynamic\"", self.html)
        self.assertNotIn('data-plan=', self.html)
        self.assertNotIn('data-preset=', self.html)
        self.assertNotIn("秦皇岛", self.html)

    def test_time_allocation_is_dynamic_and_clickable(self):
        self.assertIn('id="allocationSummary"', self.html)
        self.assertIn('id="phaseRail"', self.html)
        self.assertIn('id="stayControls"', self.html)
        self.assertIn('id="limitNote"', self.html)
        self.assertIn('data-phase=', self.html)
        for token in (
            "function trunkMinutes()",
            "已知干线约",
            "青岛",
            "大连",
            "新干探亲",
            "南昌",
            "固定交通不压缩",
            "超过14天上限",
            "后续日期与预算会一起顺延",
        ):
            self.assertIn(token, self.html)
        self.assertNotIn("一路向海", self.html)
        self.assertIn("function buildPlan()", self.html)
        self.assertIn("function dateInfo(offset)", self.html)
        self.assertIn("var total=built.length", self.html)
        for token in (
            'd:"10/17",w:"周六"',
            'd:"10/25",w:"周日"',
            "烟台北站 → 旅顺西站",
            "星海广场与海湾散步",
            "陪爷爷奶奶的一整天",
            "（可选）县城顺路看堂妹",
        ):
            self.assertIn(token, self.html)

    def test_jiangxi_leg_runs_nanchang_then_xingan_then_overnight_home(self):
        for token in (
            "K8723 南昌 → 新干",
            "K441 新干 → 广州白云",
            'label:"返穗卧铺"',
            '["广州白云","青岛","烟台北港","旅顺 / 大连","南昌","新干县","广州白云"]',
        ):
            self.assertIn(token, self.html)
        self.assertNotIn('label:"南昌中转"', self.html)

    def test_hotels_are_budgeted_at_most_150_per_night(self):
        self.assertIn("每晚¥150的预算", self.html)
        for stale in ("约 ¥260–420 / 晚", "估算 ¥260–450 / 晚", "估算 ¥180–280"):
            self.assertNotIn(stale, self.html)

    def test_overview_segments_expand_in_place(self):
        self.assertIn("function panelHtml(", self.html)
        self.assertIn('aria-expanded="', self.html)
        self.assertIn("data-goto=", self.html)

    def test_first_layer_has_direction_state_budget_and_unknowns(self):
        for element_id in (
            "dateRail",
            "routeChain",
            "dayLegs",
            "dayBudget",
            "budgetBasis",
            "budgetUnknown",
        ):
            self.assertIn('id="%s"' % element_id, self.html)
        self.assertIn("routeHtml(d.route)", self.html)
        self.assertIn("dayBudget(d)", self.html)
        self.assertIn('"待核： "+d.unknown', self.html)

    def test_budget_is_derived_from_days_without_cross_night_double_charge(self):
        self.assertIn("totalBudget(days)", self.html)
        self.assertIn("跨夜车票/船票只在出发日计一次", self.html)
        self.assertIn("酒店只在实际入住夜计一次", self.html)
        self.assertIn("船票已在前一日计入", self.html)
        self.assertIn("不计酒店", self.html)

    def test_ferry_uses_real_ports_and_berth_price_not_seat_floor(self):
        for token in (
            "C6571 青岛北 → 烟台",
            "13:40参考",
            "14:54到烟台站",
            "不是烟台南站",
            "二等座公开参考约 ¥74–81",
            "烟台北站",
            "旅顺西站",
            "环海路86号",
            "海韵路1020号",
            "次日约05:00到",
            "官方挂牌三等舱约 ¥180–200",
            "未用坐席最低价冒充卧铺",
            "候船预留90分钟",
        ):
            self.assertIn(token, self.html)

    def test_page_shows_no_photos(self):
        body = self.html.split("<body>", 1)[1]
        for token in ("<img", "<picture", 'id="dayVisual"', "photo-btn", "preconnect"):
            self.assertNotIn(token, body if token != "preconnect" else self.html)

    def test_progressive_controls_and_reduced_motion_remain(self):
        for element_id in ("overlay", "budgetBtn", "mapBtn", "stayControls"):
            self.assertIn('id="%s"' % element_id, self.html)
        self.assertIn("pointerdown", self.html)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.html)
        self.assertIn('localStorage.getItem("china-trip-v3-stays")', self.html)

    def test_public_page_omits_private_family_location_and_old_customer(self):
        for token in ("傅堎村", "三湖镇", "Nate", "Junshuo Plastics", "广州骏烁"):
            self.assertNotIn(token, self.html)
        self.assertIn("不公开村庄、门牌或家庭具体位置", self.html)


    def test_transport_modes_switch_per_leg_with_rail_defaults(self):
        self.assertIn('var tripModes={gzqd:"rail",dlnc:"hsr",ncxg:"rail",xggz:"rail"}', self.html)
        self.assertIn('localStorage.getItem("china-trip-v3-modes")', self.html)
        for token in ("G566 广州南 → 青岛北", "K683/K682 大连 → 北京", "T167 北京西 → 南昌", "G3065 南昌西 → 新干东", "G3065 新干东 → 广州东", "function simulate(", "data-mode="):
            self.assertIn(token, self.html)


    def test_time_ledger_adds_up_to_calendar_days(self):
        for token in ("时间怎么分", "出发前/到家后", "var hrs=[tGo,", "total*24-tHome", "广州出发", "回到广州"):
            self.assertIn(token, self.html)


    def test_transit_shows_departure_and_arrival_like_a_ticket(self):
        for token in ("function ticketHtml(", 'from:"广州白云站",arr:"22:45",to:"青岛北站"', 'from:"新干站",arr:"07:00",to:"广州白云站"', "k.depDate=days[x.start].d", "k.arrDate=days[arr].d", "今天的车船"):
            self.assertIn(token, self.html)
        self.assertNotIn('<span class="summary-label">状态</span>', self.html)


    def test_packing_list_with_weather_and_sources(self):
        for token in ('id="packBtn"', "function packDrawer(", 'localStorage.getItem("china-trip-v3-pack")', "不用带行李箱", "身份证", "防风外套", "中央气象台 10/10 20:00 发布", "nmc.cn/publish/forecast/ASD/qingdao.html"):
            self.assertIn(token, self.html)


if __name__ == "__main__":
    unittest.main()
