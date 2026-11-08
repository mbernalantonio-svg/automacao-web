import pytest

from main import _validate_cli_paths
import base64
from pathlib import Path

from src.result_downloader import (
    _as_renderable_html,
    _build_day_download_name,
    _decode_result_payload,
    _extract_result_file_urls,
    _html_to_pdf_bytes,
    _is_expired_auth_token,
    _is_login_page_candidate,
    _result_has_downloaded_files,
    _safe_filename,
    build_new_ids,
)


def test_build_new_ids_returns_only_new_results():
    existing = {"#255952", "#250359"}
    incoming = ["#255952", "#250359", "#255953", "#255954"]

    assert build_new_ids(existing, incoming) == ["#255953", "#255954"]


def test_safe_filename_removes_tmp_suffix():
    assert _safe_filename("#255952_1234.tmp.pdf") == "#255952_1234.pdf"
    assert _safe_filename("#255952_1234.pdf") == "#255952_1234.pdf"


def test_build_day_download_name_uses_day_folder_and_file_type():
    row_text = "#255952 25/10/2026 Prova"
    assert _build_day_download_name(row_text, "Prova") == "Prova_2026-10-25.html"
    assert _build_day_download_name(row_text, "Tomada") == "Tomada_2026-10-25.html"
    assert _build_day_download_name(row_text, "Volta a Volta") == "Volta_a_Volta_2026-10-25.html"


def test_extract_result_file_urls_uses_historico_api_payload():
    entry = {
        "idvenda": 255952,
        "idvendacliente": 218541,
        "horario_inicio": "2026-10-25 09:30:00",
        "resultados_pista": "https://example.test/obterResultadoPistaToken/?token=prova-token",
        "resultados_pista_tomada": "https://example.test/obterResultadoPistaToken/?token=tomada-token",
        "resultados_pista_volta_a_volta": "https://example.test/obterResultadoPistaToken/?token=volta-token",
    }

    assert _extract_result_file_urls(entry) == {
        "Prova": "https://example.test/obterResultadoPistaToken/?token=prova-token",
        "Tomada": "https://example.test/obterResultadoPistaToken/?token=tomada-token",
        "Volta a Volta": "https://example.test/obterResultadoPistaToken/?token=volta-token",
    }


def test_validate_cli_paths_rejects_example_user_path():
    with pytest.raises(ValueError, match="seu_usuario"):
        _validate_cli_paths(
            r"C:\Users\seu_usuario\OneDrive\kart",
            r"C:\Users\seu_usuario\OneDrive\kart\.downloaded_results.json",
        )


def test_result_has_downloaded_files_ignores_stale_state_when_files_missing(tmp_path):
    row_text = "#255952 25/10/2026 Prova"
    assert not _result_has_downloaded_files(tmp_path, row_text)

    output = tmp_path / "2026" / "10" / "25"
    output.mkdir(parents=True)
    (output / "Prova_2026-10-25.pdf").write_bytes(b"%PDF-1.4")

    assert _result_has_downloaded_files(tmp_path, row_text)


def test_result_has_downloaded_files_rejects_json_content_as_invalid_pdf(tmp_path):
    row_text = "#255952 25/10/2026 Prova"
    output = tmp_path / "2026" / "10" / "25"
    output.mkdir(parents=True)
    (output / "Prova_2026-10-25.pdf").write_text('{"status":"success"}', encoding='utf-8')

    assert not _result_has_downloaded_files(tmp_path, row_text)


def test_result_has_downloaded_files_accepts_html_content_as_valid_result(tmp_path):
    row_text = "#255952 25/10/2026 Prova"
    output = tmp_path / "2026" / "10" / "25"
    output.mkdir(parents=True)
    (output / "Prova_2026-10-25.html").write_text('<html><body>Resultado</body></html>', encoding='utf-8')

    assert _result_has_downloaded_files(tmp_path, row_text)


def test_html_to_pdf_bytes_generates_renderable_html_document():
    html = '<html><body><h1>Resultado</h1></body></html>'
    rendered = _html_to_pdf_bytes(html)
    assert rendered.startswith(b'<html')
    assert b'<table' in rendered.lower() or b'<body' in rendered.lower()


def test_html_to_pdf_bytes_handles_plain_text_results():
    html = "Tempos de volta\n09:56:49.703 1 1 22.857 44.100\n09:58:04.408 2 2 1:14.705 48.912"
    rendered = _html_to_pdf_bytes(html)
    assert rendered.startswith(b'<html')
    assert b'09:56' in rendered


def test_as_renderable_html_keeps_table_markup_when_present():
    html = '<html><body><table><tr><td>09:56</td><td>1</td></tr></table></body></html>'
    rendered = _as_renderable_html(html)
    assert '<table' in rendered.lower()
    assert '<td>' in rendered.lower()


def test_decode_result_payload_handles_base64_pdf_response():
    base64_content = base64.b64encode(b"%PDF").decode("ascii")
    payload = {
        "status": "success",
        "data": {
            "status": "success",
            "data": {
                "mode": "base64",
                "content": base64_content,
                "filename": "Prova_2026-10-25.pdf",
                "mime": "application/pdf",
            },
        },
    }

    decoded = _decode_result_payload(payload)
    assert decoded.startswith(b"%PDF")
    assert decoded == b"%PDF"


def test_expired_auth_token_is_detected():
    payload = {"exp": 1}
    encoded = base64.urlsafe_b64encode(
        __import__("json").dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    expired_token = f"eyJhbGciOiJIUzI1NiJ9.{encoded}.signature"

    assert _is_expired_auth_token(expired_token) is True
    assert _is_expired_auth_token(None) is True

    future_payload = {"exp": 4102444800}
    future_encoded = base64.urlsafe_b64encode(
        __import__("json").dumps(future_payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    valid_token = f"eyJhbGciOiJIUzI1NiJ9.{future_encoded}.signature"
    assert _is_expired_auth_token(valid_token) is False


def test_login_page_candidate_detects_login_screen():
    page_source = """
    <html><body>
      <h1>Para reservar, faça login</h1>
      <input placeholder="seu@email.com" />
      <input placeholder="Digite sua senha" />
      <button>Entrar</button>
    </body></html>
    """
    assert _is_login_page_candidate(page_source) is True
    assert _is_login_page_candidate("<html><body>Minhas Corridas</body></html>") is False
