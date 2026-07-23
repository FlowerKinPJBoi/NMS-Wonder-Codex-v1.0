using WonderCodex.Importer.Core.Services;
using WonderCodex.PegasusTransit.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class SteamTransitWriter
{
    private readonly HgSaveDecoder _decoder;
    private readonly UniverseAddressPatcher _patcher;
    private readonly TransitBackupService _backups;

    public SteamTransitWriter(
        HgSaveDecoder decoder,
        UniverseAddressPatcher patcher,
        TransitBackupService backups)
    {
        _decoder = decoder;
        _patcher = patcher;
        _backups = backups;
    }

    public async Task<TransitExecutionResult> ExecuteAsync(
        TransitPlan plan,
        CancellationToken cancellationToken = default)
    {
        var sourcePath = plan.Character.SourcePath;
        var accountDirectory = Path.GetDirectoryName(sourcePath)
            ?? throw new InvalidDataException("The Steam account directory could not be resolved.");
        var fileName = Path.GetFileName(sourcePath)
            ?? throw new InvalidDataException("The Steam save file name could not be resolved.");
        if (!fileName.StartsWith("save", StringComparison.OrdinalIgnoreCase) ||
            !fileName.EndsWith(".hg", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Pegasus Transit requires the active Steam save*.hg file.");

        var metadataPath = Path.Combine(accountDirectory, "mf_" + fileName);
        if (!File.Exists(metadataPath))
            throw new FileNotFoundException("The matching Steam mf_save metadata file was not found.", metadataPath);

        var backupPath = await _backups.CreateAsync(
            accountDirectory,
            "Steam",
            plan.OperatorName,
            cancellationToken);

        using var sourceDocument = await _decoder.DecodeAsync(sourcePath, cancellationToken);
        var patch = _patcher.CreatePatch(sourceDocument, plan.Destination);
        var encoded = HgSaveEncoder.Encode(patch.JsonBytes);
        var metadata = SaveMetadataUpdater.WithExpandedSize(
            await File.ReadAllBytesAsync(metadataPath, cancellationToken),
            encoded.ExpandedSize);

        var token = Guid.NewGuid().ToString("N");
        var saveTemporary = Path.Combine(accountDirectory, $".{fileName}.{token}.tmp");
        var metadataTemporary = Path.Combine(accountDirectory, $".{Path.GetFileName(metadataPath)}.{token}.tmp");
        try
        {
            await File.WriteAllBytesAsync(saveTemporary, encoded.Bytes, cancellationToken);
            await File.WriteAllBytesAsync(metadataTemporary, metadata, cancellationToken);
            await VerifyDestinationAsync(saveTemporary, plan.Destination, cancellationToken);

            File.Move(saveTemporary, sourcePath, overwrite: true);
            File.Move(metadataTemporary, metadataPath, overwrite: true);
            var now = DateTime.UtcNow;
            File.SetLastWriteTimeUtc(sourcePath, now);
            File.SetLastWriteTimeUtc(metadataPath, now);

            var verified = await VerifyDestinationAsync(sourcePath, plan.Destination, cancellationToken);
            return new TransitExecutionResult(
                true,
                "Steam",
                backupPath,
                verified,
                "Steam transit save written and decoded successfully.");
        }
        finally
        {
            TryDelete(saveTemporary);
            TryDelete(metadataTemporary);
        }
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
            throw new InvalidDataException("The Steam transit verification did not reproduce the requested address.");
        return location;
    }

    private static void TryDelete(string path)
    {
        try
        {
            if (File.Exists(path)) File.Delete(path);
        }
        catch (IOException)
        {
            // A harmless temporary file may remain; the source save was not pointed at it.
        }
        catch (UnauthorizedAccessException)
        {
            // Cleanup must not hide the authoritative transit result.
        }
    }
}
