using System.Buffers.Binary;
using K4os.Compression.LZ4;
using WonderCodex.Importer.Core.Services;

namespace WonderCodex.PegasusTransit.Core.Services;

public static class HgSaveEncoder
{
    private const int ChunkSize = 512 * 1024;
    private const int HeaderSize = 16;

    public static EncodedHgSave Encode(ReadOnlySpan<byte> jsonBytes)
    {
        var expanded = new byte[jsonBytes.Length + 1];
        jsonBytes.CopyTo(expanded);

        using var output = new MemoryStream(expanded.Length + 4096);
        for (var offset = 0; offset < expanded.Length; offset += ChunkSize)
        {
            var length = Math.Min(ChunkSize, expanded.Length - offset);
            var compressed = new byte[LZ4Codec.MaximumOutputSize(length)];
            var compressedLength = LZ4Codec.Encode(
                expanded.AsSpan(offset, length),
                compressed,
                LZ4Level.L00_FAST);
            if (compressedLength <= 0)
                throw new InvalidDataException("LZ4 could not encode an HG save chunk.");
            var header = new byte[HeaderSize];
            BinaryPrimitives.WriteUInt32LittleEndian(header, HgSaveDecoder.Magic);
            BinaryPrimitives.WriteInt32LittleEndian(header.AsSpan(4), compressedLength);
            BinaryPrimitives.WriteInt32LittleEndian(header.AsSpan(8), length);
            BinaryPrimitives.WriteInt32LittleEndian(header.AsSpan(12), 0);
            output.Write(header);
            output.Write(compressed, 0, compressedLength);
        }

        return new EncodedHgSave(output.ToArray(), expanded.Length);
    }
}

public sealed record EncodedHgSave(byte[] Bytes, int ExpandedSize);
