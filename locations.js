(() => {
  'use strict';

  const GALAXY_NAMES = [
    null,
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
    "Odyalutai"
  ];

  function normalizeUa(value) {
    if (value === null || value === undefined || value === '') return '';
    let number;
    const text = String(value).trim();
    try {
      if (/^0x/i.test(text)) number = BigInt(text);
      else if (/^\d+$/.test(text)) number = BigInt(text);
      else if (/^[0-9a-f]+$/i.test(text)) number = BigInt(`0x${text}`);
      else return '';
    } catch {
      return '';
    }
    if (number < 0n || number >= (1n << 56n)) return '';
    return number.toString(16).toUpperCase().padStart(14, '0');
  }

  function decode(value) {
    const uaHex = normalizeUa(value);
    if (!uaHex) return null;

    const planetHex = uaHex.slice(0, 1);
    const systemHex = uaHex.slice(1, 4);
    const realityHex = uaHex.slice(4, 6);
    const yHex = uaHex.slice(6, 8);
    const zHex = uaHex.slice(8, 11);
    const xHex = uaHex.slice(11, 14);
    const portalGlyphs = `${planetHex}${systemHex}${yHex}${zHex}${xHex}`;
    const realityIndex = Number.parseInt(realityHex, 16);
    const galaxyNumber = realityIndex + 1;
    if (galaxyNumber < 1 || galaxyNumber > 256) return null;

    return {
      ua_normalized: uaHex,
      portal_glyphs: portalGlyphs,
      portal_hex: portalGlyphs,
      glyph_values: [...portalGlyphs],
      planet_index: Number.parseInt(planetHex, 16),
      solar_system_index: Number.parseInt(systemHex, 16),
      reality_index: realityIndex,
      galaxy_number: galaxyNumber,
      galaxy_name: GALAXY_NAMES[galaxyNumber] || '',
      voxel_y_encoded: Number.parseInt(yHex, 16),
      voxel_z_encoded: Number.parseInt(zHex, 16),
      voxel_x_encoded: Number.parseInt(xHex, 16),
      location_derivation_method: 'ua_confirmed_v1',
    };
  }

  function cleanGlyphs(value) {
    return String(value || '').toUpperCase().replace(/[^0-9A-F]/g, '').slice(0, 12);
  }

  function enrich(record) {
    const source = record || {};
    const storedNumber = Number(source.galaxy_number) || null;
    const storedGlyphs = cleanGlyphs(source.portal_glyphs);
    const storedComplete = Boolean(storedNumber >= 1 && storedNumber <= 256 && storedGlyphs.length === 12);
    const decoded = decode(source.ua);

    let galaxyNumber = storedNumber;
    let galaxyName = source.galaxy_name || (storedNumber ? GALAXY_NAMES[storedNumber] || '' : '');
    let portalGlyphs = storedGlyphs;
    let locationSource = storedComplete ? (source.location_status === 'verified' ? 'verified' : 'catalog') : '';
    let locationIsDerived = false;
    let locationConflict = false;

    if (!storedComplete && decoded) {
      galaxyNumber = decoded.galaxy_number;
      galaxyName = decoded.galaxy_name;
      portalGlyphs = decoded.portal_glyphs;
      locationSource = decoded.location_derivation_method;
      locationIsDerived = true;
      locationConflict = Boolean(
        (storedNumber && storedNumber !== galaxyNumber)
        || (storedGlyphs && storedGlyphs !== portalGlyphs)
      );
    } else if (storedComplete && decoded) {
      locationConflict = decoded.galaxy_number !== galaxyNumber || decoded.portal_glyphs !== portalGlyphs;
    }

    const hasTravelAddress = Boolean(galaxyNumber && portalGlyphs.length === 12);
    const hasLocation = Boolean(source.location_status === 'verified' && storedComplete);
    let travelStatus = source.travel_status || '';
    if (!travelStatus) {
      if (hasLocation) travelStatus = 'verified';
      else if (source.location_status === 'disputed') travelStatus = 'disputed';
      else if (source.location_status === 'pending') travelStatus = 'pending';
      else if (locationIsDerived && hasTravelAddress) travelStatus = 'derived';
      else travelStatus = 'unverified';
    }

    return {
      ...source,
      galaxy_number: galaxyNumber,
      galaxy_name: galaxyName,
      portal_glyphs: portalGlyphs,
      has_location: hasLocation,
      has_travel_address: hasTravelAddress,
      travel_status: travelStatus,
      location_source: source.location_source || locationSource,
      location_is_derived: source.location_is_derived ?? locationIsDerived,
      location_conflict: source.location_conflict ?? locationConflict,
      ua_normalized: source.ua_normalized || decoded?.ua_normalized || '',
      reality_index: source.reality_index ?? decoded?.reality_index ?? null,
      planet_index: source.planet_index ?? decoded?.planet_index ?? null,
      solar_system_index: source.solar_system_index ?? decoded?.solar_system_index ?? null,
      location_derivation_method: source.location_derivation_method || decoded?.location_derivation_method || '',
    };
  }

  window.WCLocation = {
    galaxyNames: GALAXY_NAMES,
    normalizeUa,
    decode,
    enrich,
    galaxyName(number) { return GALAXY_NAMES[Number(number)] || ''; },
  };
})();
