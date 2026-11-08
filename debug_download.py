from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

email='mbernalantonio@hotmail.com'
password='Mba@190313'
opts=Options()
opts.add_argument('--headless=new')
opts.add_argument('--disable-gpu')
opts.add_argument('--no-sandbox')
opts.add_argument('--window-size=1536,960')
opts.add_experimental_option('prefs', {'download.default_directory': r'C:\Users\mbern\OneDrive\kart\.downloads-debug', 'download.prompt_for_download': False, 'download.directory_upgrade': True, 'safebrowsing.enabled': False})
d=webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

try:
    d.get('https://reservas.kartodromogranjaviana.com.br/reservaonline/')
    try:
        WebDriverWait(d,10).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Aceitar Tudo']"))).click()
    except Exception:
        pass
    WebDriverWait(d,20).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Entrar']"))).click()
    WebDriverWait(d,20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="seu@email.com"]'))).send_keys(email)
    d.find_element(By.CSS_SELECTOR, 'input[placeholder="Digite sua senha"]').send_keys(password)
    d.find_element(By.XPATH, "(//button[normalize-space()='Entrar'])[last()]").click()
    WebDriverWait(d,30).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Minhas Corridas']"))).click()
    WebDriverWait(d,30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'table tbody tr')))
    rows=d.find_elements(By.CSS_SELECTOR, 'table tbody tr')
    for i,row in enumerate(rows[:2],1):
        result=row.text.strip().split('\n')[0]
        print('RESULT', result)
        btn=row.find_element(By.CSS_SELECTOR, 'button[title="Visualizar Prova"]')
        btn.click()
        time.sleep(2)
        found=[]
        for el in d.find_elements(By.XPATH, ".//button"):
            text=(el.text or '').strip()
            if 'Baixar' in text or 'Fechar' in text or 'Close' in text or 'Visualizar' in text or 'Prova' in text:
                found.append((text, el))
        print('found buttons:', len(found))
        for text, el in found[:20]:
            print('TEXT:', text)
            print('onclick:', el.get_attribute('onclick'))
            print('data-url:', el.get_attribute('data-url'))
            print('href:', el.get_attribute('href'))
            print('aria-label:', el.get_attribute('aria-label'))
            print('outerHTML:', el.get_attribute('outerHTML')[:1500])
            print('---')
        page_html = d.page_source
        for token in ['Baixar', 'download', 'Visualizar Prova', 'blob', 'pdf', 'downloadPdf', 'window.open']:
            idx = page_html.lower().find(token.lower())
            if idx != -1:
                print('TOKEN', token, 'found at', idx)
                print(page_html[idx:idx+500])
                print('---')
        try:
            d.find_element(By.XPATH, "//button[normalize-space()='Fechar']").click()
        except Exception:
            try:
                d.find_element(By.XPATH, "//button[normalize-space()='Close']").click()
            except Exception:
                pass
        time.sleep(1)
finally:
    d.quit()
