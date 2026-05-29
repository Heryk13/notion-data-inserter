from json import load
from pathlib import Path
import sys
import questionary


def _resource_dir() -> Path:
    """Funciona tanto rodando como script quanto bundlado pelo PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).parent.parent / "data"

_DATA_FILE = _resource_dir() / "japan_regions.json"

with open(_DATA_FILE, encoding="utf-8") as f:
    _REGIONS = load(f)


_CITY_SUFFIXES = (
    "-shi", "-ku", "-cho", "-machi", "-mura",
    "-son", "-gun", "-to", "-ken", "-fu", "-do",
)


def normalize_for_notion(value: str) -> str:
    """
    Converte 'Nishio-shi' -> 'nishio', 'Aichi' -> 'aichi'.
    Para 'Aichi-gun Togo-cho' pega só o último componente: 'togo'.
    """
    last_part = value.strip().split()[-1].lower()
    for suffix in _CITY_SUFFIXES:
        if last_part.endswith(suffix):
            return last_part[: -len(suffix)]
    return last_part


def _clean(value) -> str:
    """Texto cru higienizado; '' para None, vazio ou NaN."""
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def _key(value) -> str:
    """Chave de busca canônica (minúscula, sem sufixo); '' não casa com nada."""
    s = _clean(value)
    return normalize_for_notion(s) if s else ""


def _build_lookups() -> tuple[dict, dict]:
    """Indexa japan_regions.json por chave canônica (aceita romaji ou kanji)."""
    pref_lookup: dict[str, str] = {}
    city_lookup: dict[str, dict[str, str]] = {}
    for pref_romaji, data in _REGIONS.items():
        for name in (pref_romaji, data.get("kanji")):
            if name:
                pref_lookup[_key(name)] = pref_romaji
        cmap: dict[str, str] = {}
        for c in data.get("cities", []):
            for name in (c["romaji"], c.get("kanji")):
                if name:
                    cmap.setdefault(_key(name), c["romaji"])
        city_lookup[pref_romaji] = cmap
    return pref_lookup, city_lookup


_PREF_LOOKUP, _CITY_LOOKUP = _build_lookups()


def verify_location(state, city) -> tuple[str, str] | None:
    """
    Confere se (state, city) batem com japan_regions.json.

    Aceita romaji ('Aichi', 'Nishio-shi'), kanji ('愛知県') ou forma sem sufixo
    ('aichi', 'nishio'). Retorna (prefeitura, cidade) canônicas em romaji ou
    None se a cidade não pertence à prefeitura informada.
    """
    pref = _PREF_LOOKUP.get(_key(state))
    if not pref:
        return None
    canon_city = _CITY_LOOKUP[pref].get(_key(city))
    return (pref, canon_city) if canon_city else None


def _build_choice(romaji: str, kanji: str, include_kanji: bool) -> questionary.Choice:
    label = f"{romaji} ({kanji})" if include_kanji else romaji
    return questionary.Choice(title=label, value=romaji)


def pick_japan_location(include_kanji: bool = True) -> tuple[str, str]:
    """
    Pergunta ao usuário prefeitura e cidade do Japão.

    Returns:
        Tupla (prefeitura, cidade) com nomes em romaji.

    Raises:
        KeyboardInterrupt: se o usuário cancelar (Ctrl+C).
    """
    pref_choices = [
        _build_choice(romaji, _REGIONS[romaji]["kanji"], include_kanji)
        for romaji in sorted(_REGIONS.keys())
    ]
    prefecture = questionary.select(
        "De qual prefeitura do Japão são esses dados?",
        choices=pref_choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()
    if prefecture is None:
        raise KeyboardInterrupt

    cities = _REGIONS[prefecture]["cities"]
    city_choices = [
        _build_choice(c["romaji"], c["kanji"], include_kanji) for c in cities
    ]
    city_choices.append(questionary.Choice(title="Outra (digitar)", value="__OTHER__"))

    city = questionary.select(
        f"Qual cidade de {prefecture}? ({len(cities)} opções)",
        choices=city_choices,
        use_search_filter=True,
        use_jk_keys=False,
    ).ask()
    if city is None:
        raise KeyboardInterrupt

    if city == "__OTHER__":
        city = questionary.text(
            f"Digite o nome da cidade em {prefecture}:",
            validate=lambda x: len(x.strip()) > 0 or "Não pode ficar vazio",
        ).ask()
        if city is None:
            raise KeyboardInterrupt
        city = city.strip()

    return prefecture, city


def resolve_locations(pairs, include_kanji: bool = True) -> list[tuple[str, str]]:
    """
    Verifica cada par (state, city) contra japan_regions.json e devolve os
    valores normalizados prontos pro Notion, na mesma ordem da entrada.

    Pares não reconhecidos caem no picker interativo. Respostas (e verificações)
    são cacheadas por valor bruto, então valores repetidos não perguntam de novo.
    """
    cache: dict[tuple[str, str], tuple[str, str]] = {}
    results: list[tuple[str, str]] = []

    for state, city in pairs:
        key = (_key(state), _key(city))
        if key not in cache:
            match = verify_location(state, city)
            if match is None:
                print(
                    f"Localização não reconhecida (estado='{_clean(state)}', "
                    f"cidade='{_clean(city)}'). Selecione manualmente:"
                )
                match = pick_japan_location(include_kanji=include_kanji)
            cache[key] = (normalize_for_notion(match[0]), normalize_for_notion(match[1]))
        results.append(cache[key])

    return results
