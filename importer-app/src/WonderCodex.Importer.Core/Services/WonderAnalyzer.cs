using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed class WonderAnalyzer
{
    private static readonly IReadOnlyDictionary<string, TypeBlock> TypeBlocks =
        new Dictionary<string, TypeBlock>(StringComparer.OrdinalIgnoreCase)
        {
            ["Animal"] = new(3, 3, 3),
            ["Flora"] = new(4, 2, 2),
            ["Mineral"] = new(5, 2, 2)
        };

    private static readonly HashSet<string> ReadableMarkers = new(StringComparer.Ordinal)
    {
        "CommonStateData",
        "PlayerStateData",
        "DiscoveryManagerData",
        "PersistentPlayerBases",
        "SaveName",
        "CreatureID",
        "CreatureSeed",
        "SpeciesSeed",
        "GenusSeed",
        "GenerationID",
        "DD",
        "UA",
        "DT",
        "VP"
    };

    public AnalysisReport Analyze(JsonElement root, SaveCharacter character)
    {
        var scan = Scan(root);
        var saveName = SaveMetadataParser.GetSaveName(root, character.DisplayName);
        var report = new AnalysisReport
        {
            SaveName = saveName,
            Platform = character.PlatformLabel
        };

        var discoveryIndex = BuildDiscoveryIndex(scan.Discoveries);
        BuildMatches(scan.Pets, discoveryIndex, report);
        BuildDiscoveries(scan.Discoveries, report);

        var animalCount = report.Discoveries.Count(row => EqualsText(row, "DT", "Animal"));
        var floraCount = report.Discoveries.Count(row => EqualsText(row, "DT", "Flora"));
        var mineralCount = report.Discoveries.Count(row => EqualsText(row, "DT", "Mineral"));
        var otherCount = report.Discoveries.Count - animalCount - floraCount - mineralCount;
        var unmatchedPets = report.Issues.Count(row => EqualsText(row, "RecordType", "Pet"));

        report.Summary["pets"] = scan.Pets.Count;
        report.Summary["discoveries"] = report.Discoveries.Count;
        report.Summary["generations"] = scan.GenerationCount;
        report.Summary["matches"] = report.Matches.Count;
        report.Summary["unmatchedPets"] = unmatchedPets;
        report.Summary["Animal"] = animalCount;
        report.Summary["Flora"] = floraCount;
        report.Summary["Mineral"] = mineralCount;
        report.Summary["Other"] = otherCount;

        if (report.DiscoveryCount == 0 && report.MatchCount == 0)
            AddEmptyAnalysisDiagnostics(root, scan, report);

        return report;
    }

    private static ScanData Scan(JsonElement root)
    {
        var pets = new List<NodeReference>();
        var discoveries = new List<NodeReference>();
        var generationCount = 0;
        var objectCount = 0;
        var propertyCount = 0;
        var shortPropertyCount = 0;
        var readableMarkerCount = 0;
        var stack = new Stack<(JsonElement Element, string Path)>();
        stack.Push((root, "$"));

        while (stack.Count > 0)
        {
            var (element, path) = stack.Pop();
            switch (element.ValueKind)
            {
                case JsonValueKind.Array:
                    var index = 0;
                    foreach (var child in element.EnumerateArray())
                    {
                        stack.Push((child, $"{path}[{index}]") );
                        index++;
                    }
                    break;

                case JsonValueKind.Object:
                    objectCount++;
                    if (LooksLikePet(element)) pets.Add(new NodeReference(path, element.Clone()));
                    if (LooksLikeDiscovery(element)) discoveries.Add(new NodeReference(path, element.Clone()));
                    if (element.TryGetProperty("GenerationID", out var generation) && generation.ValueKind == JsonValueKind.Array)
                        generationCount++;

                    foreach (var property in element.EnumerateObject())
                    {
                        propertyCount++;
                        if (property.Name.Length <= 4) shortPropertyCount++;
                        if (ReadableMarkers.Contains(property.Name)) readableMarkerCount++;
                        stack.Push((property.Value, $"{path}.{property.Name}"));
                    }
                    break;
            }
        }

        var topLevelKeys = root.ValueKind == JsonValueKind.Object
            ? root.EnumerateObject().Select(property => property.Name).Take(24).ToArray()
            : [];

        return new ScanData(
            pets,
            discoveries,
            generationCount,
            objectCount,
            propertyCount,
            shortPropertyCount,
            readableMarkerCount,
            topLevelKeys);
    }

    private static void AddEmptyAnalysisDiagnostics(JsonElement root, ScanData scan, AnalysisReport report)
    {
        var topLevel = scan.TopLevelKeys.Count == 0
            ? "(none)"
            : string.Join(", ", scan.TopLevelKeys);

        var shortRatio = scan.PropertyCount == 0
            ? 0d
            : (double)scan.ShortPropertyCount / scan.PropertyCount;

        report.Issues.Add(new Dictionary<string, object?>
        {
            ["Severity"] = "Diagnostic",
            ["RecordType"] = "JSON",
            ["Issue"] = $"Root kind: {root.ValueKind}. Top-level keys: {topLevel}"
        });

        report.Issues.Add(new Dictionary<string, object?>
        {
            ["Severity"] = "Diagnostic",
            ["RecordType"] = "Key profile",
            ["Issue"] =
                $"{scan.ObjectCount:N0} objects; {scan.PropertyCount:N0} properties; " +
                $"{shortRatio:P0} of property names are 4 characters or shorter; " +
                $"{scan.ReadableMarkerCount:N0} readable save markers found."
        });

        report.Issues.Add(new Dictionary<string, object?>
        {
            ["Severity"] = "Diagnostic",
            ["RecordType"] = "WGS",
            ["Issue"] =
                "No readable DD/UA/DT/VP Wonder structures were found in this candidate. " +
                "This can mean the selected WGS object is not a character save, or the raw save keys still require mapping."
        });
    }

    private static bool LooksLikePet(JsonElement element)
        => element.ValueKind == JsonValueKind.Object
           && element.TryGetProperty("CreatureID", out var creatureId)
           && !string.Equals(JsonValueReader.GetString(creatureId), "^", StringComparison.Ordinal)
           && element.TryGetProperty("CreatureSeed", out _)
           && element.TryGetProperty("SpeciesSeed", out _)
           && element.TryGetProperty("GenusSeed", out _)
           && element.TryGetProperty("UA", out _);

    private static bool LooksLikeDiscovery(JsonElement element)
    {
        if (!element.TryGetProperty("DD", out var dd) || dd.ValueKind != JsonValueKind.Object) return false;
        return dd.TryGetProperty("UA", out _)
               && dd.TryGetProperty("DT", out _)
               && dd.TryGetProperty("VP", out var vp)
               && vp.ValueKind == JsonValueKind.Array;
    }

    private static Dictionary<string, List<NodeReference>> BuildDiscoveryIndex(IEnumerable<NodeReference> discoveries)
    {
        var index = new Dictionary<string, List<NodeReference>>(StringComparer.Ordinal);
        foreach (var discovery in discoveries)
        {
            if (!TryGetAnimalDiscoveryKey(discovery.Element, out var key)) continue;
            if (!index.TryGetValue(key, out var values))
            {
                values = [];
                index[key] = values;
            }
            values.Add(discovery);
        }
        return index;
    }

    private static void BuildMatches(
        IEnumerable<NodeReference> pets,
        IReadOnlyDictionary<string, List<NodeReference>> discoveryIndex,
        AnalysisReport report)
    {
        foreach (var pet in pets)
        {
            if (!TryGetPetKey(pet.Element, out var key)) continue;
            discoveryIndex.TryGetValue(key, out var candidates);
            candidates ??= [];

            var creatureId = GetCreatureId(pet.Element);
            if (candidates.Count != 1)
            {
                report.Issues.Add(new Dictionary<string, object?>
                {
                    ["Severity"] = candidates.Count > 1 ? "Warning" : "Info",
                    ["RecordType"] = "Pet",
                    ["CreatureID"] = creatureId,
                    ["UA"] = TryReadHex(pet.Element, "UA"),
                    ["Issue"] = candidates.Count > 1
                        ? "Multiple exact discovery candidates"
                        : "No exact DiscoveryData match",
                    ["Path"] = pet.Path
                });
                continue;
            }

            var discovery = candidates[0];
            var dd = discovery.Element.GetProperty("DD");
            var vp = ReadVp(dd);
            if (!JsonValueReader.TryGetUInt64(dd.GetProperty("UA"), out var ua)) continue;

            var secondarySeed = pet.Element.TryGetProperty("CreatureSecondarySeed", out var secondaryElement)
                && JsonValueReader.TryGetSeed(secondaryElement, out var parsedSecondary)
                ? parsedSecondary
                : 0UL;
            var vp4 = vp.Count > 4 ? vp[4] : 0UL;
            var creatureType = ReadCreatureType(pet.Element);

            report.Matches.Add(new Dictionary<string, object?>
            {
                ["CreatureID"] = creatureId,
                ["CreatureType"] = creatureType,
                ["UA"] = JsonValueReader.Hex(ua),
                ["VP0"] = HexAt(vp, 0),
                ["VP1"] = HexAt(vp, 1),
                ["VP2"] = HexAt(vp, 2),
                ["VP3"] = HexAt(vp, 3),
                ["VP4"] = vp.Count > 4 ? JsonValueReader.Hex(vp4) : string.Empty,
                ["SecondarySeed"] = JsonValueReader.Hex(secondarySeed),
                ["SecondaryCheck"] = secondarySeed == vp4 ? "Match" : "Different",
                ["MessageID"] = BuildMessageId("Animal", ua, vp),
                ["PetPath"] = pet.Path,
                ["DiscoveryPath"] = discovery.Path
            });
        }
    }

    private static void BuildDiscoveries(IEnumerable<NodeReference> discoveries, AnalysisReport report)
    {
        foreach (var reference in discoveries)
        {
            var record = reference.Element;
            var dd = record.GetProperty("DD");
            var dt = dd.TryGetProperty("DT", out var dtElement)
                ? JsonValueReader.GetString(dtElement, "Other")
                : "Other";
            if (!JsonValueReader.TryGetUInt64(dd.GetProperty("UA"), out var ua)) continue;
            var vp = ReadVp(dd);

            var owner = string.Empty;
            var platform = string.Empty;
            if (record.TryGetProperty("OWS", out var ows) && ows.ValueKind == JsonValueKind.Object)
            {
                if (ows.TryGetProperty("USN", out var ownerElement)) owner = JsonValueReader.GetString(ownerElement);
                if (ows.TryGetProperty("PTK", out var platformElement)) platform = JsonValueReader.GetString(platformElement);
            }

            var messageId = BuildMessageId(dt, ua, vp);

            report.Discoveries.Add(new Dictionary<string, object?>
            {
                ["DT"] = dt,
                ["UA"] = JsonValueReader.Hex(ua),
                ["VP0"] = HexAt(vp, 0),
                ["VP1"] = HexAt(vp, 1),
                ["VP2"] = HexAt(vp, 2),
                ["VP3"] = HexAt(vp, 3),
                ["VP4"] = HexAt(vp, 4),
                ["MessageID"] = messageId,
                ["Owner"] = owner,
                ["Platform"] = platform,
                ["Path"] = reference.Path
            });

            var contributionRecord = new ContributionSourceRecord
            {
                DiscoveryType = dt,
                UniversalAddress = ua,
                Vp = [.. vp],
                MessageId = string.IsNullOrWhiteSpace(messageId) ? null : messageId
            };

            if (string.Equals(dt, "Animal", StringComparison.OrdinalIgnoreCase))
            {
                var match = FindAnimalMatch(report.Matches, ua, vp);
                if (match is not null)
                {
                    contributionRecord.CreatureId = Value(match, "CreatureID");
                    contributionRecord.CreatureType = Value(match, "CreatureType");
                    contributionRecord.PetDataMatchedLocally = true;
                }
            }

            report.ContributionRecords.Add(contributionRecord);
        }
    }

    private static IReadOnlyDictionary<string, object?>? FindAnimalMatch(
        IEnumerable<Dictionary<string, object?>> matches,
        ulong ua,
        IReadOnlyList<ulong> vp)
    {
        if (vp.Count < 4) return null;

        var normalizedUa = JsonValueReader.Hex(ua);
        var vp0 = JsonValueReader.Hex(vp[0]);
        var vp2 = JsonValueReader.Hex(vp[2]);
        var vp3 = JsonValueReader.Hex(vp[3]);

        return matches.FirstOrDefault(row =>
            EqualsValue(row, "UA", normalizedUa) &&
            EqualsValue(row, "VP0", vp0) &&
            EqualsValue(row, "VP2", vp2) &&
            EqualsValue(row, "VP3", vp3));
    }

    private static bool EqualsValue(
        IReadOnlyDictionary<string, object?> row,
        string key,
        string expected)
        => row.TryGetValue(key, out var value)
           && string.Equals(value?.ToString(), expected, StringComparison.OrdinalIgnoreCase);

    private static string? Value(IReadOnlyDictionary<string, object?> row, string key)
    {
        if (!row.TryGetValue(key, out var value)) return null;
        var text = value?.ToString()?.Trim();
        return string.IsNullOrWhiteSpace(text) ? null : text;
    }

    private static bool TryGetPetKey(JsonElement pet, out string key)
    {
        key = string.Empty;
        if (!TryReadUInt64(pet, "UA", out var ua)) return false;
        if (!pet.TryGetProperty("CreatureSeed", out var creatureSeedElement)
            || !JsonValueReader.TryGetSeed(creatureSeedElement, out var creatureSeed)) return false;
        if (!TryReadUInt64(pet, "SpeciesSeed", out var speciesSeed)) return false;
        if (!TryReadUInt64(pet, "GenusSeed", out var genusSeed)) return false;
        key = string.Join('|',
            JsonValueReader.Hex(ua),
            JsonValueReader.Hex(creatureSeed),
            JsonValueReader.Hex(speciesSeed),
            JsonValueReader.Hex(genusSeed));
        return true;
    }

    private static bool TryGetAnimalDiscoveryKey(JsonElement record, out string key)
    {
        key = string.Empty;
        if (!record.TryGetProperty("DD", out var dd)) return false;
        if (!dd.TryGetProperty("DT", out var dtElement)
            || !string.Equals(JsonValueReader.GetString(dtElement), "Animal", StringComparison.OrdinalIgnoreCase)) return false;
        if (!TryReadUInt64(dd, "UA", out var ua)) return false;
        var vp = ReadVp(dd);
        if (vp.Count < 4) return false;
        key = string.Join('|',
            JsonValueReader.Hex(ua),
            JsonValueReader.Hex(vp[0]),
            JsonValueReader.Hex(vp[2]),
            JsonValueReader.Hex(vp[3]));
        return true;
    }

    private static List<ulong> ReadVp(JsonElement dd)
    {
        var values = new List<ulong>();
        if (!dd.TryGetProperty("VP", out var vpElement) || vpElement.ValueKind != JsonValueKind.Array)
            return values;
        foreach (var element in vpElement.EnumerateArray())
            values.Add(JsonValueReader.TryGetUInt64(element, out var value) ? value : 0UL);
        return values;
    }

    private static string BuildMessageId(string discoveryType, ulong ua, IReadOnlyList<ulong> vp)
    {
        if (!TypeBlocks.TryGetValue(discoveryType, out var block) || vp.Count < block.VpCount)
            return string.Empty;

        var payload = new byte[16 + block.VpCount * 8];
        BinaryPrimitives.WriteUInt64LittleEndian(payload.AsSpan(0, 8), ua);
        BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(8, 4), block.TypeCode);
        BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(12, 4), block.LayoutCode);
        for (var index = 0; index < block.VpCount; index++)
            BinaryPrimitives.WriteUInt64LittleEndian(payload.AsSpan(16 + index * 8, 8), vp[index]);
        return Convert.ToBase64String(payload);
    }

    private static bool TryReadUInt64(JsonElement element, string propertyName, out ulong value)
    {
        value = 0;
        return element.TryGetProperty(propertyName, out var property)
               && JsonValueReader.TryGetUInt64(property, out value);
    }

    private static string TryReadHex(JsonElement element, string propertyName)
        => TryReadUInt64(element, propertyName, out var value) ? JsonValueReader.Hex(value) : string.Empty;

    private static string HexAt(IReadOnlyList<ulong> values, int index)
        => index >= 0 && index < values.Count ? JsonValueReader.Hex(values[index]) : string.Empty;

    private static string GetCreatureId(JsonElement pet)
    {
        if (!pet.TryGetProperty("CreatureID", out var element)) return string.Empty;
        return JsonValueReader.GetString(element).TrimStart('^');
    }

    private static string ReadCreatureType(JsonElement pet)
    {
        if (!pet.TryGetProperty("CreatureType", out var type)) return string.Empty;
        if (type.ValueKind == JsonValueKind.Object
            && type.TryGetProperty("CreatureType", out var nested))
            return JsonValueReader.GetString(nested);
        return JsonValueReader.GetString(type);
    }

    private static bool EqualsText(IReadOnlyDictionary<string, object?> row, string key, string expected)
        => row.TryGetValue(key, out var value)
           && string.Equals(value?.ToString(), expected, StringComparison.OrdinalIgnoreCase);

    private sealed record TypeBlock(int TypeCode, int LayoutCode, int VpCount);
    private sealed record NodeReference(string Path, JsonElement Element);
    private sealed record ScanData(
        List<NodeReference> Pets,
        List<NodeReference> Discoveries,
        int GenerationCount,
        int ObjectCount,
        int PropertyCount,
        int ShortPropertyCount,
        int ReadableMarkerCount,
        IReadOnlyList<string> TopLevelKeys);
}
