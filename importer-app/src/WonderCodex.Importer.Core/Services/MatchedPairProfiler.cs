using System.Text.Json;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed class MatchedPairProfiler
{
    private const int MaxDepth = 220;
    private const int MaxObjectProperties = 4000;
    private const int MaxArraySamples = 8;

    public MatchedPairProfile Profile(JsonElement compactRoot, JsonElement readableRoot)
    {
        var state = new ProfileState();
        Compare(
            compactRoot,
            readableRoot,
            compactPath: "$",
            readablePath: "$",
            depth: 0,
            state);

        var mapping = new Dictionary<string, string>(StringComparer.Ordinal);
        var evidence = new List<MappingEvidence>();
        var conflicts = 0;

        foreach (var (compactKey, candidates) in state.Votes.OrderBy(item => item.Key, StringComparer.Ordinal))
        {
            var ranked = candidates
                .OrderByDescending(item => item.Value.Score)
                .ThenByDescending(item => item.Value.Observations)
                .ThenBy(item => item.Key, StringComparer.Ordinal)
                .ToArray();

            if (ranked.Length == 0) continue;

            var best = ranked[0];
            var secondScore = ranked.Length > 1 ? ranked[1].Value.Score : -1;
            var accepted = best.Value.Score > secondScore;

            if (!accepted)
            {
                conflicts++;
                continue;
            }

            mapping[compactKey] = best.Key;
            evidence.Add(new MappingEvidence(
                compactKey,
                best.Key,
                best.Value.Observations,
                best.Value.Score,
                best.Value.BestContext));
        }

        return new MatchedPairProfile
        {
            ComparedNodes = state.ComparedNodes,
            AcceptedMappings = mapping.Count,
            ConflictingKeys = conflicts,
            Mapping = mapping,
            Evidence = evidence
        };
    }

    private static void Compare(
        JsonElement compact,
        JsonElement readable,
        string compactPath,
        string readablePath,
        int depth,
        ProfileState state)
    {
        if (depth > MaxDepth || compact.ValueKind != readable.ValueKind) return;
        state.ComparedNodes++;

        switch (compact.ValueKind)
        {
            case JsonValueKind.Object:
            {
                var compactProperties = compact.EnumerateObject().Take(MaxObjectProperties).ToArray();
                var readableProperties = readable.EnumerateObject().Take(MaxObjectProperties).ToArray();
                if (compactProperties.Length != readableProperties.Length) return;

                for (var index = 0; index < compactProperties.Length; index++)
                {
                    var compactProperty = compactProperties[index];
                    var readableProperty = readableProperties[index];
                    if (compactProperty.Value.ValueKind != readableProperty.Value.ValueKind) continue;

                    var score = ScorePair(compactProperty.Value, readableProperty.Value);
                    state.AddVote(
                        compactProperty.Name,
                        readableProperty.Name,
                        score,
                        Context(readablePath));

                    Compare(
                        compactProperty.Value,
                        readableProperty.Value,
                        $"{compactPath}.{compactProperty.Name}",
                        $"{readablePath}.{readableProperty.Name}",
                        depth + 1,
                        state);
                }

                break;
            }

            case JsonValueKind.Array:
            {
                var compactLength = compact.GetArrayLength();
                var readableLength = readable.GetArrayLength();
                if (compactLength == 0 || readableLength == 0) return;

                var comparableLength = Math.Min(compactLength, readableLength);
                foreach (var index in SampleIndices(comparableLength))
                {
                    Compare(
                        compact[index],
                        readable[index],
                        $"{compactPath}[{index}]",
                        $"{readablePath}[{index}]",
                        depth + 1,
                        state);
                }

                break;
            }
        }
    }

    private static int ScorePair(JsonElement compact, JsonElement readable)
    {
        var score = 2;

        if (compact.ValueKind == JsonValueKind.Object &&
            compact.EnumerateObject().Count() == readable.EnumerateObject().Count())
            score += 3;

        if (compact.ValueKind == JsonValueKind.Array &&
            compact.GetArrayLength() == readable.GetArrayLength())
            score += 3;

        if (IsPrimitive(compact.ValueKind) && PrimitiveEquals(compact, readable))
            score += 8;

        return score;
    }

    private static bool IsPrimitive(JsonValueKind kind) =>
        kind is JsonValueKind.String or JsonValueKind.Number or JsonValueKind.True or
            JsonValueKind.False or JsonValueKind.Null;

    private static bool PrimitiveEquals(JsonElement left, JsonElement right) =>
        string.Equals(left.GetRawText(), right.GetRawText(), StringComparison.Ordinal);

    private static IEnumerable<int> SampleIndices(int length)
    {
        if (length <= MaxArraySamples)
            return Enumerable.Range(0, length);

        var indices = new SortedSet<int>
        {
            0,
            1,
            2,
            length / 3,
            length / 2,
            (length * 2) / 3,
            length - 2,
            length - 1
        };

        return indices.Where(index => index >= 0 && index < length);
    }

    private static string Context(string readablePath)
    {
        var parts = readablePath.Split('.', StringSplitOptions.RemoveEmptyEntries);
        return string.Join('.', parts.TakeLast(3));
    }

    private sealed class ProfileState
    {
        public int ComparedNodes { get; set; }

        public Dictionary<string, Dictionary<string, VoteBucket>> Votes { get; } =
            new(StringComparer.Ordinal);

        public void AddVote(string compactKey, string readableKey, int score, string context)
        {
            if (!Votes.TryGetValue(compactKey, out var candidates))
            {
                candidates = new Dictionary<string, VoteBucket>(StringComparer.Ordinal);
                Votes[compactKey] = candidates;
            }

            if (!candidates.TryGetValue(readableKey, out var bucket))
            {
                bucket = new VoteBucket();
                candidates[readableKey] = bucket;
            }

            bucket.Observations++;
            bucket.Score += score;
            if (string.IsNullOrWhiteSpace(bucket.BestContext) || context.Length < bucket.BestContext.Length)
                bucket.BestContext = context;
        }
    }

    private sealed class VoteBucket
    {
        public int Observations { get; set; }
        public int Score { get; set; }
        public string BestContext { get; set; } = "$";
    }
}
