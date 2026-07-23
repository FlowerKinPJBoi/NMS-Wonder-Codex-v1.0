using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace WonderCodex.Importer.Core.Services;

public sealed partial class DecodedJsonLoader
{
    public async Task<JsonDocument> LoadAsync(
        Stream stream,
        CancellationToken cancellationToken = default)
    {
        using var reader = new StreamReader(
            stream,
            Encoding.UTF8,
            detectEncodingFromByteOrderMarks: true,
            bufferSize: 64 * 1024,
            leaveOpen: true);

        var text = await reader.ReadToEndAsync(cancellationToken);
        var repaired = HexEscapePattern().Replace(text, "\\u00$1");
        return JsonDocument.Parse(repaired, JsonOptions);
    }

    private static readonly JsonDocumentOptions JsonOptions = new()
    {
        AllowTrailingCommas = true,
        CommentHandling = JsonCommentHandling.Skip,
        MaxDepth = 512
    };

    [GeneratedRegex(@"\\x([0-9a-fA-F]{2})", RegexOptions.CultureInvariant)]
    private static partial Regex HexEscapePattern();
}
