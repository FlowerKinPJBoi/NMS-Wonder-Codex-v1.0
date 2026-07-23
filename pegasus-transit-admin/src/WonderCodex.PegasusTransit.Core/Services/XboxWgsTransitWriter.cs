using System.Buffers.Binary;
using System.Globalization;
using System.Text;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;
using WonderCodex.PegasusTransit.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class XboxWgsTransitWriter
{
    private const uint SupportedContainerIndexVersion = 14;
    private const uint ContainerEntryStateSynched = 1;
    internal const uint ContainerEntryStateModified = 5;
    internal const uint ContainerSyncFlagsFullyDownloaded = 1u << 1;

    private readonly HgSaveDecoder _decoder;
    private readonly UniverseAddressPatcher _patcher;
    private readonly TransitBackupService _backups;

    public XboxWgsTransitWriter(
        HgSaveDecoder decoder,
        UniverseAddressPatcher patcher,
        TransitBackupService backups)
    {
        _decoder = decoder;
        _patcher = patcher;
        _backups = backups;
    }

    public SaveCharacter SelectManualRevision(SaveCharacter character)
    {
        var pair = ResolveSlotPair(character);
        var manual = pair.Manual.Revision;
        return character with
        {
            SourcePath = manual.SourcePath,
            LastModifiedUtc = manual.LastModifiedUtc,
            FileSize = manual.FileSize,
            SlotLabel = $"{character.SlotLabel} • {pair.Manual.Label}"
        };
    }

    public async Task<string> ComputeSourceLockAsync(
        SaveCharacter character,
        CancellationToken cancellationToken = default)
    {
        var pair = ResolveSlotPair(character);
        var manual = await ResolveActiveRevisionAsync(pair.Manual, cancellationToken);
        var automatic = await ResolveActiveRevisionAsync(pair.Automatic, cancellationToken);
        return await FileHash.CompositeSha256Async(
        [
            pair.IndexPath,
            manual.SourcePath,
            manual.MetadataPath,
            manual.DescriptorPath,
            automatic.SourcePath,
            automatic.MetadataPath,
            automatic.DescriptorPath
        ], cancellationToken);
    }

    public async Task<TransitExecutionResult> ExecuteAsync(
        TransitPlan plan,
        CancellationToken cancellationToken = default)
    {
        var pair = ResolveSlotPair(plan.Character);
        var manual = await ResolveActiveRevisionAsync(pair.Manual, cancellationToken);
        var automatic = await ResolveActiveRevisionAsync(pair.Automatic, cancellationToken);
        if (!string.Equals(manual.SourcePath, plan.Character.SourcePath, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                "The selected Xbox WGS source is not the slot's Manual revision. Rescan and preview again.");

        var suffixes = NextContainerSuffixes(pair.AccountDirectory, 2);
        var automaticNewSuffix = suffixes[0];
        var manualNewSuffix = suffixes[1];
        var backupPath = await _backups.CreateAsync(
            pair.AccountDirectory,
            "Xbox-WGS-BEFORE",
            plan.OperatorName,
            cancellationToken);

        using var sourceDocument = await _decoder.DecodeAsync(manual.SourcePath, cancellationToken);
        var patch = _patcher.CreatePatch(sourceDocument, plan.Destination);
        var encoded = HgSaveEncoder.Encode(patch.JsonBytes);
        var now = DateTimeOffset.UtcNow;
        var manualMetadata = SaveMetadataUpdater.WithXboxCloudRevision(
            await File.ReadAllBytesAsync(manual.MetadataPath, cancellationToken),
            encoded.ExpandedSize,
            now);
        var automaticMetadata = await File.ReadAllBytesAsync(automatic.MetadataPath, cancellationToken);

        var manualDataGuid = Guid.NewGuid();
        var manualMetadataGuid = Guid.NewGuid();
        var automaticMetadataGuid = Guid.NewGuid();
        var manualDataPath = Path.Combine(
            manual.ContainerDirectory,
            manualDataGuid.ToString("N").ToUpperInvariant());
        var manualNewMetadataPath = Path.Combine(
            manual.ContainerDirectory,
            manualMetadataGuid.ToString("N").ToUpperInvariant());
        var manualNewDescriptorPath = Path.Combine(
            manual.ContainerDirectory,
            $"container.{manualNewSuffix}");
        var automaticNewMetadataPath = Path.Combine(
            automatic.ContainerDirectory,
            automaticMetadataGuid.ToString("N").ToUpperInvariant());
        var automaticNewDescriptorPath = Path.Combine(
            automatic.ContainerDirectory,
            $"container.{automaticNewSuffix}");

        var manualNewDescriptor = BuildDescriptor(
            manual.Descriptor,
            manual.SourceGuid,
            manualDataGuid,
            manual.MetadataGuid,
            manualMetadataGuid);
        var automaticNewDescriptor = BuildDescriptor(
            automatic.Descriptor,
            automatic.SourceGuid,
            automatic.SourceGuid,
            automatic.MetadataGuid,
            automaticMetadataGuid);

        var automaticTime = now.UtcDateTime;
        var manualTime = now.AddMilliseconds(1).UtcDateTime;
        var originalIndex = await File.ReadAllBytesAsync(pair.IndexPath, cancellationToken);
        var originalIndexLastWriteTimeUtc = File.GetLastWriteTimeUtc(pair.IndexPath);
        var index = BuildIndex(
            originalIndex,
            Path.GetFileName(automatic.ContainerDirectory)
                ?? throw new InvalidDataException("The Xbox WGS Auto container name could not be resolved."),
            automatic.CurrentSuffix,
            automaticNewSuffix,
            automaticTime.ToFileTimeUtc(),
            new FileInfo(automatic.SourcePath).Length + automaticMetadata.LongLength);
        index = BuildIndex(
            index,
            Path.GetFileName(manual.ContainerDirectory)
                ?? throw new InvalidDataException("The Xbox WGS Manual container name could not be resolved."),
            manual.CurrentSuffix,
            manualNewSuffix,
            manualTime.ToFileTimeUtc(),
            encoded.Bytes.LongLength + manualMetadata.LongLength);

        var indexCommitted = false;
        var newFiles = new[]
        {
            manualDataPath,
            manualNewMetadataPath,
            manualNewDescriptorPath,
            automaticNewMetadataPath,
            automaticNewDescriptorPath
        };

        try
        {
            await File.WriteAllBytesAsync(manualDataPath, encoded.Bytes, cancellationToken);
            await File.WriteAllBytesAsync(manualNewMetadataPath, manualMetadata, cancellationToken);
            await File.WriteAllBytesAsync(manualNewDescriptorPath, manualNewDescriptor, cancellationToken);
            await File.WriteAllBytesAsync(automaticNewMetadataPath, automaticMetadata, cancellationToken);
            await File.WriteAllBytesAsync(automaticNewDescriptorPath, automaticNewDescriptor, cancellationToken);
            await VerifyDestinationAsync(manualDataPath, plan.Destination, cancellationToken);

            await WriteIndexInPlaceWithRollbackAsync(
                pair.IndexPath,
                index,
                originalIndex,
                originalIndexLastWriteTimeUtc,
                cancellationToken);
            indexCommitted = true;
            File.SetLastWriteTimeUtc(manualDataPath, manualTime);
            File.SetLastWriteTimeUtc(manualNewMetadataPath, manualTime);
            File.SetLastWriteTimeUtc(manualNewDescriptorPath, manualTime);
            File.SetLastWriteTimeUtc(automaticNewMetadataPath, automaticTime);
            File.SetLastWriteTimeUtc(automaticNewDescriptorPath, automaticTime);
            File.SetLastWriteTimeUtc(pair.IndexPath, manualTime);

            var verified = await VerifyDestinationAsync(manualDataPath, plan.Destination, cancellationToken);
            TryDelete(manual.SourcePath);
            TryDelete(manual.MetadataPath);
            TryDelete(manual.DescriptorPath);
            TryDelete(automatic.MetadataPath);
            TryDelete(automatic.DescriptorPath);

            string? postWriteSnapshotPath = null;
            try
            {
                postWriteSnapshotPath = await _backups.CreateAsync(
                    pair.AccountDirectory,
                    "Xbox-WGS-AFTER-LOCAL-WRITE",
                    plan.OperatorName,
                    cancellationToken);
            }
            catch (Exception)
            {
                // The pre-write backup remains authoritative if the optional evidence snapshot fails.
            }

            return new TransitExecutionResult(
                true,
                "Xbox / Game Pass WGS",
                backupPath,
                verified,
                $"Local WGS pair verified and marked pending upload " +
                $"({pair.Manual.Label} patched; {pair.Automatic.Label} refreshed). " +
                "Open No Man's Sky to the main menu on this PC, choose the local-save upload prompt, " +
                "then exit before launching Xbox.",
                postWriteSnapshotPath);
        }
        catch (Exception transactionError)
        {
            Exception? recoveryError = null;
            if (indexCommitted)
            {
                try
                {
                    await WriteIndexInPlaceAsync(pair.IndexPath, originalIndex, CancellationToken.None);
                    File.SetLastWriteTimeUtc(pair.IndexPath, originalIndexLastWriteTimeUtc);
                }
                catch (Exception exception)
                {
                    recoveryError = exception;
                }
            }

            foreach (var path in newFiles) TryDelete(path);
            if (recoveryError is not null)
                throw new IOException(
                    "Pegasus Transit could not restore containers.index after a failed Xbox WGS transaction. " +
                    $"Do not open No Man's Sky. Restore the backup at {backupPath} first.",
                    new AggregateException(transactionError, recoveryError));
            throw;
        }
    }

    internal static byte[] BuildDescriptor(
        ReadOnlySpan<byte> descriptor,
        Guid oldDataGuid,
        Guid newDataGuid,
        Guid oldMetadataGuid,
        Guid newMetadataGuid)
    {
        var updated = descriptor.ToArray();
        var dataReplacements = BinaryPattern.ReplaceAll(
            updated,
            oldDataGuid.ToByteArray(),
            newDataGuid.ToByteArray());
        var metadataReplacements = BinaryPattern.ReplaceAll(
            updated,
            oldMetadataGuid.ToByteArray(),
            newMetadataGuid.ToByteArray());
        if (dataReplacements != 2 || metadataReplacements != 2)
            throw new InvalidDataException(
                "The Xbox WGS descriptor did not contain the expected duplicated data and metadata identifiers.");
        return updated;
    }

    internal static byte[] BuildIndex(
        ReadOnlySpan<byte> index,
        string containerDirectoryName,
        byte currentSuffix,
        byte newSuffix,
        long fileTimeUtc,
        long combinedPayloadSize)
    {
        if (!Guid.TryParseExact(containerDirectoryName, "N", out var containerGuid))
            throw new InvalidDataException("The Xbox WGS container directory is not a GUID.");
        var updated = index.ToArray();
        var guidOffsets = BinaryPattern.FindAll(updated, containerGuid.ToByteArray());
        if (guidOffsets.Count != 1)
            throw new InvalidDataException("The selected Xbox WGS container was not uniquely present in containers.index.");

        var guidOffset = guidOffsets[0];
        if (guidOffset < 5 || guidOffset + 40 > updated.Length)
            throw new InvalidDataException("The Xbox WGS index entry is truncated.");
        if (updated[guidOffset - 5] != currentSuffix)
            throw new InvalidDataException("The Xbox WGS descriptor generation does not match containers.index.");

        var stateOffset = guidOffset - sizeof(uint);
        var currentState = BinaryPrimitives.ReadUInt32LittleEndian(
            updated.AsSpan(stateOffset, sizeof(uint)));
        if (currentState != ContainerEntryStateSynched && currentState != ContainerEntryStateModified)
            throw new InvalidDataException(
                $"The Xbox WGS entry has unsupported transaction state {currentState}.");

        const int timestampCharacterCount = 19;
        var timestampByteCount = checked(timestampCharacterCount * sizeof(char));
        var timestampLengthOffset = guidOffset - 5 - timestampByteCount - sizeof(int);
        if (timestampLengthOffset < 0 ||
            BinaryPrimitives.ReadInt32LittleEndian(updated.AsSpan(timestampLengthOffset, sizeof(int))) != timestampCharacterCount)
            throw new InvalidDataException("The Xbox WGS entry timestamp field was not found at the expected position.");

        var timestampOffset = timestampLengthOffset + sizeof(int);
        var previousStamp = Encoding.Unicode.GetString(updated, timestampOffset, timestampByteCount);
        if (previousStamp.Length != timestampCharacterCount ||
            !previousStamp.StartsWith("\"0x", StringComparison.Ordinal) ||
            previousStamp[^1] != '\"' ||
            !long.TryParse(
                previousStamp.AsSpan(3, timestampCharacterCount - 4),
                NumberStyles.AllowHexSpecifier,
                CultureInfo.InvariantCulture,
                out _))
            throw new InvalidDataException("The Xbox WGS entry timestamp field has an unsupported format.");

        var dateTimeTicks = DateTime.FromFileTimeUtc(fileTimeUtc).Ticks;
        var newStamp = Encoding.Unicode.GetBytes($"\"0x{dateTimeTicks:X}\"");
        if (newStamp.Length != timestampByteCount)
            throw new InvalidDataException("The Xbox WGS timestamp width changed unexpectedly.");

        newStamp.CopyTo(updated.AsSpan(timestampOffset, timestampByteCount));
        updated[guidOffset - 5] = newSuffix;
        BinaryPrimitives.WriteUInt32LittleEndian(
            updated.AsSpan(stateOffset, sizeof(uint)),
            ContainerEntryStateModified);
        BinaryPrimitives.WriteInt64LittleEndian(updated.AsSpan(guidOffset + 16, sizeof(long)), fileTimeUtc);
        BinaryPrimitives.WriteInt64LittleEndian(updated.AsSpan(guidOffset + 32, sizeof(long)), combinedPayloadSize);

        if (updated.Length < 8)
            throw new InvalidDataException("The Xbox WGS index header is truncated.");

        var version = BinaryPrimitives.ReadUInt32LittleEndian(updated.AsSpan(0, sizeof(uint)));
        if (version != SupportedContainerIndexVersion)
            throw new InvalidDataException(
                $"Pegasus Transit supports Xbox WGS containers.index version {SupportedContainerIndexVersion}; " +
                $"this index is version {version}.");

        var entryCount = BinaryPrimitives.ReadInt32LittleEndian(updated.AsSpan(4, sizeof(int)));
        if (entryCount <= 0)
            throw new InvalidDataException("The Xbox WGS index does not contain any entries.");

        var headerOffset = 8;
        headerOffset = SkipUnicodeIndexString(updated, headerOffset, int.MaxValue, "name");
        headerOffset = SkipUnicodeIndexString(updated, headerOffset, 130, "application identifier");
        var headerTimestampOffset = headerOffset;
        var flagsOffset = headerTimestampOffset + sizeof(long);
        if (flagsOffset + sizeof(uint) > updated.Length)
            throw new InvalidDataException("The Xbox WGS index sync header is truncated.");

        BinaryPrimitives.WriteInt64LittleEndian(updated.AsSpan(headerTimestampOffset, sizeof(long)), fileTimeUtc);
        BinaryPrimitives.WriteUInt32LittleEndian(
            updated.AsSpan(flagsOffset, sizeof(uint)),
            ContainerSyncFlagsFullyDownloaded);
        return updated;
    }

    private static int SkipUnicodeIndexString(
        ReadOnlySpan<byte> index,
        int lengthOffset,
        int maximumCharacterCount,
        string fieldName)
    {
        if (lengthOffset < 0 || lengthOffset + sizeof(int) > index.Length)
            throw new InvalidDataException($"The Xbox WGS index {fieldName} field is truncated.");

        var characterCount = BinaryPrimitives.ReadInt32LittleEndian(
            index.Slice(lengthOffset, sizeof(int)));
        var availableCharacterCount = (index.Length - lengthOffset - sizeof(int)) / sizeof(char);
        if (characterCount < 0 ||
            characterCount > maximumCharacterCount ||
            characterCount > availableCharacterCount)
            throw new InvalidDataException(
                $"The Xbox WGS index {fieldName} length {characterCount} is invalid.");

        var nextOffset = checked(lengthOffset + sizeof(int) + characterCount * sizeof(char));
        if (nextOffset > index.Length)
            throw new InvalidDataException($"The Xbox WGS index {fieldName} field is truncated.");
        return nextOffset;
    }

    internal static async Task WriteIndexInPlaceWithRollbackAsync(
        string indexPath,
        ReadOnlyMemory<byte> updatedIndex,
        ReadOnlyMemory<byte> originalIndex,
        DateTime originalLastWriteTimeUtc,
        CancellationToken cancellationToken = default)
    {
        try
        {
            await WriteIndexInPlaceAsync(indexPath, updatedIndex, cancellationToken);
        }
        catch (Exception writeError)
        {
            try
            {
                await WriteIndexInPlaceAsync(indexPath, originalIndex, CancellationToken.None);
                File.SetLastWriteTimeUtc(indexPath, originalLastWriteTimeUtc);
            }
            catch (Exception restoreError)
            {
                throw new IOException(
                    "The Xbox WGS index write failed and the original index could not be restored in place.",
                    new AggregateException(writeError, restoreError));
            }

            throw;
        }
    }

    private static async Task WriteIndexInPlaceAsync(
        string indexPath,
        ReadOnlyMemory<byte> bytes,
        CancellationToken cancellationToken)
    {
        await using var stream = new FileStream(
            indexPath,
            FileMode.Create,
            FileAccess.Write,
            FileShare.Read,
            bufferSize: 4096,
            options: FileOptions.Asynchronous | FileOptions.WriteThrough);
        await stream.WriteAsync(bytes, cancellationToken);
        await stream.FlushAsync(cancellationToken);
        stream.Flush(flushToDisk: true);
    }

    internal static string ReadSlotLabel(ReadOnlySpan<byte> index, string containerDirectoryName)
    {
        if (!Guid.TryParseExact(containerDirectoryName, "N", out var containerGuid))
            throw new InvalidDataException("The Xbox WGS container directory is not a GUID.");
        var offsets = BinaryPattern.FindAll(index, containerGuid.ToByteArray());
        if (offsets.Count != 1)
            throw new InvalidDataException("The Xbox WGS slot container was not uniquely present in containers.index.");

        const int timestampCharacterCount = 19;
        var timestampLengthOffset = offsets[0] - 5 -
                                    timestampCharacterCount * sizeof(char) - sizeof(int);
        if (timestampLengthOffset < 0 ||
            BinaryPrimitives.ReadInt32LittleEndian(index.Slice(timestampLengthOffset, sizeof(int))) !=
            timestampCharacterCount)
            throw new InvalidDataException("The Xbox WGS slot entry timestamp is invalid.");

        var nearest = ReadPrecedingIndexString(index, timestampLengthOffset);
        if (!string.IsNullOrWhiteSpace(nearest.Value)) return nearest.Value;
        var prior = ReadPrecedingIndexString(index, nearest.Offset);
        if (string.IsNullOrWhiteSpace(prior.Value))
            throw new InvalidDataException("The Xbox WGS slot label was empty.");
        return prior.Value;
    }

    private async Task<TransitLocation> VerifyDestinationAsync(
        string path,
        TransitDestination destination,
        CancellationToken cancellationToken)
    {
        using var document = await _decoder.DecodeAsync(path, cancellationToken);
        var location = _patcher.ReadLocation(document);
        if (location.RealityIndex != destination.RealityIndex ||
            location.VoxelX != destination.VoxelX ||
            location.VoxelY != destination.VoxelY ||
            location.VoxelZ != destination.VoxelZ ||
            location.SolarSystemIndex != destination.SolarSystemIndex ||
            location.PlanetIndex != destination.PlanetIndex)
            throw new InvalidDataException("The Xbox transit verification did not reproduce the requested address.");
        return location;
    }

    private SlotPair ResolveSlotPair(SaveCharacter character)
    {
        IReadOnlyList<SaveRevision> revisions = character.ReadOnlyRevisions.Count > 0
            ? character.ReadOnlyRevisions
            :
            [
                new SaveRevision(
                    character.Id,
                    "Selected revision",
                    character.SourcePath,
                    character.LastModifiedUtc,
                    character.FileSize,
                    string.Empty,
                    true)
            ];

        var firstContainer = Path.GetDirectoryName(revisions[0].SourcePath)
            ?? throw new InvalidDataException("The Xbox WGS container directory could not be resolved.");
        var accountDirectory = Directory.GetParent(firstContainer)?.FullName
            ?? throw new InvalidDataException("The Xbox WGS account directory could not be resolved.");
        var indexPath = Path.Combine(accountDirectory, "containers.index");
        if (!File.Exists(indexPath))
            throw new FileNotFoundException("The Xbox WGS containers.index file was not found.", indexPath);

        var index = File.ReadAllBytes(indexPath);
        var labeled = revisions.Select(revision =>
        {
            var container = Path.GetDirectoryName(revision.SourcePath)
                ?? throw new InvalidDataException("An Xbox WGS revision container could not be resolved.");
            var candidateAccount = Directory.GetParent(container)?.FullName
                ?? throw new InvalidDataException("An Xbox WGS revision account could not be resolved.");
            if (!string.Equals(candidateAccount, accountDirectory, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("The grouped Xbox WGS revisions do not belong to one account.");
            return new SlotRevision(
                revision,
                ReadSlotLabel(index, Path.GetFileName(container)
                    ?? throw new InvalidDataException("An Xbox WGS container name could not be resolved.")));
        }).ToArray();

        var manualMatches = labeled
            .Where(item => item.Label.EndsWith("Manual", StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (manualMatches.Length != 1)
            throw new InvalidDataException(
                "The selected Xbox character did not resolve to exactly one Manual WGS revision.");

        var manual = manualMatches[0];
        var slotStem = manual.Label[..^"Manual".Length];
        var automaticMatches = labeled
            .Where(item => string.Equals(item.Label, slotStem + "Auto", StringComparison.OrdinalIgnoreCase))
            .ToArray();
        if (automaticMatches.Length != 1)
            throw new InvalidDataException(
                $"The paired Xbox WGS revision {slotStem}Auto was not uniquely resolved.");

        return new SlotPair(manual, automaticMatches[0], accountDirectory, indexPath);
    }

    private static async Task<ActiveRevision> ResolveActiveRevisionAsync(
        SlotRevision slot,
        CancellationToken cancellationToken)
    {
        var sourcePath = slot.Revision.SourcePath;
        var containerDirectory = Path.GetDirectoryName(sourcePath)
            ?? throw new InvalidDataException("The Xbox WGS container directory could not be resolved.");
        var sourceGuid = ParseGuidFileName(sourcePath, "save payload");
        var descriptorPath = FindActiveDescriptor(containerDirectory, sourceGuid);
        var descriptor = await File.ReadAllBytesAsync(descriptorPath, cancellationToken);
        var metadataPath = FindMetadataPath(containerDirectory, sourcePath, descriptor);
        var metadataGuid = ParseGuidFileName(metadataPath, "save metadata");
        return new ActiveRevision(
            slot,
            sourcePath,
            containerDirectory,
            sourceGuid,
            descriptorPath,
            descriptor,
            metadataPath,
            metadataGuid,
            ParseDescriptorSuffix(descriptorPath));
    }

    private static string FindActiveDescriptor(string containerDirectory, Guid sourceGuid)
    {
        var sourcePattern = sourceGuid.ToByteArray();
        var matches = Directory.EnumerateFiles(containerDirectory, "container.*", SearchOption.TopDirectoryOnly)
            .Select(path => new { Path = path, Suffix = TryDescriptorSuffix(path) })
            .Where(item => item.Suffix.HasValue)
            .OrderByDescending(item => item.Suffix)
            .Where(item => BinaryPattern.FindAll(File.ReadAllBytes(item.Path), sourcePattern).Count == 2)
            .ToArray();
        return matches.Length == 1
            ? matches[0].Path
            : throw new InvalidDataException("The active Xbox WGS descriptor for this save was not uniquely resolved.");
    }

    private static string FindMetadataPath(
        string containerDirectory,
        string sourcePath,
        byte[] descriptor)
    {
        var matches = Directory.EnumerateFiles(containerDirectory, "*", SearchOption.TopDirectoryOnly)
            .Where(path => !string.Equals(path, sourcePath, StringComparison.OrdinalIgnoreCase))
            .Where(path => Guid.TryParseExact(Path.GetFileName(path) ?? string.Empty, "N", out _))
            .Where(path => new FileInfo(path).Length is > 0 and <= 4096)
            .Where(path =>
            {
                var guid = ParseGuidFileName(path, "metadata candidate");
                return BinaryPattern.FindAll(descriptor, guid.ToByteArray()).Count == 2;
            })
            .ToArray();
        return matches.Length == 1
            ? matches[0]
            : throw new InvalidDataException("The Xbox WGS metadata file was not uniquely resolved.");
    }

    private static byte[] NextContainerSuffixes(string accountDirectory, int count)
    {
        if (count <= 0) throw new ArgumentOutOfRangeException(nameof(count));
        var suffixes = Directory.EnumerateFiles(accountDirectory, "container.*", SearchOption.AllDirectories)
            .Select(TryDescriptorSuffix)
            .Where(value => value.HasValue)
            .Select(value => value.GetValueOrDefault())
            .ToArray();
        var maximum = suffixes.Length == 0 ? 0 : suffixes.Max();
        if (maximum + count > byte.MaxValue)
            throw new NotSupportedException(
                "The Xbox WGS descriptor generation cannot allocate the paired transaction before wraparound.");
        return Enumerable.Range(1, count)
            .Select(offset => checked((byte)(maximum + offset)))
            .ToArray();
    }

    private static IndexString ReadPrecedingIndexString(ReadOnlySpan<byte> index, int endOffset)
    {
        const int maximumCharacters = 64;
        for (var length = 0; length <= maximumCharacters; length++)
        {
            var start = endOffset - sizeof(int) - length * sizeof(char);
            if (start < 0 || start + sizeof(int) > index.Length) continue;
            if (BinaryPrimitives.ReadInt32LittleEndian(index.Slice(start, sizeof(int))) != length) continue;
            var value = Encoding.Unicode.GetString(index.Slice(start + sizeof(int), length * sizeof(char)));
            if (value.All(character => character is >= ' ' and <= '~'))
                return new IndexString(start, value);
        }
        throw new InvalidDataException("A preceding Xbox WGS index string could not be resolved.");
    }

    private static byte ParseDescriptorSuffix(string path)
        => TryDescriptorSuffix(path)
           ?? throw new InvalidDataException("The Xbox WGS descriptor suffix is invalid.");

    private static byte? TryDescriptorSuffix(string path)
    {
        var name = Path.GetFileName(path) ?? string.Empty;
        const string prefix = "container.";
        return name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) &&
               byte.TryParse(name.AsSpan(prefix.Length), NumberStyles.None, CultureInfo.InvariantCulture, out var value)
            ? value
            : null;
    }

    private static Guid ParseGuidFileName(string path, string label)
        => Guid.TryParseExact(Path.GetFileName(path) ?? string.Empty, "N", out var value)
            ? value
            : throw new InvalidDataException($"The Xbox WGS {label} file name is not a GUID.");

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch (IOException)
        {
            // Orphan cleanup is non-authoritative; containers.index selects the active generation.
        }
        catch (UnauthorizedAccessException)
        {
            // Cleanup must not hide a successfully validated transaction.
        }
    }

    private sealed record SlotRevision(SaveRevision Revision, string Label);

    private sealed record SlotPair(
        SlotRevision Manual,
        SlotRevision Automatic,
        string AccountDirectory,
        string IndexPath);

    private sealed record ActiveRevision(
        SlotRevision Slot,
        string SourcePath,
        string ContainerDirectory,
        Guid SourceGuid,
        string DescriptorPath,
        byte[] Descriptor,
        string MetadataPath,
        Guid MetadataGuid,
        byte CurrentSuffix);

    private sealed record IndexString(int Offset, string Value);
}
