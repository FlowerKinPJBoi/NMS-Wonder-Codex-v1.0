using System.Text.Json;
using System.Text.RegularExpressions;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed partial class SteamSaveScanner
{
    private readonly IReadOnlyFileSystem _fileSystem;
    private readonly HgSaveDecoder _decoder;
    private readonly JsonKeyTranslator _translator;
    private readonly ProductionKeyMapProvider _productionMap;
    private readonly WonderAnalyzer _analyzer;
    private readonly CharacterRevisionGrouper _grouper;

    public SteamSaveScanner(
        IReadOnlyFileSystem fileSystem,
        HgSaveDecoder decoder,
        JsonKeyTranslator translator,
        ProductionKeyMapProvider productionMap,
        WonderAnalyzer analyzer,
        CharacterRevisionGrouper grouper)
    {
        _fileSystem = fileSystem;
        _decoder = decoder;
        _translator = translator;
        _productionMap = productionMap;
        _analyzer = analyzer;
        _grouper = grouper;
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
            progress?.Report($"Resolving Steam account {accountNumber} locally…");
            var characters = await ScanAccountAsync(accountDirectory, progress, cancellationToken);
            if (characters.Count == 0) continue;

            var accountId = $"steam-{PathRedactor.AccountToken(accountDirectory)}";
            accounts.Add(new SaveAccount(
                accountId,
                BuildAccountDisplayName(characters, accountNumber),
                SavePlatform.Steam,
                characters));
        }

        return accounts;
    }

    private async Task<IReadOnlyList<SaveCharacter>> ScanAccountAsync(
        string accountDirectory,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        var candidates = _fileSystem.EnumerateFiles(accountDirectory, "*.hg", SearchOption.TopDirectoryOnly)
            .Where(path => TryDescribeSlotFile(
                Path.GetFileName(path) ?? string.Empty,
                out _,
                out _))
            .OrderByDescending(path => _fileSystem.GetFileInfo(path).LastWriteTimeUtc)
            .ToArray();

        var accountId = $"steam-{PathRedactor.AccountToken(accountDirectory)}";
        var decoded = new List<SaveCharacter>();
        foreach (var path in candidates)
        {
            cancellationToken.ThrowIfCancellationRequested();
            var fileName = Path.GetFileName(path) ?? string.Empty;
            if (!TryDescribeSlotFile(fileName, out var slotNumber, out var revisionLabel)) continue;
            if (!await _decoder.LooksLikeHgAsync(path, cancellationToken)) continue;

            try
            {
                progress?.Report($"Resolving Steam slot {slotNumber}…");
                using var compactDocument = await _decoder.DecodeAsync(path, cancellationToken);
                using var translatedDocument = TranslateWhenSupported(compactDocument.RootElement);
                var root = translatedDocument?.RootElement ?? compactDocument.RootElement;

                var info = _fileSystem.GetFileInfo(path);
                var fallback = $"Unnamed Character — Slot {slotNumber}";
                var saveName = SaveMetadataParser.GetSaveName(root, fallback);
                var gameMode = SaveMetadataParser.GetGameMode(root);
                var slotLabel = string.IsNullOrWhiteSpace(gameMode)
                    ? $"Steam slot {slotNumber}"
                    : $"Steam slot {slotNumber} • {gameMode}";
                var slotKey = $"steam-slot-{slotNumber}";

                var provisional = new SaveCharacter(
                    Id: $"steam-{PathRedactor.AccountToken(path)}",
                    AccountId: accountId,
                    DisplayName: saveName,
                    SlotLabel: slotLabel,
                    Platform: SavePlatform.Steam,
                    SourcePath: path,
                    LastModifiedUtc: info.LastWriteTimeUtc,
                    FileSize: info.Length,
                    Revisions:
                    [
                        new SaveRevision(
                            $"revision-{PathRedactor.AccountToken(path)}",
                            revisionLabel,
                            path,
                            info.LastWriteTimeUtc,
                            info.Length,
                            $"SLOT{slotNumber}")
                    ],
                    IsAutomaticallyResolved: translatedDocument is not null,
                    SlotKey: slotKey,
                    IsPlayableCharacterState: SaveMetadataParser.HasPlayableCharacterState(root));

                var report = _analyzer.Analyze(root, provisional);
                decoded.Add(provisional with
                {
                    DiscoveryCount = report.DiscoveryCount,
                    PetCount = SummaryInt(report, "pets"),
                    ExactMatchCount = report.MatchCount
                });
            }
            catch
            {
                // Unreadable slot revisions are skipped. No source file is changed.
            }
        }

        return _grouper.Group(decoded);
    }

    private JsonDocument? TranslateWhenSupported(JsonElement root)
    {
        if (!_productionMap.Supports(root)) return null;
        return _translator.Translate(root, _productionMap.Mapping);
    }

    public static bool TryDescribeSlotFile(
        string fileName,
        out int slotNumber,
        out string revisionLabel)
    {
        var match = CurrentSlotPattern().Match(fileName);
        if (!match.Success)
        {
            slotNumber = 0;
            revisionLabel = string.Empty;
            return false;
        }

        var slotText = match.Groups["slot"].Value;
        slotNumber = string.IsNullOrWhiteSpace(slotText) ? 1 : int.Parse(slotText);
        revisionLabel = match.Groups["manual"].Success ? "mf_save revision" : "save revision";
        return true;
    }

    private static int SummaryInt(AnalysisReport report, string key)
    {
        if (!report.Summary.TryGetValue(key, out var value) || value is null) return 0;
        return Convert.ToInt32(value);
    }

    private static string BuildAccountDisplayName(IReadOnlyList<SaveCharacter> characters, int accountNumber)
    {
        var allNames = characters
            .Select(character => character.DisplayName)
            .Where(name => !name.StartsWith("Research candidate", StringComparison.OrdinalIgnoreCase))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var shown = allNames.Take(3).ToArray();

        if (shown.Length == 0) return $"Steam Account {accountNumber}";

        var remaining = allNames.Length - shown.Length;
        var suffix = remaining > 0 ? $" +{remaining} more" : string.Empty;
        return string.Join(", ", shown) + suffix;
    }

    [GeneratedRegex("^(?<manual>mf_)?save(?<slot>\\d*)\\.hg$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex CurrentSlotPattern();
}
