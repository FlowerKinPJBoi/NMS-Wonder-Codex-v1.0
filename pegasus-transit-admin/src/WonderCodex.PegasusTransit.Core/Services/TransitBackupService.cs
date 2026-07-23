using System.IO.Compression;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class TransitBackupService
{
    public string BackupRoot { get; }

    public TransitBackupService(string? backupRoot = null)
    {
        BackupRoot = backupRoot ?? Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "WonderCodex",
            "PegasusTransit",
            "Backups");
    }

    public Task<string> CreateAsync(
        string sourceDirectory,
        string platform,
        string operatorName,
        CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!Directory.Exists(sourceDirectory))
            throw new DirectoryNotFoundException("The selected save directory no longer exists.");

        Directory.CreateDirectory(BackupRoot);
        var stamp = DateTimeOffset.UtcNow.ToString("yyyyMMdd-HHmmss");
        var fileName = $"Pegasus-{Safe(platform)}-{Safe(operatorName)}-{stamp}-{Guid.NewGuid():N}.zip";
        var destination = Path.Combine(BackupRoot, fileName);
        ZipFile.CreateFromDirectory(
            sourceDirectory,
            destination,
            CompressionLevel.Fastest,
            includeBaseDirectory: true);
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(destination);
    }

    private static string Safe(string value)
    {
        var cleaned = new string(value
            .Where(character => char.IsLetterOrDigit(character) || character is '-' or '_')
            .Take(40)
            .ToArray());
        return string.IsNullOrWhiteSpace(cleaned) ? "operator" : cleaned;
    }
}
