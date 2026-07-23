using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace WonderCodex.Importer.Core.Services;

public sealed partial class HgSaveDecoder
{
    public const uint Magic = 0xFEEDA1E5;
    private const int HeaderSize = 16;
    private readonly IReadOnlyFileSystem _fileSystem;

    public HgSaveDecoder(IReadOnlyFileSystem fileSystem)
    {
        _fileSystem = fileSystem;
    }

    public async Task<bool> LooksLikeHgAsync(string path, CancellationToken cancellationToken = default)
    {
        if (!_fileSystem.FileExists(path)) return false;
        await using var stream = _fileSystem.OpenRead(path);
        var header = new byte[4];
        var read = await stream.ReadAsync(header.AsMemory(0, 4), cancellationToken);
        return read == 4 && BinaryPrimitives.ReadUInt32LittleEndian(header) == Magic;
    }

    public async Task<JsonDocument> DecodeAsync(string path, CancellationToken cancellationToken = default)
    {
        await using var stream = _fileSystem.OpenRead(path);
        return await DecodeAsync(stream, cancellationToken);
    }

    public static async Task<JsonDocument> DecodeAsync(Stream stream, CancellationToken cancellationToken = default)
    {
        using var output = new MemoryStream();
        var header = new byte[HeaderSize];

        while (stream.Position < stream.Length)
        {
            await ReadExactlyAsync(stream, header, cancellationToken);
            var magic = BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(0, 4));
            if (magic != Magic) throw new InvalidDataException("Invalid No Man's Sky HG save header.");

            var compressedSize = BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(4, 4));
            var expandedSize = BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(8, 4));
            if (compressedSize <= 0 || expandedSize <= 0)
                throw new InvalidDataException("Invalid HG chunk size.");
            if (compressedSize > 128 * 1024 * 1024 || expandedSize > 256 * 1024 * 1024)
                throw new InvalidDataException("HG chunk exceeds the importer safety limit.");

            var compressed = new byte[compressedSize];
            await ReadExactlyAsync(stream, compressed, cancellationToken);
            var expanded = Lz4BlockDecoder.Decode(compressed, expandedSize);
            await output.WriteAsync(expanded, cancellationToken);
        }

        var bytes = output.ToArray();
        var end = bytes.Length;
        while (end > 0 && bytes[end - 1] == 0) end--;
        var jsonText = Encoding.UTF8.GetString(bytes, 0, end);

        try
        {
            return JsonDocument.Parse(jsonText, JsonOptions);
        }
        catch (JsonException first)
        {
            var repaired = HexEscapePattern().Replace(jsonText, "\\u00$1");
            try
            {
                return JsonDocument.Parse(repaired, JsonOptions);
            }
            catch (JsonException second)
            {
                throw new InvalidDataException(
                    $"The HG save decoded, but its JSON could not be parsed. {first.Message} / {second.Message}",
                    second);
            }
        }
    }

    public static byte[] CreateSyntheticHgForSelfTest(string json)
    {
        var payload = Encoding.UTF8.GetBytes(json);
        var compressed = Lz4BlockDecoder.EncodeLiteralOnly(payload);
        var result = new byte[HeaderSize + compressed.Length];
        BinaryPrimitives.WriteUInt32LittleEndian(result.AsSpan(0, 4), Magic);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(4, 4), compressed.Length);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(8, 4), payload.Length);
        BinaryPrimitives.WriteInt32LittleEndian(result.AsSpan(12, 4), 0);
        compressed.CopyTo(result.AsSpan(HeaderSize));
        return result;
    }

    private static async Task ReadExactlyAsync(Stream stream, byte[] buffer, CancellationToken cancellationToken)
    {
        var offset = 0;
        while (offset < buffer.Length)
        {
            var read = await stream.ReadAsync(buffer.AsMemory(offset), cancellationToken);
            if (read == 0) throw new EndOfStreamException("Unexpected end of HG save data.");
            offset += read;
        }
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
