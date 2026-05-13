import keyring
from keyring.errors import PasswordDeleteError


class CredentialStore:
    """Wrapper de keyring para as credenciais do Notion (api_key + database_id)."""

    API_KEY_NAME = "api_key"
    DB_KEY_NAME = "database_id"

    def __init__(self, tool_name: str = "notion_tool"):
        self.tool_name = tool_name

    def _get(self, key: str) -> str | None:
        return keyring.get_password(self.tool_name, key)

    def _set(self, key: str, value: str) -> None:
        keyring.set_password(self.tool_name, key, value)

    def _delete(self, key: str) -> None:
        try:
            keyring.delete_password(self.tool_name, key)
        except PasswordDeleteError:
            pass

    def get_api_key(self) -> str | None:
        return self._get(self.API_KEY_NAME)

    def set_api_key(self, api_key: str) -> None:
        self._set(self.API_KEY_NAME, api_key)

    def delete_api_key(self) -> None:
        self._delete(self.API_KEY_NAME)

    def get_database_id(self) -> str | None:
        return self._get(self.DB_KEY_NAME)

    def set_database_id(self, database_id: str) -> None:
        self._set(self.DB_KEY_NAME, database_id)

    def delete_database_id(self) -> None:
        self._delete(self.DB_KEY_NAME)