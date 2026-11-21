"""Exercise CataloguePage in real Chromium against a static DOM stub.

The stub (below) hand-mirrors the markup in the AUT's JSX; it is NOT the AUT. These tests
only prove the page object's locator logic. They say nothing about the running application.
"""

import pytest

from qe.pages.catalogue_page import CataloguePage

pytestmark = pytest.mark.unit

STUB = """
<main class="page"><h1>Course catalogue</h1>
<div class="level-filter" role="group" aria-label="Filter by level">
  <button type="button" class="chip chip--on">All levels</button>
  <button type="button" class="chip">Foundation</button>
  <button type="button" class="chip">Intermediate</button>
  <button type="button" class="chip">Advanced</button>
</div>
<ul class="course-list">
 <li class="course-card"><div><span class="course-card__code">T-1</span>
   <span class="course-card__level">Foundation</span></div>
   <h2 class="course-card__title">Stub One</h2><p class="course-card__credits">10 credits</p></li>
 <li class="course-card"><div><span class="course-card__code">T-2</span>
   <span class="course-card__level">Advanced</span></div>
   <h2 class="course-card__title">Stub Two</h2><p class="course-card__credits">20 credits</p></li>
</ul></main>
<script>
document.querySelectorAll('.chip').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.chip').forEach(x => x.className = 'chip');
  b.className = 'chip chip--on';
}));
</script>
"""


@pytest.fixture
def stub_page(page):
    page.set_content(STUB)
    return CataloguePage(page, "http://localhost:5173")


def test_heading_and_filter_found(stub_page):
    assert stub_page.heading.is_visible()
    assert stub_page.filter_group.is_visible()


def test_read_cards(stub_page):
    assert stub_page.card_codes() == ["T-1", "T-2"]
    cards = stub_page.read_cards()
    assert (cards[0].title, cards[0].credits_text, cards[1].level_label) == ("Stub One", "10 credits", "Advanced")


def test_select_level_moves_selected_chip(stub_page):
    assert stub_page.selected_filter_labels() == ["All levels"]
    stub_page.select_level("ADVANCED")
    assert stub_page.selected_filter_labels() == ["Advanced"]
    stub_page.select_level(None)
    assert stub_page.selected_filter_labels() == ["All levels"]
