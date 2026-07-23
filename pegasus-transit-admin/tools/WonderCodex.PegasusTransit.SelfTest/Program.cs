using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using WonderCodex.Importer.Core.Services;
using WonderCodex.PegasusTransit.Core.Services;

var failures = new List<string>();

TestDestination(failures);
TestCatalogTicket(failures);
await TestPatchAndEncodingAsync(failures);
await TestCompressedEncodingAsync(failures);
TestMetadata(failures);
TestWgsDescriptor(failures);
TestWgsIndex(failures);
await TestWgsIndexCommitAsync(failures);
TestWgsSlotLabels(failures);

if (failures.Count > 0)
{
    Console.Error.WriteLine("Pegasus Transit self-test FAILED:");
    foreach (var failure in failures) Console.Error.WriteLine(" - " + failure);
    return 1;
}

Console.WriteLine("Pegasus Transit self-test passed.");
return 0;

static void TestDestination(List<string> failures)
{
    var destination = TransitDestinationParser.Parse(170, "1081 FC25 0959", "Ezdaranit");
    if (destination.RealityIndex != 169 ||
        destination.VoxelX != -1703 ||
        destination.VoxelY != -4 ||
        destination.VoxelZ != 592 ||
        destination.SolarSystemIndex != 129 ||
        destination.PlanetIndex != 0 ||
        destination.UniversalAddress != "0x1081A9FC250959")
        failures.Add("Ezdaranit destination parsing did not reproduce the verified address.");
}

static void TestCatalogTicket(List<string> failures)
{
    var ticket = new WonderCodex.PegasusTransit.Core.Models.CatalogTransitTicket
    {
        Format = "wonder-codex-transit/0.1",
        WonderRecordId = "WC-A-003084",
        GalaxyNumber = 170,
        GalaxyName = "Ezdaranit",
        PortalGlyphs = "1081FC250959",
        UniversalAddress = "0x1081A9FC250959"
    };
    var destination = ticket.ValidateAndBuildDestination();
    if (destination.RealityIndex != 169 || destination.UniversalAddress != ticket.UniversalAddress)
        failures.Add("Catalog transit ticket did not validate its redundant route fields.");
}

static async Task TestPatchAndEncodingAsync(List<string> failures)
{
    const string fixture = """
    {"F2P":4733,"vLc":{"6f=":{"yhJ":{"Iis":23,"oZw":{"dZj":2046,"IyE":9,"uXE":2047,"vby":159,"jsv":0}},"ux@":{"Iis":23,"oZw":{"dZj":-1703,"IyE":-4,"uXE":592,"vby":129,"jsv":0}}}}}
    """;
    using var document = JsonDocument.Parse(fixture);
    var destination = TransitDestinationParser.Parse(170, "1081FC250959", "Ezdaranit");
    var patcher = new UniverseAddressPatcher();
    var patch = patcher.CreatePatch(document, destination);
    if (patch.Before.RealityIndex != 23 || patch.After.RealityIndex != 169)
        failures.Add("Universe address patch did not retain the before location and apply the target galaxy.");

    using var patchedDocument = JsonDocument.Parse(patch.JsonBytes);
    var root = patchedDocument.RootElement.GetProperty("vLc").GetProperty("6f=");
    var current = root.GetProperty("yhJ");
    var previous = root.GetProperty("ux@");
    if (current.GetProperty("Iis").GetInt32() != 169 ||
        current.GetProperty("oZw").GetProperty("dZj").GetInt32() != -1703 ||
        previous.GetProperty("Iis").GetInt32() != 23 ||
        previous.GetProperty("oZw").GetProperty("dZj").GetInt32() != 2046)
        failures.Add("UniverseAddress and PreviousUniverseAddress were not patched as a reversible pair.");

    var encoded = HgSaveEncoder.Encode(patch.JsonBytes);
    await using var stream = new MemoryStream(encoded.Bytes, writable: false);
    using var decoded = await HgSaveDecoder.DecodeAsync(stream);
    var verified = patcher.ReadLocation(decoded);
    if (verified.RealityIndex != 169 || verified.VoxelX != -1703 || verified.SolarSystemIndex != 129)
        failures.Add("Encoded HG save did not decode to the target destination.");
    if (encoded.ExpandedSize != patch.JsonBytes.Length + 1)
        failures.Add("HG expanded size does not include the required trailing null byte.");
}

static async Task TestCompressedEncodingAsync(List<string> failures)
{
    var repeated = new string('A', 700_000);
    var json = Encoding.UTF8.GetBytes($"{{\"Repeated\":\"{repeated}\"}}");
    var encoded = HgSaveEncoder.Encode(json);
    if (encoded.Bytes.Length >= json.Length / 10)
        failures.Add("HG encoder did not produce a normally compressed LZ4 payload.");

    await using var stream = new MemoryStream(encoded.Bytes, writable: false);
    using var decoded = await HgSaveDecoder.DecodeAsync(stream);
    if (decoded.RootElement.GetProperty("Repeated").GetString()?.Length != repeated.Length)
        failures.Add("Compressed HG encoder round-trip did not preserve the multi-chunk payload.");
}

static void TestMetadata(List<string> failures)
{
    var metadata = new byte[360];
    var updated = SaveMetadataUpdater.WithExpandedSize(metadata, 5_038_066);
    if (BinaryPrimitives.ReadInt32LittleEndian(updated.AsSpan(16, sizeof(int))) != 5_038_066)
        failures.Add("Save metadata expanded size was not written at offset 16.");
    if (metadata.Any(value => value != 0))
        failures.Add("Save metadata updater mutated its input buffer.");

    var revisionTime = DateTimeOffset.FromUnixTimeSeconds(1_784_125_679);
    var cloudUpdated = SaveMetadataUpdater.WithXboxCloudRevision(metadata, 2_958_034, revisionTime);
    if (BinaryPrimitives.ReadInt32LittleEndian(cloudUpdated.AsSpan(16, sizeof(int))) != 2_958_034 ||
        BinaryPrimitives.ReadInt32LittleEndian(cloudUpdated.AsSpan(288, sizeof(int))) != 1_784_125_679)
        failures.Add("Xbox metadata size and cloud revision timestamp were not updated together.");
}

static void TestWgsDescriptor(List<string> failures)
{
    var oldData = Guid.NewGuid();
    var oldMeta = Guid.NewGuid();
    var newData = Guid.NewGuid();
    var newMeta = Guid.NewGuid();
    var descriptor = new byte[328];
    oldData.ToByteArray().CopyTo(descriptor, 0x88);
    oldData.ToByteArray().CopyTo(descriptor, 0x98);
    oldMeta.ToByteArray().CopyTo(descriptor, 0x128);
    oldMeta.ToByteArray().CopyTo(descriptor, 0x138);
    var updated = XboxWgsTransitWriter.BuildDescriptor(descriptor, oldData, newData, oldMeta, newMeta);
    if (BinaryPattern.FindAll(updated, oldData.ToByteArray()).Count != 0 ||
        BinaryPattern.FindAll(updated, newData.ToByteArray()).Count != 2 ||
        BinaryPattern.FindAll(updated, newMeta.ToByteArray()).Count != 2)
        failures.Add("Xbox WGS descriptor identifiers were not replaced exactly twice.");

    var refreshed = XboxWgsTransitWriter.BuildDescriptor(descriptor, oldData, oldData, oldMeta, newMeta);
    if (BinaryPattern.FindAll(refreshed, oldData.ToByteArray()).Count != 2 ||
        BinaryPattern.FindAll(refreshed, newMeta.ToByteArray()).Count != 2)
        failures.Add("Xbox WGS Auto refresh did not retain data while rotating metadata.");
}

static void TestWgsIndex(List<string> failures)
{
    var container = Guid.NewGuid();
    const byte oldSuffix = 150;
    const byte newSuffix = 151;
    const long oldFileTime = 134_285_493_270_820_000;
    const long newFileTime = 134_285_500_000_000_000;
    const long newSize = 1_234_567;
    var index = new byte[240];
    BinaryPrimitives.WriteUInt32LittleEndian(index.AsSpan(0, sizeof(uint)), 14);
    BinaryPrimitives.WriteInt32LittleEndian(index.AsSpan(4, sizeof(int)), 1);
    BinaryPrimitives.WriteInt32LittleEndian(index.AsSpan(8, sizeof(int)), 0);
    BinaryPrimitives.WriteInt32LittleEndian(index.AsSpan(12, sizeof(int)), 4);
    Encoding.Unicode.GetBytes("TEST").CopyTo(index, 16);
    BinaryPrimitives.WriteInt64LittleEndian(index.AsSpan(24, sizeof(long)), oldFileTime);
    BinaryPrimitives.WriteUInt32LittleEndian(index.AsSpan(32, sizeof(uint)), 3);
    const int guidOffset = 120;
    // The quoted WGS entry timestamp and binary file time are related but independently recorded.
    var oldEntryTicks = DateTime.FromFileTimeUtc(oldFileTime).Ticks + 99_944_079;
    var oldStamp = Encoding.Unicode.GetBytes($"\"0x{oldEntryTicks:X}\"");
    var timestampLengthOffset = guidOffset - 5 - oldStamp.Length - sizeof(int);
    BinaryPrimitives.WriteInt32LittleEndian(index.AsSpan(timestampLengthOffset, sizeof(int)), 19);
    oldStamp.CopyTo(index, timestampLengthOffset + sizeof(int));
    index[guidOffset - 5] = oldSuffix;
    BinaryPrimitives.WriteUInt32LittleEndian(index.AsSpan(guidOffset - sizeof(uint), sizeof(uint)), 1);
    container.ToByteArray().CopyTo(index, guidOffset);
    BinaryPrimitives.WriteInt64LittleEndian(index.AsSpan(guidOffset + 16, sizeof(long)), oldFileTime);
    BinaryPrimitives.WriteInt64LittleEndian(index.AsSpan(guidOffset + 32, sizeof(long)), 1_000_000);

    var updated = XboxWgsTransitWriter.BuildIndex(
        index,
        container.ToString("N"),
        oldSuffix,
        newSuffix,
        newFileTime,
        newSize);
    if (updated[guidOffset - 5] != newSuffix ||
        BinaryPrimitives.ReadUInt32LittleEndian(
            updated.AsSpan(guidOffset - sizeof(uint), sizeof(uint))) !=
        XboxWgsTransitWriter.ContainerEntryStateModified ||
        BinaryPrimitives.ReadInt64LittleEndian(updated.AsSpan(guidOffset + 16, sizeof(long))) != newFileTime ||
        BinaryPrimitives.ReadInt64LittleEndian(updated.AsSpan(guidOffset + 32, sizeof(long))) != newSize ||
        BinaryPrimitives.ReadInt64LittleEndian(updated.AsSpan(24, sizeof(long))) != newFileTime ||
        BinaryPrimitives.ReadUInt32LittleEndian(updated.AsSpan(32, sizeof(uint))) !=
        XboxWgsTransitWriter.ContainerSyncFlagsFullyDownloaded ||
        Encoding.Unicode.GetString(
            updated,
            timestampLengthOffset + sizeof(int),
            oldStamp.Length) != $"\"0x{DateTime.FromFileTimeUtc(newFileTime).Ticks:X}\"")
        failures.Add("Xbox WGS index entry was not marked as a pending local upload transaction.");
}

static async Task TestWgsIndexCommitAsync(List<string> failures)
{
    var directory = Path.Combine(Path.GetTempPath(), $"PegasusTransitSelfTest-{Guid.NewGuid():N}");
    Directory.CreateDirectory(directory);
    var indexPath = Path.Combine(directory, "containers.index");
    var original = Encoding.ASCII.GetBytes("original-index");
    var updated = Encoding.ASCII.GetBytes("updated-index-with-a-different-length");
    await File.WriteAllBytesAsync(indexPath, original);
    var originalTime = File.GetLastWriteTimeUtc(indexPath);

    try
    {
        await using (var observer = new FileStream(
                         indexPath,
                         FileMode.Open,
                         FileAccess.Read,
                         FileShare.ReadWrite))
        {
            await XboxWgsTransitWriter.WriteIndexInPlaceWithRollbackAsync(
                indexPath,
                updated,
                original,
                originalTime);
            observer.Position = 0;
            var observed = new byte[updated.Length];
            var count = await observer.ReadAsync(observed);
            if (count != updated.Length || !observed.AsSpan(0, count).SequenceEqual(updated))
                failures.Add("Xbox WGS index commit replaced the file instead of updating the observed file in place.");
        }

        await File.WriteAllBytesAsync(indexPath, original);
        File.SetLastWriteTimeUtc(indexPath, originalTime);
        using var cancelled = new CancellationTokenSource();
        cancelled.Cancel();
        try
        {
            await XboxWgsTransitWriter.WriteIndexInPlaceWithRollbackAsync(
                indexPath,
                updated,
                original,
                originalTime,
                cancelled.Token);
            failures.Add("Cancelled Xbox WGS index commit did not stop.");
        }
        catch (OperationCanceledException)
        {
            var restored = await File.ReadAllBytesAsync(indexPath);
            if (!restored.AsSpan().SequenceEqual(original))
                failures.Add("Cancelled Xbox WGS index commit did not restore the original bytes.");
        }
    }
    finally
    {
        Directory.Delete(directory, recursive: true);
    }
}

static void TestWgsSlotLabels(List<string> failures)
{
    foreach (var expected in new[] { "Slot3Auto", "Slot3Manual" })
    {
        var container = Guid.NewGuid();
        var index = new byte[220];
        var offset = 20;
        offset = WriteIndexString(index, offset, expected);
        offset = WriteIndexString(index, offset, string.Empty);
        var timestamp = Encoding.Unicode.GetBytes("\"0x123456789ABCDEF\"");
        BinaryPrimitives.WriteInt32LittleEndian(index.AsSpan(offset, sizeof(int)), 19);
        timestamp.CopyTo(index, offset + sizeof(int));
        var guidOffset = offset + sizeof(int) + timestamp.Length + 5;
        container.ToByteArray().CopyTo(index, guidOffset);

        var actual = XboxWgsTransitWriter.ReadSlotLabel(index, container.ToString("N"));
        if (!string.Equals(actual, expected, StringComparison.Ordinal))
            failures.Add($"Xbox WGS slot label {expected} was resolved as {actual}.");
    }
}

static int WriteIndexString(byte[] target, int offset, string value)
{
    BinaryPrimitives.WriteInt32LittleEndian(target.AsSpan(offset, sizeof(int)), value.Length);
    var bytes = Encoding.Unicode.GetBytes(value);
    bytes.CopyTo(target, offset + sizeof(int));
    return offset + sizeof(int) + bytes.Length;
}
