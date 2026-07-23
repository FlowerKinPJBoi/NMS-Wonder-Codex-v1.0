using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed partial class SaveLoader
{
    private readonly IReadOnlyFileSystem _fileSystem;
    private readonly HgSaveDecoder _decoder;

    public SaveLoader(IReadOnlyFileSystem fileSystem, HgSaveDecoder decoder)
    {
        _fileSystem = fileSystem;
        _decoder = decoder;
    }

    public async Task<JsonDocument> LoadAsync(SaveCharacter character, CancellationToken cancellationToken = default)
    {
        if (character.IsDecodedJson)
        {
            await using var stream = _fileSystem.OpenRead(character.SourcePath);
            try
            {
                return await JsonDocument.ParseAsync(stream, JsonOptions, cancellationToken);
            }
            catch (JsonException)
            {
                stream.Position = 0;
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
        }

        return await _decoder.DecodeAsync(character.SourcePath, cancellationToken);
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
