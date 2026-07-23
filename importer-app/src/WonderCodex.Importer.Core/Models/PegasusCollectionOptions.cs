namespace WonderCodex.Importer.Core.Models;

public sealed record PegasusCollectionOptions(
    bool IncludeCompanionPets = true,
    bool IncludeCreatureEggSignals = true,
    bool IncludeStarships = true,
    bool IncludeFreighter = true,
    bool IncludeFrigates = true,
    bool IncludeMultitools = true,
    bool IncludeInventoryCatalog = false,
    bool IncludeInventoryAmounts = false,
    bool IncludeCustomNames = false);
