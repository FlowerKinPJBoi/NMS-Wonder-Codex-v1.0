namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record TransitDestination(
    int GalaxyNumber,
    int RealityIndex,
    string GalaxyName,
    string PortalGlyphs,
    string UniversalAddress,
    int VoxelX,
    int VoxelY,
    int VoxelZ,
    int SolarSystemIndex,
    int PlanetIndex = 0)
{
    public string DisplayName => string.IsNullOrWhiteSpace(GalaxyName)
        ? $"Galaxy {GalaxyNumber} — {PortalGlyphs}"
        : $"Galaxy {GalaxyNumber} — {GalaxyName} — {PortalGlyphs}";
}
