"""SPEC-317 domain templates — structure + non-destructive apply."""

import domain_templates


def test_gut_healing_pack_shape():
    template = domain_templates.get_template("gut_healing")
    assert template is not None
    domains = template["domains"]
    # 6–8 relevant domains.
    assert 6 <= len(domains) <= 8
    assert "Gut Health / Digestion" in domains
    for name, definition in domains.items():
        assert isinstance(definition.get("checklist"), list) and definition["checklist"]
        for metric in definition.get("metrics", []):
            assert metric["type"] in ("rating", "number")
            if metric["type"] == "rating":
                assert metric["min"] < metric["max"]
            else:
                assert "unit" in metric
            assert "name" in metric and "default" in metric


def test_list_templates_summaries():
    summaries = domain_templates.list_templates()
    assert any(s["id"] == "gut_healing" for s in summaries)
    gut = next(s for s in summaries if s["id"] == "gut_healing")
    assert gut["domain_count"] == len(domain_templates.get_template("gut_healing")["domains"])
    assert gut["title"] and gut["description"]


def test_apply_template_is_non_destructive():
    existing = {
        "Money/Freedom": {"checklist": ["keep me"], "metrics": []},
        "Gut Health / Digestion": {"checklist": ["user edited"], "metrics": []},
    }
    merged, added, skipped = domain_templates.apply_template(existing, "gut_healing")
    # Existing user domain untouched.
    assert merged["Money/Freedom"]["checklist"] == ["keep me"]
    # Collision skipped, not overwritten.
    assert "Gut Health / Digestion" in skipped
    assert merged["Gut Health / Digestion"]["checklist"] == ["user edited"]
    # New domains added.
    assert "Breathwork & Mindfulness" in added
    assert "Breathwork & Mindfulness" in merged


def test_apply_twice_adds_nothing_second_time():
    merged, added, _ = domain_templates.apply_template({}, "gut_healing")
    assert added
    merged2, added2, skipped2 = domain_templates.apply_template(merged, "gut_healing")
    assert added2 == []
    assert len(skipped2) == len(added)
    assert merged2 == merged


def test_apply_deep_copies_metrics():
    merged, _, _ = domain_templates.apply_template({}, "gut_healing")
    merged["Gut Health / Digestion"]["metrics"][0]["default"] = 99
    template_default = domain_templates.get_template("gut_healing")["domains"][
        "Gut Health / Digestion"
    ]["metrics"][0]["default"]
    assert template_default != 99


def test_unknown_template_raises():
    try:
        domain_templates.apply_template({}, "nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown template")
