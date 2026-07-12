"""Tests for richtext, cross-entity links, and backlinks."""

from datetime import date

import integral_links
import journal
import richtext


def test_bold_and_heading_spans():
    text = "# Title\nHello **world** and *italics* plus `code`."
    styles = {s.style for s in richtext.find_style_spans(text)}
    assert "h1" in styles
    assert "bold" in styles
    assert "italic" in styles
    assert "code" in styles


def test_cross_entity_link_parse():
    text = (
        "See [[journal:abcdef123456|Note]] "
        "[[domain:2026-07-11|Body & Presence]] "
        "[[fitness:2026-07-10|CC]] "
        "[[project:aabbccddeeff|Novel]] "
        "integral://project/aabbccddeeff"
    )
    links = integral_links.find_all_links(text)
    kinds = {link.kind for link in links}
    assert kinds == {"journal", "domain", "fitness", "project"}


def test_backlinks():
    data = journal.empty_journal()
    a = journal.create_entry(date.today().strftime("%Y-%m-%d"), "Root note.")
    journal.upsert_entry(data, a)
    b = journal.create_entry(
        date.today().strftime("%Y-%m-%d"),
        f"Refs {integral_links.format_journal_wiki(a['id'], 'Root')}",
    )
    journal.upsert_entry(data, b)
    hits = integral_links.find_backlinks(data, a["id"])
    assert len(hits) == 1
    assert hits[0]["id"] == b["id"]


def test_parse_deep_domain_and_fitness():
    domain = integral_links.parse_deep_link(
        integral_links.format_domain_uri("2026-07-11", "Body & Presence")
    )
    assert domain is not None
    assert domain.kind == "domain"
    assert domain.target == "2026-07-11"
    assert domain.extra == "Body & Presence"

    fitness = integral_links.parse_deep_link("integral://fitness/2026-07-10")
    assert fitness is not None
    assert fitness.kind == "fitness"
