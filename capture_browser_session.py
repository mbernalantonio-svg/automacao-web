from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    print("Abra o site autenticado e execute isto no console do navegador:")
    print()
    print("const payload = {")
    print("  token: localStorage.getItem('kgv_auth_token'),")
    print("  loginId: localStorage.getItem('login_id'),")
    print("  currentUser: localStorage.getItem('currentUser'),")
    print("  loginEmail: localStorage.getItem('login_email'),")
    print("  cookies: document.cookie,")
    print("  customerId: (() => {")
    print("    const raw = localStorage.getItem('currentUser');")
    print("    if (!raw) return null;")
    print("    try { return JSON.parse(raw).idcliente ?? JSON.parse(raw).id ?? null; } catch (e) { return null; }")
    print("  })(),")
    print("  url: location.href,")
    print("};")
    print("console.log(JSON.stringify(payload, null, 2));")
    print()
    print("Depois copie a saída e rode:")
    print("python main.py --email \"SEU_EMAIL\" --password \"SUA_SENHA\" --auth-token \"TOKEN\" --cookie-string \"COOKIE1=VALOR; COOKIE2=VALOR\" --customer-id \"455\"")
    print()
    print("Exemplo:")
    print("python main.py --email \"mbernalantonio@hotmail.com\" --password \"SUA_SENHA\" --auth-token \"eyJ...\" --cookie-string \"__obref=...; _ga=...\" --customer-id \"455\"")


if __name__ == "__main__":
    main()
