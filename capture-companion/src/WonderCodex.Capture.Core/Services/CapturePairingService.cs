using WonderCodex.Capture.Core.Models;

namespace WonderCodex.Capture.Core.Services;

public sealed class CapturePairingService
{
    public TimeSpan MaximumDifference { get; }

    public CapturePairingService(TimeSpan? maximumDifference = null)
    {
        MaximumDifference = maximumDifference ?? TimeSpan.FromMinutes(3);
    }

    public IReadOnlyList<CapturePairCandidate> Propose(
        IEnumerable<CaptureDiscovery> discoveries,
        IEnumerable<ScreenshotCandidate> screenshots,
        IEnumerable<CapturePairCandidate>? existing = null)
    {
        var pairs = existing?.ToList() ?? [];
        var usedDiscoveries = pairs.Select(pair => pair.Discovery.Fingerprint).ToHashSet(StringComparer.Ordinal);
        var usedScreenshots = pairs.Select(pair => pair.Screenshot.FullPath).ToHashSet(StringComparer.OrdinalIgnoreCase);

        foreach (var discovery in discoveries.Where(item => !usedDiscoveries.Contains(item.Fingerprint)))
        {
            var nearest = screenshots
                .Where(item => !usedScreenshots.Contains(item.FullPath))
                .Select(item => new
                {
                    Screenshot = item,
                    Difference = item.ObservedUtc - discovery.DetectedUtc
                })
                .Where(item => item.Difference.Duration() <= MaximumDifference)
                .OrderBy(item => item.Difference.Duration())
                .FirstOrDefault();

            if (nearest is null) continue;

            var pair = new CapturePairCandidate(
                Guid.NewGuid().ToString("N"),
                discovery,
                nearest.Screenshot,
                nearest.Difference,
                DateTimeOffset.UtcNow);
            pairs.Add(pair);
            usedDiscoveries.Add(discovery.Fingerprint);
            usedScreenshots.Add(nearest.Screenshot.FullPath);
        }

        return pairs
            .OrderByDescending(pair => pair.ProposedUtc)
            .ToArray();
    }
}
