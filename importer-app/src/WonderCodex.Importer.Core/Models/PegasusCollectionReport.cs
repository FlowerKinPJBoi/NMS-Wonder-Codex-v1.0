using System.Text.Json.Serialization;

namespace WonderCodex.Importer.Core.Models;

public sealed class PegasusCollectionReport
{
    [JsonPropertyName("schema")]
    public string Schema { get; set; } = "wonder-codex-pegasus-asset-manifest/v0.2.1-beta";

    [JsonPropertyName("createdUTC")]
    public string CreatedUtc { get; set; } = DateTimeOffset.UtcNow.ToString("O");

    [JsonPropertyName("saveName")]
    public string SaveName { get; set; } = "Unknown Save";

    [JsonPropertyName("platform")]
    public string Platform { get; set; } = string.Empty;

    [JsonPropertyName("modules")]
    public Dictionary<string, bool> Modules { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("privacy")]
    public Dictionary<string, object?> Privacy { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("summary")]
    public Dictionary<string, int> Summary { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonPropertyName("assets")]
    public List<PegasusAssetRecord> Assets { get; init; } = [];

    [JsonPropertyName("notes")]
    public List<string> Notes { get; init; } = [];

    [JsonIgnore]
    public int AssetCount => Assets.Count;

    [JsonIgnore]
    public IReadOnlyList<string> PreviewLines
        => Assets.Take(120).Select(asset => asset.PreviewLine).ToArray();

    public int Count(string assetType)
        => Assets.Count(asset => string.Equals(asset.AssetType, assetType, StringComparison.OrdinalIgnoreCase));
}
