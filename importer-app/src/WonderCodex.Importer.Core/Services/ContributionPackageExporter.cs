using System.Buffers.Binary;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed class ContributionPackageExporter
{
    private const int MaximumCompressedBytes = 25 * 1024 * 1024;
    private readonly ContributionPackageValidator _validator;

    private static readonly JsonSerializerOptions WriteOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never
    };

    public ContributionPackageExporter(ContributionPackageValidator validator)
    {
        _validator = validator;
    }

    public byte[] CreatePackage(ContributionPackageDraft draft)
    {
        ArgumentNullException.ThrowIfNull(draft);

        var manifestBytes = JsonSerializer.SerializeToUtf8Bytes(draft.Manifest, WriteOptions);
        var discoveriesBytes = JsonSerializer.SerializeToUtf8Bytes(draft.Discoveries, WriteOptions);
        var checksums = new ContributionChecksums
        {
            Files = new Dictionary<string, string>(StringComparer.Ordinal)
            {
                ["manifest.json"] = Hash(manifestBytes),
                ["discoveries.json"] = Hash(discoveriesBytes)
            }
        };
        var checksumBytes = JsonSerializer.SerializeToUtf8Bytes(checksums, WriteOptions);

        using var output = new MemoryStream();
        using (var archive = new ZipArchive(output, ZipArchiveMode.Create, leaveOpen: true))
        {
            AddEntry(archive, "manifest.json", manifestBytes);
            AddEntry(archive, "discoveries.json", discoveriesBytes);
            AddEntry(archive, "checksums.json", checksumBytes);
        }

        var package = output.ToArray();
        if (package.Length > MaximumCompressedBytes)
            throw new InvalidOperationException("The contribution package exceeds the 25 MiB compressed limit.");

        var validation = _validator.Validate(package);
        if (!validation.IsValid)
            throw new InvalidOperationException(
                "The contribution package failed self-validation: " + string.Join(" ", validation.Errors));

        return package;
    }

    public async Task<ContributionExportResult> ExportAsync(
        Stream destination,
        ContributionPackageDraft draft,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(destination);
        if (!destination.CanWrite)
            throw new InvalidOperationException("The selected contribution destination is not writable.");

        var package = CreatePackage(draft);
        if (destination.CanSeek) destination.SetLength(0);
        await destination.WriteAsync(package, cancellationToken);
        await destination.FlushAsync(cancellationToken);

        return new ContributionExportResult
        {
            RecordCount = draft.Manifest.RecordCount,
            PackageBytes = package.Length,
            SubmissionId = draft.Manifest.SubmissionId
        };
    }

    private static void AddEntry(ZipArchive archive, string name, ReadOnlySpan<byte> content)
    {
        var entry = archive.CreateEntry(name, CompressionLevel.Optimal);
        using var stream = entry.Open();
        stream.Write(content);
    }

    private static string Hash(ReadOnlySpan<byte> content)
        => Convert.ToHexString(SHA256.HashData(content)).ToLowerInvariant();
}

public sealed partial class ContributionPackageValidator
{
    private const int MaximumCompressedBytes = 25 * 1024 * 1024;
    private const long MaximumUncompressedBytes = 100L * 1024 * 1024;
    private static readonly string[] RequiredFiles = ["manifest.json", "discoveries.json", "checksums.json"];
    private static readonly HashSet<string> ProhibitedPropertyNames = new(StringComparer.OrdinalIgnoreCase)
    {
        "LID",
        "UID",
        "USN",
        "PTK",
        "TS",
        "OWS",
        "accountId",
        "savePath",
        "sourcePath",
        "computerName",
        "machineName",
        "email"
    };

    private static readonly JsonSerializerOptions ReadOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = false,
        UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow
    };

    [GeneratedRegex("^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", RegexOptions.CultureInvariant)]
    private static partial Regex ArchetypeKeyPattern();

    [GeneratedRegex("^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$", RegexOptions.CultureInvariant)]
    private static partial Regex RecordIdPattern();

    [GeneratedRegex("^[A-Z0-9_]+$", RegexOptions.CultureInvariant)]
    private static partial Regex CreatureIdPattern();

    public ContributionValidationResult Validate(ReadOnlySpan<byte> package)
    {
        var result = new ContributionValidationResult();
        if (package.Length == 0)
        {
            result.Errors.Add("WC-PKG-E001: The ZIP is empty.");
            return result;
        }
        if (package.Length > MaximumCompressedBytes)
        {
            result.Errors.Add("WC-PKG-E011: The compressed package exceeds 25 MiB.");
            return result;
        }

        try
        {
            using var input = new MemoryStream(package.ToArray(), writable: false);
            using var archive = new ZipArchive(input, ZipArchiveMode.Read, leaveOpen: false);
            ValidateArchive(archive, result);
        }
        catch (Exception error) when (error is InvalidDataException or JsonException or IOException)
        {
            result.Errors.Add($"WC-PKG-E001: The package could not be read safely: {error.Message}");
        }
        catch (Exception error) when (
            error is ArgumentException or FormatException or InvalidOperationException or
                NullReferenceException or OverflowException)
        {
            result.Errors.Add("WC-PKG-E007: The package contains an invalid or incomplete data structure.");
        }

        return result;
    }

    private static void ValidateArchive(ZipArchive archive, ContributionValidationResult result)
    {
        var names = archive.Entries.Select(entry => entry.FullName).ToArray();
        if (names.Length != RequiredFiles.Length ||
            names.Distinct(StringComparer.Ordinal).Count() != names.Length ||
            RequiredFiles.Any(required => !names.Contains(required, StringComparer.Ordinal)) ||
            names.Any(name => name.Contains('/') || name.Contains('\\') || name.Contains("..", StringComparison.Ordinal)))
        {
            result.Errors.Add("WC-PKG-E003: The ZIP must contain exactly the three required root files.");
            return;
        }

        if (archive.Entries.Sum(entry => entry.Length) > MaximumUncompressedBytes)
        {
            result.Errors.Add("WC-PKG-E011: The uncompressed package exceeds 100 MiB.");
            return;
        }

        var manifestBytes = ReadEntry(archive, "manifest.json");
        var discoveriesBytes = ReadEntry(archive, "discoveries.json");
        var checksumBytes = ReadEntry(archive, "checksums.json");

        ContributionManifest? manifest = null;
        ContributionDiscoveriesDocument? discoveries = null;
        ContributionChecksums? checksums = null;
        try
        {
            manifest = JsonSerializer.Deserialize<ContributionManifest>(manifestBytes, ReadOptions);
            discoveries = JsonSerializer.Deserialize<ContributionDiscoveriesDocument>(discoveriesBytes, ReadOptions);
            checksums = JsonSerializer.Deserialize<ContributionChecksums>(checksumBytes, ReadOptions);
        }
        catch (JsonException error)
        {
            result.Errors.Add($"WC-PKG-E007: JSON validation failed: {error.Message}");
        }

        ScanPrivacy(manifestBytes, result);
        ScanPrivacy(discoveriesBytes, result);
        ScanPrivacy(checksumBytes, result);

        if (manifest is null || discoveries is null || checksums is null) return;
        ValidateChecksums(checksums, manifestBytes, discoveriesBytes, result);
        ValidateManifest(manifest, discoveries, result);
        ValidateDiscoveries(discoveries, result);
    }

    private static void ValidateChecksums(
        ContributionChecksums checksums,
        ReadOnlySpan<byte> manifestBytes,
        ReadOnlySpan<byte> discoveriesBytes,
        ContributionValidationResult result)
    {
        if (!string.Equals(checksums.Algorithm, "sha256", StringComparison.Ordinal) ||
            checksums.Files.Count != 2 ||
            !checksums.Files.TryGetValue("manifest.json", out var manifestHash) ||
            !checksums.Files.TryGetValue("discoveries.json", out var discoveriesHash) ||
            !string.Equals(manifestHash, Hash(manifestBytes), StringComparison.Ordinal) ||
            !string.Equals(discoveriesHash, Hash(discoveriesBytes), StringComparison.Ordinal))
            result.Errors.Add("WC-PKG-E006: Package checksums do not match the JSON content.");
    }

    private static void ValidateManifest(
        ContributionManifest manifest,
        ContributionDiscoveriesDocument discoveries,
        ContributionValidationResult result)
    {
        if (!string.Equals(manifest.PackageType, "wondercodex.contribution", StringComparison.Ordinal) ||
            !string.Equals(manifest.SchemaVersion, "0.1", StringComparison.Ordinal) ||
            !string.Equals(discoveries.SchemaVersion, "0.1", StringComparison.Ordinal))
            result.Errors.Add("WC-PKG-E002: Package type or schema version is unsupported.");

        if (manifest.RecordCount != discoveries.Records.Count || manifest.RecordCount is < 1 or > 10000)
            result.Errors.Add("WC-PKG-E005: Manifest record count does not match discoveries.json.");

        if (string.IsNullOrWhiteSpace(manifest.SubmissionId) || manifest.SubmissionId.Length is < 8 or > 80)
            result.Errors.Add("WC-PKG-E007: Submission ID is invalid.");

        if (string.IsNullOrWhiteSpace(manifest.Importer.Name) || manifest.Importer.Name.Length > 80 ||
            string.IsNullOrWhiteSpace(manifest.Importer.Version) || manifest.Importer.Version.Length > 40)
            result.Errors.Add("WC-PKG-E007: Importer identity is invalid.");

        var platforms = new[] { "pc", "playstation", "xbox", "nintendo", "mac", "unknown" };
        var acquisitionMethods = new[] { "local_pc_save", "official_cross_save_to_pc", "unknown" };
        if (!platforms.Contains(manifest.Source.PlatformFamily, StringComparer.Ordinal) ||
            !acquisitionMethods.Contains(manifest.Source.AcquisitionMethod, StringComparer.Ordinal))
            result.Errors.Add("WC-PKG-E007: Source platform or acquisition method is invalid.");

        var crossSaveOrigin = manifest.Source.PlatformFamily is
            "playstation" or "xbox" or "nintendo" or "mac";
        if ((crossSaveOrigin && manifest.Source.AcquisitionMethod != "official_cross_save_to_pc") ||
            (!crossSaveOrigin && manifest.Source.AcquisitionMethod == "official_cross_save_to_pc") ||
            (manifest.Source.PlatformFamily == "pc" && manifest.Source.AcquisitionMethod != "local_pc_save") ||
            (manifest.Source.AcquisitionMethod == "unknown" && manifest.Source.PlatformFamily != "unknown"))
            result.Errors.Add("WC-PKG-E007: Source platform and acquisition method are inconsistent.");

        if (!manifest.CreatedUtc.EndsWith('Z') || !DateTimeOffset.TryParse(manifest.CreatedUtc, out _))
            result.Errors.Add("WC-PKG-E007: createdUtc must be a valid UTC timestamp ending in Z.");

        if (!string.Equals(manifest.Privacy.Profile, "wc-sanitized-v0.1", StringComparison.Ordinal) ||
            manifest.Privacy.RawSaveIncluded ||
            manifest.Privacy.AccountIdentifiersIncluded ||
            manifest.Privacy.LocalPathsIncluded ||
            manifest.Privacy.MediaIncluded)
            result.Errors.Add("WC-PKG-E004: The privacy manifest does not satisfy wc-sanitized-v0.1.");

        if (!string.Equals(manifest.Content.DiscoveriesFile, "discoveries.json", StringComparison.Ordinal) ||
            !string.Equals(manifest.Content.ChecksumsFile, "checksums.json", StringComparison.Ordinal))
            result.Errors.Add("WC-PKG-E003: Manifest content filenames are invalid.");

        var attributionIsValid = manifest.Attribution.Preference switch
        {
            "anonymous" => manifest.Attribution.DisplayName is null,
            "credited" => manifest.Attribution.DisplayName is { Length: <= 60 } displayName &&
                          !string.IsNullOrWhiteSpace(displayName),
            _ => false
        };
        if (!attributionIsValid)
            result.Errors.Add("WC-PKG-E007: Attribution preference and display name are inconsistent.");
    }

    private static void ValidateDiscoveries(
        ContributionDiscoveriesDocument document,
        ContributionValidationResult result)
    {
        var recordIds = new HashSet<string>(StringComparer.Ordinal);
        foreach (var record in document.Records)
        {
            if (!RecordIdPattern().IsMatch(record.PackageRecordId))
                result.Errors.Add($"WC-PKG-E007: Invalid packageRecordId {record.PackageRecordId}.");
            else if (!recordIds.Add(record.PackageRecordId))
                result.Errors.Add($"WC-PKG-E007: Duplicate packageRecordId {record.PackageRecordId}.");

            ValidateClassification(record, result);
            ValidateLocation(record, result);
            ValidateProceduralData(record, result);
            ValidateProjector(record, result);
            ValidateFingerprint(record, result);
        }
    }

    private static void ValidateClassification(
        ContributionDiscoveryRecord record,
        ContributionValidationResult result)
    {
        var classification = record.Classification;
        if (!string.Equals(record.RecordType, "discovery", StringComparison.Ordinal) ||
            string.IsNullOrWhiteSpace(classification.DiscoveryType) || classification.DiscoveryType.Length > 40 ||
            !new[] { "Fauna", "Flora", "Mineral", "Other" }
                .Contains(classification.WonderCategory, StringComparer.Ordinal))
            result.Errors.Add($"WC-PKG-E007: Classification is invalid in {record.PackageRecordId}.");

        if (classification.CreatureId is not null &&
            (!CreatureIdPattern().IsMatch(classification.CreatureId) || classification.CreatureId.Length > 80))
            result.Errors.Add($"WC-PKG-E007: Creature ID is invalid in {record.PackageRecordId}.");

        if (!ArchetypeKeyPattern().IsMatch(classification.ArchetypeKey) ||
            classification.ArchetypeKey.Length > 100)
            result.Errors.Add($"WC-PKG-E007: Invalid archetype key in {record.PackageRecordId}.");

        if (classification.Descriptors.Count > 128 ||
            classification.Descriptors.Any(value => string.IsNullOrWhiteSpace(value) || value.Length > 100) ||
            classification.Descriptors.Distinct(StringComparer.Ordinal).Count() != classification.Descriptors.Count)
            result.Errors.Add($"WC-PKG-E007: Descriptor list is invalid in {record.PackageRecordId}.");
    }

    private static void ValidateLocation(
        ContributionDiscoveryRecord record,
        ContributionValidationResult result)
    {
        var ua = record.Location.UniversalAddress;
        if (!IsNormalizedHex(ua, 14, prefixed: true))
        {
            result.Errors.Add($"WC-PKG-E007: Invalid UA in {record.PackageRecordId}.");
            return;
        }

        var digits = ua[2..];
        var expectedPortal = string.Concat(digits.AsSpan(0, 4), digits.AsSpan(6));
        if (!string.Equals(record.Location.PortalAddressHex, expectedPortal, StringComparison.Ordinal) ||
            record.Location.Glyphs.Count != 12 ||
            !record.Location.Glyphs.SequenceEqual(expectedPortal.Select(character => character.ToString())))
            result.Errors.Add($"WC-PKG-E008: Portal derivation mismatch in {record.PackageRecordId}.");

        if (!string.Equals(record.Location.PortalDerivation.Method, "ua-remove-rr-v1", StringComparison.Ordinal) ||
            !string.Equals(record.Location.PortalDerivation.Confidence, "confirmed", StringComparison.Ordinal))
            result.Errors.Add($"WC-PKG-E008: Portal derivation metadata mismatch in {record.PackageRecordId}.");

        if (record.Location.GalaxyNumber is < 1 or > 256)
            result.Errors.Add($"WC-PKG-E007: Galaxy number is outside 1-256 in {record.PackageRecordId}.");
    }

    private static void ValidateProceduralData(
        ContributionDiscoveryRecord record,
        ContributionValidationResult result)
    {
        var vp = record.Procedural.Vp;
        if (vp.Count is < 1 or > 32 || vp.Any(value => !IsNormalizedHex(value, 16, prefixed: true)))
            result.Errors.Add($"WC-PKG-E007: VP normalization failed in {record.PackageRecordId}.");

        ValidateMapping(record, record.Procedural.SeedMappings.CreatureSeed, result);
        ValidateMapping(record, record.Procedural.SeedMappings.ArchetypeGenerator, result);
        ValidateMapping(record, record.Procedural.SeedMappings.SpeciesSeed, result);
        ValidateMapping(record, record.Procedural.SeedMappings.GenusSeed, result);
        ValidateMapping(record, record.Procedural.SeedMappings.SecondarySeed, result);
    }

    private static void ValidateMapping(
        ContributionDiscoveryRecord record,
        ContributionSeedMapping? mapping,
        ContributionValidationResult result)
    {
        if (mapping is null) return;
        if (mapping.VpIndex < 0 || mapping.VpIndex >= record.Procedural.Vp.Count ||
            !string.Equals(mapping.Value, record.Procedural.Vp[mapping.VpIndex], StringComparison.Ordinal) ||
            !IsConfidence(mapping.Confidence))
            result.Errors.Add($"WC-PKG-E007: Seed mapping mismatch in {record.PackageRecordId}.");
    }

    private static void ValidateProjector(
        ContributionDiscoveryRecord record,
        ContributionValidationResult result)
    {
        var projector = record.Projector;
        if (projector.MessageId is null)
        {
            if (projector.PayloadBytes is not null || projector.PayloadHex is not null ||
                projector.Encoder is not null || !string.Equals(projector.Provenance, "unavailable", StringComparison.Ordinal))
                result.Errors.Add($"WC-PKG-E009: Unavailable projector fields are inconsistent in {record.PackageRecordId}.");
            return;
        }

        if (!new[] { "extracted", "calculated" }.Contains(projector.Provenance, StringComparer.Ordinal) ||
            !IsConfidence(projector.Verification))
            result.Errors.Add($"WC-PKG-E009: Projector provenance is invalid in {record.PackageRecordId}.");

        byte[] payload;
        try
        {
            payload = Convert.FromBase64String(projector.MessageId);
        }
        catch (FormatException)
        {
            result.Errors.Add($"WC-PKG-E009: Message ID is not Base64 in {record.PackageRecordId}.");
            return;
        }

        if (projector.PayloadBytes != payload.Length ||
            !string.Equals(projector.PayloadHex, Convert.ToHexString(payload), StringComparison.Ordinal) ||
            projector.PayloadHex is null || projector.PayloadHex.Length > 512)
            result.Errors.Add($"WC-PKG-E009: Projector payload mismatch in {record.PackageRecordId}.");

        var reconstructionValues = new[] { "confirmed", "failed", "not_tested", "not_applicable" };
        if (!reconstructionValues.Contains(record.Evidence.ProjectorReconstruction, StringComparer.Ordinal) ||
            !IsConfidence(record.Evidence.OverallConfidence))
            result.Errors.Add($"WC-PKG-E007: Evidence confidence is invalid in {record.PackageRecordId}.");

        if (!string.Equals(record.Classification.DiscoveryType, "Animal", StringComparison.Ordinal)) return;
        if (record.Procedural.Vp.Count < 3 || payload.Length != 40)
        {
            result.Errors.Add($"WC-PKG-E009: Fauna payload shape is invalid in {record.PackageRecordId}.");
            return;
        }

        var expected = new byte[40];
        BinaryPrimitives.WriteUInt64LittleEndian(
            expected.AsSpan(0, 8),
            Convert.ToUInt64(record.Location.UniversalAddress[2..], 16));
        BinaryPrimitives.WriteInt32LittleEndian(expected.AsSpan(8, 4), 3);
        BinaryPrimitives.WriteInt32LittleEndian(expected.AsSpan(12, 4), 3);
        for (var index = 0; index < 3; index++)
        {
            BinaryPrimitives.WriteUInt64LittleEndian(
                expected.AsSpan(16 + index * 8, 8),
                Convert.ToUInt64(record.Procedural.Vp[index][2..], 16));
        }

        if (!payload.SequenceEqual(expected))
            result.Errors.Add($"WC-PKG-E009: Fauna encoder mismatch in {record.PackageRecordId}.");
    }

    private static void ValidateFingerprint(
        ContributionDiscoveryRecord record,
        ContributionValidationResult result)
    {
        var canonical = string.Join("|", new[]
        {
            record.Classification.DiscoveryType,
            record.Location.UniversalAddress
        }.Concat(record.Procedural.Vp));
        var expected = Hash(Encoding.UTF8.GetBytes(canonical));
        if (!string.Equals(record.Deduplication.Algorithm, "wc-discovery-sha256-v0.1", StringComparison.Ordinal) ||
            !string.Equals(record.Deduplication.CanonicalForm, "DiscoveryType|UA|VP*", StringComparison.Ordinal) ||
            !string.Equals(record.Deduplication.ScientificFingerprint, expected, StringComparison.Ordinal))
            result.Errors.Add($"WC-PKG-E010: Scientific fingerprint mismatch in {record.PackageRecordId}.");
    }

    private static void ScanPrivacy(ReadOnlySpan<byte> json, ContributionValidationResult result)
    {
        using var document = JsonDocument.Parse(json.ToArray());
        ScanPrivacy(document.RootElement, result);
    }

    private static void ScanPrivacy(JsonElement element, ContributionValidationResult result)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                foreach (var property in element.EnumerateObject())
                {
                    if (ProhibitedPropertyNames.Contains(property.Name))
                        result.Errors.Add($"WC-PKG-E004: Prohibited property {property.Name} was detected.");
                    ScanPrivacy(property.Value, result);
                }
                break;
            case JsonValueKind.Array:
                foreach (var item in element.EnumerateArray()) ScanPrivacy(item, result);
                break;
            case JsonValueKind.String:
                var value = element.GetString() ?? string.Empty;
                if (LooksLikeLocalPath(value))
                    result.Errors.Add("WC-PKG-E004: A local file path was detected.");
                break;
        }
    }

    private static bool LooksLikeLocalPath(string value)
        => value.StartsWith("\\\\", StringComparison.Ordinal) ||
           value.StartsWith("/Users/", StringComparison.OrdinalIgnoreCase) ||
           value.StartsWith("/home/", StringComparison.OrdinalIgnoreCase) ||
           value.StartsWith("file://", StringComparison.OrdinalIgnoreCase) ||
           (value.Length >= 3 && char.IsAsciiLetter(value[0]) && value[1] == ':' &&
            value[2] is '\\' or '/');

    private static byte[] ReadEntry(ZipArchive archive, string name)
    {
        var entry = archive.GetEntry(name) ?? throw new InvalidDataException($"Missing {name}.");
        using var source = entry.Open();
        using var destination = new MemoryStream();
        source.CopyTo(destination);
        return destination.ToArray();
    }

    private static bool IsNormalizedHex(string value, int digits, bool prefixed)
    {
        var expectedLength = digits + (prefixed ? 2 : 0);
        if (value.Length != expectedLength) return false;
        var offset = prefixed ? 2 : 0;
        if (prefixed && !value.StartsWith("0x", StringComparison.Ordinal)) return false;
        for (var index = offset; index < value.Length; index++)
        {
            var character = value[index];
            if (!char.IsAsciiDigit(character) && character is not (>= 'A' and <= 'F')) return false;
        }
        return true;
    }

    private static bool IsConfidence(string value)
        => value is "confirmed" or "likely" or "hypothesis";

    private static string Hash(ReadOnlySpan<byte> content)
        => Convert.ToHexString(SHA256.HashData(content)).ToLowerInvariant();
}
