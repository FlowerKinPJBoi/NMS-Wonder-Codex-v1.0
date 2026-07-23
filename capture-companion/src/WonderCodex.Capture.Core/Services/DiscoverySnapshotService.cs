using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using WonderCodex.Capture.Core.Models;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Capture.Core.Services;

public sealed class DiscoverySnapshotService
{
    public DiscoverySnapshot Build(
        string characterId,
        AnalysisReport report,
        DateTimeOffset? observedUtc = null)
    {
        var timestamp = observedUtc ?? DateTimeOffset.UtcNow;
        var records = new Dictionary<string, CaptureDiscovery>(StringComparer.Ordinal);

        foreach (var source in report.ContributionRecords)
        {
            var fingerprint = Fingerprint(source);
            records[fingerprint] = new CaptureDiscovery(
                fingerprint,
                Normalize(source.DiscoveryType, "Other"),
                source.UniversalAddress.ToString("X16", CultureInfo.InvariantCulture),
                source.MessageId ?? string.Empty,
                Clean(source.CreatureId),
                Clean(source.CreatureType),
                timestamp);
        }

        return new DiscoverySnapshot(characterId, timestamp, records);
    }

    public IReadOnlyList<CaptureDiscovery> FindAdded(
        DiscoverySnapshot baseline,
        DiscoverySnapshot current)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(baseline.CharacterId);
        ArgumentException.ThrowIfNullOrWhiteSpace(current.CharacterId);

        return current.Records
            .Where(item => !baseline.Records.ContainsKey(item.Key))
            .Select(item => item.Value with { DetectedUtc = current.CreatedUtc })
            .OrderBy(item => item.DiscoveryType, StringComparer.OrdinalIgnoreCase)
            .ThenBy(item => item.UniversalAddress, StringComparer.Ordinal)
            .ToArray();
    }

    public static string Fingerprint(ContributionSourceRecord source)
    {
        var canonical = string.Join('|',
            Normalize(source.DiscoveryType, "OTHER").ToUpperInvariant(),
            source.UniversalAddress.ToString("X16", CultureInfo.InvariantCulture),
            string.Join(',', source.Vp.Select(value => value.ToString("X16", CultureInfo.InvariantCulture))));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(canonical))).ToLowerInvariant();
    }

    private static string Normalize(string? value, string fallback)
        => string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();

    private static string? Clean(string? value)
        => string.IsNullOrWhiteSpace(value) ? null : value.Trim();
}
