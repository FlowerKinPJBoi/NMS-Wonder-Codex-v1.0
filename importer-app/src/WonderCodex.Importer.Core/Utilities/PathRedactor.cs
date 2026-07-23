using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace WonderCodex.Importer.Core.Utilities;

public static partial class PathRedactor
{
    public static string AccountToken(string path)
    {
        var normalized = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(normalized));
        return Convert.ToHexString(hash.AsSpan(0, 4));
    }

    public static string Redact(string path)
    {
        var fileName = Path.GetFileName(path) ?? string.Empty;
        var parentDirectory = Path.GetDirectoryName(path) ?? string.Empty;
        var parent = Path.GetFileName(parentDirectory) ?? string.Empty;
        if (LongIdPattern().IsMatch(parent)) parent = "<account>";
        if (SteamAccountPattern().IsMatch(parent)) parent = "<steam-account>";
        return string.IsNullOrWhiteSpace(parent) ? fileName : $"{parent}{Path.DirectorySeparatorChar}{fileName}";
    }

    [GeneratedRegex("^[0-9A-F]{20,}$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex LongIdPattern();

    [GeneratedRegex("^st_\\d{8,}$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex SteamAccountPattern();
}
