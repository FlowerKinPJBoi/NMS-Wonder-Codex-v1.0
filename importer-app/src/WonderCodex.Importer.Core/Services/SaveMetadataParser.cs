using System.Text.Json;

namespace WonderCodex.Importer.Core.Services;

public static class SaveMetadataParser
{
    public static string GetSaveName(JsonElement root, string fallback)
    {
        if (TryNestedString(root, ["CommonStateData", "SaveName"], out var common)) return common;
        if (TryNestedString(root, ["PlayerStateData", "SaveName"], out var player)) return player;
        if (TryNestedString(root, ["SaveName"], out var direct)) return direct;
        return fallback;
    }

    public static string GetGameMode(JsonElement root)
    {
        if (TryNestedString(root, ["GameMode"], out var mode)) return mode;
        if (TryNestedString(root, ["GameModePreset"], out var preset)) return preset;
        if (TryNestedString(root, ["CommonStateData", "GameMode"], out var nested)) return nested;
        return string.Empty;
    }

    public static bool HasPlayableCharacterState(JsonElement root)
    {
        if (root.ValueKind != JsonValueKind.Object) return false;

        var hasPlayerState =
            TryNestedObject(root, ["PlayerStateData"]) ||
            TryNestedObject(root, ["BaseContext", "PlayerStateData"]);
        var hasCommonState = TryNestedObject(root, ["CommonStateData"]);
        var hasDiscoveryState = HasStructuredProperty(root, "DiscoveryManagerData");
        var hasBaseState = HasStructuredProperty(root, "PersistentPlayerBases");
        var hasTransitAddressPair =
            TryNestedObject(root, ["BaseContext", "PlayerStateData", "UniverseAddress"]) &&
            TryNestedObject(root, ["BaseContext", "PlayerStateData", "PreviousUniverseAddress"]);

        return hasPlayerState && (hasCommonState || hasDiscoveryState || hasBaseState || hasTransitAddressPair);
    }

    private static bool HasStructuredProperty(JsonElement root, string propertyName)
        => root.ValueKind == JsonValueKind.Object &&
           root.TryGetProperty(propertyName, out var value) &&
           value.ValueKind is JsonValueKind.Object or JsonValueKind.Array;

    private static bool TryNestedObject(JsonElement root, IReadOnlyList<string> path)
    {
        var current = root;
        foreach (var segment in path)
        {
            if (current.ValueKind != JsonValueKind.Object || !current.TryGetProperty(segment, out current))
                return false;
        }

        return current.ValueKind == JsonValueKind.Object;
    }

    private static bool TryNestedString(JsonElement root, IReadOnlyList<string> path, out string value)
    {
        var current = root;
        foreach (var segment in path)
        {
            if (current.ValueKind != JsonValueKind.Object || !current.TryGetProperty(segment, out current))
            {
                value = string.Empty;
                return false;
            }
        }

        if (current.ValueKind == JsonValueKind.String)
        {
            value = current.GetString()?.Trim() ?? string.Empty;
            return !string.IsNullOrWhiteSpace(value);
        }

        value = string.Empty;
        return false;
    }
}
