"""Tests for journal cross-links and deep-link parsing."""

from datetime import date

import journal


def test_format_and_get_entry():
    data = journal.empty_journal()
    item = journal.create_entry(date.today().strftime("%Y-%m-%d"), "Hello stacked work.")
    journal.upsert_entry(data, item)
    assert journal.get_entry(data, item["id"])["body"] == "Hello stacked work."
    assert journal.get_entry(data, "deadbeefdead") is None


def test_wiki_and_uri_links_parsed():
    eid = "abcdef123456"
    text = f"See [[journal:{eid}|Monday notes]] and also integral://journal/{eid} later."
    spans = journal.find_journal_links(text)
    assert len(spans) == 2
    assert spans[0].entry_id == eid
    assert spans[0].label == "Monday notes"
    assert spans[1].entry_id == eid


def test_format_journal_links():
    wiki = journal.format_journal_wiki_link("abcdef123456", "Label")
    assert wiki == "[[journal:abcdef123456|Label]]"
    assert journal.format_journal_uri("ABCDEF123456") == "integral://journal/abcdef123456"


def test_parse_deep_link_target():
    assert journal.parse_deep_link_target("integral://journal/abcdef123456") == (
        "journal",
        "abcdef123456",
    )
    assert journal.parse_deep_link_target("integral://journal/nope") is None
    assert journal.parse_deep_link_target("https://example.com") is None
    assert journal.parse_deep_link_target("[[journal:abcdef123456|x]]") == ("journal", "abcdef123456")
