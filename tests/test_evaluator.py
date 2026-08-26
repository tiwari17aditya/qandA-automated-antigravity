import pytest
from email_evaluator import extract_answers_from_text, extract_drill_id_from_email
from db import get_quiz_by_drill_key

def test_whitespace_middle_no_shift():
    """
    Test string "DBCBCBBBCCCBCCCADAABBBBBBCCBBBBABBCCABBBB BCDBCACB" (50 Qs)
    to ensure Q42 (index 41) is marked None (unattempted) and Q43-Q50 retain exact positions.
    """
    questions = [{"id": i} for i in range(50)]
    input_str = "DBCBCBBBCCCBCCCADAABBBBBBCCBBBBABBCCABBBB BCDBCACB"
    result = extract_answers_from_text(input_str, questions)
    
    assert len(result) == 50
    assert result[41] is None  # Q42 is space -> None
    assert result[42] == "B"   # Q43 is 'B'
    assert result[43] == "C"   # Q44 is 'C'
    assert result[44] == "D"   # Q45 is 'D'
    assert result[49] == "B"   # Q50 is 'B'

def test_multiple_consecutive_spaces():
    """
    Test "A  B C" for 6 questions -> indices 1, 2, 4 (Q2, Q3, Q5) marked None.
    """
    questions = [{"id": i} for i in range(6)]
    input_str = "A  B C"
    result = extract_answers_from_text(input_str, questions)
    
    assert len(result) == 6
    assert result[0] == "A"
    assert result[1] is None
    assert result[2] is None
    assert result[3] == "B"
    assert result[4] is None
    assert result[5] == "C"

def test_trailing_blanks_partial_submission():
    """
    50 answers provided for a 60-question drill -> Q51-Q60 marked None (unattempted).
    """
    questions = [{"id": i} for i in range(60)]
    input_str = "A" * 50
    result = extract_answers_from_text(input_str, questions)
    
    assert len(result) == 60
    assert result[:50] == ["A"] * 50
    assert result[50:] == [None] * 10

def test_formatted_numbered_inputs():
    """
    Formatted numbered inputs: "1. A\n2. B\n3. \n4. C" -> Q3 is None.
    """
    questions = [{"id": i} for i in range(4)]
    input_str = "1. A\n2. B\n3. -\n4. C"
    result = extract_answers_from_text(input_str, questions)
    
    assert len(result) == 4
    assert result == ["A", "B", None, "C"]

def test_delimited_tokens_and_hyphens():
    """
    Test continuous stream with hyphens and spaces: "ABCD AB--CD" (11 Qs).
    """
    questions = [{"id": i} for i in range(11)]
    input_str = "ABCD AB--CD"
    result = extract_answers_from_text(input_str, questions)
    
    assert len(result) == 11
    assert result[0:4] == ["A", "B", "C", "D"]
    assert result[4] is None
    assert result[5:7] == ["A", "B"]
    assert result[7:9] == [None, None]
    assert result[9:11] == ["C", "D"]

def test_drill_id_extraction():
    """
    Test extraction of DRILL-YYYYMMDD, DRILL-YYYYMMDD-HHMM, and fallback date patterns from subjects and bodies.
    """
    assert extract_drill_id_from_email("Re: Daily Drill - [DRILL-20260825]") == "DRILL-20260825"
    assert extract_drill_id_from_email("Re: Daily Drill", "Drill ID: DRILL-20260825-0700") == "DRILL-20260825-0700"
    assert extract_drill_id_from_email("Re: MPPSC Daily Drill 2026-08-25") == "2026-08-25"
    assert extract_drill_id_from_email("Hello Random Subject Without Drill") is None

def test_db_verification_guardrail_nonexistent():
    """
    Ensure get_quiz_by_drill_key returns None for invalid/corrupted drill keys without defaulting to latest test.
    """
    record = get_quiz_by_drill_key(drill_id="DRILL-19990101", target_date="1999-01-01", pipeline_id="non_existent_pipeline")
    assert record is None
