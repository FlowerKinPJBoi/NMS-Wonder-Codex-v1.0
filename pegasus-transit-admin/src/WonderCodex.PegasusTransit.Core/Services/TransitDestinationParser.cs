using System.Globalization;
using WonderCodex.PegasusTransit.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Services;

public static class TransitDestinationParser
{
    public static TransitDestination Parse(
        int galaxyNumber,
        string portalGlyphs,
        string? galaxyName = null)
    {
        if (galaxyNumber is < 1 or > 256)
            throw new ArgumentOutOfRangeException(nameof(galaxyNumber), "Galaxy number must be between 1 and 256.");

        var glyphs = new string((portalGlyphs ?? string.Empty)
            .Where(character => !char.IsWhiteSpace(character) && character is not '-' and not ':')
            .ToArray())
            .ToUpperInvariant();

        if (glyphs.Length != 12 || glyphs.Any(character => !Uri.IsHexDigit(character)))
            throw new FormatException("Portal glyphs must contain exactly 12 hexadecimal characters.");

        var system = ParseHex(glyphs.AsSpan(1, 3));
        var rawY = ParseHex(glyphs.AsSpan(4, 2));
        var rawZ = ParseHex(glyphs.AsSpan(6, 3));
        var rawX = ParseHex(glyphs.AsSpan(9, 3));
        var realityIndex = galaxyNumber - 1;

        return new TransitDestination(
            GalaxyNumber: galaxyNumber,
            RealityIndex: realityIndex,
            GalaxyName: galaxyName?.Trim() ?? string.Empty,
            PortalGlyphs: glyphs,
            UniversalAddress: $"0x{glyphs[0]}{glyphs.Substring(1, 3)}{realityIndex:X2}{glyphs.Substring(4, 8)}",
            VoxelX: Signed(rawX, 0x800, 0x1000),
            VoxelY: Signed(rawY, 0x80, 0x100),
            VoxelZ: Signed(rawZ, 0x800, 0x1000),
            SolarSystemIndex: system,
            PlanetIndex: 0);
    }

    private static int ParseHex(ReadOnlySpan<char> value)
        => int.Parse(value, NumberStyles.AllowHexSpecifier, CultureInfo.InvariantCulture);

    private static int Signed(int value, int signBit, int range)
        => value >= signBit ? value - range : value;
}
