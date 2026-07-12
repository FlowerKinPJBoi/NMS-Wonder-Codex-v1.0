using System.Text.RegularExpressions;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed partial class SteamSaveScanner
{
    private readonly IReadOnlyFileSystem _fileSystem;
    private readonly HgSaveDecoder _decoder;

    public SteamSaveScanner(IReadOnlyFileSystem fileSystem, HgSaveDecoder decoder)
    {
        _fileSystem = fileSystem;
        _decoder = decoder;
    }

    public async Task<IReadOnlyList<SaveAccount>> ScanAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var root = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "HelloGames",
            "NMS");

        if (!_fileSystem.DirectoryExists(root)) return [];

        var accountDirectories = _fileSystem.EnumerateDirectories(root, "st_*", SearchOption.TopDirectoryOnly)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var accounts = new List<SaveAccount>();
        var accountNumber = 0;
        foreach (var accountDirectory in accountDirectories)
        {
            cancellationToken.ThrowIfCancellationRequested();
            accountNumber++;
            progress?.Report($"Scanning Steam account {accountNumber}…");
            var characters = await ScanAccountAsync(accountDirectory, cancellationToken);
            if (characters.Count == 0) continue;

            var accountId = $"steam-{PathRedactor.AccountToken(accountDirectory)}";
            accounts.Add(new SaveAccount(
                accountId,
                $"Steam Account {accountNumber}",
                SavePlatform.Steam,
                characters));
        }

        return accounts;
    }

    private async Task<IReadOnlyList<SaveCharacter>> ScanAccountAsync(
        string accountDirectory,
        CancellationToken cancellationToken)
    {
        var candidates = _fileSystem.EnumerateFiles(accountDirectory, "save*.hg", SearchOption.TopDirectoryOnly)
            .Where(path => CurrentSlotPattern().IsMatch(Path.GetFileName(path) ?? string.Empty))
            .OrderByDescending(path => _fileSystem.GetFileInfo(path).LastWriteTimeUtc)
            .ToArray();

        var decoded = new List<SaveCharacter>();
        foreach (var path in candidates)
        {
            cancellationToken.ThrowIfCancellationRequested();
            if (!await _decoder.LooksLikeHgAsync(path, cancellationToken)) continue;

            try
            {
                using var document = await _decoder.DecodeAsync(path, cancellationToken);
                var info = _fileSystem.GetFileInfo(path);
                var fallback = Path.GetFileNameWithoutExtension(path) ?? "Detected character";
                var saveName = SaveMetadataParser.GetSaveName(document.RootElement, fallback);
                var gameMode = SaveMetadataParser.GetGameMode(document.RootElement);
                var fileName = Path.GetFileName(path) ?? fallback;
                var slotLabel = string.IsNullOrWhiteSpace(gameMode)
                    ? fileName
                    : $"{fileName} • {gameMode}";
                decoded.Add(new SaveCharacter(
                    Id: $"steam-{PathRedactor.AccountToken(path)}",
                    AccountId: $"steam-{PathRedactor.AccountToken(accountDirectory)}",
                    DisplayName: saveName,
                    SlotLabel: slotLabel,
                    Platform: SavePlatform.Steam,
                    SourcePath: path,
                    LastModifiedUtc: info.LastWriteTimeUtc,
                    FileSize: info.Length));
            }
            catch
            {
                // Alpha behavior: unreadable slots are skipped, never altered.
            }
        }

        return DeduplicateCharacters(decoded);
    }

    private static IReadOnlyList<SaveCharacter> DeduplicateCharacters(IEnumerable<SaveCharacter> candidates)
        => candidates
            .GroupBy(character => character.DisplayName, StringComparer.OrdinalIgnoreCase)
            .Select(group => group.OrderByDescending(character => character.LastModifiedUtc).First())
            .OrderByDescending(character => character.LastModifiedUtc)
            .ToArray();

    [GeneratedRegex("^save\\d*\\.hg$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex CurrentSlotPattern();
}
