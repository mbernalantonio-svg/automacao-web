import os
import re
import json
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# Credenciais e caminhos com suporte a variáveis de ambiente (GitHub Actions / Local)
EMAIL = os.getenv("KGV_EMAIL", "mbernalantonio@hotmail.com")
SENHA = os.getenv("KGV_PASSWORD", "Mba@190313")
BASE_DIR = Path(os.getenv("OUTPUT_DIR", r"C:\Users\mbern\OneDrive\kart"))
STATE_FILE = BASE_DIR / ".downloaded_results.json"
BASE_URL = "https://reservas.kartodromogranjaviana.com.br/reservaonline/"

TIPOS_BOTOES = [
    {
        "tipo": "Prova",
        "seletor": "button[title='Visualizar Prova'], button:has-text('Visualizar Prova')"
    },
    {
        "tipo": "Tomada",
        "seletor": "button[title='Visualizar Tomada'], button:has-text('Visualizar Tomada')"
    },
    {
        "tipo": "Volta_a_Volta",
        "seletor": "button[title='Visualizar Volta-a-Volta'], button:has-text('Visualizar Volta-a-Volta'), button:has-text('Volta a Volta')"
    }
]

def load_state() -> set:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_state(processed_ids: set):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(processed_ids)), f, indent=2)

def process_results():
    processed_ids = load_state()
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=is_ci,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print(">> Acessando o portal do Kartódromo Granja Viana...")
        page.goto(BASE_URL, wait_until="networkidle")

        try:
            btn_cookie = page.locator("button:has-text('Aceitar Tudo')")
            if btn_cookie.is_visible(timeout=3000):
                btn_cookie.click()
        except Exception:
            pass

        print(">> Realizando autenticação...")
        page.locator("button:has-text('Entrar')").first.click()
        page.wait_for_selector('input[placeholder="seu@email.com"]', timeout=10000)
        page.fill('input[placeholder="seu@email.com"]', EMAIL)
        page.fill('input[placeholder="Digite sua senha"]', SENHA)
        page.locator("button:has-text('Entrar')").last.click()

        print(">> Aguardando painel e acessando 'Minhas Corridas'...")
        btn_corridas = page.wait_for_selector("button:has-text('Minhas Corridas')", timeout=20000)
        btn_corridas.click()

        page.wait_for_selector("table tbody tr", timeout=20000)
        page.wait_for_timeout(3000)

        rows = page.locator("table tbody tr")
        total_rows = rows.count()
        print(f">> Total de linhas na tabela: {total_rows}")

        novos_arquivos = 0

        for i in range(total_rows):
            row = rows.nth(i)
            row_text = row.inner_text().replace("\n", " ")

            match_id = re.search(r"#?(\d{5,8})", row_text)
            corrida_id = match_id.group(1) if match_id else f"linha_{i+1}"

            match_data = re.search(r"(\d{2})/(\d{2})/(\d{4})", row_text)
            if match_data:
                dia, mes, ano = match_data.group(1), match_data.group(2), match_data.group(3)
                data_iso = f"{ano}-{mes}-{dia}"
            else:
                agora = datetime.now()
                ano, mes, dia = agora.strftime("%Y"), agora.strftime("%m"), agora.strftime("%d")
                data_iso = f"{ano}-{mes}-{dia}"

            pasta_destino = BASE_DIR / ano / mes / dia
            pasta_destino.mkdir(parents=True, exist_ok=True)

            linha_processou_algo = False

            for cfg in TIPOS_BOTOES:
                tipo = cfg["tipo"]
                seletor = cfg["seletor"]
                item_chave = f"{corrida_id}_{tipo}"

                btn = row.locator(seletor)
                if btn.count() == 0 or not btn.first.is_visible():
                    continue

                if item_chave in processed_ids:
                    continue

                print(f">> Gerando PDF de {tipo} da Corrida #{corrida_id} ({data_iso})...")

                btn.first.click()
                page.wait_for_timeout(2500)

                # Localiza o modal/área do relatório
                modal = page.locator("[role='dialog'], .modal, .MuiDialog-root, [class*='dialog']")
                caminho_pdf = pasta_destino / f"{tipo}_{data_iso}_#{corrida_id}.pdf"

                try:
                    # Em modo headless, o Playwright gera o PDF direto da visualização
                    page.pdf(path=str(caminho_pdf), format="A4", print_background=True)
                    print(f"   [OK] Salvo em PDF: {caminho_pdf.name}")
                    processed_ids.add(item_chave)
                    novos_arquivos += 1
                    linha_processou_algo = True
                except Exception as e:
                    print(f"   [AVISO] Falha ao imprimir PDF: {e}")

                try:
                    btn_fechar = page.locator("button:has-text('Fechar'), button[aria-label='Close'], button:has-text('OK')")
                    if btn_fechar.count() > 0 and btn_fechar.first.is_visible():
                        btn_fechar.first.click()
                    else:
                        page.keyboard.press("Escape")
                    page.wait_for_timeout(1000)
                except Exception:
                    page.keyboard.press("Escape")

            if linha_processou_algo:
                save_state(processed_ids)

        save_state(processed_ids)
        print(f"\n>> Concluído! Total de {novos_arquivos} arquivos PDF gerados com sucesso.")
        browser.close()

if __name__ == "__main__":
    process_results()
