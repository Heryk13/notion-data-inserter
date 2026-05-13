from getpass import getpass

import questionary
import requests

from .credential_store import CredentialStore
from .notion_client import (
    NotionClient,
    extract_db_id_from_input,
    extract_db_title,
)


def connect_to_notion(store: CredentialStore) -> NotionClient:
    """Pega a API key (do keyring ou do usuário), valida, e devolve um NotionClient pronto."""
    while True:
        api_key = store.get_api_key()
        if not api_key:
            print("Notion credential não encontrada.")
            api_key = getpass("Insira a API-KEY do Notion: ").strip()
            store.set_api_key(api_key)

        client = NotionClient(api_key)
        if client.is_valid():
            print("Credential Notion validada ✓")
            return client

        print("Credential inválida. Tente novamente.")
        store.delete_api_key()


def pick_database(client: NotionClient, store: CredentialStore) -> str:
    """Confirma o database_id salvo ou pede um novo. Retorna o ID validado."""
    stored_id = store.get_database_id()

    if stored_id:
        try:
            db = client.get_database(stored_id)
            if questionary.confirm(
                f"Usar o database '{extract_db_title(db)}'?", default=True
            ).ask():
                return stored_id
        except requests.HTTPError:
            print("Database salvo não encontrado ou sem acesso.")
        store.delete_database_id()

    while True:
        raw = questionary.text("Cole o ID ou URL do database do Notion:").ask()
        if raw is None:
            raise KeyboardInterrupt
        try:
            db_id = extract_db_id_from_input(raw)
            db = client.get_database(db_id)
            print(f"Database encontrado: {extract_db_title(db)}")
            store.set_database_id(db_id)
            return db_id
        except (ValueError, requests.HTTPError) as e:
            print(f"Falhou: {e}. Tente novamente.")


__all__ = [
    "CredentialStore",
    "NotionClient",
    "connect_to_notion",
    "pick_database",
]
