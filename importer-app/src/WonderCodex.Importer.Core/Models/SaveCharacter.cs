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
    bool IsDecodedJson = false)
{
    public string PlatformLabel => Platform switch
    {
        SavePlatform.XboxGamePass => "Xbox / Game Pass PC",
        SavePlatform.Gog => "GOG",
        SavePlatform.ManualJson => "Manual JSON",
        _ => "Steam"
    };

    public string DetailLine => $"{SlotLabel} • {LastModifiedUtc.LocalDateTime:g} • {FormatBytes(FileSize)}";

    private static string FormatBytes(long value)
    {
        if (value < 1024) return $"{value} B";
        if (value < 1024 * 1024) return $"{value / 1024d:0.0} KB";
        return $"{value / 1024d / 1024d:0.0} MB";
    }
}
