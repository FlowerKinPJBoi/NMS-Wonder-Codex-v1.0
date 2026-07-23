using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed class PegasusAssetAnalyzer
{
    private static readonly string[] EggKeywords =
    [
        "EGG", "CHILD", "HATCH", "COMPANION", "JELLY", "HORROR", "SANDWORM"
    ];

    public PegasusCollectionReport Analyze(
        JsonElement root,
        string saveName,
        string platform,
        PegasusCollectionOptions options)
    {
        var report = new PegasusCollectionReport
        {
            SaveName = saveName,
            Platform = platform
        };

        report.Modules["companionPets"] = options.IncludeCompanionPets;
        report.Modules["creatureEggSignals"] = options.IncludeCreatureEggSignals;
        report.Modules["starships"] = options.IncludeStarships;
        report.Modules["freighter"] = options.IncludeFreighter;
        report.Modules["frigates"] = options.IncludeFrigates;
        report.Modules["multitools"] = options.IncludeMultitools;
        report.Modules["inventoryCatalog"] = options.IncludeInventoryCatalog;

        report.Privacy["rawSaveUploaded"] = false;
        report.Privacy["rawSavePathIncluded"] = false;
        report.Privacy["accountIdentifiersIncluded"] = false;
        report.Privacy["inventoryCoordinatesIncluded"] = false;
        report.Privacy["inventoryAmountsIncluded"] = options.IncludeInventoryAmounts;
        report.Privacy["customNamesIncluded"] = options.IncludeCustomNames;
        report.Privacy["submissionState"] = "local beta export only";

        var assetKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var inventory = new Dictionary<string, InventoryAggregate>(StringComparer.OrdinalIgnoreCase);
        var queue = new Queue<SourceNode>();
        queue.Enqueue(new SourceNode(root, string.Empty, null));

        while (queue.Count > 0)
        {
            var node = queue.Dequeue();
            var element = node.Element;

            if (element.ValueKind == JsonValueKind.Array)
            {
                var index = 0;
                foreach (var child in element.EnumerateArray())
                    queue.Enqueue(new SourceNode(child, node.Collection, index++));
                continue;
            }

            if (element.ValueKind != JsonValueKind.Object) continue;

            if (options.IncludeCompanionPets && LooksLikePet(element))
                AddPet(element, report, assetKeys, options, node.Collection, node.Ordinal);

            if (options.IncludeStarships && LooksLikeStarship(element))
                AddStarship(element, report, assetKeys, options, node.Collection, node.Ordinal);

            if (options.IncludeMultitools && LooksLikeMultitool(element))
                AddMultitool(element, report, assetKeys, options, node.Collection, node.Ordinal);

            if (options.IncludeFrigates && LooksLikeFrigate(element))
                AddFrigate(element, report, assetKeys, options, node.Collection, node.Ordinal);

            if (options.IncludeFreighter && element.TryGetProperty("CurrentFreighter", out var freighter))
                AddFreighter(element, freighter, report, assetKeys, options);

            if ((options.IncludeInventoryCatalog || options.IncludeCreatureEggSignals) && LooksLikeInventorySlot(element))
                AddInventorySignal(element, inventory);

            foreach (var property in element.EnumerateObject())
            {
                var collection = property.Value.ValueKind == JsonValueKind.Array
                    ? property.Name
                    : node.Collection;
                queue.Enqueue(new SourceNode(property.Value, collection, node.Ordinal));
            }
        }

        AddInventoryAssets(inventory, report, assetKeys, options);
        PopulateSummary(report);

        report.Notes.Add("All source save files were opened read-only. No save values were edited, moved, renamed, or uploaded.");
        report.Notes.Add("Pegasus asset categories are local beta evidence only. The current public submission endpoint still receives only normalized Wonder discoveries and exact pet matches.");
        report.Notes.Add("Delivery eligibility is a research label, not a promise that an asset can already be transferred between players.");
        return report;
    }

    private static void AddPet(
        JsonElement pet,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options,
        string sourceCollection,
        int? sourceOrdinal)
    {
        var creatureId = ReadString(pet, "CreatureID").TrimStart('^');
        var creatureType = ReadNestedString(pet, "CreatureType", "CreatureType");
        var ua = ReadHex(pet, "UA");
        var creatureSeed = ReadSeedHex(pet, "CreatureSeed");
        var secondarySeed = ReadSeedHex(pet, "CreatureSecondarySeed");
        var speciesSeed = ReadHex(pet, "SpeciesSeed");
        var genusSeed = ReadHex(pet, "GenusSeed");
        var key = CreateKey("pet", creatureId, ua, creatureSeed, speciesSeed, genusSeed);
        if (!assetKeys.Add(key)) return;

        var customName = options.IncludeCustomNames ? ReadString(pet, "CustomName") : string.Empty;
        var displayName = !string.IsNullOrWhiteSpace(customName)
            ? customName
            : string.IsNullOrWhiteSpace(creatureType)
                ? $"Companion {creatureId}"
                : $"{creatureType} companion";

        var classOverride = ReadBool(pet, "PetBattlerUseCoreStatClassOverrides");
        var classes = ReadClassArray(pet, "PetBattlerCoreStatClassOverrides");
        var moves = ReadStringArray(pet, "PetBattlerMoves", trimCaret: true);
        var traits = ReadNumberArray(pet, "Traits");
        var isSpecialTemplate = IsSpecialCompanionTemplate(creatureId, creatureSeed, speciesSeed);

        var fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
        {
            ["creatureID"] = creatureId,
            ["creatureType"] = creatureType,
            ["ua"] = ua,
            ["creatureSeed"] = creatureSeed,
            ["secondarySeed"] = secondarySeed,
            ["speciesSeed"] = speciesSeed,
            ["genusSeed"] = genusSeed,
            ["scale"] = ReadDouble(pet, "Scale"),
            ["predator"] = ReadBool(pet, "Predator"),
            ["eggModified"] = ReadBool(pet, "EggModified"),
            ["battleClassOverride"] = classOverride,
            ["battleClasses"] = classes,
            ["battleMoves"] = moves,
            ["battleVictories"] = ReadInt(pet, "PetBattlerVictories"),
            ["traits"] = traits,
            ["specialTemplateSignal"] = isSpecialTemplate
        };

        if (options.IncludeCustomNames && !string.IsNullOrWhiteSpace(customName))
            fields["customName"] = customName;

        report.Assets.Add(new PegasusAssetRecord
        {
            AssetType = "CompanionPet",
            AssetKey = key,
            DisplayName = displayName,
            SourceRole = SourceRole("CompanionPet", sourceCollection),
            SourceCollection = sourceCollection,
            SourceOrdinal = sourceOrdinal,
            IdentityBasis = "creature_id_and_seed",
            ModifiedOrSpecialSignal = isSpecialTemplate || ReadBool(pet, "EggModified"),
            DeliveryEligibility = "research_only",
            DeliveryEvidenceStatus = "not_evaluated",
            DeliveryLane = isSpecialTemplate
                ? "Pegasus special-companion research"
                : "Pegasus Courier / egg research",
            Confidence = isSpecialTemplate ? "Template signal" : "Normalized pet record",
            Fields = fields
        });
    }

    private static void AddStarship(
        JsonElement ship,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options,
        string sourceCollection,
        int? sourceOrdinal)
    {
        if (!TryReadResource(ship, out var filename, out var resourceSeed)) return;
        var ownSeed = ReadSeedHex(ship, "Seed");
        var shipSeed = !IsZeroSeed(ownSeed) ? ownSeed : resourceSeed;
        var assetClass = ReadInventoryClass(ship, "Inventory");
        if (string.IsNullOrWhiteSpace(assetClass)) assetClass = ReadInventoryClass(ship, "Inventory_Cargo");
        var key = CreateKey("starship", filename, shipSeed);
        if (!assetKeys.Add(key)) return;

        var customName = options.IncludeCustomNames ? ReadString(ship, "Name") : string.Empty;
        var displayName = !string.IsNullOrWhiteSpace(customName)
            ? customName
            : $"{FriendlyResourceName(filename)} starship";

        report.Assets.Add(new PegasusAssetRecord
        {
            AssetType = "Starship",
            AssetKey = key,
            DisplayName = displayName,
            SourceRole = SourceRole("Starship", sourceCollection),
            SourceCollection = sourceCollection,
            SourceOrdinal = sourceOrdinal,
            IdentityBasis = "resource_filename_and_seed",
            DeliveryEligibility = "acquisition_research",
            DeliveryEvidenceStatus = "location_not_evaluated",
            DeliveryLane = "Pegasus Acquisition research",
            Confidence = "Owned-asset seed",
            Fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
            {
                ["resourceFilename"] = filename,
                ["seed"] = shipSeed,
                ["class"] = assetClass,
                ["baseStats"] = ReadBaseStats(ship, "Inventory"),
                ["cargoBaseStats"] = ReadBaseStats(ship, "Inventory_Cargo")
            }
        });
    }

    private static void AddFreighter(
        JsonElement parent,
        JsonElement freighter,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options)
    {
        var filename = ReadString(freighter, "Filename");
        var seed = ReadSeedHex(freighter, "Seed");
        if (string.IsNullOrWhiteSpace(filename) || IsZeroSeed(seed)) return;
        var key = CreateKey("freighter", filename, seed);
        if (!assetKeys.Add(key)) return;

        var customName = options.IncludeCustomNames ? ReadString(parent, "PlayerFreighterName") : string.Empty;
        var displayName = !string.IsNullOrWhiteSpace(customName)
            ? customName
            : $"{FriendlyResourceName(filename)} freighter";

        report.Assets.Add(new PegasusAssetRecord
        {
            AssetType = "Freighter",
            AssetKey = key,
            DisplayName = displayName,
            SourceRole = "current",
            SourceCollection = "CurrentFreighter",
            IdentityBasis = "resource_filename_and_seed",
            DeliveryEligibility = "acquisition_research",
            DeliveryEvidenceStatus = "location_not_evaluated",
            DeliveryLane = "Pegasus Acquisition route research",
            Confidence = "Current freighter seed",
            Fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
            {
                ["resourceFilename"] = filename,
                ["seed"] = seed,
                ["class"] = ReadInventoryClass(parent, "FreighterInventory"),
                ["homeSystemSeed"] = ReadSeedHex(parent, "CurrentFreighterHomeSystemSeed"),
                ["fleetSeed"] = ReadSeedHex(parent, "FleetSeed"),
                ["baseStats"] = ReadBaseStats(parent, "FreighterInventory")
            }
        });
    }

    private static void AddFrigate(
        JsonElement frigate,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options,
        string sourceCollection,
        int? sourceOrdinal)
    {
        var seed = ReadSeedHex(frigate, "ResourceSeed");
        var frigateClass = ReadNestedString(frigate, "FrigateClass", "FrigateClass");
        if (IsZeroSeed(seed) || string.IsNullOrWhiteSpace(frigateClass)) return;
        var key = CreateKey("frigate", seed, frigateClass);
        if (!assetKeys.Add(key)) return;

        var customName = options.IncludeCustomNames ? ReadString(frigate, "CustomName") : string.Empty;
        var displayName = !string.IsNullOrWhiteSpace(customName)
            ? customName
            : $"{frigateClass} frigate";

        report.Assets.Add(new PegasusAssetRecord
        {
            AssetType = "Frigate",
            AssetKey = key,
            DisplayName = displayName,
            SourceRole = SourceRole("Frigate", sourceCollection),
            SourceCollection = sourceCollection,
            SourceOrdinal = sourceOrdinal,
            IdentityBasis = "resource_seed_and_frigate_class",
            DeliveryEligibility = "recruitment_research",
            DeliveryEvidenceStatus = "location_not_evaluated",
            DeliveryLane = "Pegasus Acquisition / recruitment research",
            Confidence = "Fleet record",
            Fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
            {
                ["resourceSeed"] = seed,
                ["homeSystemSeed"] = ReadSeedHex(frigate, "HomeSystemSeed"),
                ["frigateClass"] = frigateClass,
                ["class"] = ReadNestedString(frigate, "InventoryClass", "InventoryClass"),
                ["race"] = ReadNestedString(frigate, "Race", "AlienRace"),
                ["stats"] = ReadNumberArray(frigate, "Stats"),
                ["traits"] = ReadStringArray(frigate, "TraitIDs", trimCaret: true),
                ["expeditions"] = ReadInt(frigate, "TotalNumberOfExpeditions")
            }
        });
    }

    private static void AddMultitool(
        JsonElement multitool,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options,
        string sourceCollection,
        int? sourceOrdinal)
    {
        if (!TryReadResource(multitool, out var filename, out _)) return;
        var seed = ReadSeedHex(multitool, "Seed");
        if (IsZeroSeed(seed)) return;
        var key = CreateKey("multitool", filename, seed);
        if (!assetKeys.Add(key)) return;

        var customName = options.IncludeCustomNames ? ReadString(multitool, "Name") : string.Empty;
        var archivedName = options.IncludeCustomNames ? ReadString(multitool, "ArchivedName") : string.Empty;
        var displayName = !string.IsNullOrWhiteSpace(customName)
            ? customName
            : !string.IsNullOrWhiteSpace(archivedName)
                ? archivedName
                : $"{FriendlyResourceName(filename)} multitool";

        var assetClass = ReadInventoryClass(multitool, "Store");
        if (string.IsNullOrWhiteSpace(assetClass))
            assetClass = ReadNestedString(multitool, "ArchivedInventoryClass", "InventoryClass");

        report.Assets.Add(new PegasusAssetRecord
        {
            AssetType = "Multitool",
            AssetKey = key,
            DisplayName = displayName,
            SourceRole = SourceRole("Multitool", sourceCollection),
            SourceCollection = sourceCollection,
            SourceOrdinal = sourceOrdinal,
            IdentityBasis = "resource_filename_and_seed",
            DeliveryEligibility = "acquisition_research",
            DeliveryEvidenceStatus = "location_not_evaluated",
            DeliveryLane = "Pegasus Acquisition route research",
            Confidence = "Owned-asset seed",
            Fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
            {
                ["resourceFilename"] = filename,
                ["seed"] = seed,
                ["class"] = assetClass,
                ["weaponClass"] = ReadNestedString(multitool, "WeaponClass", "WeaponStatClass"),
                ["baseStats"] = ReadBaseStats(multitool, "Store")
            }
        });
    }

    private static void AddInventorySignal(
        JsonElement slot,
        IDictionary<string, InventoryAggregate> inventory)
    {
        var id = ReadString(slot, "Id").TrimStart('^');
        if (string.IsNullOrWhiteSpace(id)) return;
        var inventoryType = ReadNestedString(slot, "Type", "InventoryType");
        if (string.Equals(inventoryType, "Technology", StringComparison.OrdinalIgnoreCase)) return;

        var key = $"{inventoryType}|{id}";
        if (!inventory.TryGetValue(key, out var aggregate))
        {
            aggregate = new InventoryAggregate(id, inventoryType);
            inventory[key] = aggregate;
        }

        aggregate.Occurrences++;
        aggregate.TotalAmount += Math.Max(0, ReadInt(slot, "Amount"));
    }

    private static void AddInventoryAssets(
        IReadOnlyDictionary<string, InventoryAggregate> inventory,
        PegasusCollectionReport report,
        ISet<string> assetKeys,
        PegasusCollectionOptions options)
    {
        foreach (var aggregate in inventory.Values.OrderBy(value => value.Id, StringComparer.OrdinalIgnoreCase))
        {
            var eggLike = IsEggLike(aggregate.Id);
            if (eggLike && options.IncludeCreatureEggSignals)
            {
                var eggKey = CreateKey("egg-signal", aggregate.InventoryType, aggregate.Id);
                if (assetKeys.Add(eggKey))
                {
                    var fields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
                    {
                        ["itemID"] = aggregate.Id,
                        ["inventoryType"] = aggregate.InventoryType,
                        ["occurrences"] = aggregate.Occurrences,
                        ["detection"] = "item identifier heuristic"
                    };
                    if (options.IncludeInventoryAmounts) fields["amount"] = aggregate.TotalAmount;

                    report.Assets.Add(new PegasusAssetRecord
                    {
                        AssetType = "CreatureEggSignal",
                        AssetKey = eggKey,
                        DisplayName = aggregate.Id,
                        DeliveryLane = "Pegasus Courier research",
                        Confidence = "Heuristic inventory signal",
                        Fields = fields
                    });
                }
            }

            if (!options.IncludeInventoryCatalog) continue;
            var itemKey = CreateKey("inventory-item", aggregate.InventoryType, aggregate.Id);
            if (!assetKeys.Add(itemKey)) continue;

            var itemFields = new Dictionary<string, object?>(StringComparer.OrdinalIgnoreCase)
            {
                ["itemID"] = aggregate.Id,
                ["inventoryType"] = aggregate.InventoryType,
                ["occurrences"] = aggregate.Occurrences,
                ["eggLikeSignal"] = eggLike
            };
            if (options.IncludeInventoryAmounts) itemFields["amount"] = aggregate.TotalAmount;

            report.Assets.Add(new PegasusAssetRecord
            {
                AssetType = "InventoryItem",
                AssetKey = itemKey,
                DisplayName = aggregate.Id,
                DeliveryLane = "Pegasus Courier capability review",
                Confidence = "Recognized inventory identifier",
                Fields = itemFields
            });
        }
    }

    private static bool LooksLikePet(JsonElement element)
        => element.TryGetProperty("CreatureID", out var creatureId)
           && !string.IsNullOrWhiteSpace(JsonValueReader.GetString(creatureId).Trim('^'))
           && element.TryGetProperty("SpeciesSeed", out _)
           && element.TryGetProperty("GenusSeed", out _)
           && element.TryGetProperty("UA", out _);

    private static bool LooksLikeStarship(JsonElement element)
        => TryReadResource(element, out var filename, out _)
           && filename.Contains("/SPACECRAFT/", StringComparison.OrdinalIgnoreCase)
           && (element.TryGetProperty("Inventory", out _)
               || element.TryGetProperty("Inventory_TechOnly", out _)
               || element.TryGetProperty("Inventory_Cargo", out _));

    private static bool LooksLikeMultitool(JsonElement element)
        => TryReadResource(element, out var filename, out _)
           && filename.Contains("/WEAPONS/MULTITOOL/", StringComparison.OrdinalIgnoreCase)
           && element.TryGetProperty("Store", out _);

    private static bool LooksLikeFrigate(JsonElement element)
        => element.TryGetProperty("ResourceSeed", out _)
           && element.TryGetProperty("FrigateClass", out _)
           && element.TryGetProperty("InventoryClass", out _)
           && element.TryGetProperty("Stats", out var stats)
           && stats.ValueKind == JsonValueKind.Array;

    private static bool LooksLikeInventorySlot(JsonElement element)
        => element.TryGetProperty("Id", out _)
           && element.TryGetProperty("Amount", out _)
           && element.TryGetProperty("Type", out var type)
           && type.ValueKind == JsonValueKind.Object;

    private static bool TryReadResource(JsonElement element, out string filename, out string seed)
    {
        filename = string.Empty;
        seed = string.Empty;
        if (!element.TryGetProperty("Resource", out var resource) || resource.ValueKind != JsonValueKind.Object)
            return false;
        filename = ReadString(resource, "Filename");
        seed = ReadSeedHex(resource, "Seed");
        return !string.IsNullOrWhiteSpace(filename);
    }

    private static Dictionary<string, double> ReadBaseStats(JsonElement element, string inventoryProperty)
    {
        var values = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        if (!element.TryGetProperty(inventoryProperty, out var inventory) || inventory.ValueKind != JsonValueKind.Object)
            return values;
        if (!inventory.TryGetProperty("BaseStatValues", out var stats) || stats.ValueKind != JsonValueKind.Array)
            return values;

        foreach (var stat in stats.EnumerateArray())
        {
            if (stat.ValueKind != JsonValueKind.Object) continue;
            var id = ReadString(stat, "BaseStatID").TrimStart('^');
            if (string.IsNullOrWhiteSpace(id)) continue;
            values[id] = ReadDouble(stat, "Value");
        }
        return values;
    }

    private static string ReadInventoryClass(JsonElement element, string inventoryProperty)
    {
        if (!element.TryGetProperty(inventoryProperty, out var inventory) || inventory.ValueKind != JsonValueKind.Object)
            return string.Empty;
        return ReadNestedString(inventory, "Class", "InventoryClass");
    }

    private static string ReadNestedString(JsonElement element, string propertyName, string nestedName)
    {
        if (!element.TryGetProperty(propertyName, out var nested) || nested.ValueKind != JsonValueKind.Object)
            return string.Empty;
        return ReadString(nested, nestedName).TrimStart('^');
    }

    private static string ReadString(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var value)
            ? JsonValueReader.GetString(value)
            : string.Empty;

    private static bool ReadBool(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var value)) return false;
        return value.ValueKind switch
        {
            JsonValueKind.True => true,
            JsonValueKind.False => false,
            JsonValueKind.String => bool.TryParse(value.GetString(), out var parsed) && parsed,
            _ => false
        };
    }

    private static int ReadInt(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var value)) return 0;
        if (value.ValueKind == JsonValueKind.Number && value.TryGetInt32(out var parsed)) return parsed;
        return int.TryParse(JsonValueReader.GetString(value), NumberStyles.Integer, CultureInfo.InvariantCulture, out parsed)
            ? parsed
            : 0;
    }

    private static double ReadDouble(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var value)) return 0d;
        if (value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var parsed)) return parsed;
        return double.TryParse(JsonValueReader.GetString(value), NumberStyles.Float, CultureInfo.InvariantCulture, out parsed)
            ? parsed
            : 0d;
    }

    private static string ReadHex(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var value) && JsonValueReader.TryGetUInt64(value, out var parsed)
            ? JsonValueReader.Hex(parsed)
            : string.Empty;

    private static string ReadSeedHex(JsonElement element, string propertyName)
        => element.TryGetProperty(propertyName, out var value) && JsonValueReader.TryGetSeed(value, out var parsed)
            ? JsonValueReader.Hex(parsed)
            : string.Empty;

    private static IReadOnlyList<string> ReadClassArray(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var values) || values.ValueKind != JsonValueKind.Array)
            return [];
        return values.EnumerateArray()
            .Select(value => value.ValueKind == JsonValueKind.Object
                ? ReadString(value, "InventoryClass")
                : JsonValueReader.GetString(value))
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .ToArray();
    }

    private static IReadOnlyList<string> ReadStringArray(
        JsonElement element,
        string propertyName,
        bool trimCaret = false)
    {
        if (!element.TryGetProperty(propertyName, out var values) || values.ValueKind != JsonValueKind.Array)
            return [];
        return values.EnumerateArray()
            .Select(value => JsonValueReader.GetString(value))
            .Select(value => trimCaret ? value.TrimStart('^') : value)
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .ToArray();
    }

    private static IReadOnlyList<double> ReadNumberArray(JsonElement element, string propertyName)
    {
        if (!element.TryGetProperty(propertyName, out var values) || values.ValueKind != JsonValueKind.Array)
            return [];
        return values.EnumerateArray()
            .Select(value => value.ValueKind == JsonValueKind.Number && value.TryGetDouble(out var number) ? number : 0d)
            .ToArray();
    }

    private static bool IsSpecialCompanionTemplate(string creatureId, string creatureSeed, string speciesSeed)
        => creatureId.Contains("JELLYFISH", StringComparison.OrdinalIgnoreCase)
           || creatureId.Contains("ROBOT", StringComparison.OrdinalIgnoreCase)
           || (IsZeroSeed(creatureSeed) && !IsZeroSeed(speciesSeed));

    private static bool IsEggLike(string id)
        => EggKeywords.Any(keyword => id.Contains(keyword, StringComparison.OrdinalIgnoreCase));

    private static bool IsZeroSeed(string value)
        => string.IsNullOrWhiteSpace(value)
           || string.Equals(value, "0x0000000000000000", StringComparison.OrdinalIgnoreCase)
           || string.Equals(value, "0x0", StringComparison.OrdinalIgnoreCase);

    private static string FriendlyResourceName(string filename)
    {
        if (string.IsNullOrWhiteSpace(filename)) return "Procedural";
        var leaf = filename.Replace('\\', '/').Split('/').LastOrDefault() ?? filename;
        var withoutExtension = leaf.Split('.').FirstOrDefault() ?? leaf;
        return withoutExtension.Replace('_', ' ').Trim();
    }

    private static string CreateKey(string type, params string[] parts)
    {
        var canonical = string.Join('|', new[] { type }.Concat(parts).Select(value => value ?? string.Empty));
        var digest = SHA256.HashData(Encoding.UTF8.GetBytes(canonical));
        return $"PGA-{type.ToUpperInvariant()}-{Convert.ToHexString(digest)[..16]}";
    }

    private static string SourceRole(string assetType, string sourceCollection)
    {
        var collection = sourceCollection ?? string.Empty;
        if (collection.Contains("Archived", StringComparison.OrdinalIgnoreCase)) return "archived";
        if (collection.Contains("Squadron", StringComparison.OrdinalIgnoreCase)) return "squadron_member";
        if (assetType == "Frigate" && collection.Contains("Fleet", StringComparison.OrdinalIgnoreCase)) return "fleet_member";
        if (assetType == "Starship" && collection.Contains("ShipOwnership", StringComparison.OrdinalIgnoreCase)) return "owned_slot";
        if (assetType == "Multitool" && collection.Contains("Multitool", StringComparison.OrdinalIgnoreCase)) return "owned_slot";
        if (assetType == "CompanionPet" && (collection.Contains("Pet", StringComparison.OrdinalIgnoreCase) || collection.Contains("Companion", StringComparison.OrdinalIgnoreCase))) return "owned_slot";
        return "unknown";
    }

    private static void PopulateSummary(PegasusCollectionReport report)
    {
        report.Summary["totalAssets"] = report.Assets.Count;
        report.Summary["companionPets"] = report.Count("CompanionPet");
        report.Summary["creatureEggSignals"] = report.Count("CreatureEggSignal");
        report.Summary["starships"] = report.Count("Starship");
        report.Summary["freighters"] = report.Count("Freighter");
        report.Summary["frigates"] = report.Count("Frigate");
        report.Summary["multitools"] = report.Count("Multitool");
        report.Summary["inventoryItems"] = report.Count("InventoryItem");
    }

    private sealed class InventoryAggregate(string id, string inventoryType)
    {
        public string Id { get; } = id;
        public string InventoryType { get; } = inventoryType;
        public int Occurrences { get; set; }
        public int TotalAmount { get; set; }
    }

    private readonly record struct SourceNode(JsonElement Element, string Collection, int? Ordinal);
}
