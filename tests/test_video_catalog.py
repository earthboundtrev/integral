from progression.video_catalog import get_exercise_video


def test_get_exercise_video_prefers_specific_override():
    video = get_exercise_video("ss_back_squat", "SS", "main", "Back Squat")
    assert video is not None
    assert "startingstrength" in video["url"].lower() or "youtube.com" in video["url"]
    assert "Starting Strength" in video["source"]


def test_get_exercise_video_falls_back_to_series():
    video = get_exercise_video("cc1_squat_03", "CC1", "squat", "Supported Squats")
    assert video is not None
    assert video["url"]
    assert "Dragon Door" in video["source"] or "Paul Wade" in video["source"]


def test_get_exercise_video_for_ftr():
    video = get_exercise_video("ftr_rite_1", "FTR", "rites", "Rite 1 - Spinning")
    assert video is not None
    assert "Chris Kilham" in video["source"]


def test_get_exercise_video_for_cc2():
    video = get_exercise_video(
        "cc2_trifecta_l_hold_04", "CC2", "trifecta_l_hold", "L-Hold"
    )
    assert video is not None
    assert "FitnessFAQs" in video["source"]
    assert "youtube.com" in video["url"]

    flag = get_exercise_video(
        "cc2_clutch_flag_03", "CC2", "clutch_flag", "Clutch Flag"
    )
    assert flag is not None
    assert "THENX" in flag["source"] or "Heria" in flag["source"]

    series = get_exercise_video("cc2_hang_01", "CC2", "hang", "Horizontal Hang")
    assert series is not None
    assert "Dragon Door" in series["source"] or "Paul Wade" in series["source"]
