using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed class XboxWgsSaveScanner
{
    private readonly IReadOnlyFileSystem _fileSystem;
    private readonly HgSaveDecoder _decoder;

    public XboxWgsSaveScanner(IReadOnlyFileSystem fileSystem, HgSaveDecoder decoder)
    {
        _fileSystem = fileSystem;
        _decoder = decoder;
    }

    public async Task<IReadOnlyList<SaveAccount>> ScanAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var packagesRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Packages");

        if (!_fileSystem.DirectoryExists(packagesRoot)) return [];

        var packageDirectories = _fileSystem.EnumerateDirectories(
                packagesRoot,
                "HelloGames.NoMansSky_*",
                SearchOption.TopDirectoryOnly)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var accounts = new List<SaveAccount>();
        var accountNumber = 0;

        foreach (var packageDirectory in packageDirectories)
        {
            var wgsRoot = Path.Combine(packageDirectory, "SystemAppData", "wgs");
            if (!_fileSystem.DirectoryExists(wgsRoot)) continue;

            var accountDirectories = _fileSystem.EnumerateDirectories(wgsRoot)
                .Where(path => !string.Equals(Path.GetFileName(path), "t", StringComparison.OrdinalIgnoreCase))
                .Where(path => _fileSystem.FileExists(Path.Combine(path, "containers.index")))
                .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
                .ToArray();

            foreach (var accountDirectory in accountDirectories)
            {
                cancellationToken.ThrowIfCancellationRequested();
                accountNumber++;
                progress?.Report($"Scanning Xbox / Game Pass account {accountNumber}…");
                var characters = await ScanAccountAsync(accountDirectory, cancellationToken);
                if (characters.Count == 0) continue;

                var accountId = $"xbox-{PathRedactor.AccountToken(accountDirectory)}";
                accounts.Add(new SaveAccount(
                    accountId,
                    $"Xbox / Game Pass Account {accountNumber}",
                    SavePlatform.XboxGamePass,
                    characters));
            }
        }

        return accounts;
    }

    private async Task<IReadOnlyList<SaveCharacter>> ScanAccountAsync(
        string accountDirectory,
        CancellationToken cancellationToken)
    {
        var characterCandidates = new List<SaveCharacter>();
        var childDirectories = _fileSystem.EnumerateDirectories(accountDirectory)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        foreach (var containerDirectory in childDirectories)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var files = _fileSystem.EnumerateFiles(containerDirectory, "*", SearchOption.TopDirectoryOnly)
                .Where(path => !(Path.GetFileName(path) ?? string.Empty).StartsWith("container", StringComparison.OrdinalIgnoreCase))
                .OrderByDescending(path => _fileSystem.GetFileInfo(path).Length)
                .ToArray();

            foreach (var path in files)
            {
                cancellationToken.ThrowIfCancellationRequested();
                if (!await _decoder.LooksLikeHgAsync(path, cancellationToken)) continue;

                try
                {
                    using var document = await _decoder.DecodeAsync(path, cancellationToken);
                    var info = _fileSystem.GetFileInfo(path);
                    var fallback = "Detected character";
                    var saveName = SaveMetadataParser.GetSaveName(document.RootElement, fallback);
                    var gameMode = SaveMetadataParser.GetGameMode(document.RootElement);
                    var slotLabel = string.IsNullOrWhiteSpace(gameMode)
                        ? "Cloud save"
                        : $"Cloud save • {gameMode}";
                    characterCandidates.Add(new SaveCharacter(
                        Id: $"xbox-{PathRedactor.AccountToken(path)}",
                        AccountId: $"xbox-{PathRedactor.AccountToken(accountDirectory)}",
                        DisplayName: saveName,
                        SlotLabel: slotLabel,
                        Platform: SavePlatform.XboxGamePass,
                        SourcePath: path,
                        LastModifiedUtc: info.LastWriteTimeUtc,
                        FileSize: info.Length));
                }
                catch
                {
                    // Unreadable metadata/revision blobs are ignored. No file is changed.
                }
            }
        }

        var newestPerContainer = characterCandidates
            .GroupBy(
                character => Path.GetDirectoryName(character.SourcePath) ?? character.SourcePath,
                StringComparer.OrdinalIgnoreCase)
            .Select(group => group.OrderByDescending(character => character.LastModifiedUtc).First())
            .OrderByDescending(character => character.LastModifiedUtc)
            .ToArray();

        var candidateNumber = 0;
        return newestPerContainer
            .Select(character =>
            {
                if (!string.Equals(character.DisplayName, "Detected character", StringComparison.OrdinalIgnoreCase))
                    return character;

                candidateNumber++;
                var containerPath = Path.GetDirectoryName(character.SourcePath) ?? character.SourcePath;
                var token = PathRedactor.AccountToken(containerPath);
                return character with
                {
                    DisplayName = $"WGS candidate {candidateNumber}",
                    SlotLabel = $"{character.SlotLabel} • container {token}"
                };
            })
            .ToArray();
    }
}
