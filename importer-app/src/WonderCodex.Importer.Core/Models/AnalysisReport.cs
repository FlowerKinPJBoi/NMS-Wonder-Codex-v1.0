using System.Text.Json.Serialization;

namespace WonderCodex.Importer.Core.Models;

public sealed class AnalysisReport
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "Wonder Codex Importer 0.1.0";

    [JsonPropertyName("createdUTC")]
    public string CreatedUtc { get; set; } = DateTimeOffset.UtcNow.ToString("O");

    [JsonPropertyName("contributor")]
    public string Contributor { get; set; } = string.Empty;

    [JsonPropertyName("publicAttribution")]
    public bool PublicAttribution { get; set; } = true;

    [JsonPropertyName("saveName")]
    public string SaveName { get; set; } = "Unknown Save";

    [JsonPropertyName("platform")]
    public string Platform { get; set; } = string.Empty;

    [JsonPropertyName("summary")]
    public Dictionary<string, object?> Summary { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("matches")]
    public List<Dictionary<string, object?>> Matches { get; init; } = [];

    [JsonPropertyName("discoveries")]
    public List<Dictionary<string, object?>> Discoveries { get; init; } = [];

    [JsonPropertyName("issues")]
    public List<Dictionary<string, object?>> Issues { get; init; } = [];

    [JsonPropertyName("website")]
    public string Website { get; set; } = string.Empty;

    [JsonIgnore]
    public int DiscoveryCount => Discoveries.Count;

    [JsonIgnore]
    public int MatchCount => Matches.Count;

    [JsonIgnore]
    public int IssueCount => Issues.Count;

    [JsonIgnore]
    public IReadOnlyList<string> PreviewLines => Discoveries
        .Take(100)
        .Select(row => $"{Value(row, "DT", "Other"),-8}  {Value(row, "UA")}  {Value(row, "MessageID")}")
        .ToArray();

    private static string Value(IReadOnlyDictionary<string, object?> row, string key, string fallback = "")
        => row.TryGetValue(key, out var value) ? value?.ToString() ?? fallback : fallback;
}
