using WonderCodex.Importer.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record TransitPlan(
    SaveCharacter Character,
    TransitDestination Destination,
    TransitLocation CurrentLocation,
    string SourceSha256,
    DateTimeOffset PreparedUtc,
    string OperatorName,
    string? WonderRecordId);
