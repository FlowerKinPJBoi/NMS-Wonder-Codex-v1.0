from __future__ import annotations

import re
from typing import Any

# Index 0 is intentionally None so the tuple index equals the displayed galaxy number.
GALAXY_NAMES: tuple[str | None, ...] = (
    None,
    "Euclid",
    "Hilbert Dimension",
    "Calypso",
    "Hesperius Dimension",
    "Hyades",
    "Ickjamatew",
    "Budullangr",
    "Kikolgallr",
    "Eltiensleen",
    "Eissentam",
    "Elkupalos",
    "Aptarkaba",
    "Ontiniangp",
    "Odiwagiri",
    "Ogtialabi",
    "Muhacksonto",
    "Hitonskyer",
    "Rerasmutul",
    "Isdoraijung",
    "Doctinawyra",
    "Loychazinq",
    "Zukasizawa",
    "Ekwathore",
    "Yeberhahne",
    "Twerbetek",
    "Sivarates",
    "Eajerandal",
    "Aldukesci",
    "Wotyarogii",
    "Sudzerbal",
    "Maupenzhay",
    "Sugueziume",
    "Brogoweldian",
    "Ehbogdenbu",
    "Ijsenufryos",
    "Nipikulha",
    "Autsurabin",
    "Lusontrygiamh",
    "Rewmanawa",
    "Ethiophodhe",
    "Urastrykle",
    "Xobeurindj",
    "Oniijialdu",
    "Wucetosucc",
    "Ebyeloofdud",
    "Odyavanta",
    "Milekistri",
    "Waferganh",
    "Agnusopwit",
    "Teyaypilny",
    "Zalienkosm",
    "Ladgudiraf",
    "Mushonponte",
    "Amsentisz",
    "Fladiselm",
    "Laanawemb",
    "Ilkerloor",
    "Davanossi",
    "Ploehrliou",
    "Corpinyaya",
    "Leckandmeram",
    "Quulngais",
    "Nokokipsechl",
    "Rinblodesa",
    "Loydporpen",
    "Ibtrevskip",
    "Elkowaldb",
    "Heholhofsko",
    "Yebrilowisod",
    "Husalvangewi",
    "Ovna'uesed",
    "Bahibusey",
    "Nuybeliaure",
    "Doshawchuc",
    "Ruckinarkh",
    "Thorettac",
    "Nuponoparau",
    "Moglaschil",
    "Uiweupose",
    "Nasmilete",
    "Ekdaluskin",
    "Hakapanasy",
    "Dimonimba",
    "Cajaccari",
    "Olonerovo",
    "Umlanswick",
    "Henayliszm",
    "Utzenmate",
    "Umirpaiya",
    "Paholiang",
    "Iaereznika",
    "Yudukagath",
    "Boealalosnj",
    "Yaevarcko",
    "Coellosipp",
    "Wayndohalou",
    "Smoduraykl",
    "Apmaneessu",
    "Hicanpaav",
    "Akvasanta",
    "Tuychelisaor",
    "Rivskimbe",
    "Daksanquix",
    "Kissonlin",
    "Aediabiel",
    "Ulosaginyik",
    "Roclaytonycar",
    "Kichiaroa",
    "Irceauffey",
    "Nudquathsenfe",
    "Getaizakaal",
    "Hansolmien",
    "Bloytisagra",
    "Ladsenlay",
    "Luyugoslasr",
    "Ubredhatk",
    "Cidoniana",
    "Jasinessa",
    "Torweierf",
    "Saffneckm",
    "Thnistner",
    "Dotusingg",
    "Luleukous",
    "Jelmandan",
    "Otimanaso",
    "Enjaxusanto",
    "Sezviktorew",
    "Zikehpm",
    "Bephembah",
    "Broomerrai",
    "Meximicka",
    "Venessika",
    "Gaiteseling",
    "Zosakasiro",
    "Drajayanes",
    "Ooibekuar",
    "Urckiansi",
    "Dozivadido",
    "Emiekereks",
    "Meykinunukur",
    "Kimycuristh",
    "Roansfien",
    "Isgarmeso",
    "Daitibeli",
    "Gucuttarik",
    "Enlaythie",
    "Drewweste",
    "Akbulkabi",
    "Homskiw",
    "Zavainlani",
    "Jewijkmas",
    "Itlhotagra",
    "Podalicess",
    "Hiviusauer",
    "Halsebenk",
    "Puikitoac",
    "Gaybakuaria",
    "Grbodubhe",
    "Rycempler",
    "Indjalala",
    "Fontenikk",
    "Pasycihelwhee",
    "Ikbaksmit",
    "Telicianses",
    "Oyleyzhan",
    "Uagerosat",
    "Impoxectin",
    "Twoodmand",
    "Hilfsesorbs",
    "Ezdaranit",
    "Wiensanshe",
    "Ewheelonc",
    "Litzmantufa",
    "Emarmatosi",
    "Mufimbomacvi",
    "Wongquarum",
    "Hapirajua",
    "Igbinduina",
    "Wepaitvas",
    "Sthatigudi",
    "Yekathsebehn",
    "Ebedeagurst",
    "Nolisonia",
    "Ulexovitab",
    "Iodhinxois",
    "Irroswitzs",
    "Bifredait",
    "Beiraghedwe",
    "Yeonatlak",
    "Cugnatachh",
    "Nozoryenki",
    "Ebralduri",
    "Evcickcandj",
    "Ziybosswin",
    "Heperclait",
    "Sugiuniam",
    "Aaseertush",
    "Uglyestemaa",
    "Horeroedsh",
    "Drundemiso",
    "Ityanianat",
    "Purneyrine",
    "Dokiessmat",
    "Nupiacheh",
    "Dihewsonj",
    "Rudrailhik",
    "Tweretnort",
    "Snatreetze",
    "Iwundaracos",
    "Digarlewena",
    "Erquagsta",
    "Logovoloin",
    "Boyaghosganh",
    "Kuolungau",
    "Pehneldept",
    "Yevettiiqidcon",
    "Sahliacabru",
    "Noggalterpor",
    "Chmageaki",
    "Veticueca",
    "Vittesbursul",
    "Nootanore",
    "Innebdjerah",
    "Kisvarcini",
    "Cuzcogipper",
    "Pamanhermonsu",
    "Brotoghek",
    "Mibittara",
    "Huruahili",
    "Raldwicarn",
    "Ezdartlic",
    "Badesclema",
    "Isenkeyan",
    "Iadoitesu",
    "Yagrovoisi",
    "Ewcomechio",
    "Inunnunnoda",
    "Dischiutun",
    "Yuwarugha",
    "Ialmendra",
    "Reponudrle",
    "Rinjanagrbo",
    "Zeziceloh",
    "Oeileutasc",
    "Zicniijinis",
    "Dugnowarilda",
    "Neuxoisan",
    "Ilmenhorn",
    "Rukwatsuku",
    "Nepitzaspru",
    "Chcehoemig",
    "Haffneyrin",
    "Uliciawai",
    "Tuhgrespod",
    "Iousongola",
    "Odyalutai",
)

_UA_HEX = re.compile(r"^[0-9A-F]+$")
_MAX_UA = 1 << 56


def normalize_ua(value: Any) -> str | None:
    """Return the low 56-bit Universal Address as exactly 14 uppercase hex digits."""
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        if isinstance(value, int):
            number = value
        else:
            text = str(value).strip()
            if not text:
                return None
            if text.lower().startswith("0x"):
                number = int(text, 16)
            elif text.isdigit():
                # Save exports sometimes serialize UA as a decimal integer.
                number = int(text, 10)
            else:
                hex_text = text.upper()
                if not _UA_HEX.fullmatch(hex_text):
                    return None
                number = int(hex_text, 16)
    except (TypeError, ValueError):
        return None

    if number < 0 or number >= _MAX_UA:
        return None
    return f"{number:014X}"


def decode_universal_address(value: Any) -> dict[str, Any] | None:
    """Decode a No Man's Sky Universal Address into galaxy + 12 portal glyph values.

    Confirmed format:
        P SSS RR YY ZZZ XXX

    Portal address:
        P SSS YY ZZZ XXX
    """
    ua_hex = normalize_ua(value)
    if not ua_hex:
        return None

    planet_hex = ua_hex[0:1]
    system_hex = ua_hex[1:4]
    reality_hex = ua_hex[4:6]
    y_hex = ua_hex[6:8]
    z_hex = ua_hex[8:11]
    x_hex = ua_hex[11:14]

    portal_hex = f"{planet_hex}{system_hex}{y_hex}{z_hex}{x_hex}"
    reality_index = int(reality_hex, 16)
    galaxy_number = reality_index + 1

    if not (1 <= galaxy_number <= 256):
        return None

    return {
        "ua_normalized": ua_hex,
        "portal_glyphs": portal_hex,
        "portal_hex": portal_hex,
        "planet_index": int(planet_hex, 16),
        "solar_system_index": int(system_hex, 16),
        "reality_index": reality_index,
        "galaxy_number": galaxy_number,
        "galaxy_name": GALAXY_NAMES[galaxy_number],
        "voxel_y_encoded": int(y_hex, 16),
        "voxel_z_encoded": int(z_hex, 16),
        "voxel_x_encoded": int(x_hex, 16),
        "location_derivation_method": "ua_confirmed_v1",
    }


def effective_location(
    *,
    ua: Any,
    galaxy_number: int | None,
    galaxy_name: str,
    portal_glyphs: str,
    location_status: str,
) -> dict[str, Any]:
    """Return curated location data when complete, otherwise a confirmed UA-derived route."""
    stored_glyphs = re.sub(r"[^0-9A-F]", "", (portal_glyphs or "").upper())[:12]
    stored_number = galaxy_number if galaxy_number and 1 <= galaxy_number <= 256 else None
    stored_complete = bool(stored_number and len(stored_glyphs) == 12)

    decoded = decode_universal_address(ua)

    if stored_complete:
        effective_number = stored_number
        effective_name = galaxy_name or GALAXY_NAMES[stored_number]
        effective_glyphs = stored_glyphs
        source = "verified" if location_status == "verified" else "catalog"
        derived = False
        conflict = bool(
            decoded
            and (
                decoded["galaxy_number"] != effective_number
                or decoded["portal_glyphs"] != effective_glyphs
            )
        )
    elif decoded:
        effective_number = decoded["galaxy_number"]
        effective_name = decoded["galaxy_name"] or ""
        effective_glyphs = decoded["portal_glyphs"]
        source = decoded["location_derivation_method"]
        derived = True
        conflict = bool(
            (stored_number and stored_number != effective_number)
            or (stored_glyphs and stored_glyphs != effective_glyphs)
        )
    else:
        effective_number = stored_number
        effective_name = galaxy_name or (GALAXY_NAMES[stored_number] if stored_number else "")
        effective_glyphs = stored_glyphs
        source = "catalog" if (stored_number or stored_glyphs) else ""
        derived = False
        conflict = False

    complete = bool(effective_number and len(effective_glyphs) == 12)
    verified = bool(location_status == "verified" and stored_complete)

    if verified:
        travel_status = "verified"
    elif location_status == "disputed":
        travel_status = "disputed"
    elif location_status == "pending":
        travel_status = "pending"
    elif derived and complete:
        travel_status = "derived"
    else:
        travel_status = "unverified"

    return {
        "galaxy_number": effective_number,
        "galaxy_name": effective_name,
        "portal_glyphs": effective_glyphs,
        "has_location": verified,
        "has_travel_address": complete,
        "travel_status": travel_status,
        "location_source": source,
        "location_is_derived": derived,
        "location_conflict": conflict,
        "ua_decoded": decoded,
    }
