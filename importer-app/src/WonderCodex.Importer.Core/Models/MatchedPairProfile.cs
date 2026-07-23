using System.Text.Json;

namespace WonderCodex.Importer.Core.Models;

public sealed class MatchedPairProfile
{
    public string Version { get; init; } = "Wonder Codex Importer 0.1.8.1";
    public string GeneratedUtc { get; init; } = DateTimeOffset.UtcNow.ToString("O");
    public int ComparedNodes { get; init; }
    public int AcceptedMappings { get; init; }
    public int ConflictingKeys { get; init; }
    public IReadOnlyDictionary<string, string> Mapping { get; init; } =
        new Dictionary<string, string>(StringComparer.Ordinal);
    public IReadOnlyList<MappingEvidence> Evidence { get; init; } = [];

    public IReadOnlyList<string> PreviewLines =>
        Evidence
            .OrderByDescending(item => item.Observations)
            .ThenBy(item => item.CompactKey, StringComparer.Ordinal)
            .Take(120)
            .Select(item =>
                $"{item.CompactKey,-8} → {item.ReadableKey,-34} " +
                $"obs={item.Observations,-5} score={item.Score,-6} {item.Context}")
            .ToArray();

    public string ToRedactedJson()
    {
        var payload = new
        {
            version = Version,
            generated_utc = GeneratedUtc,
            compared_nodes = ComparedNodes,
            accepted_mappings = AcceptedMappings,
            conflicting_keys = ConflictingKeys,
            evidence = Evidence.Select(item => new
            {
                compact_key = item.CompactKey,
                readable_key = item.ReadableKey,
                observations = item.Observations,
                score = item.Score,
                context = item.Context
            })
        };

        return JsonSerializer.Serialize(payload, new JsonSerializerOptions
        {
            WriteIndented = true
        });
    }
}

public sealed record MappingEvidence(
    string CompactKey,
    string ReadableKey,
    int Observations,
    int Score,
    string Context);
