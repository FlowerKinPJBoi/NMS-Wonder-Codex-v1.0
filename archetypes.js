(() => {
  'use strict';

  const entries = Object.freeze({
    'fauna.unknown': {
      url: 'assets/archetypes/fauna/unknown.svg',
      label: 'Unclassified fauna',
      alt: 'Representative scan illustration of unclassified fauna',
    },
    'fauna.antelope': {
      url: 'assets/archetypes/fauna/antelope.svg',
      label: 'Slender grazer',
      alt: 'Representative scan illustration of a slender grazing creature',
    },
    'fauna.cat': {
      url: 'assets/archetypes/fauna/cat.svg',
      label: 'Feline predator',
      alt: 'Representative scan illustration of a feline predator',
    },
    'fauna.floatspider': {
      url: 'assets/archetypes/fauna/floatspider.svg',
      label: 'Floating arachnid',
      alt: 'Representative scan illustration of a floating arachnid creature',
    },
    'fauna.hermitcrab': {
      url: 'assets/archetypes/fauna/hermitcrab.svg',
      label: 'Shelled arthropod',
      alt: 'Representative scan illustration of a shelled arthropod creature',
    },
    'fauna.trex': {
      url: 'assets/archetypes/fauna/trex.svg',
      label: 'Large bipedal predator',
      alt: 'Representative scan illustration of a large bipedal predator',
    },
    'fauna.triceratops': {
      url: 'assets/archetypes/fauna/triceratops.svg',
      label: 'Horned grazer',
      alt: 'Representative scan illustration of a horned grazing creature',
    },
    'flora.unknown': {
      url: 'assets/archetypes/flora/unknown.svg',
      label: 'Unclassified flora',
      alt: 'Neutral botanical scan illustration for flora awaiting a specimen image',
    },
    'mineral.unknown': {
      url: 'assets/archetypes/mineral/unknown.svg',
      label: 'Unclassified mineral',
      alt: 'Neutral crystalline scan illustration for a mineral awaiting a specimen image',
    },
    'other.unknown': {
      url: 'assets/archetypes/other/unknown.svg',
      label: 'Unclassified Wonder',
      alt: 'Neutral survey scan illustration for a Wonder awaiting a specimen image',
    },
  });

  const typeDefaults = Object.freeze({
    Animal: 'fauna.unknown',
    Fauna: 'fauna.unknown',
    Flora: 'flora.unknown',
    Mineral: 'mineral.unknown',
  });

  function defaultKey(record = {}) {
    return typeDefaults[record.discovery_type] || 'other.unknown';
  }

  function resolve(record = {}) {
    const requested = String(record.archetype_key || '').trim().toLowerCase();
    const key = Object.prototype.hasOwnProperty.call(entries, requested)
      ? requested
      : defaultKey(record);
    return Object.freeze({key, ...entries[key]});
  }

  window.WCArchetypes = Object.freeze({resolve, entries});
})();
