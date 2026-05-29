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


def _bad_column(state, city) -> str:
    """Qual coluna está incorreta: 'State', 'City' (ou '' se a localização é válida)."""
    pref = _PREF_LOOKUP.get(_key(state))
    if not pref:
        return "State"
    if _CITY_LOOKUP[pref].get(_key(city)) is None:
        return "City"
    return ""


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


def _correct_location(name, state, city, bad, include_kanji: bool) -> tuple[str, str]:
    """Pergunta como corrigir uma linha com localização inválida."""
    label = _clean(name) or "(sem nome)"
    choice = questionary.select(
        f"Corrigir '{label}' (coluna {bad} inválida):",
        choices=[
            questionary.Choice("Escolher prefeitura e cidade", value="pick"),
            questionary.Choice(
                f"Manter como está (State='{_clean(state)}', City='{_clean(city)}')",
                value="keep",
            ),
        ],
    ).ask()
    if choice is None:
        raise KeyboardInterrupt
    if choice == "pick":
        pref, city_romaji = pick_japan_location(include_kanji=include_kanji)
        return normalize_for_notion(pref), normalize_for_notion(city_romaji)
    return _key(state), _key(city)


def resolve_locations(rows, include_kanji: bool = True) -> list[tuple[str, str]]:
    """
    Verifica a localização de cada linha e devolve (state, city) normalizados,
    na mesma ordem. `rows` é uma lista de (nome, state, city).

    Linhas válidas são resolvidas automaticamente (com cache por valor). As
    inválidas são listadas com nome e coluna problemática, e corrigidas uma a uma.
    """
    cache: dict[tuple[str, str], tuple[str, str]] = {}
    results: list[tuple[str, str]] = [("", "")] * len(rows)
    problems: list[tuple[int, object, object, object, str]] = []

    for i, (name, state, city) in enumerate(rows):
        key = (_key(state), _key(city))
        if key in cache:
            results[i] = cache[key]
            continue
        match = verify_location(state, city)
        if match is None:
            problems.append((i, name, state, city, _bad_column(state, city)))
        else:
            cache[key] = (normalize_for_notion(match[0]), normalize_for_notion(match[1]))
            results[i] = cache[key]

    if problems:
        print(f"\n{len(problems)} linha(s) com localização incorreta:")
        for _, name, state, city, bad in problems:
            print(
                f"  - {_clean(name) or '(sem nome)'}: coluna {bad} inválida "
                f"(State='{_clean(state)}', City='{_clean(city)}')"
            )
        print()
        for i, name, state, city, bad in problems:
            results[i] = _correct_location(name, state, city, bad, include_kanji)

    return results
