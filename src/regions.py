from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class Region:
    code: str
    name_ru: str
    short: str
    center: str
    is_city: bool
    iso: str
    krisha_oblast: str
    krisha_center: str
    aliases: tuple[str, ...] = field(default=())


REGIONS: list[Region] = [
    Region("astana", "город Астана", "Астана", "Астана", True, "KZ-71",
           "astana", "astana",
           ("астана", "нур султан", "нурсултан", "nur sultan", "astana", "целиноград")),
    Region("almaty", "город Алматы", "Алматы", "Алматы", True, "KZ-75",
           "almaty", "almaty",
           ("алматы", "алма ата", "almaty", "almatycity")),
    Region("shymkent", "город Шымкент", "Шымкент", "Шымкент", True, "KZ-79",
           "shymkent", "shymkent",
           ("шымкент", "чимкент", "shymkent")),

    Region("abay", "область Абай", "Абай", "Семей", False, "KZ-10",
           "abay-oblast", "semej",
           ("абай", "абайская", "область абай", "abai", "abay", "семей", "семипалатинск")),
    Region("akmola", "Акмолинская область", "Акмолинская", "Кокшетау", False, "KZ-11",
           "akmolinskaja-oblast", "kokshetau",
           ("акмолинская", "акмола", "akmola", "кокшетау", "кокчетав")),
    Region("aktobe", "Актюбинская область", "Актюбинская", "Актобе", False, "KZ-15",
           "aktjubinskaja-oblast", "aktobe",
           ("актюбинская", "актобе", "aktobe", "aktyubinsk")),
    Region("almatyobl", "Алматинская область", "Алматинская", "Конаев", False, "KZ-19",
           "almatinskaja-oblast", "konaev",
           ("алматинская", "конаев", "капшагай", "almatyregion")),
    Region("atyrau", "Атырауская область", "Атырауская", "Атырау", False, "KZ-23",
           "atyrauskaja-oblast", "atyrau",
           ("атырауская", "атырау", "atyrau", "гурьев", "гурьевская")),
    Region("vko", "Восточно-Казахстанская область", "Восточно-Казахстанская", "Усть-Каменогорск", False, "KZ-63",
           "vostochno-kazahstanskaja-oblast", "ust-kamenogorsk",
           ("вко", "восточно казахстанская", "восточноказахстанская", "east kazakhstan",
            "усть каменогорск", "оскемен")),
    Region("zhambyl", "Жамбылская область", "Жамбылская", "Тараз", False, "KZ-31",
           "zhambylskaja-oblast", "taraz",
           ("жамбылская", "джамбулская", "zhambyl", "jambyl", "тараз", "джамбул")),
    Region("zhetisu", "область Жетісу", "Жетісу", "Талдыкорган", False, "KZ-33",
           "jetisyskaya-oblast", "taldykorgan",
           ("жетісу", "жетысу", "жетысуская", "область жетісу", "zhetysu", "jetisu", "талдыкорган")),
    Region("zko", "Западно-Казахстанская область", "Западно-Казахстанская", "Уральск", False, "KZ-27",
           "zapadno-kazahstanskaja-oblast", "uralsk",
           ("зко", "западно казахстанская", "западноказахстанская", "west kazakhstan", "уральск", "орал")),
    Region("karagandy", "Карагандинская область", "Карагандинская", "Караганда", False, "KZ-35",
           "karagandinskaja-oblast", "karaganda",
           ("карагандинская", "караганда", "karaganda", "karagandy")),
    Region("kostanay", "Костанайская область", "Костанайская", "Костанай", False, "KZ-39",
           "kostanajskaja-oblast", "kostanaj",
           ("костанайская", "кустанайская", "костанай", "кустанай", "kostanay")),
    Region("kyzylorda", "Кызылординская область", "Кызылординская", "Кызылорда", False, "KZ-43",
           "kyzylordinskaja-oblast", "kyzylorda",
           ("кызылординская", "кзылординская", "кызылорда", "kyzylorda", "qyzylorda")),
    Region("mangystau", "Мангистауская область", "Мангистауская", "Актау", False, "KZ-47",
           "mangistauskaja-oblast", "aktau",
           ("мангистауская", "мангышлакская", "мангистау", "mangystau", "актау", "шевченко")),
    Region("pavlodar", "Павлодарская область", "Павлодарская", "Павлодар", False, "KZ-55",
           "pavlodarskaja-oblast", "pavlodar",
           ("павлодарская", "павлодар", "pavlodar")),
    Region("sko", "Северо-Казахстанская область", "Северо-Казахстанская", "Петропавловск", False, "KZ-59",
           "severo-kazahstanskaja-oblast", "petropavlovsk",
           ("ско", "северо казахстанская", "североказахстанская", "north kazakhstan",
            "петропавловск", "петропавл")),
    Region("turkestan", "Туркестанская область", "Туркестанская", "Туркестан", False, "KZ-61",
           "juzhno-kazahstanskaja-oblast", "turkestan",
           ("туркестанская", "туркестан", "turkistan", "turkestan",
            "юко", "южно казахстанская", "южноказахстанская", "south kazakhstan")),
    Region("ulytau", "область Ұлытау", "Ұлытау", "Жезказган", False, "KZ-62",
           "ulitayskay-oblast", "zhezkazgan",
           ("ұлытау", "улытау", "улытауская", "область ұлытау", "ulytau", "жезказган", "жезқазған")),
]


SPLITS: dict[str, tuple[str, int]] = {
    "abay":     ("vko",        2022),
    "zhetisu":  ("almatyobl",  2022),
    "ulytau":   ("karagandy",  2022),
    "shymkent": ("turkestan",  2018),
}


def code_as_of(code: str, year: int) -> str:
    while code in SPLITS and year < SPLITS[code][1]:
        code = SPLITS[code][0]
    return code


_KZ_FOLD = str.maketrans({
    "ә": "а", "ғ": "г", "қ": "к", "ң": "н", "ө": "о",
    "ұ": "у", "ү": "у", "һ": "х", "і": "и", "ё": "е",
})

_STOPWORDS = {
    "область", "обл", "области", "областей", "облысы", "oblast", "oblysy",
    "region", "regionu", "г", "гор", "город", "қаласы", "каласы", "city", "the",
}


def normalize(s: str) -> str:
    s = s.strip().lower().translate(_KZ_FOLD)
    s = "".join(ch if ch.isalnum() else " " for ch in s)
    words = [w for w in s.split() if w not in _STOPWORDS]
    return "".join(words)


BY_CODE: dict[str, Region] = {r.code: r for r in REGIONS}

_LOOKUP: dict[str, str] = {}


def _register(key: str, code: str) -> None:
    k = normalize(key)
    if not k:
        return
    if k in _LOOKUP and _LOOKUP[k] != code:
        raise ValueError(
            f"Конфликт алиасов: {k!r} claimed by {_LOOKUP[k]!r} and {code!r}"
        )
    _LOOKUP[k] = code


for _r in REGIONS:
    for _key in (_r.code, _r.name_ru, _r.short, _r.iso,
                 _r.krisha_oblast, _r.krisha_center, *_r.aliases):
        _register(_key, _r.code)
    if normalize(_r.center) not in _LOOKUP:
        _register(_r.center, _r.code)


def to_code(name: str) -> Optional[str]:
    if name is None:
        return None
    return _LOOKUP.get(normalize(str(name)))


def require_code(name: str) -> str:
    code = to_code(name)
    if code is None:
        raise KeyError(
            f"Неизвестный регион: {name!r} (нормализовано: {normalize(str(name))!r}). "
            f"Добавь написание в aliases соответствующего региона в regions.py"
        )
    return code


def to_dataframe():
    import pandas as pd
    return pd.DataFrame([asdict(r) for r in REGIONS]).set_index("code")


if __name__ == "__main__":
    assert len(REGIONS) == 20, f"Регионов должно быть 20, а не {len(REGIONS)}"
    assert len(BY_CODE) == 20, "Коды регионов не уникальны"
    assert sum(r.is_city for r in REGIONS) == 3, "Городов респ. значения должно быть 3"
    assert len({r.krisha_oblast for r in REGIONS}) == 20, "Слаги Krisha не уникальны"

    cases = [
        ("СКО", "sko"),
        ("Северо-Казахстанская область", "sko"),
        ("  северо-казахстанская  ", "sko"),
        ("Петропавловск", "sko"),
        ("severo-kazahstanskaja-oblast", "sko"),
        ("Ұлытау", "ulytau"),
        ("Улытауская область", "ulytau"),
        ("ulitayskay-oblast", "ulytau"),
        ("Туркестанская", "turkestan"),
        ("juzhno-kazahstanskaja-oblast", "turkestan"),
        ("ЮКО", "turkestan"),
        ("г.Алматы", "almaty"),
        ("Алматинская область", "almatyobl"),
        ("Нур-Султан", "astana"),
        ("KZ-59", "sko"),
    ]
    for raw, expected in cases:
        got = to_code(raw)
        assert got == expected, f"{raw!r}: ожидали {expected!r}, получили {got!r}"

    assert code_as_of("abay", 2026) == "abay"
    assert code_as_of("abay", 2019) == "vko"
    assert code_as_of("shymkent", 2015) == "turkestan"
    assert code_as_of("sko", 2010) == "sko"

    try:
        require_code("Гвинея-Бисау")
    except KeyError:
        pass
    else:
        raise AssertionError("require_code не упал на неизвестном регионе")

    print(f"OK — {len(REGIONS)} регионов, {len(_LOOKUP)} написаний в индексе\n")
    print(f"{'code':<11} {'ISO':<7} {'регион':<26} {'центр':<18} krisha")
    print("-" * 92)
    for r in REGIONS:
        print(f"{r.code:<11} {r.iso:<7} {r.short:<26} {r.center:<18} {r.krisha_oblast}")
