from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import json

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
    WebDriverWait(d,30).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'table tbody tr')))
    js="""
    return fetch('https://reservas.kartodromogranjaviana.com.br/kgv/reserva_online/onHistoricoVendas/?idcliente=455', {
      method: 'GET',
      credentials: 'include',
      headers: {'Accept': 'application/json'}
    }).then(r => r.text())
    """
    text = d.execute_script(js)
    print(text[:4000])
finally:
    d.quit()
