namespace WonderCodex.PegasusTransit.Core.Services;

internal static class BinaryPattern
{
    public static IReadOnlyList<int> FindAll(ReadOnlySpan<byte> source, ReadOnlySpan<byte> pattern)
    {
        if (pattern.Length == 0) throw new ArgumentException("Pattern cannot be empty.", nameof(pattern));
        var offsets = new List<int>();
        for (var offset = 0; offset <= source.Length - pattern.Length; offset++)
        {
            if (source.Slice(offset, pattern.Length).SequenceEqual(pattern)) offsets.Add(offset);
        }
        return offsets;
    }

    public static int ReplaceAll(Span<byte> source, ReadOnlySpan<byte> oldValue, ReadOnlySpan<byte> newValue)
    {
        if (oldValue.Length != newValue.Length)
            throw new ArgumentException("Binary replacement values must have the same length.");
        var offsets = FindAll(source, oldValue);
        foreach (var offset in offsets) newValue.CopyTo(source[offset..]);
        return offsets.Count;
    }
}
