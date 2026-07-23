using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed class CharacterRevisionGrouper
{
    public IReadOnlyList<SaveCharacter> Group(IReadOnlyList<SaveCharacter> candidates)
    {
        var named = candidates
            .Where(candidate => !IsGenericName(candidate.DisplayName))
            .GroupBy(BuildResolvedGroupKey, StringComparer.OrdinalIgnoreCase)
            .Select(BuildCharacter)
            .ToList();

        var generic = candidates
            .Where(candidate => IsGenericName(candidate.DisplayName))
            .ToArray();

        var playableGeneric = generic
            .Where(IsPlayableCharacterCandidate)
            .ToArray();
        var unnamedGroups = BuildUnnamedGroups(playableGeneric);
        var unnamed = unnamedGroups
            .Select((group, index) => BuildUnnamedCharacter(
                group,
                unnamedGroups.Count == 1 ? "Unnamed Character" : $"Unnamed Character {index + 1}"))
            .ToList();

        var research = generic
            .Where(candidate => !IsPlayableCharacterCandidate(candidate))
            .OrderByDescending(candidate => candidate.LastModifiedUtc)
            .Select((candidate, index) => BuildResearchCharacter(candidate, index + 1))
            .ToList();

        return named
            .Concat(unnamed)
            .Concat(research)
            .OrderBy(character => IsResearchName(character.DisplayName))
            .ThenByDescending(character => character.LastModifiedUtc)
            .ThenBy(character => character.DisplayName, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    private static string BuildResolvedGroupKey(SaveCharacter candidate)
        => !string.IsNullOrWhiteSpace(candidate.SlotKey)
            ? $"slot:{candidate.SlotKey}"
            : $"name:{candidate.DisplayName.Trim()}";

    private static SaveCharacter BuildCharacter(IGrouping<string, SaveCharacter> group)
        => BuildCharacter(group.ToArray(), group.OrderByDescending(candidate => candidate.LastModifiedUtc).First().DisplayName);

    private static SaveCharacter BuildCharacter(IReadOnlyList<SaveCharacter> source, string displayName)
    {
        var ordered = source
            .OrderByDescending(candidate => candidate.LastModifiedUtc)
            .ThenByDescending(candidate => candidate.FileSize)
            .ThenBy(candidate => candidate.SourcePath, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var preferred = ordered[0];
        var revisions = LabelRevisions(ordered.SelectMany(ToRevisions));

        return preferred with
        {
            DisplayName = displayName,
            SlotLabel = preferred.Platform == SavePlatform.XboxGamePass
                ? $"Cloud save • {revisions.Length} read-only revision{(revisions.Length == 1 ? string.Empty : "s")}"
                : preferred.SlotLabel,
            Revisions = revisions,
            SourcePath = revisions[0].SourcePath,
            LastModifiedUtc = revisions[0].LastModifiedUtc,
            FileSize = revisions[0].FileSize,
            DiscoveryCount = preferred.DiscoveryCount,
            PetCount = preferred.PetCount,
            ExactMatchCount = preferred.ExactMatchCount,
            IsAutomaticallyResolved = ordered.Any(candidate => candidate.IsAutomaticallyResolved)
        };
    }

    private static List<IReadOnlyList<SaveCharacter>> BuildUnnamedGroups(IReadOnlyList<SaveCharacter> candidates)
    {
        var pending = candidates
            .OrderByDescending(candidate => candidate.LastModifiedUtc)
            .ThenByDescending(candidate => candidate.FileSize)
            .ToList();
        var result = new List<IReadOnlyList<SaveCharacter>>();

        while (pending.Count > 0)
        {
            var seed = pending[0];
            pending.RemoveAt(0);

            var group = new List<SaveCharacter> { seed };
            var match = pending
                .Where(candidate => AreLikelyRevisions(seed, candidate))
                .OrderBy(candidate => RevisionDistance(seed, candidate))
                .FirstOrDefault();

            if (match is not null)
            {
                group.Add(match);
                pending.Remove(match);
            }

            result.Add(group);
        }

        return result;
    }

    private static bool AreLikelyRevisions(SaveCharacter left, SaveCharacter right)
    {
        if (left.Platform != right.Platform ||
            !string.Equals(left.AccountId, right.AccountId, StringComparison.OrdinalIgnoreCase))
            return false;

        if (!string.IsNullOrWhiteSpace(left.SlotKey) || !string.IsNullOrWhiteSpace(right.SlotKey))
            return !string.IsNullOrWhiteSpace(left.SlotKey) &&
                   string.Equals(left.SlotKey, right.SlotKey, StringComparison.OrdinalIgnoreCase);

        var maxDiscoveries = Math.Max(left.DiscoveryCount, right.DiscoveryCount);
        var discoveryTolerance = Math.Max(5, (int)Math.Ceiling(maxDiscoveries * 0.01));
        var maxSize = Math.Max(left.FileSize, right.FileSize);
        var sizeRatio = maxSize == 0
            ? 0d
            : Math.Abs(left.FileSize - right.FileSize) / (double)maxSize;

        var leftHasCatalog = HasCatalogSignal(left);
        var rightHasCatalog = HasCatalogSignal(right);

        if (!leftHasCatalog && !rightHasCatalog)
        {
            var timeGap = (left.LastModifiedUtc - right.LastModifiedUtc).Duration();
            return left.IsPlayableCharacterState &&
                   right.IsPlayableCharacterState &&
                   string.Equals(left.SlotLabel, right.SlotLabel, StringComparison.OrdinalIgnoreCase) &&
                   sizeRatio <= 0.10 &&
                   timeGap <= TimeSpan.FromHours(8);
        }

        return Math.Abs(left.DiscoveryCount - right.DiscoveryCount) <= discoveryTolerance &&
               Math.Abs(left.PetCount - right.PetCount) <= 1 &&
               Math.Abs(left.ExactMatchCount - right.ExactMatchCount) <= 1 &&
               sizeRatio <= 0.10;
    }

    private static double RevisionDistance(SaveCharacter left, SaveCharacter right)
    {
        var maxSize = Math.Max(left.FileSize, right.FileSize);
        var sizeDistance = maxSize == 0
            ? 0d
            : Math.Abs(left.FileSize - right.FileSize) / (double)maxSize;

        var timeDistanceHours = (left.LastModifiedUtc - right.LastModifiedUtc).Duration().TotalHours;

        return Math.Abs(left.DiscoveryCount - right.DiscoveryCount) +
               Math.Abs(left.PetCount - right.PetCount) * 3d +
               Math.Abs(left.ExactMatchCount - right.ExactMatchCount) * 3d +
               sizeDistance +
               Math.Min(timeDistanceHours, 24d) * 0.01d;
    }

    private static SaveCharacter BuildUnnamedCharacter(IReadOnlyList<SaveCharacter> group, string displayName)
    {
        var preferred = group
            .OrderByDescending(candidate => candidate.LastModifiedUtc)
            .ThenByDescending(candidate => candidate.FileSize)
            .First();

        if (!string.IsNullOrWhiteSpace(preferred.SlotKey) &&
            preferred.DisplayName.StartsWith("Unnamed Character", StringComparison.OrdinalIgnoreCase))
            displayName = preferred.DisplayName;

        return BuildCharacter(group, displayName);
    }

    private static SaveCharacter BuildResearchCharacter(SaveCharacter candidate, int number)
    {
        var revisions = LabelRevisions(ToRevisions(candidate));
        return candidate with
        {
            DisplayName = $"Research candidate {number}",
            Revisions = revisions,
            SourcePath = revisions[0].SourcePath,
            LastModifiedUtc = revisions[0].LastModifiedUtc,
            FileSize = revisions[0].FileSize
        };
    }

    private static SaveRevision[] LabelRevisions(IEnumerable<SaveRevision> source)
        => source
            .OrderByDescending(revision => revision.LastModifiedUtc)
            .ThenByDescending(revision => revision.FileSize)
            .ThenBy(revision => revision.SourcePath, StringComparer.OrdinalIgnoreCase)
            .Select((revision, index) => revision with
            {
                Label = BuildRevisionLabel(revision.Label, index),
                IsPreferred = index == 0
            })
            .ToArray();

    private static string BuildRevisionLabel(string sourceLabel, int index)
    {
        var source = string.IsNullOrWhiteSpace(sourceLabel) ||
                     string.Equals(sourceLabel, "Read-only revision", StringComparison.OrdinalIgnoreCase)
            ? string.Empty
            : $" • {sourceLabel}";

        return index == 0
            ? $"Preferred revision{source}"
            : $"Alternate revision {index + 1}{source}";
    }

    private static IEnumerable<SaveRevision> ToRevisions(SaveCharacter candidate)
    {
        if (candidate.Revisions is { Count: > 0 }) return candidate.Revisions;

        var containerPath = Path.GetDirectoryName(candidate.SourcePath) ?? candidate.SourcePath;
        return
        [
            new SaveRevision(
                candidate.Id,
                "Read-only revision",
                candidate.SourcePath,
                candidate.LastModifiedUtc,
                candidate.FileSize,
                PathRedactor.AccountToken(containerPath))
        ];
    }

    private static bool HasCatalogSignal(SaveCharacter candidate)
        => candidate.DiscoveryCount > 0 || candidate.PetCount > 0 || candidate.ExactMatchCount > 0;

    private static bool IsPlayableCharacterCandidate(SaveCharacter candidate)
        => candidate.IsPlayableCharacterState || HasCatalogSignal(candidate);

    private static bool IsGenericName(string value)
        => string.IsNullOrWhiteSpace(value) ||
           value.StartsWith("WGS candidate", StringComparison.OrdinalIgnoreCase) ||
           value.StartsWith("Unnamed Character", StringComparison.OrdinalIgnoreCase) ||
           value.StartsWith("Research candidate", StringComparison.OrdinalIgnoreCase) ||
           string.Equals(value, "Detected character", StringComparison.OrdinalIgnoreCase) ||
           string.Equals(value, "Unknown Save", StringComparison.OrdinalIgnoreCase);

    private static bool IsResearchName(string value)
        => value.StartsWith("Research candidate", StringComparison.OrdinalIgnoreCase);
}
