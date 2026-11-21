"""Catalogue page (Playwright, Chromium).

Two modes, marked separately:
* full-stack (needs_backend + needs_frontend): real Vite page talking to the real backend.
  Expected cards come from qe.data.seed. Locators come from CataloguePage (JSX cited there).
* route-mocked (needs_frontend only): page.route() replaces GET /api/courses so that the
  empty, error and loading states can be produced on demand.

Failure screenshots and traces are written under reports/ by pytest.ini
(--screenshot=only-on-failure, --tracing=retain-on-failure, --output=reports/playwright).
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, Route, expect

from qe.data import seed
from qe.pages.catalogue_page import EMPTY_STATE_TEXT, CataloguePage


def _card(catalogue: CataloguePage, code: str):
    matches = [c for c in catalogue.read_cards() if c.code == code]
    assert len(matches) == 1, f"expected exactly one card for {code}, found {len(matches)}"
    return matches[0]


def _mock_courses(page: Page, status: int = 200, payload: object = None) -> None:
    body = json.dumps([] if payload is None else payload)

    def handler(route: Route) -> None:
        route.fulfill(status=status, content_type="application/json", body=body)

    page.route("**/api/courses*", handler)


# --- full-stack ------------------------------------------------------------------------------


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("UI-01")
def test_default_view_shows_heading_and_every_active_course(catalogue):
    """App.jsx:39 heading; LevelFilter.jsx:5 'All levels' selected by default (App.jsx:8);
    CourseList renders one li.course-card per course in API order (CourseList.jsx:16-22).
    """
    catalogue.open().wait_until_loaded()
    expect(catalogue.heading).to_be_visible()
    assert catalogue.selected_filter_labels() == ["All levels"]
    assert catalogue.card_codes() == list(seed.ACTIVE_CATALOGUE)


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("UI-02")
def test_selecting_advanced_shows_only_advanced_courses(catalogue):
    """LevelFilter.jsx:17 marks the selected chip 'chip--on'; App.jsx refetches on level change."""
    catalogue.open().wait_until_loaded()
    catalogue.select_level("ADVANCED")
    expect(catalogue.cards).to_have_count(len(seed.BY_LEVEL["ADVANCED"]))
    assert catalogue.card_codes() == list(seed.BY_LEVEL["ADVANCED"])
    assert catalogue.selected_filter_labels() == ["Advanced"]


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("UI-03")
def test_switching_filters_and_back_to_all_restores_the_full_list(catalogue):
    """Regression: after a filtered view, 'All levels' (LevelFilter.jsx:11) restores all cards."""
    catalogue.open().wait_until_loaded()
    catalogue.select_level("FOUNDATION")
    expect(catalogue.cards).to_have_count(len(seed.BY_LEVEL["FOUNDATION"]))
    assert catalogue.card_codes() == list(seed.BY_LEVEL["FOUNDATION"])

    catalogue.select_level(None)
    expect(catalogue.cards).to_have_count(len(seed.ACTIVE_CATALOGUE))
    assert catalogue.card_codes() == list(seed.ACTIVE_CATALOGUE)
    assert catalogue.selected_filter_labels() == ["All levels"]


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("UI-04")
def test_course_card_shows_code_level_title_and_credits(catalogue):
    """CourseCard.jsx:5-11 renders code, formatted level (constants.js:4-6), title and
    '<n> credits'. Values from seed: CS2110, INTERMEDIATE, 15 credits (V2 seed row).
    """
    catalogue.open().wait_until_loaded()
    card = _card(catalogue, "CS2110")
    assert card.level_label == "Intermediate"
    assert card.title == "Object Oriented Design"
    assert card.credits_text == "15 credits"


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.needs_backend
@pytest.mark.needs_seed
@pytest.mark.gate("UI-05")
def test_partner_record_title_renders_but_injected_description_does_not(catalogue, page):
    """Security regression. LMS9001's description holds injected instructions (V90 section 2).
    The card shows only the title, level and credits (CourseCard.jsx), so the description
    text must not appear anywhere on the page. The record is data, not instructions.
    """
    catalogue.open().wait_until_loaded()
    card = _card(catalogue, seed.PARTNER_RECORD)
    assert card.title == seed.PARTNER_RECORD_TITLE
    expect(page.locator("body")).not_to_contain_text(seed.INJECTED_TEXT_MARKER)


# --- route-mocked ----------------------------------------------------------------------------


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.gate("UI-06")
def test_empty_response_shows_the_empty_state_message(catalogue, page):
    """CourseList.jsx:13 shows the empty-state text when the list is empty."""
    _mock_courses(page, payload=[])
    catalogue.open().wait_until_loaded()
    expect(catalogue.cards).to_have_count(0)
    expect(catalogue.state_message).to_have_text(EMPTY_STATE_TEXT)


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.gate("UI-07")
def test_server_error_shows_the_error_state_with_status(catalogue, page):
    """catalog.js throws 'Catalogue request failed with status <n>' on a non-2xx response.
    CourseList.jsx:9 shows that message followed by the port hint.
    """
    _mock_courses(page, status=500, payload={"error": "boom"})
    catalogue.open().wait_until_loaded()
    expect(catalogue.cards).to_have_count(0)
    expect(catalogue.state_message).to_have_text(
        "Catalogue request failed with status 500 Check that the API is running on port 8080."
    )


@pytest.mark.ui
@pytest.mark.needs_frontend
@pytest.mark.gate("UI-08")
def test_loading_state_is_shown_until_the_response_arrives(catalogue, page):
    """CourseList.jsx:5 shows 'Loading the catalogue' while the request is pending. The routes
    are held open, so the loading text is observed before any card exists.

    main.jsx wraps the app in React.StrictMode, so the dev build issues the request twice and
    the first response is ignored (App.jsx cancels it). Every held request is fulfilled.
    """
    held: list[Route] = []
    page.route("**/api/courses*", lambda route: held.append(route))

    catalogue.open()
    expect(catalogue.state_message).to_contain_text("Loading the catalogue")
    expect(catalogue.cards).to_have_count(0)

    assert held, "the catalogue request was never issued"
    payload = json.dumps(
        [{"id": 2, "code": "CS2110", "title": "Object Oriented Design", "level": "INTERMEDIATE", "credits": 15}]
    )
    for route in held:
        route.fulfill(status=200, content_type="application/json", body=payload)
    expect(catalogue.cards).to_have_count(1)
    assert catalogue.card_codes() == ["CS2110"]
