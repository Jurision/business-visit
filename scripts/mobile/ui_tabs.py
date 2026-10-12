"""Shared real-UI navigation for the tabbed itinerary acceptance scripts."""


def tab(pg, name):
    pg.locator(f'#tab-{name}').click()


def adjust(pg):
    if pg.locator('#adjustOverlay').is_hidden():
        tab(pg, 'route')
        pg.locator('#adjustTop').click()


def close_adjust(pg):
    if pg.locator('#adjustOverlay').is_visible():
        pg.locator('#closeAdjust').click()


def prepare(pg, selector):
    if selector == '#adjustToggle':
        if pg.locator('#adjustOverlay').is_visible():
            pg.locator('#closeAdjust').click()
        else:
            adjust(pg)
        return False
    if selector == '#packBtn':
        close_adjust(pg)
        tab(pg, 'packing')
        return False
    if selector == '#bookingSummary':
        close_adjust(pg)
        tab(pg, 'booking')
        return False
    if selector.startswith('#bookingList'):
        close_adjust(pg)
        tab(pg, 'booking')
    elif '#phaseRail' in selector or '[data-adjust=' in selector or selector in (
            '#weihaiToggle', '#compareToggle', '#closeBar', '#resetStays'):
        adjust(pg)
    elif selector in ('#budgetBtn', '#mapBtn'):
        close_adjust(pg)
        tab(pg, 'route')
    elif '#steps' in selector or selector.startswith('#next'):
        close_adjust(pg)
        tab(pg, 'today')
    return True
