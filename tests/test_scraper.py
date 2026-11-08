from src.scraper import parse_cookie_string


def test_parse_cookie_string():
    cookies = parse_cookie_string("sessionid=abc123; csrftoken=xyz789")
    assert cookies == {"sessionid": "abc123", "csrftoken": "xyz789"}
