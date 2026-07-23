using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Capture.Core.Models;

public sealed record CaptureCharacterSelection(
    string AccountId,
    string CharacterId,
    string DisplayName,
    SavePlatform Platform,
    string SlotLabel,
    string? SlotKey)
{
    public string PlatformLabel => Platform switch
    {
        SavePlatform.XboxGamePass => "Xbox / Game Pass PC",
        SavePlatform.Gog => "GOG",
        SavePlatform.ManualJson => "Manual JSON",
        _ => "Steam"
    };

    public string Display => $"{DisplayName} — {PlatformLabel} — {SlotLabel}";

    public static CaptureCharacterSelection From(SaveCharacter character)
        => new(
            character.AccountId,
            character.Id,
            character.DisplayName,
            character.Platform,
            character.SlotLabel,
            character.SlotKey);
}

public sealed record CaptureDiscovery(
    string Fingerprint,
    string DiscoveryType,
    string UniversalAddress,
    string MessageId,
    string? CreatureId,
    string? CreatureType,
    DateTimeOffset DetectedUtc)
{
    public string Identity => string.IsNullOrWhiteSpace(CreatureType)
        ? DiscoveryType
        : $"{DiscoveryType} • {CreatureType}";

    public string Summary => $"{Identity} • UA {UniversalAddress}";
}

public sealed record DiscoverySnapshot(
    string CharacterId,
    DateTimeOffset CreatedUtc,
    IReadOnlyDictionary<string, CaptureDiscovery> Records)
{
    public int Count => Records.Count;
}

public sealed record ScreenshotCandidate(
    string FullPath,
    string FileName,
    DateTimeOffset ObservedUtc,
    DateTimeOffset LastWriteUtc,
    long FileSize)
{
    public string Summary => $"{FileName} • {LastWriteUtc.LocalDateTime:T}";
}

public sealed record CapturePairCandidate(
    string PairId,
    CaptureDiscovery Discovery,
    ScreenshotCandidate Screenshot,
    TimeSpan Difference,
    DateTimeOffset ProposedUtc,
    bool Confirmed = false)
{
    public string Timing => Difference.Duration().TotalSeconds < 1
        ? "same second"
        : $"{Difference.Duration().TotalSeconds:0} seconds apart";

    public string Status => Confirmed ? "CONFIRMED LOCALLY" : "REVIEW REQUIRED";
    public string Title => Discovery.Identity;
    public string Detail => $"{Discovery.UniversalAddress} • {Screenshot.FileName} • {Timing}";
}

public sealed record NormalizedDiscoveryReadResult(
    SaveCharacter Character,
    AnalysisReport Report,
    bool UsedProductionTranslation,
    string? TranslationSchema);
