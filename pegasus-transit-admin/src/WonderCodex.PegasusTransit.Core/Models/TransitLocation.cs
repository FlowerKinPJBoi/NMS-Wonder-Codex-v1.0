namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record TransitLocation(
    int RealityIndex,
    int VoxelX,
    int VoxelY,
    int VoxelZ,
    int SolarSystemIndex,
    int PlanetIndex)
{
    public int GalaxyNumber => RealityIndex + 1;

    public string CoordinateSummary =>
        $"Galaxy {GalaxyNumber}; X {VoxelX}; Y {VoxelY}; Z {VoxelZ}; system {SolarSystemIndex}; planet {PlanetIndex}";
}
