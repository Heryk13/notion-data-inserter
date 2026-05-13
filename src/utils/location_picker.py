import json
from pathlib import Path

import questionary


_DATA_FILE = Path(__file__).parent.parent / "data" / "japan_regions.json"

with open(_DATA_FILE, encoding="utf-8") as f:
    _REGIONS = json.load(f)


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
