using System.Globalization;
using System.Text.Json;

namespace WonderCodex.Importer.Core.Utilities;

public static class JsonValueReader
{
    public static bool TryGetUInt64(JsonElement element, out ulong value)
    {
        value = 0;
        switch (element.ValueKind)
        {
            case JsonValueKind.Number:
                if (element.TryGetUInt64(out value)) return true;
                if (element.TryGetInt64(out var signed))
                {
                    value = unchecked((ulong)signed);
                    return true;
                }
                return false;

            case JsonValueKind.String:
                var text = element.GetString()?.Trim();
                if (string.IsNullOrWhiteSpace(text)) return false;
                if (text.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
                    return ulong.TryParse(text.AsSpan(2), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out value);
                if (ulong.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out value)) return true;
                if (long.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out signed))
                {
                    value = unchecked((ulong)signed);
                    return true;
                }
                return false;

            default:
                return false;
        }
    }

    public static bool TryGetSeed(JsonElement element, out ulong value)
    {
        if (element.ValueKind == JsonValueKind.Array)
        {
            JsonElement? first = null;
            var index = 0;
            foreach (var item in element.EnumerateArray())
            {
                if (index == 1) return TryGetUInt64(item, out value);
                first ??= item;
                index++;
            }

            if (first.HasValue) return TryGetUInt64(first.Value, out value);
            value = 0;
            return false;
        }

        return TryGetUInt64(element, out value);
    }

    public static string GetString(JsonElement element, string fallback = "")
        => element.ValueKind switch
        {
            JsonValueKind.String => element.GetString() ?? fallback,
            JsonValueKind.Number => element.GetRawText(),
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            _ => fallback
        };

    public static string Hex(ulong value) => $"0x{value:X16}";
}
