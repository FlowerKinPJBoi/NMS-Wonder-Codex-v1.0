namespace WonderCodex.Importer.Core.Models;

public sealed record SaveCharacter(
    string Id,
    string AccountId,
    string DisplayName,
    string SlotLabel,
    SavePlatform Platform,
    string SourcePath,
    DateTimeOffset LastModifiedUtc,
    long FileSize,
    bool IsDecodedJson = false,
    IReadOnlyList<SaveRevision>? Revisions = null,
    int DiscoveryCount = 0,
    int PetCount = 0,
    int ExactMatchCount = 0,
    bool IsAutomaticallyResolved = false,
    string? SlotKey = null,
    bool IsPlayableCharacterState = false)
{
    public string PlatformLabel => Platform switch
    {
        SavePlatform.XboxGamePass => "Xbox / Game Pass PC",
        SavePlatform.Gog => "GOG",
        SavePlatform.ManualJson => "Manual JSON",
        _ => "Steam"
    };

    public IReadOnlyList<SaveRevision> ReadOnlyRevisions => Revisions ?? [];

    public int RevisionCount => ReadOnlyRevisions.Count > 0 ? ReadOnlyRevisions.Count : 1;

    public string RevisionSummary => RevisionCount == 1
        ? "1 read-only revision"
        : $"{RevisionCount} read-only revisions grouped • newest selected";

    public string CatalogSummary => DiscoveryCount > 0 || PetCount > 0 || ExactMatchCount > 0
        ? $"{DiscoveryCount:N0} discoveries • {PetCount:N0} pets • {ExactMatchCount:N0} exact matches"
        : RevisionSummary;

    public string DetailLine =>
        $"{SlotLabel} • {LastModifiedUtc.LocalDateTime:g} • {FormatBytes(FileSize)}";

    private static string FormatBytes(long value)
    {
        if (value < 1024) return $"{value} B";
        if (value < 1024 * 1024) return $"{value / 1024d:0.0} KB";
        return $"{value / 1024d / 1024d:0.0} MB";
    }
}
