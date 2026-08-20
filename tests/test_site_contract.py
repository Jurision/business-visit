import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SiteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "nate" / "index.html").read_text(encoding="utf-8")

    def test_private_itinerary_is_not_advertised_to_crawlers(self):
        self.assertIn('name="robots" content="noindex,nofollow,noarchive"', self.html)
        self.assertIn("Disallow: /nate/", (ROOT / "robots.txt").read_text(encoding="utf-8"))
        self.assertNotIn("/nate/", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))

    def test_local_assets_referenced_by_html_exist(self):
        refs = re.findall(r"url\('((?:font|img)/[^']+)'\)", self.html)
        props = self.html.split("var PROPS=[", 1)[1].split("];", 1)[0]
        refs.extend("img/%s.jpg" % key for key in re.findall(r"\{k:'([^']+)'", props))
        self.assertGreaterEqual(len(refs), 6)
        missing = [ref for ref in refs if not (ROOT / "nate" / ref).is_file()]
        self.assertEqual(missing, [])

    def test_schedule_contains_rail_and_inter_visit_travel_paths(self):
        self.assertIn("High-speed rail day trip to Shantou", self.html)
        self.assertIn("Travel to ", self.html)
        self.assertIn("Return to hotel · ", self.html)
        self.assertNotIn("Math.min(t+(first.at?legMin(first):0),19*60)", self.html)

    def test_map_is_mobile_safe_and_schedule_aware(self):
        self.assertIn("Schematic Visit Map", self.html)
        self.assertIn('id="readout" role="status" aria-live="polite"', self.html)
        self.assertIn('data-map-day="', self.html)
        self.assertIn("var A=null,B=null,MAP_DAY=0", self.html)
        self.assertIn(
            "dock.dataset.state==='mini'||dock.dataset.state==='open'",
            self.html,
        )
        self.assertIn("var initial=phone()?'peek'", self.html)
        self.assertIn("Select a hotel to calculate travel time", self.html)

    def test_map_controls_and_pins_are_keyboard_accessible(self):
        self.assertIn('aria-controls="mapPanel" aria-expanded="false"', self.html)
        self.assertIn(
            'class="pinhit" role="button" tabindex="0"',
            self.html,
        )
        self.assertIn("e.key!=='Enter'&&e.key!==' '", self.html)
        self.assertIn("Open visit map", self.html)
        self.assertIn("width:44px;height:44px", self.html)


if __name__ == "__main__":
    unittest.main()
