from __future__ import annotations

import argparse
import os

from src.result_downloader import download_new_results


def _validate_cli_paths(output_dir: str, state_file: str) -> None:
    placeholders = ("seu_usuario", "seu_user", "example", "your_user", "usuario_exemplo")
    for name, value in (("output_dir", output_dir), ("state_file", state_file)):
        lowered = str(value).lower()
        if any(marker in lowered for marker in placeholders):
            raise ValueError(
                f"O valor de {name} parece ser um caminho de exemplo: '{value}'. "
                "Use o diretório real do seu usuário, por exemplo: "
                "'C:\\Users\\mbern\\OneDrive\\kart'."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baixa novos arquivos de resultados da aba Minhas Corridas."
    )
    parser.add_argument(
        "--email",
        default=os.getenv("KGV_EMAIL"),
        help="E-mail usado para autenticação no site.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("KGV_PASSWORD"),
        help="Senha usada para autenticação no site.",
    )
    parser.add_argument(
        "--output-dir",
        default=r"C:\Users\mbern\OneDrive\kart",
        help="Diretório local para os arquivos baixados.",
    )
    parser.add_argument(
        "--state-file",
        default=r"C:\Users\mbern\OneDrive\kart\.downloaded_results.json",
        help="Arquivo usado para registrar quais resultados já foram baixados.",
    )
    parser.add_argument(
        "--login-url",
        default="https://reservas.kartodromogranjaviana.com.br/reservaonline/",
        help="URL do site alvo.",
    )
    parser.add_argument(
        "--auth-token",
        default=os.getenv("KGV_AUTH_TOKEN"),
        help="Token JWT capturado do navegador para tentar a sessão real sem headless.",
    )
    parser.add_argument(
        "--cookie-string",
        default=os.getenv("KGV_COOKIE_STRING"),
        help="Cookie string do navegador para autenticação direta.",
    )
    parser.add_argument(
        "--customer-id",
        default=os.getenv("KGV_CUSTOMER_ID"),
        help="ID do cliente autenticado no navegador.",
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error(
            "Informe --email e --password ou defina as variáveis de ambiente KGV_EMAIL e KGV_PASSWORD."
        )

    try:
        _validate_cli_paths(args.output_dir, args.state_file)
    except ValueError as exc:
        parser.error(str(exc))

    downloaded = download_new_results(
        email=args.email,
        password=args.password,
        output_dir=args.output_dir,
        state_file=args.state_file,
        login_url=args.login_url,
        auth_token=args.auth_token,
        browser_cookie_string=args.cookie_string,
        customer_id=args.customer_id,
    )

    if not downloaded:
        print("Nenhum novo resultado encontrado para baixar.")
        return

    print(f"Foram baixados {len(downloaded)} novo(s) resultado(s):")
    for item in downloaded:
        print(f"- {item}")


if __name__ == "__main__":
    main()
