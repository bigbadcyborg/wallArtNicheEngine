from app.modules import compliance


def test_blocked_franchise_term():
    r = compliance.scan_text("cute disney nursery prints")
    assert r.blocked
    assert any(f["term"] == "disney" for f in r.flags)
    assert r.risk_score == 100.0


def test_sports_league_blocked():
    assert compliance.scan_text("NFL team wall art").blocked


def test_flag_pattern_not_blocking():
    r = compliance.scan_text("abstract print in the style of a famous painter")
    assert not r.blocked
    assert any(f["severity"] == "flag" for f in r.flags)
    assert 0 < r.risk_score < 100


def test_clean_text_passes():
    r = compliance.scan_text("neutral boho nursery wall art set")
    assert not r.blocked and not r.flags and r.risk_score == 0


def test_word_boundary_no_false_positive():
    # "nba" inside another word must not match
    assert not compliance.scan_text("sunbathing beach print").blocked


def test_ai_disclosure_trigger():
    assert compliance.scan_text("made with midjourney").needs_ai_disclosure
