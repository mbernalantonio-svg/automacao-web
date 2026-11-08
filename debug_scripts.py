from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

opts=Options(); opts.add_argument('--headless=new'); opts.add_argument('--disable-gpu'); opts.add_argument('--no-sandbox'); opts.add_argument('--window-size=1536,960')
d=webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
try:
    d.get('https://reservas.kartodromogranjaviana.com.br/reservaonline/')
    try:
        WebDriverWait(d,10).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Aceitar Tudo']"))).click()
    except Exception:
        pass
    WebDriverWait(d,20).until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Entrar']"))).click()
    WebDriverWait(d,20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[placeholder="seu@email.com"]')))
    for i, s in enumerate(d.find_elements(By.TAG_NAME,'script'),1):
        src=s.get_attribute('src')
        if src:
            print('SCRIPT', i, src)
        else:
            txt=(s.get_attribute('innerHTML') or '')
            if 'fetch' in txt.lower() or 'blob' in txt.lower() or 'download' in txt.lower() or 'pdf' in txt.lower():
                print('INLINE', i, txt[:1000])
    print('done')
finally:
    d.quit()
