import re

import pandas as pd
import requests


def extract_db_title(db: dict) -> str:
    parts = db.get("title", [])
    return "".join(p.get("plain_text", "") for p in parts) or "(sem título)"


def extract_db_id_from_input(raw: str) -> str:
    """Aceita URL do Notion ou ID puro. Retorna o ID limpo (32 hex chars)."""
    match = re.search(r"([0-9a-f]{32})", raw.strip().replace("-", ""), re.IGNORECASE)
    if not match:
        raise ValueError("ID do database inválido")
    return match.group(1)


def normalize_phone(phone) -> str:
    """Remove tudo que não é dígito para comparação robusta."""
    if phone is None or pd.isna(phone):
        return ""
    return re.sub(r"\D", "", str(phone))


def format_phone(phone) -> str:
    """Formata telefone pro Notion sem parênteses: '(056)-111-111' -> '056-111-111'."""
    return str(phone).strip().replace("(", "").replace(")", "")


def extract_property_value(page: dict, prop_name: str) -> str | None:
    """Extrai valor de uma propriedade independente do tipo."""
    prop = page.get("properties", {}).get(prop_name)
    if not prop:
        return None
    ptype = prop.get("type")
    if ptype == "phone_number":
        return prop.get("phone_number")
    if ptype == "rich_text":
        return "".join(rt.get("plain_text", "") for rt in prop.get("rich_text", [])) or None
    if ptype == "title":
        return "".join(t.get("plain_text", "") for t in prop.get("title", [])) or None
    return None


def _is_empty(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(value, str) and not value.strip()


def format_property(value, prop_type: str) -> dict | None:
    """Converte um valor Python no payload esperado pelo Notion para um dado tipo de propriedade."""
    if _is_empty(value):
        return None

    if prop_type == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return None
    if prop_type == "checkbox":
        return {"checkbox": bool(value)}

    s = str(value).strip()
    if prop_type == "title":
        return {"title": [{"text": {"content": s}}]}
    if prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": s}}]}
    if prop_type == "phone_number":
        return {"phone_number": format_phone(s)}
    if prop_type == "url":
        return {"url": s}
    if prop_type == "email":
        return {"email": s}
    if prop_type == "select":
        return {"select": {"name": s}}
    if prop_type == "multi_select":
        return {"multi_select": [{"name": s}]}
    return {"rich_text": [{"text": {"content": s}}]}


class NotionClient:
    """Cliente HTTP puro para a API do Notion. Não toca em keyring nem em prompts."""

    BASE_URL = "https://api.notion.com"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": self.NOTION_VERSION,
            "Content-Type": "application/json",
        })

    def is_valid(self) -> bool:
        try:
            resp = self.session.get(f"{self.BASE_URL}/v1/users/me", timeout=10)
        except requests.RequestException as e:
            print(f"Erro de rede: {e}")
            return False
        return resp.status_code == 200

    def get_database(self, database_id: str) -> dict:
        resp = self.session.get(f"{self.BASE_URL}/v1/databases/{database_id}", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def query_database(self, database_id: str) -> list[dict]:
        """Retorna TODAS as pages do database (lida com paginação)."""
        url = f"{self.BASE_URL}/v1/databases/{database_id}/query"
        pages: list[dict] = []
        payload: dict = {"page_size": 100}

        while True:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            pages.extend(data["results"])
            if not data.get("has_more"):
                break
            payload["start_cursor"] = data["next_cursor"]

        return pages

    def create_page(self, database_id: str, properties: dict) -> dict:
        payload = {"parent": {"database_id": database_id}, "properties": properties}
        resp = self.session.post(f"{self.BASE_URL}/v1/pages", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def filter_duplicates(
        self,
        df: pd.DataFrame,
        database_id: str,
        df_phone_col: str = "Phone Number",
        notion_phone_prop: str = "Phone",
    ) -> pd.DataFrame:
        """Remove do DataFrame as linhas cujo telefone já existe no Notion."""
        print("Buscando registros existentes no Notion...")
        pages = self.query_database(database_id)
        print(f"Registros no Notion: {len(pages)}")
        existing = {
            normalize_phone(extract_property_value(p, notion_phone_prop))
            for p in pages
        }
        existing.discard("")
        is_dup = df[df_phone_col].apply(lambda v: normalize_phone(v) in existing)
        new_rows = df[~is_dup].copy()
        print(f"Duplicados removidos: {is_dup.sum()}")
        print(f"Novos para importar: {len(new_rows)}")
        return new_rows

    def insert_rows(
        self,
        df: pd.DataFrame,
        database_id: str,
        column_mapping: dict[str, str],
        extra_properties: dict[str, object] | None = None,
    ) -> tuple[int, list[tuple]]:
        """Insere cada linha do DataFrame como uma nova page no database.

        column_mapping: nome da coluna do df -> nome da propriedade no Notion.
        extra_properties: propriedades constantes para aplicar em todas as linhas.
        """
        schema = self.get_database(database_id)["properties"]
        extras = extra_properties or {}

        success = 0
        failures: list[tuple] = []

        for idx, row in df.iterrows():
            properties: dict = {}
            for df_col, notion_prop in column_mapping.items():
                prop_def = schema.get(notion_prop)
                if not prop_def:
                    continue
                formatted = format_property(row[df_col], prop_def["type"])
                if formatted is not None:
                    properties[notion_prop] = formatted

            for notion_prop, value in extras.items():
                prop_def = schema.get(notion_prop)
                if not prop_def:
                    continue
                formatted = format_property(value, prop_def["type"])
                if formatted is not None:
                    properties[notion_prop] = formatted

            try:
                self.create_page(database_id, properties)
                success += 1
            except requests.HTTPError as e:
                failures.append((idx, str(e)))

        print(f"Inseridos: {success}")
        if failures:
            print(f"Falhas: {len(failures)}")
            for idx, err in failures[:5]:
                print(f"  linha {idx}: {err}")
            if len(failures) > 5:
                print(f"  ... e mais {len(failures) - 5}")

        return success, failures