from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests, json

opts=Options(); opts.add_argument('--headless=new'); opts.add_argument('--disable-gpu'); opts.add_argument('--no-sandbox'); opts.add_argument('--window-size=1536,960')

d=webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
try:
    d.get('https://reservas.kartodromogranjaviana.com.br/reservaonline/')
    try:
        WebDriverWait(d,10).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Aceitar Tudo']"))).click()
    except Exception:
        pass
    WebDriverWait(d,20).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Entrar']"))).click()
    WebDriverWait(d,20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="seu@email.com"]'))).send_keys('mbernalantonio@hotmail.com')
    d.find_element(By.CSS_SELECTOR, 'input[placeholder="Digite sua senha"]').send_keys('Mba@190313')
    d.find_element(By.XPATH, "(//button[normalize-space()='Entrar'])[last()]").click()
    WebDriverWait(d,30).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Minhas Corridas']"))).click()

    s=requests.Session()
    for c in d.get_cookies():
        s.cookies.set(c['name'], c['value'], domain=c.get('domain') or None, path=c.get('path') or '/')
    token = d.execute_script("return localStorage.getItem('kgv_auth_token') || ''")
    s.headers.update({'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/plain, */*'})

    hist = s.get('https://reservas.kartodromogranjaviana.com.br/kgv/reserva_online/onHistoricoVendas/?idcliente=455', timeout=30)
    print('HIST STATUS', hist.status_code, hist.headers.get('content-type'))
    print(hist.text[:500])
    payload = hist.json()
    item = payload['data']['data'][0]
    url = item['resultados_pista']
    print('URL', url)
    rr = s.get(url, timeout=60)
    print('RR STATUS', rr.status_code, rr.headers.get('content-type'))
    payload = rr.json()
    data = payload['data']['data']
    decoded = __import__('base64').b64decode(data['content'])
    print('MIME', data.get('mime'))
    print('DECODED_START', decoded[:500].decode('utf-8', 'replace'))
    print('BYTES', rr.content[:60])
finally:
    d.quit()
