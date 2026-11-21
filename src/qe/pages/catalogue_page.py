"""Page object for the catalogue page (frontend/src/App.jsx, one page, no routing).

Every locator is derived from the AUT's JSX (read-only):
  heading        App.jsx:39                 <h1>Course catalogue</h1>
  filter group   LevelFilter.jsx:5          role="group" aria-label="Filter by level"
  filter buttons LevelFilter.jsx:8-19       "All levels" (line 11) + one chip per level (constants.js:4-6)
  selected chip  LevelFilter.jsx:8,17       class "chip chip--on"
  course cards   CourseCard.jsx:5-11        li.course-card with __code, __level, __title, __credits
  states         CourseList.jsx:5,9,13      p.state (loading / error / empty)
tests/unit/test_page_contracts.py re-checks each of these against the JSX source.
"""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Locator, Page

LEVEL_LABELS = {"FOUNDATION": "Foundation", "INTERMEDIATE": "Intermediate", "ADVANCED": "Advanced"}  # constants.js:4-6
ALL_LEVELS_LABEL = "All levels"  # LevelFilter.jsx:11
EMPTY_STATE_TEXT = "No courses match this filter. Clear the filter to see the full catalogue."  # CourseList.jsx:13


@dataclass(frozen=True)
class CardData:
    code: str
    level_label: str
    title: str
    credits_text: str


class CataloguePage:
    def __init__(self, page: Page, base_url: str) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")

    # -- navigation ----------------------------------------------------------------
    def open(self) -> CataloguePage:
        self.page.goto(self.base_url + "/")
        return self

    def wait_until_loaded(self, timeout_ms: int = 10_000) -> CataloguePage:
        """Wait until the 'loading' state is gone (cards, empty state or error shown)."""
        self.page.locator("p.state", has_text="Loading the catalogue").wait_for(state="detached", timeout=timeout_ms)
        return self

    # -- locators ------------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name="Course catalogue", level=1)

    @property
    def filter_group(self) -> Locator:
        return self.page.get_by_role("group", name="Filter by level")

    def filter_button(self, level: str | None) -> Locator:
        label = ALL_LEVELS_LABEL if level is None else LEVEL_LABELS[level]
        return self.filter_group.get_by_role("button", name=label, exact=True)

    @property
    def cards(self) -> Locator:
        return self.page.locator("li.course-card")

    @property
    def state_message(self) -> Locator:
        return self.page.locator("p.state")

    # -- actions -------------------------------------------------------------------
    def select_level(self, level: str | None) -> CataloguePage:
        self.filter_button(level).click()
        return self

    # -- reads ---------------------------------------------------------------------
    def selected_filter_labels(self) -> list[str]:
        return [
            t.strip()
            for t in self.filter_group.locator("button.chip--on").all_inner_texts()
        ]

    def card_codes(self) -> list[str]:
        return [t.strip() for t in self.cards.locator(".course-card__code").all_inner_texts()]

    def read_cards(self) -> list[CardData]:
        out = []
        for i in range(self.cards.count()):
            c = self.cards.nth(i)
            out.append(
                CardData(
                    code=c.locator(".course-card__code").inner_text().strip(),
                    level_label=c.locator(".course-card__level").inner_text().strip(),
                    title=c.locator(".course-card__title").inner_text().strip(),
                    credits_text=c.locator(".course-card__credits").inner_text().strip(),
                )
            )
        return out
