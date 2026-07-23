(() => {
  'use strict';

  const entries = Object.freeze({
    'fauna.unknown': {
      url: 'assets/archetypes/fauna/unknown.svg',
      label: 'Unclassified fauna',
      alt: 'Representative scan illustration of unclassified fauna',
    },
    'fauna.antelope': {
      url: 'assets/archetypes/fauna/projector/antelope.webp',
      label: 'Slender grazer',
      alt: 'Representative family artwork of a slender grazing creature, not this exact specimen',
    },
    'fauna.blob': {
      url: 'assets/archetypes/fauna/projector/blob.webp',
      label: 'Gelatinous blob',
      alt: 'Representative family artwork of a gelatinous blob creature, not this exact specimen',
    },
    'fauna.bonecow': {
      url: 'assets/archetypes/fauna/projector/bonecow.webp',
      label: 'Skeletal grazer',
      alt: 'Representative family artwork of a skeletal grazing creature, not this exact specimen',
    },
    'fauna.cat': {
      url: 'assets/archetypes/fauna/projector/cat.webp',
      label: 'Feline predator',
      alt: 'Representative family artwork of a feline predator, not this exact specimen',
    },
    'fauna.cow': {
      url: 'assets/archetypes/fauna/projector/cow.webp',
      label: 'Armored grazer',
      alt: 'Representative family artwork of an armored grazing creature, not this exact specimen',
    },
    'fauna.floatspider': {
      url: 'assets/archetypes/fauna/projector/floatspider.webp',
      label: 'Floating arachnid',
      alt: 'Representative family artwork of a floating arachnid creature, not this exact specimen',
    },
    'fauna.flyingbeetle': {
      url: 'assets/archetypes/fauna/projector/flyingbeetle.webp',
      label: 'Flying beetle',
      alt: 'Representative family artwork of a flying beetle creature, not this exact specimen',
    },
    'fauna.grunt': {
      url: 'assets/archetypes/fauna/projector/grunt.webp',
      label: 'Primate-like fauna',
      alt: 'Representative family artwork of a primate-like creature, not this exact specimen',
    },
    'fauna.hermitcrab': {
      url: 'assets/archetypes/fauna/projector/hermitcrab.webp',
      label: 'Shelled arthropod',
      alt: 'Representative family artwork of a shelled arthropod creature, not this exact specimen',
    },
    'fauna.largebutterfly': {
      url: 'assets/archetypes/fauna/projector/largebutterfly.webp',
      label: 'Large winged insect',
      alt: 'Representative family artwork of a large winged insect, not this exact specimen',
    },
    'fauna.protoflyer': {
      url: 'assets/archetypes/fauna/projector/protoflyer.webp',
      label: 'Proto flyer',
      alt: 'Representative family artwork of a broad translucent flying creature, not this exact specimen',
    },
    'fauna.robotantelope': {
      url: 'assets/archetypes/fauna/projector/robotantelope.webp',
      label: 'Mechanical grazer',
      alt: 'Representative family artwork of a mechanical grazing creature, not this exact specimen',
    },
    'fauna.sixlegcow': {
      url: 'assets/archetypes/fauna/projector/sixlegcow.webp',
      label: 'Six-legged grazer',
      alt: 'Representative family artwork of a six-legged grazing creature, not this exact specimen',
    },
    'fauna.spider': {
      url: 'assets/archetypes/fauna/projector/spider.webp',
      label: 'Ground arachnid',
      alt: 'Representative family artwork of a ground arachnid creature, not this exact specimen',
    },
    'fauna.strider': {
      url: 'assets/archetypes/fauna/projector/strider.webp',
      label: 'Tall strider',
      alt: 'Representative family artwork of a tall two-legged strider, not this exact specimen',
    },
    'fauna.trex': {
      url: 'assets/archetypes/fauna/projector/trex.webp',
      label: 'Large bipedal predator',
      alt: 'Representative family artwork of a large bipedal predator, not this exact specimen',
    },
    'fauna.triceratops': {
      url: 'assets/archetypes/fauna/projector/triceratops.webp',
      label: 'Horned grazer',
      alt: 'Representative family artwork of a horned grazing creature, not this exact specimen',
    },
    'fauna.twolegantelope': {
      url: 'assets/archetypes/fauna/projector/twolegantelope.webp',
      label: 'Bipedal grazer',
      alt: 'Representative family artwork of a bipedal grazing creature, not this exact specimen',
    },
    'fauna.walkingbuilding': {
      url: 'assets/archetypes/fauna/projector/walkingbuilding.webp',
      label: 'Walking construct',
      alt: 'Representative family artwork of a walking construct creature, not this exact specimen',
    },
    'fauna.weirdfloat': {
      url: 'assets/archetypes/fauna/projector/weirdfloat.webp',
      label: 'Crystalline floater',
      alt: 'Representative family artwork of a crystalline floating creature, not this exact specimen',
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
    'asset.starship': {
      url: 'assets/archetypes/assets/starship.svg',
      label: 'Procedural starship',
      alt: 'Illustrative Wonder Codex scan of a procedural starship, not the exact specimen',
    },
    'asset.freighter': {
      url: 'assets/archetypes/assets/freighter.svg',
      label: 'Capital freighter',
      alt: 'Illustrative Wonder Codex scan of a capital freighter, not the exact specimen',
    },
    'asset.frigate': {
      url: 'assets/archetypes/assets/frigate.svg',
      label: 'Fleet frigate',
      alt: 'Illustrative Wonder Codex scan of a fleet frigate, not the exact specimen',
    },
    'asset.multitool': {
      url: 'assets/archetypes/assets/multitool.svg',
      label: 'Procedural multi-tool',
      alt: 'Illustrative Wonder Codex scan of a procedural multi-tool, not the exact specimen',
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
    const assetKey = {
      Starship: 'asset.starship',
      Freighter: 'asset.freighter',
      Frigate: 'asset.frigate',
      Multitool: 'asset.multitool',
    }[record.asset_type];
    if (assetKey) return assetKey;
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
