# Automação Web com Python

Este projeto serve como base para coleta de dados de páginas web e salvar o resultado em arquivo local.

A URL alvo desta automação é:

https://reservas.kartodromogranjaviana.com.br/reservaonline/

A aba “Minhas Corridas” normalmente exige login, então o fluxo ideal é:

1. abrir o site no navegador;
2. autenticar-se com a conta correta;
3. localizar o cookie de sessão no navegador;
4. passar esse cookie para o script via parâmetro `--cookie`.

## Estrutura

- `main.py` — ponto de entrada da aplicação
- `src/scraper.py` — lógica de download, extração e gravação dos dados
- `data/` — arquivos gerados pela automação
- `requirements.txt` — dependências do projeto
- `tests/` — testes automatizados

## Como usar

1. Crie um ambiente virtual:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Execute o script sem autenticação (quando a página for pública):

   ```bash
   python main.py --url https://reservas.kartodromogranjaviana.com.br/reservaonline/ --output data/minhas_corridas.txt
   ```

4. Execute com cookie de sessão para páginas autenticadas:

   ```bash
   python main.py --url https://reservas.kartodromogranjaviana.com.br/reservaonline/ --output data/minhas_corridas.txt --cookie "sessionid=SEU_COOKIE; csrftoken=SEU_CSRF"
   ```

5. Salve o HTML bruto:

   ```bash
   python main.py --url https://reservas.kartodromogranjaviana.com.br/reservaonline/ --output data/minhas_corridas.html --raw
   ```

## Como obter o cookie

No navegador:

- abra a página após fazer login;
- abra DevTools;
- vá em Application / Storage / Cookies;
- copie o valor do cookie de sessão do domínio da reserva;
- passe esse valor no parâmetro `--cookie`.

## Observações

- O script usa `requests` para acessar a página.
- O conteúdo pode ser salvo como texto limpo ou como HTML bruto.
- Para páginas com conteúdo dinâmico em JavaScript, o próximo passo pode ser usar Selenium ou Playwright.
