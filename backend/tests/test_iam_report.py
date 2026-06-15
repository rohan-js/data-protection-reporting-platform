from app.ingestion.iam_report import parse_credential_report


def test_parse_credential_report_calculates_key_age():
    content = b"""user,arn,mfa_active,password_last_used,access_key_1_last_rotated,access_key_2_last_rotated
alice,arn:aws:iam::123456789012:user/alice,false,2026-06-01T00:00:00+00:00,2026-01-01T00:00:00+00:00,N/A
"""
    rows = parse_credential_report(content)

    assert rows[0]["name"] == "alice"
    assert rows[0]["mfa_enabled"] == 0
    assert rows[0]["access_key_age_days"] is not None

