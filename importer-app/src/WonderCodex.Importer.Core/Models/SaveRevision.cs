namespace WonderCodex.Importer.Core.Models;

public sealed record SaveRevision(
    string Id,
    string Label,
    string SourcePath,
    DateTimeOffset LastModifiedUtc,
    long FileSize,
    string ContainerToken,
    bool IsPreferred = false)
{
    public string DetailLine =>
        $"{Label} • container {ContainerToken} • {LastModifiedUtc.LocalDateTime:g} • {FormatBytes(FileSize)}";

    private static string FormatBytes(long value)
    {
        if (value < 1024) return $"{value} B";
        if (value < 1024 * 1024) return $"{value / 1024d:0.0} KB";
        return $"{value / 1024d / 1024d:0.0} MB";
    }
}
