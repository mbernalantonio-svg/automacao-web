from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if not cookie_string:
        return cookies

    for chunk in cookie_string.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        cookies[name.strip()] = value.strip()

    return cookies


def fetch_page(
    url: str,
    timeout: int = 30,
    cookie_string: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> str:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    if extra_headers:
        session.headers.update(extra_headers)

    if cookie_string:
        for name, value in parse_cookie_string(cookie_string).items():
            domain = urlparse(url).hostname or ""
            session.cookies.set(name, value, domain=domain)

    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def save_to_file(content: str, output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def download_data(
    url: str,
    output_path: str | Path,
    raw: bool = False,
    cookie_string: str | None = None,
) -> Path:
    html = fetch_page(url, cookie_string=cookie_string)
    content = html if raw else extract_text(html)
    destination = save_to_file(content, output_path)
    return destination


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python src/scraper.py <URL> <arquivo_saida> [--raw] [--cookie 'nome=valor; ...']")
        raise SystemExit(1)

    url = sys.argv[1]
    output_path = sys.argv[2]
    raw = any(arg.lower() == "--raw" for arg in sys.argv[3:])
    cookie_string = None

    for index, arg in enumerate(sys.argv[3:]):
        if arg.lower() == "--cookie" and index + 3 < len(sys.argv):
            cookie_string = sys.argv[index + 3]
            break

    try:
        saved_path = download_data(url, output_path, raw=raw, cookie_string=cookie_string)
        print(f"Dados salvos em: {saved_path.resolve()}")
    except requests.RequestException as exc:
        print(f"Erro ao acessar o site: {exc}", file=sys.stderr)
        raise SystemExit(1)
