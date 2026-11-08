from __future__ import annotations

import base64
import html
import json
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


DEFAULT_LOGIN_URL = "https://reservas.kartodromogranjaviana.com.br/reservaonline/"
DEFAULT_API_BASE_URL = "https://reservas.kartodromogranjaviana.com.br"


def build_new_ids(existing_ids: set[str] | list[str], incoming_ids: list[str]) -> list[str]:
    seen = set(existing_ids if isinstance(existing_ids, set) else set(existing_ids))
    new_ids: list[str] = []

    for result_id in incoming_ids:
        normalized = normalize_result_id(result_id)
        if normalized and normalized not in seen and normalized not in new_ids:
            new_ids.append(normalized)

    return new_ids


def normalize_result_id(value: str) -> str:
    if not value:
        return ""

    match = re.search(r"#?\d+", str(value).strip())
    if not match:
        return ""

    return f"#{match.group(0).lstrip('#')}"


def load_downloaded_ids(path: str | Path) -> set[str]:
    file_path = Path(path)
    if not file_path.exists():
        return set()

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()

    if isinstance(data, list):
        return {normalize_result_id(item) for item in data if normalize_result_id(item)}

    if isinstance(data, dict):
        items = data.get("downloaded_ids", [])
        return {normalize_result_id(item) for item in items if normalize_result_id(item)}

    return set()


def save_downloaded_ids(path: str | Path, ids: set[str]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(ids)
    file_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def _collect_result_ids(driver: webdriver.Chrome) -> list[str]:
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    result_ids: list[str] = []
    for row in rows:
        row_text = row.text.strip()
        result_id = normalize_result_id(row_text)
        if result_id and row.find_elements(By.CSS_SELECTOR, 'button[title="Visualizar Prova"]'):
            result_ids.append(result_id)
    return result_ids


def _find_row_by_result_id(driver: webdriver.Chrome, result_id: str):
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    for row in rows:
        if normalize_result_id(row.text) == result_id:
            return row
    raise ValueError(f"Linha do resultado {result_id} não encontrada.")


def _wait_for_new_file(directory: Path, before: set[Path], timeout: int = 60) -> Path:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = set(directory.rglob("*"))
        new_files = current - before
        if new_files:
            newest = max(new_files, key=lambda item: item.stat().st_mtime)
            return newest
        time.sleep(1)

    raise TimeoutError(f"Nenhum novo arquivo foi gerado em {directory} dentro de {timeout} segundos.")


def _safe_filename(filename: str) -> str:
    cleaned = filename.strip()
    cleaned = re.sub(r"(?i)\.tmp(?=\.[a-z0-9]+$)", "", cleaned)
    cleaned = re.sub(r"(?i)\.(crdownload|part)$", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9.#_-]", "_", cleaned)
    cleaned = cleaned.replace("__", "_")

    if not cleaned:
        return "resultado.pdf"

    if "." not in cleaned:
        return f"{cleaned}.pdf"

    suffix = Path(cleaned).suffix.lower()
    if suffix not in {".pdf", ".html", ".htm", ".csv", ".xlsx", ".xls", ".zip"}:
        return f"{cleaned}.pdf"

    return cleaned


def _normalize_file_type(file_type: str) -> str | None:
    normalized = (file_type or "").strip().lower()
    if not normalized:
        return None
    if "prova" in normalized:
        return "Prova"
    if "tomada" in normalized:
        return "Tomada"
    if "volta" in normalized:
        return "Volta a Volta"
    return None


def _build_day_download_name(row_text: str, file_type: str) -> str:
    activity_date = _extract_activity_date(row_text)
    date_fragment = activity_date.strftime("%Y-%m-%d") if activity_date else "0000-00-00"
    normalized_type = _normalize_file_type(file_type) or "Arquivo"
    cleaned_name = re.sub(r"[^A-Za-z0-9]+", "_", normalized_type).strip("_")
    return f"{cleaned_name}_{date_fragment}.html"


def _is_valid_download_file(path: Path) -> bool:
    if not path.is_file():
        return False

    try:
        head = path.read_bytes()[:128]
    except OSError:
        return False

    lowered = head.lower()
    return head.startswith(b"%PDF") or b"<html" in lowered or b"<!doctype html" in lowered


def _result_has_downloaded_files(output_dir: Path, row_text: str) -> bool:
    activity_date = _extract_activity_date(row_text)
    if activity_date is None:
        return False

    day_dir = output_dir / str(activity_date.year) / activity_date.strftime("%m") / str(activity_date.day)
    if not day_dir.exists():
        return False

    expected_files = {
        _build_day_download_name(row_text, "Prova"),
        _build_day_download_name(row_text, "Tomada"),
        _build_day_download_name(row_text, "Volta a Volta"),
    }
    candidates = set(expected_files)
    for filename in list(expected_files):
        if filename.lower().endswith(".pdf"):
            candidates.add(filename[:-4] + ".html")
        elif filename.lower().endswith(".html"):
            candidates.add(filename[:-5] + ".pdf")

    return any(_is_valid_download_file(day_dir / filename) for filename in candidates)


def _cleanup_temp_downloads(base_dir: Path) -> None:
    if not base_dir.exists():
        return

    for path in list(base_dir.rglob("*")):
        if not path.is_file():
            continue

        name = path.name.lower()
        if name.endswith((".tmp", ".tmp.pdf", ".part", ".crdownload")):
            path.unlink(missing_ok=True)


def _extract_activity_date(row_text: str) -> datetime | None:
    match = re.search(r"(\d{2}/\d{2}/\d{4})", row_text)
    if not match:
        return None

    try:
        return datetime.strptime(match.group(1), "%d/%m/%Y")
    except ValueError:
        return None


def _get_destination_for_result(base_dir: Path, row_text: str, proposed_name: str) -> Path:
    activity_date = _extract_activity_date(row_text)
    if activity_date is None:
        target_dir = base_dir
    else:
        target_dir = base_dir / str(activity_date.year) / activity_date.strftime("%m") / str(activity_date.day)

    target_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(proposed_name)
    suffix = filename.suffix.lower()
    if suffix not in {".pdf", ".html", ".htm", ".csv", ".xlsx", ".xls", ".zip"}:
            filename = Path(f"{filename.name}.html")

def _collect_modal_download_types(driver: webdriver.Chrome) -> list[str]:
    detected: list[str] = []
    for button in driver.find_elements(By.XPATH, ".//button"):
        label = button.text.strip()
        file_type = _normalize_file_type(label)
        if file_type and file_type not in detected:
            detected.append(file_type)
    return detected


def _find_modal_download_button(driver: webdriver.Chrome, file_type: str):
    target = _normalize_file_type(file_type)
    if not target:
        return None

    candidates = driver.find_elements(By.XPATH, ".//button")
    for button in candidates:
        label = button.text.strip()
        if target == _normalize_file_type(label):
            return button
    return None


def _extract_result_file_urls(result_entry: dict) -> dict[str, str]:
    file_urls: dict[str, str] = {}
    mapping = {
        "Prova": "resultados_pista",
        "Tomada": "resultados_pista_tomada",
        "Volta a Volta": "resultados_pista_volta_a_volta",
    }

    for file_type, key in mapping.items():
        value = (result_entry or {}).get(key)
        if isinstance(value, str) and value.strip():
            file_urls[file_type] = value.strip()

    return file_urls


def _get_customer_id_from_local_storage(driver: webdriver.Chrome) -> str | None:
    script = """
    const keys = ['currentUser', 'kgv_user'];
    for (const key of keys) {
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      try {
        const data = JSON.parse(raw);
        const candidate = data.idcliente ?? data.id ?? data.cliente_id ?? data.user_id;
        if (candidate !== undefined && candidate !== null && candidate !== '') {
          return String(candidate);
        }
      } catch (error) {
        // ignore malformed localStorage entries
      }
    }
    return null;
    """
    return driver.execute_script(script)


def _decode_jwt_payload(token: str) -> dict | None:
    if not token or not isinstance(token, str):
        return None

    try:
        _, payload, _ = token.split(".")
        if not payload:
            return None
        padded = payload + "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _is_expired_auth_token(token: str | None) -> bool:
    if not token:
        return True

    payload = _decode_jwt_payload(token)
    if not payload:
        return True

    expires = payload.get("exp")
    if expires is None:
        return True

    try:
        expires = int(expires)
    except (TypeError, ValueError):
        return True

    return expires <= int(time.time()) + 30


def _clear_browser_session(driver: webdriver.Chrome) -> None:
    try:
        driver.execute_script("try { localStorage.clear(); } catch (error) {}")
        driver.execute_script("try { sessionStorage.clear(); } catch (error) {}")
    except Exception:
        pass
    try:
        driver.delete_all_cookies()
    except Exception:
        pass


def _build_authenticated_session(driver: webdriver.Chrome) -> requests.Session:
    session = requests.Session()
    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie.get("name"),
            cookie.get("value"),
            domain=cookie.get("domain") or None,
            path=cookie.get("path") or "/",
        )

    token = driver.execute_script("return localStorage.getItem('kgv_auth_token') || '';")
    if token:
        session.headers.update({"Authorization": f"Bearer {token}"})

    return session


def _apply_cookie_string(session: requests.Session, cookie_string: str | None, url: str) -> None:
    if not cookie_string:
        return
    parsed = {}
    for chunk in cookie_string.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        name, value = chunk.split("=", 1)
        parsed[name.strip()] = value.strip()

    for name, value in parsed.items():
        session.cookies.set(name, value, domain=urlparse(url).hostname or None, path="/")


def _manual_session_from_browser_data(
    auth_token: str | None,
    cookie_string: str | None,
    customer_id: str | None,
    base_url: str = DEFAULT_API_BASE_URL,
) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": base_url,
        "Referer": f"{base_url}/reservaonline/",
        "X-Requested-With": "XMLHttpRequest",
    })
    if auth_token:
        session.headers.update({"Authorization": f"Bearer {auth_token}"})
    if customer_id:
        session.headers.update({"X-Client-Id": str(customer_id)})
    _apply_cookie_string(session, cookie_string, f"{base_url}/reservaonline/")
    return session


def _load_history_via_manual_session(
    auth_token: str | None,
    cookie_string: str | None,
    customer_id: str | None,
    base_url: str = DEFAULT_API_BASE_URL,
) -> list[dict]:
    if not auth_token or not customer_id:
        return []

    session = _manual_session_from_browser_data(auth_token, cookie_string, customer_id, base_url)
    url = f"{base_url}/kgv/reserva_online/onHistoricoVendas/?idcliente={customer_id}"
    response = session.get(url, timeout=30)
    if response.status_code == 401:
        raise PermissionError("Sessão autenticada do navegador foi rejeitada pelo servidor.")
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise ValueError("Resposta do histórico não estava em JSON válido.") from exc

    data = payload.get("data", {})
    items = data.get("data", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _find_result_entry_by_id(driver: webdriver.Chrome, result_id: str) -> dict | None:
    customer_id = _get_customer_id_from_local_storage(driver)
    if not customer_id:
        return None

    session = _build_authenticated_session(driver)
    base_url = "https://reservas.kartodromogranjaviana.com.br"
    url = f"{base_url}/kgv/reserva_online/onHistoricoVendas/?idcliente={customer_id}"
    try:
        response = session.get(url, timeout=30, headers={"Accept": "application/json"})
        response.raise_for_status()
    except requests.RequestException:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    candidates = payload.get("data", {}).get("data", [])
    for entry in candidates:
        item_id = entry.get("idvenda") or entry.get("idvendacliente") or entry.get("id")
        if normalize_result_id(item_id) == normalize_result_id(result_id):
            return entry

    return None


def _decode_result_payload(payload: object) -> bytes:
    if not isinstance(payload, dict):
        raise ValueError("Payload de resultado inválido.")

    if payload.get("mode") == "base64" and isinstance(payload.get("content"), str):
        return base64.b64decode(payload["content"], validate=True)

    for key in ("data", "result", "response"):
        if key in payload:
            try:
                return _decode_result_payload(payload[key])
            except ValueError:
                pass

    for key in ("content", "file", "blob", "pdf"):
        value = payload.get(key)
        if isinstance(value, str):
            try:
                return base64.b64decode(value, validate=True)
            except ValueError:
                return value.encode("utf-8")

    raise ValueError("Payload do resultado não contém PDF em base64.")


def _strip_html_to_text(raw_html: str | bytes) -> str:
    if isinstance(raw_html, bytes):
        text = raw_html.decode("utf-8", errors="replace")
    else:
        text = raw_html

    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fallback_text_pdf_bytes(text: str) -> bytes:
    plain_text = _strip_html_to_text(text) or "Resultado do kartódromo"
    lines: list[str] = []
    current: list[str] = []
    for word in plain_text.split():
        candidate = " ".join(current + [word])
        if len(candidate) > 90:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))

    pdf_objects: list[bytes] = []
    content_parts: list[str] = []
    y = 760
    for line in lines[:55]:
        safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_parts.append(f"BT /F1 12 Tf 50 {y} Td ({safe_line}) Tj ET")
        y -= 16

    content_stream = "\n".join(content_parts).encode("latin-1", errors="replace")
    pdf_objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    pdf_objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    pdf_objects.append(b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n")
    pdf_objects.append(b"4 0 obj\n<< /Length %d >>\nstream\n" % len(content_stream) + content_stream + b"\nendstream\nendobj\n")
    pdf_objects.append(b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    pdf_header = b"%PDF-1.4\n"
    chunks = [pdf_header]
    offsets = [0]
    for obj in pdf_objects:
        offsets.append(len(b"".join(chunks)))
        chunks.append(obj)
    xref_start = len(b"".join(chunks))
    xref_lines = [b"xref\n0 6\n0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(b"".join(xref_lines))
    chunks.append(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("ascii"))
    return b"".join(chunks)


def _as_renderable_html(html_text: str) -> str:
    stripped = html_text.strip()
    if not stripped:
        return "<html><body>Resultado</body></html>"

    lower = stripped.lower()
    if any(token in lower for token in ("<html", "<table", "<tbody", "<tr", "<td", "<div", "<body", "<thead", "<style")):
        return stripped

    lines = [line.strip() for line in re.split(r"\r?\n", stripped) if line.strip()]
    title_candidates = [line for line in lines if any(token in line.lower() for token in ("tempos de volta", "kartodromo", "resultado", "volta"))][:3]
    title = html.escape(title_candidates[0] if title_candidates else "Resultado")

    rows_html: list[str] = []
    for line in lines:
        if not re.search(r"\d{1,2}:\d{2}:\d{2}\.|\d{1,2}/\d{2}/\d{4}", line):
            continue
        cells = [cell.strip() for cell in re.split(r"\s{2,}|\t+", line) if cell.strip()]
        if not cells:
            continue
        cells_html = "".join(f"<td>{html.escape(cell)}</td>" for cell in cells[:8])
        rows_html.append(f"<tr>{cells_html}</tr>")

    if not rows_html:
        rows_html.append(f"<tr><td>{html.escape(stripped[:500])}</td></tr>")

    body = "".join(rows_html)
    return f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          body {{ font-family: Arial, sans-serif; margin: 18px; color: #111; background: #fff; }}
          h1 {{ font-size: 22px; margin-bottom: 12px; }}
          table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
          th, td {{ border: 1px solid #d0d0d0; padding: 4px 6px; text-align: left; }}
          tr:nth-child(even) {{ background: #f5f5f5; }}
        </style>
      </head>
      <body>
        <h1>{title}</h1>
        <table>
          {body}
        </table>
      </body>
    </html>
    """.strip()


def _html_to_pdf_bytes(html: str | bytes) -> bytes:
    if isinstance(html, bytes):
        html_text = html.decode("utf-8", errors="replace")
    else:
        html_text = html

    return _as_renderable_html(html_text).encode("utf-8", errors="replace")


def _print_current_page_to_pdf(driver: webdriver.Chrome) -> bytes:
    driver.execute_script("document.body.style.zoom = '1';")
    result = driver.execute_cdp_cmd(
        "Page.printToPDF",
        {
            "printBackground": True,
            "preferCSSPageSize": True,
            "displayHeaderFooter": False,
            "landscape": False,
            "margin": {"top": "0.15in", "bottom": "0.15in", "left": "0.15in", "right": "0.15in"},
            "scale": 1,
        },
    )
    pdf_bytes = base64.b64decode(result["data"])
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("A página renderizada não gerou um PDF válido.")
    return pdf_bytes


def _save_pdf_bytes(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)

    if destination.suffix.lower() == ".html":
        if content.startswith(b"<") or b"<html" in content.lower() or b"<!doctype html" in content.lower():
            return
        return

    if destination.suffix.lower() == ".pdf" and content.startswith(b"%PDF"):
        return

    if destination.suffix.lower() == ".pdf" and len(content) > 0 and not content.startswith(b"{"):
        return

    raise ValueError(f"Conteúdo inválido para PDF em {destination}")


def _is_login_page_candidate(page_text: str) -> bool:
    text = (page_text or "").lower()
    return (
        "para reservar, faça login" in text
        or "seu@email.com" in text
        or "digite sua senha" in text
        or "entrar" in text and "login" in text
    )


def _assert_dashboard_loaded(driver: webdriver.Chrome, timeout: int = 30) -> None:
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Minhas Corridas']"))
        )
        return
    except TimeoutException as exc:
        current_url = driver.current_url
        body_text = ""
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = body.text.strip()[:1200]
        except Exception:
            body_text = "(corpo da página indisponível)"

        if _is_login_page_candidate(body_text) or _is_login_page_candidate(driver.page_source):
            raise RuntimeError(
                "Login não foi concluído. O site continuou na tela de autenticação e não abriu a aba 'Minhas Corridas'. "
                f"URL atual: {current_url}."
            ) from exc

        raise RuntimeError(
            "Login ou navegação falhou: o botão 'Minhas Corridas' não apareceu. "
            f"URL atual: {current_url}. Texto da página: {body_text}"
        ) from exc


def _login_to_dashboard(driver: webdriver.Chrome, email: str, password: str, login_url: str) -> None:
    driver.get(login_url)

    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Aceitar Tudo']"))
        ).click()
    except Exception:
        pass

    WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Entrar']"))
    ).click()

    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="seu@email.com"]'))
    ).send_keys(email)
    driver.find_element(By.CSS_SELECTOR, 'input[placeholder="Digite sua senha"]').send_keys(password)
    driver.find_element(By.XPATH, "(//button[normalize-space()='Entrar'])[last()]").click()

    try:
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Minhas Corridas']"))
        ).click()
    except TimeoutException as exc:
        raise RuntimeError(
            "A página após o login não carregou o menu 'Minhas Corridas'. "
            "Verifique credenciais, CAPTCHA, bloqueio ou alterações no layout do site. "
            f"URL atual: {driver.current_url}"
        ) from exc

    _assert_dashboard_loaded(driver, timeout=30)


def _download_pdf_from_result_entry(session: requests.Session, result_entry: dict, row_text: str, output_path: Path) -> list[Path]:
    saved_files: list[Path] = []
    urls = _extract_result_file_urls(result_entry)
    for file_type, url in urls.items():
        response = session.get(url, timeout=60, allow_redirects=True)
        response.raise_for_status()
        if not response.content:
            raise ValueError(f"Resposta vazia ao baixar {file_type} para {row_text}.")

        content = response.content
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type or content.lstrip().startswith(b"{"):
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                content = _decode_result_payload(payload)

        mime_hint = (response.headers.get("Content-Type", "") or "").lower()
        if isinstance(response.headers.get("Content-Type"), str) and "json" in mime_hint:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                nested = payload.get("data")
                if isinstance(nested, dict):
                    mime_hint = str(nested.get("mime") or payload.get("mime") or mime_hint).lower()
                else:
                    mime_hint = str(payload.get("mime") or mime_hint).lower()
                content = _decode_result_payload(payload)

        if content.startswith(b"<html") or "html" in mime_hint:
            content = _html_to_pdf_bytes(content)
        else:
            content = _html_to_pdf_bytes(content)

        filename = _build_day_download_name(row_text, file_type)
        destination = _get_destination_for_result(output_path, row_text, filename)
        _save_pdf_bytes(destination, content)
        saved_files.append(destination)

    return saved_files


def _collect_rows_from_history(driver: webdriver.Chrome) -> list[webdriver.remote.webelement.WebElement]:
    return driver.find_elements(By.CSS_SELECTOR, "table tbody tr")


def _iter_all_history_pages(driver: webdriver.Chrome):
    seen_rows: set[str] = set()
    while True:
        rows = _collect_rows_from_history(driver)
        current = []
        for row in rows:
            key = normalize_result_id(row.text) or row.text.strip()
            if key and key not in seen_rows:
                seen_rows.add(key)
                current.append(row)
        yield current

        next_button = None
        for candidate in driver.find_elements(By.XPATH, "//button|//a|//span"):
            try:
                text = (candidate.text or "").strip().lower()
            except Exception:
                continue
            if any(token in text for token in ("próxima", "proxima", "next", "seguinte", ">", "›")):
                try:
                    if candidate.is_displayed() and candidate.is_enabled():
                        next_button = candidate
                        break
                except Exception:
                    continue
        if next_button is None:
            break
        try:
            next_button.click()
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(1)
        except Exception:
            break


def download_new_results(
    email: str,
    password: str,
    output_dir: str | Path = r"C:\Users\mbern\OneDrive\kart",
    state_file: str | Path = r"C:\Users\mbern\OneDrive\kart\.downloaded_results.json",
    login_url: str = DEFAULT_LOGIN_URL,
    auth_token: str | None = None,
    browser_cookie_string: str | None = None,
    customer_id: str | None = None,
) -> list[str]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if auth_token and customer_id:
        try:
            history_items = _load_history_via_manual_session(auth_token, browser_cookie_string, customer_id)
            if history_items:
                saved_ids: set[str] = set(load_downloaded_ids(state_file))
                downloaded_this_run: list[str] = []
                for item in history_items:
                    item_id = item.get("idvenda") or item.get("idvendacliente") or item.get("id")
                    result_id = normalize_result_id(item_id)
                    if not result_id or result_id in saved_ids:
                        continue
                    row_text = " ".join(str(value) for value in item.values() if isinstance(value, (str, int, float)))[:2000]
                    destination = _get_destination_for_result(output_path, row_text, _build_day_download_name(row_text, "Prova"))
                    payload = item
                    content = _decode_result_payload(payload) if isinstance(payload, dict) else b""
                    if not content:
                        continue
                    _save_pdf_bytes(destination, _html_to_pdf_bytes(_as_renderable_html(content.decode('utf-8', errors='replace'))))
                    saved_ids.add(result_id)
                    downloaded_this_run.append(result_id)
                save_downloaded_ids(state_file, saved_ids)
                return downloaded_this_run
        except Exception:
            pass

    temp_download_dir = output_path / ".downloads"
    temp_download_dir.mkdir(parents=True, exist_ok=True)
    _cleanup_temp_downloads(temp_download_dir)

    chrome_profile_dir = output_path / ".chrome_profile"
    if chrome_profile_dir.exists():
        for child in sorted(chrome_profile_dir.iterdir(), reverse=True):
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    chrome_profile_dir.mkdir(parents=True, exist_ok=True)

    saved_ids = set()
    save_downloaded_ids(state_file, saved_ids)
    downloaded_this_run: list[str] = []

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1536,960")
    chrome_options.add_argument("--user-data-dir=" + str(chrome_profile_dir.parent / ".chrome_user_data"))
    chrome_options.add_argument("--profile-directory=KGVAutomation")
    chrome_options.add_argument("--disable-features=PasswordManagerOnboarding")
    chrome_options.add_argument("--password-store=basic")
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(temp_download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
        },
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options,
    )

    try:
        _login_to_dashboard(driver, email, password, login_url)

        token = driver.execute_script("return localStorage.getItem('kgv_auth_token') || ''")
        if _is_expired_auth_token(token):
            _clear_browser_session(driver)
            _login_to_dashboard(driver, email, password, login_url)

        all_rows: list[tuple[str, object]] = []
        for page_rows in _iter_all_history_pages(driver):
            for row in page_rows:
                result_id = normalize_result_id(row.text)
                if result_id:
                    all_rows.append((result_id, row))

        by_id: dict[str, object] = {}
        for result_id, row in all_rows:
            if result_id and result_id not in by_id:
                by_id[result_id] = row

        new_ids: list[str] = []
        for result_id, row in all_rows:
            if result_id in saved_ids and _result_has_downloaded_files(output_path, row.text):
                continue
            if result_id not in new_ids:
                new_ids.append(result_id)

        if not new_ids and not by_id and _is_login_page_candidate(driver.page_source):
            raise RuntimeError(
                "O login não foi concluído ou a aba 'Minhas Corridas' não carregou. "
                "Verifique credenciais, bloqueio do site ou mudança no layout do painel."
            )

        if not new_ids and not by_id:
            raise RuntimeError(
                "Nenhuma linha de resultado foi encontrada na aba 'Minhas Corridas'. "
                "Verifique se a conta possui histórico, se o painel está carregado e se os seletores do site continuam iguais."
            )

        authenticated_session = _build_authenticated_session(driver)

        for result_id in new_ids:
            row = by_id.get(result_id)
            if row is None:
                continue
            row_text = row.text
            result_entry = _find_result_entry_by_id(driver, result_id)

            if result_entry is not None:
                _download_pdf_from_result_entry(authenticated_session, result_entry, row_text, output_path)
            else:
                try:
                    button = row.find_element(By.CSS_SELECTOR, 'button[title="Visualizar Prova"]')
                    button.click()
                    WebDriverWait(driver, 15).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                    time.sleep(1)
                    html_bytes = _html_to_pdf_bytes(driver.page_source)
                    destination = _get_destination_for_result(output_path, row_text, _build_day_download_name(row_text, "Prova"))
                    _save_pdf_bytes(destination, html_bytes)
                except Exception:
                    try:
                        row.click()
                        time.sleep(1)
                        html_bytes = _html_to_pdf_bytes(driver.page_source)
                        destination = _get_destination_for_result(output_path, row_text, _build_day_download_name(row_text, "Prova"))
                        _save_pdf_bytes(destination, html_bytes)
                    except Exception:
                        continue

                try:
                    WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Fechar']"))
                    ).click()
                except Exception:
                    try:
                        driver.find_element(By.XPATH, "//button[normalize-space()='Close']").click()
                    except Exception:
                        pass

            saved_ids.add(result_id)
            downloaded_this_run.append(result_id)

        save_downloaded_ids(state_file, saved_ids)

    finally:
        _clear_browser_session(driver)
        driver.quit()
        user_data_dir = output_path / ".chrome_user_data"
        shutil.rmtree(user_data_dir, ignore_errors=True)
        save_downloaded_ids(state_file, saved_ids)

    return downloaded_this_run
