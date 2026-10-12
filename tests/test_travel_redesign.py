"""Presentation contracts; approved itinerary calculation stays unchanged."""
import pathlib
import subprocess
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
HTML=(ROOT/'travel/index.html').read_text(encoding='utf-8')


class RedesignTests(unittest.TestCase):
    def test_tabs_are_accessible_and_separately_persisted(self):
        for name in ('today','route','booking','packing'):
            self.assertIn('id="tab-'+name+'"',HTML)
            self.assertIn('aria-controls="page-'+name+'"',HTML)
        self.assertIn('china-trip-v4-tab',HTML)
        self.assertIn('role","tabpanel',HTML)
        self.assertIn('env(safe-area-inset-bottom)',HTML)

    def test_adjustment_changes_are_contained(self):
        for token in ('id="adjustPanel"','aria-modal="true"','function closeAdjust()',
                      'function openAdjust()','$("changeBar")].forEach','$("backToday")'):
            self.assertIn(token,HTML)

    def test_ticket_wrap_and_font_floor(self):
        self.assertIn('.tk-mid small{font-size:14px',HTML)
        self.assertIn('text-overflow:clip;overflow-wrap:anywhere',HTML)
        self.assertIn('.step-main em{display:none}',HTML)

    def test_confirmed_hotel_not_replaced(self):
        self.assertIn('10/12 12:00前可免费取消',HTML)
        self.assertIn('10/14这一晚尚未订',HTML)
        self.assertIn('paid:133.49',HTML)

    def test_calculators_byte_identical_to_approved_base(self):
        base=subprocess.check_output(['git','show','6bdaa69:travel/index.html'],cwd=ROOT).decode('utf-8')
        for name,following in [('buildPlan','var selected'),('bookingItems','function bookingFlag'),
                               ('changeReason','function doneCount'),('nextPending','function overdueSteps')]:
            def chunk(source):
                start=source.index('function '+name+'(')
                return source[start:source.index(following,start)]
            self.assertEqual(chunk(HTML),chunk(base),name+' changed')


if __name__=='__main__':
    unittest.main()
