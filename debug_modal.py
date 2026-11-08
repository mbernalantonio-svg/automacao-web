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
    print('rows', len(rows))
    for idx,row in enumerate(rows[:3],1):
        txt=row.text.strip().replace('\n',' | ')
        print('ROW', idx, txt[:800])
        btn=row.find_elements(By.CSS_SELECTOR, 'button[title="Visualizar Prova"]')
        if not btn:
            print('sem botao visualizar')
            continue
        btn[0].click()
        time.sleep(2)
        print('dialogos=', len(d.find_elements(By.XPATH, "//div[contains(@role,'dialog')]")))
        print('title visual', len(d.find_elements(By.CSS_SELECTOR, 'button[title*="Visualizar"]')))
        print('title prova', len(d.find_elements(By.CSS_SELECTOR, 'button[title*="Prova"]')))
        print('aria labels', [b.get_attribute('aria-label') for b in d.find_elements(By.TAG_NAME, 'button') if b.get_attribute('aria-label')][:20])
        all_buttons=d.find_elements(By.TAG_NAME, 'button')
        print('total buttons=', len(all_buttons))
        for b in all_buttons:
            t=(b.text or '').strip()
            if t:
                print('BUTTON:', repr(t))
        try:
            close = d.find_element(By.XPATH, "//button[normalize-space()='Fechar']")
            close.click()
        except Exception:
            try:
                d.find_element(By.XPATH, "//button[normalize-space()='Close']").click()
            except Exception:
                pass
        time.sleep(1)
        print('---')
finally:
    d.quit()
