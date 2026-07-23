using System.Buffers.Binary;

namespace WonderCodex.PegasusTransit.Core.Services;

public static class SaveMetadataUpdater
{
    private const int ExpandedSizeOffset = 16;
    private const int CloudRevisionTimeOffset = 288;

    public static byte[] WithExpandedSize(ReadOnlySpan<byte> metadata, int expandedSize)
    {
        if (metadata.Length < ExpandedSizeOffset + sizeof(int))
            throw new InvalidDataException("The save metadata is too short to update safely.");
        if (expandedSize <= 0)
            throw new ArgumentOutOfRangeException(nameof(expandedSize));

        var updated = metadata.ToArray();
        BinaryPrimitives.WriteInt32LittleEndian(updated.AsSpan(ExpandedSizeOffset, sizeof(int)), expandedSize);
        return updated;
    }

    public static byte[] WithXboxCloudRevision(
        ReadOnlySpan<byte> metadata,
        int expandedSize,
        DateTimeOffset revisionTime)
    {
        if (metadata.Length < CloudRevisionTimeOffset + sizeof(int))
            throw new InvalidDataException(
                "The Xbox save metadata is too short to update its cloud revision timestamp safely.");

        var updated = WithExpandedSize(metadata, expandedSize);
        var unixSeconds = checked((int)revisionTime.ToUnixTimeSeconds());
        BinaryPrimitives.WriteInt32LittleEndian(
            updated.AsSpan(CloudRevisionTimeOffset, sizeof(int)),
            unixSeconds);
        return updated;
    }
}
