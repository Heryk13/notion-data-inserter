from pathlib import Path

from pandas import read_excel, DataFrame

from integrations import CredentialStore, connect_to_notion, pick_database
from utils import normalize_for_notion, pick_japan_location
from time import sleep

REQUIRED_COLUMNS = ["Phone Number", "Nome"]
COLUMN_MAPPING = {
    "Nome": "company name",
    "URL": "URL",
    "Phone Number": "Phone",
}


def clear_terminal() -> None:
    print("\033[H\033[J", end="")


def load_excel(file_path: Path) -> DataFrame | None:
    if not file_path.exists():
        print("arquivo não encontrado")
        return None

    df = read_excel(file_path)
    print(f"Total: {len(df)} linhas")
    print(f"removendo linhas sem {' e '.join(REQUIRED_COLUMNS)}")
    df = df.dropna(subset=REQUIRED_COLUMNS)
    print(f"Total de linhas validas: {len(df)} linhas")
    return df


def main() -> None:
    clear_terminal()
    print("=" * 10, " importador de dados pro notion ", "=" * 10)

    raw_path = input("arraste o arquivo excel aq -> ").strip().strip('"').strip("'")
    df = load_excel(Path(raw_path))
    if df is None or df.empty:
        return

    print("checando credencial do notion")
    store = CredentialStore()
    client = connect_to_notion(store)

    database_id = pick_database(client, store)

    print("checando dados duplicados")
    df = client.filter_duplicates(df, database_id)
    if df.empty:
        return

    prefecture, city = pick_japan_location()
    print("inserindo dados no notion")
    client.insert_rows(
        df,
        database_id,
        column_mapping=COLUMN_MAPPING,
        extra_properties={
            "state": normalize_for_notion(prefecture),
            "city": normalize_for_notion(city),
            "approaches": 0,
        },
    )
    sleep(5)


if __name__ == "__main__":
    main()
