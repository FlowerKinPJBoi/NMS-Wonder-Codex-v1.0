using System.Text.Json.Serialization;

namespace WonderCodex.Importer.Core.Models;

public sealed class SubmissionResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; init; }

    [JsonPropertyName("submission_id")]
    public string SubmissionId { get; init; } = string.Empty;

    [JsonPropertyName("public_attribution")]
    public bool PublicAttribution { get; init; }

    [JsonPropertyName("queued_records")]
    public RecordCounts QueuedRecords { get; init; } = new();

    [JsonPropertyName("duplicates_skipped")]
    public RecordCounts DuplicatesSkipped { get; init; } = new();
}

public sealed class RecordCounts
{
    [JsonPropertyName("discoveries")]
    public int Discoveries { get; init; }

    [JsonPropertyName("pet_matches")]
    public int PetMatches { get; init; }
}
