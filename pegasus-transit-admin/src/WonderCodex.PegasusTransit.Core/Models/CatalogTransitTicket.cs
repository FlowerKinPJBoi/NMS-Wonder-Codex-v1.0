using System.Text.Json.Serialization;

namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record CatalogTransitTicket
{
    [JsonPropertyName("format")]
    public string Format { get; init; } = string.Empty;

    [JsonPropertyName("wc_record_id")]
    public string WonderRecordId { get; init; } = string.Empty;

    [JsonPropertyName("galaxy_number")]
    public int GalaxyNumber { get; init; }

    [JsonPropertyName("galaxy_name")]
    public string GalaxyName { get; init; } = string.Empty;

    [JsonPropertyName("portal_glyphs")]
    public string PortalGlyphs { get; init; } = string.Empty;

    [JsonPropertyName("universal_address")]
    public string UniversalAddress { get; init; } = string.Empty;

    public TransitDestination ValidateAndBuildDestination()
    {
        if (!string.Equals(Format, "wonder-codex-transit/0.1", StringComparison.Ordinal))
            throw new InvalidDataException("This is not a supported Wonder Codex transit ticket.");
        var destination = WonderCodex.PegasusTransit.Core.Services.TransitDestinationParser.Parse(
            GalaxyNumber,
            PortalGlyphs,
            GalaxyName);
        if (!string.IsNullOrWhiteSpace(UniversalAddress))
        {
            var supplied = UniversalAddress.Trim();
            if (supplied.StartsWith("0x", StringComparison.OrdinalIgnoreCase)) supplied = supplied[2..];
            if (supplied.Length > 14) supplied = supplied[^14..];
            if (supplied.Length != 14 || supplied.Any(character => !Uri.IsHexDigit(character)) ||
                !string.Equals(destination.UniversalAddress[2..], supplied, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The ticket Universal Address does not match its galaxy and glyph route.");
        }
        return destination;
    }
}
