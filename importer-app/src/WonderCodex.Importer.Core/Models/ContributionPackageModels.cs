using System.Text.Json.Serialization;

namespace WonderCodex.Importer.Core.Models;

public sealed class ContributionPackageDraft
{
    public ContributionManifest Manifest { get; init; } = new();
    public ContributionDiscoveriesDocument Discoveries { get; init; } = new();
}

public sealed class ContributionManifest
{
    [JsonPropertyName("packageType")]
    public string PackageType { get; init; } = "wondercodex.contribution";

    [JsonPropertyName("schemaVersion")]
    public string SchemaVersion { get; init; } = "0.1";

    [JsonPropertyName("submissionId")]
    public string SubmissionId { get; init; } = string.Empty;

    [JsonPropertyName("createdUtc")]
    public string CreatedUtc { get; init; } = string.Empty;

    [JsonPropertyName("importer")]
    public ContributionImporterInfo Importer { get; init; } = new();

    [JsonPropertyName("source")]
    public ContributionSourceInfo Source { get; init; } = new();

    [JsonPropertyName("recordCount")]
    public int RecordCount { get; init; }

    [JsonPropertyName("privacy")]
    public ContributionPrivacy Privacy { get; init; } = new();

    [JsonPropertyName("attribution")]
    public ContributionAttribution Attribution { get; init; } = new();

    [JsonPropertyName("content")]
    public ContributionContentInfo Content { get; init; } = new();
}

public sealed class ContributionImporterInfo
{
    [JsonPropertyName("name")]
    public string Name { get; init; } = "Wonder Codex Importer";

    [JsonPropertyName("version")]
    public string Version { get; init; } = "0.2.1-beta";
}

public sealed class ContributionSourceInfo
{
    [JsonPropertyName("platformFamily")]
    public string PlatformFamily { get; init; } = "unknown";

    [JsonPropertyName("acquisitionMethod")]
    public string AcquisitionMethod { get; init; } = "unknown";

    [JsonPropertyName("gameVersion")]
    public string? GameVersion { get; init; }

    [JsonPropertyName("saveSchemaVersion")]
    public string? SaveSchemaVersion { get; init; }
}

public sealed class ContributionPrivacy
{
    [JsonPropertyName("profile")]
    public string Profile { get; init; } = "wc-sanitized-v0.1";

    [JsonPropertyName("rawSaveIncluded")]
    public bool RawSaveIncluded { get; init; }

    [JsonPropertyName("accountIdentifiersIncluded")]
    public bool AccountIdentifiersIncluded { get; init; }

    [JsonPropertyName("localPathsIncluded")]
    public bool LocalPathsIncluded { get; init; }

    [JsonPropertyName("mediaIncluded")]
    public bool MediaIncluded { get; init; }
}

public sealed class ContributionAttribution
{
    [JsonPropertyName("preference")]
    public string Preference { get; init; } = "anonymous";

    [JsonPropertyName("displayName")]
    public string? DisplayName { get; init; }
}

public sealed class ContributionContentInfo
{
    [JsonPropertyName("discoveriesFile")]
    public string DiscoveriesFile { get; init; } = "discoveries.json";

    [JsonPropertyName("checksumsFile")]
    public string ChecksumsFile { get; init; } = "checksums.json";
}

public sealed class ContributionDiscoveriesDocument
{
    [JsonPropertyName("schemaVersion")]
    public string SchemaVersion { get; init; } = "0.1";

    [JsonPropertyName("records")]
    public List<ContributionDiscoveryRecord> Records { get; init; } = [];
}

public sealed class ContributionDiscoveryRecord
{
    [JsonPropertyName("packageRecordId")]
    public string PackageRecordId { get; init; } = string.Empty;

    [JsonPropertyName("recordType")]
    public string RecordType { get; init; } = "discovery";

    [JsonPropertyName("classification")]
    public ContributionClassification Classification { get; init; } = new();

    [JsonPropertyName("location")]
    public ContributionLocation Location { get; init; } = new();

    [JsonPropertyName("procedural")]
    public ContributionProceduralData Procedural { get; init; } = new();

    [JsonPropertyName("projector")]
    public ContributionProjectorData Projector { get; init; } = new();

    [JsonPropertyName("evidence")]
    public ContributionEvidence Evidence { get; init; } = new();

    [JsonPropertyName("deduplication")]
    public ContributionDeduplication Deduplication { get; init; } = new();
}

public sealed class ContributionClassification
{
    [JsonPropertyName("discoveryType")]
    public string DiscoveryType { get; init; } = "Other";

    [JsonPropertyName("wonderCategory")]
    public string WonderCategory { get; init; } = "Other";

    [JsonPropertyName("creatureId")]
    public string? CreatureId { get; init; }

    [JsonPropertyName("creatureType")]
    public string? CreatureType { get; init; }

    [JsonPropertyName("archetypeKey")]
    public string ArchetypeKey { get; init; } = "other.unknown";

    [JsonPropertyName("descriptors")]
    public List<string> Descriptors { get; init; } = [];

    [JsonPropertyName("biome")]
    public string? Biome { get; init; }
}

public sealed class ContributionLocation
{
    [JsonPropertyName("universalAddress")]
    public string UniversalAddress { get; init; } = string.Empty;

    [JsonPropertyName("galaxyNumber")]
    public int? GalaxyNumber { get; init; }

    [JsonPropertyName("portalAddressHex")]
    public string PortalAddressHex { get; init; } = string.Empty;

    [JsonPropertyName("glyphs")]
    public List<string> Glyphs { get; init; } = [];

    [JsonPropertyName("portalDerivation")]
    public ContributionPortalDerivation PortalDerivation { get; init; } = new();
}

public sealed class ContributionPortalDerivation
{
    [JsonPropertyName("method")]
    public string Method { get; init; } = "ua-remove-rr-v1";

    [JsonPropertyName("confidence")]
    public string Confidence { get; init; } = "confirmed";
}

public sealed class ContributionProceduralData
{
    [JsonPropertyName("vp")]
    public List<string> Vp { get; init; } = [];

    [JsonPropertyName("seedMappings")]
    public ContributionSeedMappings SeedMappings { get; init; } = new();
}

public sealed class ContributionSeedMappings
{
    [JsonPropertyName("creatureSeed")]
    public ContributionSeedMapping? CreatureSeed { get; init; }

    [JsonPropertyName("archetypeGenerator")]
    public ContributionSeedMapping? ArchetypeGenerator { get; init; }

    [JsonPropertyName("speciesSeed")]
    public ContributionSeedMapping? SpeciesSeed { get; init; }

    [JsonPropertyName("genusSeed")]
    public ContributionSeedMapping? GenusSeed { get; init; }

    [JsonPropertyName("secondarySeed")]
    public ContributionSeedMapping? SecondarySeed { get; init; }
}

public sealed class ContributionSeedMapping
{
    [JsonPropertyName("vpIndex")]
    public int VpIndex { get; init; }

    [JsonPropertyName("value")]
    public string Value { get; init; } = string.Empty;

    [JsonPropertyName("confidence")]
    public string Confidence { get; init; } = "hypothesis";
}

public sealed class ContributionProjectorData
{
    [JsonPropertyName("messageId")]
    public string? MessageId { get; init; }

    [JsonPropertyName("payloadBytes")]
    public int? PayloadBytes { get; init; }

    [JsonPropertyName("payloadHex")]
    public string? PayloadHex { get; init; }

    [JsonPropertyName("provenance")]
    public string Provenance { get; init; } = "unavailable";

    [JsonPropertyName("encoder")]
    public string? Encoder { get; init; }

    [JsonPropertyName("verification")]
    public string Verification { get; init; } = "hypothesis";
}

public sealed class ContributionEvidence
{
    [JsonPropertyName("discoveryDataPresent")]
    public bool DiscoveryDataPresent { get; init; }

    [JsonPropertyName("petDataMatchedLocally")]
    public bool PetDataMatchedLocally { get; init; }

    [JsonPropertyName("projectorReconstruction")]
    public string ProjectorReconstruction { get; init; } = "not_tested";

    [JsonPropertyName("overallConfidence")]
    public string OverallConfidence { get; init; } = "confirmed";

    [JsonPropertyName("notes")]
    public string? Notes { get; init; }
}

public sealed class ContributionDeduplication
{
    [JsonPropertyName("algorithm")]
    public string Algorithm { get; init; } = "wc-discovery-sha256-v0.1";

    [JsonPropertyName("canonicalForm")]
    public string CanonicalForm { get; init; } = "DiscoveryType|UA|VP*";

    [JsonPropertyName("scientificFingerprint")]
    public string ScientificFingerprint { get; init; } = string.Empty;
}

public sealed class ContributionChecksums
{
    [JsonPropertyName("algorithm")]
    public string Algorithm { get; init; } = "sha256";

    [JsonPropertyName("files")]
    public Dictionary<string, string> Files { get; init; } = new(StringComparer.Ordinal);
}

public sealed class ContributionSourceRecord
{
    public string DiscoveryType { get; init; } = "Other";
    public ulong UniversalAddress { get; init; }
    public List<ulong> Vp { get; init; } = [];
    public string? MessageId { get; init; }
    public string? CreatureId { get; set; }
    public string? CreatureType { get; set; }
    public bool PetDataMatchedLocally { get; set; }
}

public sealed class ContributionExportPreview
{
    public int RecordCount { get; init; }
    public int FaunaCount { get; init; }
    public int FloraCount { get; init; }
    public int MineralCount { get; init; }
    public int OtherCount { get; init; }
    public int ConfirmedFaunaProjectorCount { get; init; }
    public int GenericArchetypeCount { get; init; }

    public string Summary =>
        $"{RecordCount:N0} catalog record(s): {FaunaCount:N0} fauna, {FloraCount:N0} flora, " +
        $"{MineralCount:N0} mineral, {OtherCount:N0} other. " +
        $"{ConfirmedFaunaProjectorCount:N0} confirmed fauna projector ID(s); " +
        $"{GenericArchetypeCount:N0} record(s) will begin with a generic archetype image.";
}

public sealed class ContributionValidationResult
{
    public List<string> Errors { get; init; } = [];
    public bool IsValid => Errors.Count == 0;
}

public sealed class ContributionExportResult
{
    public int RecordCount { get; init; }
    public int PackageBytes { get; init; }
    public string SubmissionId { get; init; } = string.Empty;
}
