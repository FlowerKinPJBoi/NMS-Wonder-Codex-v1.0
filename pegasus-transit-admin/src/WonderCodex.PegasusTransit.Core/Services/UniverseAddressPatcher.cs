using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;
using WonderCodex.PegasusTransit.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class UniverseAddressPatcher
{
    public const int SupportedSaveVersion = 4733;

    private static readonly JsonSerializerOptions CompactJson = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        WriteIndented = false
    };

    public TransitPatch CreatePatch(JsonDocument document, TransitDestination destination)
    {
        ArgumentNullException.ThrowIfNull(document);
        ArgumentNullException.ThrowIfNull(destination);

        var root = JsonNode.Parse(document.RootElement.GetRawText()) as JsonObject
            ?? throw new InvalidDataException("The save root is not a JSON object.");
        var version = RequiredInt(root, "F2P", "Version");
        if (version != SupportedSaveVersion)
            throw new NotSupportedException(
                $"Pegasus Transit supports save version {SupportedSaveVersion}; this save is version {version}.");

        var playerState = RequiredObject(RequiredObject(root, "vLc", "BaseContext"), "6f=", "PlayerStateData");
        var current = RequiredObject(playerState, "yhJ", "UniverseAddress");
        var previous = RequiredObject(playerState, "ux@", "PreviousUniverseAddress");

        var before = ReadLocation(current);
        WriteLocation(previous, before);
        var after = new TransitLocation(
            destination.RealityIndex,
            destination.VoxelX,
            destination.VoxelY,
            destination.VoxelZ,
            destination.SolarSystemIndex,
            destination.PlanetIndex);
        WriteLocation(current, after);

        return new TransitPatch(
            Encoding.UTF8.GetBytes(root.ToJsonString(CompactJson)),
            before,
            after,
            version);
    }

    public TransitLocation ReadLocation(JsonDocument document)
    {
        var root = document.RootElement;
        var baseContext = RequiredProperty(root, "vLc", "BaseContext");
        var playerState = RequiredProperty(baseContext, "6f=", "PlayerStateData");
        var current = RequiredProperty(playerState, "yhJ", "UniverseAddress");
        return ReadLocation(current);
    }

    private static TransitLocation ReadLocation(JsonObject address)
    {
        var galactic = RequiredObject(address, "oZw", "GalacticAddress");
        return new TransitLocation(
            RequiredInt(address, "Iis", "RealityIndex"),
            RequiredInt(galactic, "dZj", "VoxelX"),
            RequiredInt(galactic, "IyE", "VoxelY"),
            RequiredInt(galactic, "uXE", "VoxelZ"),
            RequiredInt(galactic, "vby", "SolarSystemIndex"),
            RequiredInt(galactic, "jsv", "PlanetIndex"));
    }

    private static TransitLocation ReadLocation(JsonElement address)
    {
        var galactic = RequiredProperty(address, "oZw", "GalacticAddress");
        return new TransitLocation(
            RequiredInt(address, "Iis", "RealityIndex"),
            RequiredInt(galactic, "dZj", "VoxelX"),
            RequiredInt(galactic, "IyE", "VoxelY"),
            RequiredInt(galactic, "uXE", "VoxelZ"),
            RequiredInt(galactic, "vby", "SolarSystemIndex"),
            RequiredInt(galactic, "jsv", "PlanetIndex"));
    }

    private static void WriteLocation(JsonObject address, TransitLocation location)
    {
        address["Iis"] = location.RealityIndex;
        var galactic = RequiredObject(address, "oZw", "GalacticAddress");
        galactic["dZj"] = location.VoxelX;
        galactic["IyE"] = location.VoxelY;
        galactic["uXE"] = location.VoxelZ;
        galactic["vby"] = location.SolarSystemIndex;
        galactic["jsv"] = location.PlanetIndex;
    }

    private static JsonObject RequiredObject(JsonObject parent, string compactKey, string readableName)
        => parent[compactKey] as JsonObject
           ?? throw new InvalidDataException($"The save is missing {readableName} ({compactKey}).");

    private static int RequiredInt(JsonObject parent, string compactKey, string readableName)
        => parent[compactKey]?.GetValue<int>()
           ?? throw new InvalidDataException($"The save is missing {readableName} ({compactKey}).");

    private static JsonElement RequiredProperty(JsonElement parent, string compactKey, string readableName)
        => parent.TryGetProperty(compactKey, out var value)
            ? value
            : throw new InvalidDataException($"The save is missing {readableName} ({compactKey}).");

    private static int RequiredInt(JsonElement parent, string compactKey, string readableName)
        => RequiredProperty(parent, compactKey, readableName).GetInt32();
}
