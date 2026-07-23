using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed class ContributionPackageBuilder
{
    public const string SchemaVersion = "0.1";
    public const string ImporterVersion = "0.2.1-beta";

    public ContributionExportPreview Preview(AnalysisReport report)
    {
        ArgumentNullException.ThrowIfNull(report);

        var fauna = report.ContributionRecords.Count(IsFauna);
        var flora = report.ContributionRecords.Count(record =>
            string.Equals(record.DiscoveryType, "Flora", StringComparison.OrdinalIgnoreCase));
        var mineral = report.ContributionRecords.Count(record =>
            string.Equals(record.DiscoveryType, "Mineral", StringComparison.OrdinalIgnoreCase));
        var other = report.ContributionRecords.Count - fauna - flora - mineral;
        var confirmedFaunaProjectors = report.ContributionRecords.Count(record =>
            IsFauna(record) && !string.IsNullOrWhiteSpace(record.MessageId));

        return new ContributionExportPreview
        {
            RecordCount = report.ContributionRecords.Count,
            FaunaCount = fauna,
            FloraCount = flora,
            MineralCount = mineral,
            OtherCount = other,
            ConfirmedFaunaProjectorCount = confirmedFaunaProjectors,
            GenericArchetypeCount = report.ContributionRecords.Count
        };
    }

    public ContributionPackageDraft Build(
        AnalysisReport report,
        string? contributorDisplayName,
        bool anonymous,
        string? sourcePlatformFamily = null,
        bool officialCrossSaveToPc = false,
        DateTimeOffset? createdUtc = null,
        string? submissionId = null)
    {
        ArgumentNullException.ThrowIfNull(report);
        if (report.ContributionRecords.Count == 0)
            throw new InvalidOperationException("No normalized discovery records are available for contribution export.");

        var displayName = NormalizeAttribution(contributorDisplayName, anonymous);
        var created = createdUtc ?? DateTimeOffset.UtcNow;
        var platformFamily = PlatformFamily(report.Platform, sourcePlatformFamily);
        var crossSaveOrigin = platformFamily is "playstation" or "xbox" or "nintendo" or "mac";
        if (crossSaveOrigin && !officialCrossSaveToPc)
            throw new InvalidOperationException(
                "Console and Mac contributions must confirm the official cross-save-to-PC pathway.");
        if (!crossSaveOrigin && officialCrossSaveToPc)
            throw new InvalidOperationException(
                "Official cross-save provenance requires the original console or Mac platform.");
        var records = report.ContributionRecords
            .Select((record, index) => BuildRecord(record, index + 1))
            .ToList();

        return new ContributionPackageDraft
        {
            Manifest = new ContributionManifest
            {
                SubmissionId = submissionId ?? CreateSubmissionId(created),
                CreatedUtc = created.UtcDateTime.ToString(
                    "yyyy-MM-dd'T'HH:mm:ss.fff'Z'",
                    CultureInfo.InvariantCulture),
                Importer = new ContributionImporterInfo
                {
                    Version = ImporterVersion
                },
                Source = new ContributionSourceInfo
                {
                    PlatformFamily = platformFamily,
                    AcquisitionMethod = officialCrossSaveToPc
                        ? "official_cross_save_to_pc"
                        : "local_pc_save",
                    GameVersion = null,
                    SaveSchemaVersion = null
                },
                RecordCount = records.Count,
                Privacy = new ContributionPrivacy
                {
                    RawSaveIncluded = false,
                    AccountIdentifiersIncluded = false,
                    LocalPathsIncluded = false,
                    MediaIncluded = false
                },
                Attribution = new ContributionAttribution
                {
                    Preference = anonymous ? "anonymous" : "credited",
                    DisplayName = displayName
                }
            },
            Discoveries = new ContributionDiscoveriesDocument
            {
                Records = records
            }
        };
    }

    private static ContributionDiscoveryRecord BuildRecord(ContributionSourceRecord source, int index)
    {
        if (source.Vp.Count is < 1 or > 32)
            throw new InvalidOperationException($"Discovery {index} has an unsupported VP count.");
        if (source.UniversalAddress > 0x00FF_FFFF_FFFF_FFFFUL)
            throw new InvalidOperationException($"Discovery {index} has a Universal Address wider than 14 hex digits.");

        var discoveryType = NormalizeDiscoveryType(source.DiscoveryType);
        var category = WonderCategory(discoveryType);
        var ua = $"0x{source.UniversalAddress:X14}";
        var uaDigits = ua[2..];
        var portalAddress = string.Concat(uaDigits.AsSpan(0, 4), uaDigits.AsSpan(6));
        var vp = source.Vp.Select(Hex64).ToList();
        var canonical = string.Join("|", new[] { discoveryType, ua }.Concat(vp));
        var fingerprint = Convert.ToHexString(
                SHA256.HashData(Encoding.UTF8.GetBytes(canonical)))
            .ToLowerInvariant();

        var creatureId = NormalizeCreatureId(source.CreatureId);
        var projector = BuildProjector(source, discoveryType);

        return new ContributionDiscoveryRecord
        {
            PackageRecordId = $"DISC-{index:D6}",
            Classification = new ContributionClassification
            {
                DiscoveryType = discoveryType,
                WonderCategory = category,
                CreatureId = creatureId,
                CreatureType = CleanOptional(source.CreatureType),
                ArchetypeKey = ArchetypeKey(category, creatureId),
                Descriptors = [],
                Biome = null
            },
            Location = new ContributionLocation
            {
                UniversalAddress = ua,
                GalaxyNumber = null,
                PortalAddressHex = portalAddress,
                Glyphs = portalAddress.Select(character => character.ToString()).ToList()
            },
            Procedural = new ContributionProceduralData
            {
                Vp = vp,
                SeedMappings = BuildSeedMappings(discoveryType, vp)
            },
            Projector = projector,
            Evidence = new ContributionEvidence
            {
                DiscoveryDataPresent = true,
                PetDataMatchedLocally = source.PetDataMatchedLocally,
                ProjectorReconstruction = "not_tested",
                OverallConfidence = "confirmed",
                Notes = null
            },
            Deduplication = new ContributionDeduplication
            {
                ScientificFingerprint = fingerprint
            }
        };
    }

    private static ContributionProjectorData BuildProjector(
        ContributionSourceRecord source,
        string discoveryType)
    {
        if (string.IsNullOrWhiteSpace(source.MessageId)) return new ContributionProjectorData();

        byte[] payload;
        try
        {
            payload = Convert.FromBase64String(source.MessageId);
        }
        catch (FormatException error)
        {
            throw new InvalidOperationException("A normalized Message ID is not valid Base64.", error);
        }

        var encoder = discoveryType switch
        {
            "Animal" => "wonder-forge.fauna.v0.1",
            "Flora" => "wonder-forge.flora.v0.1",
            "Mineral" => "wonder-forge.mineral.v0.1",
            _ => null
        };

        return new ContributionProjectorData
        {
            MessageId = source.MessageId,
            PayloadBytes = payload.Length,
            PayloadHex = Convert.ToHexString(payload),
            Provenance = "calculated",
            Encoder = encoder,
            Verification = string.Equals(discoveryType, "Animal", StringComparison.Ordinal)
                ? "confirmed"
                : "likely"
        };
    }

    private static ContributionSeedMappings BuildSeedMappings(
        string discoveryType,
        IReadOnlyList<string> vp)
    {
        if (!string.Equals(discoveryType, "Animal", StringComparison.Ordinal))
            return new ContributionSeedMappings();

        return new ContributionSeedMappings
        {
            CreatureSeed = Mapping(vp, 0, "confirmed"),
            ArchetypeGenerator = Mapping(vp, 1, "confirmed"),
            SpeciesSeed = Mapping(vp, 2, "confirmed"),
            GenusSeed = Mapping(vp, 3, "confirmed"),
            SecondarySeed = Mapping(vp, 4, "likely")
        };
    }

    private static ContributionSeedMapping? Mapping(
        IReadOnlyList<string> vp,
        int index,
        string confidence)
        => index < vp.Count
            ? new ContributionSeedMapping
            {
                VpIndex = index,
                Value = vp[index],
                Confidence = confidence
            }
            : null;

    private static string NormalizeDiscoveryType(string value)
    {
        if (string.Equals(value, "Animal", StringComparison.OrdinalIgnoreCase)) return "Animal";
        if (string.Equals(value, "Flora", StringComparison.OrdinalIgnoreCase)) return "Flora";
        if (string.Equals(value, "Mineral", StringComparison.OrdinalIgnoreCase)) return "Mineral";
        var cleaned = value.Trim();
        return string.IsNullOrWhiteSpace(cleaned) ? "Other" : cleaned;
    }

    private static string WonderCategory(string discoveryType)
        => discoveryType switch
        {
            "Animal" => "Fauna",
            "Flora" => "Flora",
            "Mineral" => "Mineral",
            _ => "Other"
        };

    private static string ArchetypeKey(string category, string? creatureId)
    {
        var prefix = category.ToLowerInvariant();
        if (string.IsNullOrWhiteSpace(creatureId)) return $"{prefix}.unknown";
        var slug = new string(creatureId
            .ToLowerInvariant()
            .Where(character => char.IsAsciiLetterOrDigit(character) || character is '_' or '-')
            .ToArray());
        return string.IsNullOrWhiteSpace(slug) ? $"{prefix}.unknown" : $"{prefix}.{slug}";
    }

    private static string? NormalizeCreatureId(string? value)
    {
        var cleaned = CleanOptional(value)?.TrimStart('^').ToUpperInvariant();
        if (string.IsNullOrWhiteSpace(cleaned)) return null;
        return cleaned.All(character => char.IsAsciiLetterOrDigit(character) || character == '_')
            ? cleaned
            : null;
    }

    private static string? NormalizeAttribution(string? value, bool anonymous)
    {
        if (anonymous) return null;
        var cleaned = CleanOptional(value);
        if (cleaned is null)
            throw new InvalidOperationException("Enter a contributor display name or choose anonymous attribution.");
        if (cleaned.Length > 60)
            throw new InvalidOperationException("Contributor display names must be 60 characters or fewer.");
        if (cleaned.Any(char.IsControl))
            throw new InvalidOperationException("Contributor display names cannot contain control characters.");
        return cleaned;
    }

    private static string? CleanOptional(string? value)
    {
        var cleaned = value?.Trim();
        return string.IsNullOrWhiteSpace(cleaned) ? null : cleaned;
    }

    private static string PlatformFamily(string detectedPlatform, string? selectedPlatform)
    {
        var selected = selectedPlatform?.Trim().ToLowerInvariant();
        if (selected is "pc" or "playstation" or "xbox" or "nintendo" or "mac" or "unknown")
            return selected;
        if (!string.IsNullOrWhiteSpace(selected))
            throw new InvalidOperationException("The selected contribution source platform is unsupported.");
        return string.IsNullOrWhiteSpace(detectedPlatform) ? "unknown" : "pc";
    }

    private static string CreateSubmissionId(DateTimeOffset created)
        => $"WC-SUB-{created.UtcDateTime:yyyyMMddHHmmss}-{Guid.NewGuid().ToString("N")[..12]}"
            .ToUpperInvariant();

    private static bool IsFauna(ContributionSourceRecord record)
        => string.Equals(record.DiscoveryType, "Animal", StringComparison.OrdinalIgnoreCase);

    private static string Hex64(ulong value) => $"0x{value:X16}";
}
