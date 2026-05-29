from getpass import getpass

from questionary import confirm, text
from requests import HTTPError

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
    """Mostra em qual database os dados serão inseridos e pede confirmação.

    Recusar permite trocar o destino colando outra URL/ID. Retorna o ID validado.
    """
    db_id = store.get_database_id()

    while True:
        if not db_id:
            raw = text("Cole o ID ou URL do database do Notion:").ask()
            if raw is None:
                raise KeyboardInterrupt
            try:
                db_id = extract_db_id_from_input(raw)
            except ValueError as e:
                print(f"Falhou: {e}. Tente novamente.")
                db_id = None
                continue

        try:
            db = client.get_database(db_id)
        except HTTPError:
            print("Database não encontrado ou sem acesso.")
            store.delete_database_id()
            db_id = None
            continue

        answer = confirm(
            f"Esses dados serão adicionados em '{extract_db_title(db)}' no Notion. Tem certeza?",
            default=True,
        ).ask()
        if answer is None:
            raise KeyboardInterrupt
        if answer:
            store.set_database_id(db_id)
            return db_id

        store.delete_database_id()
        db_id = None


__all__ = [
    "CredentialStore",
    "NotionClient",
    "connect_to_notion",
    "pick_database",
]
