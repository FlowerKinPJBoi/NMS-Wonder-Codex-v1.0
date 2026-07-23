using System.Text.Json.Serialization;

namespace WonderCodex.Importer.Core.Models;

public sealed class PegasusAssetRecord
{
    [JsonPropertyName("assetType")]
    public string AssetType { get; init; } = string.Empty;

    [JsonPropertyName("assetKey")]
    public string AssetKey { get; init; } = string.Empty;

    [JsonPropertyName("displayName")]
    public string DisplayName { get; init; } = string.Empty;

    [JsonPropertyName("sourceRole")]
    public string SourceRole { get; init; } = "unknown";

    [JsonPropertyName("sourceCollection")]
    public string SourceCollection { get; init; } = string.Empty;

    [JsonPropertyName("sourceOrdinal")]
    public int? SourceOrdinal { get; init; }

    [JsonPropertyName("identityBasis")]
    public string IdentityBasis { get; init; } = "normalized_asset_key";

    [JsonPropertyName("publicationState")]
    public string PublicationState { get; init; } = "review";

    [JsonPropertyName("modifiedOrSpecialSignal")]
    public bool ModifiedOrSpecialSignal { get; init; }

    [JsonPropertyName("deliveryEligibility")]
    public string DeliveryEligibility { get; init; } = "research_only";

    [JsonPropertyName("deliveryEvidenceStatus")]
    public string DeliveryEvidenceStatus { get; init; } = "not_evaluated";

    [JsonPropertyName("deliveryLane")]
    public string DeliveryLane { get; init; } = "Research";

    [JsonPropertyName("confidence")]
    public string Confidence { get; init; } = "Beta extracted";

    [JsonPropertyName("fields")]
    public Dictionary<string, object?> Fields { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    [JsonIgnore]
    public string PreviewLine
    {
        get
        {
            var detail = Fields.TryGetValue("class", out var assetClass) && assetClass is not null
                ? $" • class {assetClass}"
                : Fields.TryGetValue("creatureType", out var creatureType) && creatureType is not null
                    ? $" • {creatureType}"
                    : string.Empty;
            return $"{AssetType,-18} {DisplayName}{detail} • {SourceRole} • {DeliveryLane}";
        }
    }
}
