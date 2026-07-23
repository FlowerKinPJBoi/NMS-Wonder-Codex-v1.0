namespace WonderCodex.Importer.Core.Services;

public static class Lz4BlockDecoder
{
    public static byte[] Decode(ReadOnlySpan<byte> source, int expectedSize)
    {
        if (expectedSize < 0) throw new ArgumentOutOfRangeException(nameof(expectedSize));
        var output = new byte[expectedSize];
        var sourceOffset = 0;
        var outputOffset = 0;

        while (sourceOffset < source.Length)
        {
            var token = source[sourceOffset++];
            var literalLength = token >> 4;
            if (literalLength == 15)
                literalLength += ReadExtendedLength(source, ref sourceOffset);

            if (sourceOffset + literalLength > source.Length || outputOffset + literalLength > output.Length)
                throw new InvalidDataException("Corrupt LZ4 literal run.");

            source.Slice(sourceOffset, literalLength).CopyTo(output.AsSpan(outputOffset));
            sourceOffset += literalLength;
            outputOffset += literalLength;

            if (sourceOffset >= source.Length) break;
            if (sourceOffset + 2 > source.Length)
                throw new InvalidDataException("Corrupt LZ4 match offset.");

            var matchOffset = source[sourceOffset] | (source[sourceOffset + 1] << 8);
            sourceOffset += 2;
            if (matchOffset <= 0 || matchOffset > outputOffset)
                throw new InvalidDataException("Invalid LZ4 back-reference.");

            var matchLength = token & 0x0F;
            if (matchLength == 15)
                matchLength += ReadExtendedLength(source, ref sourceOffset);
            matchLength += 4;

            if (outputOffset + matchLength > output.Length)
                throw new InvalidDataException("LZ4 output exceeds its expected size.");

            var copyFrom = outputOffset - matchOffset;
            for (var index = 0; index < matchLength; index++)
                output[outputOffset++] = output[copyFrom++];
        }

        if (outputOffset != expectedSize)
            throw new InvalidDataException($"LZ4 size mismatch. Expected {expectedSize}, decoded {outputOffset}.");

        return output;
    }

    public static byte[] EncodeLiteralOnly(ReadOnlySpan<byte> source)
    {
        using var stream = new MemoryStream();
        var literalLength = source.Length;
        var tokenLiteral = Math.Min(literalLength, 15);
        stream.WriteByte((byte)(tokenLiteral << 4));
        if (literalLength >= 15)
            WriteExtendedLength(stream, literalLength - 15);
        stream.Write(source);
        return stream.ToArray();
    }

    private static int ReadExtendedLength(ReadOnlySpan<byte> source, ref int offset)
    {
        var total = 0;
        while (true)
        {
            if (offset >= source.Length) throw new InvalidDataException("Corrupt LZ4 extended length.");
            var value = source[offset++];
            total += value;
            if (value != 255) return total;
        }
    }

    private static void WriteExtendedLength(Stream stream, int value)
    {
        while (value >= 255)
        {
            stream.WriteByte(255);
            value -= 255;
        }
        stream.WriteByte((byte)value);
    }
}
