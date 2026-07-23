namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record TransitPatch(
    byte[] JsonBytes,
    TransitLocation Before,
    TransitLocation After,
    int SaveVersion);
