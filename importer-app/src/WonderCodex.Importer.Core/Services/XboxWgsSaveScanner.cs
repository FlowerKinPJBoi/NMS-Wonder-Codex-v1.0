using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Utilities;

namespace WonderCodex.Importer.Core.Services;

public sealed class XboxWgsSaveScanner
{
    private readonly IReadOnlyFileSystem _fileSystem;
    private readonly HgSaveDecoder _decoder;
    private readonly JsonKeyTranslator _translator;
    private readonly ProductionKeyMapProvider _productionMap;
    private readonly WonderAnalyzer _analyzer;
    private readonly CharacterRevisionGrouper _grouper;

    public XboxWgsSaveScanner(
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
                progress?.Report($"Resolving Xbox / Game Pass account {accountNumber} locally…");
                var characters = await ScanAccountAsync(accountDirectory, progress, cancellationToken);
                if (characters.Count == 0) continue;

                var accountId = $"xbox-{PathRedactor.AccountToken(accountDirectory)}";
                accounts.Add(new SaveAccount(
                    accountId,
                    BuildAccountDisplayName(characters, accountNumber),
                    SavePlatform.XboxGamePass,
                    characters));
            }
        }

        return accounts;
    }

    private async Task<IReadOnlyList<SaveCharacter>> ScanAccountAsync(
        string accountDirectory,
        IProgress<string>? progress,
        CancellationToken cancellationToken)
    {
        var resolvedCandidates = new List<SaveCharacter>();
        var childDirectories = _fileSystem.EnumerateDirectories(accountDirectory)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();

        var containerNumber = 0;
        var unresolvedNumber = 0;
        foreach (var containerDirectory in childDirectories)
        {
            cancellationToken.ThrowIfCancellationRequested();
            containerNumber++;

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
                    progress?.Report($"Resolving Game Pass save container {containerNumber:N0}…");
                    using var compactDocument = await _decoder.DecodeAsync(path, cancellationToken);
                    using var translatedDocument = TranslateWhenSupported(compactDocument.RootElement);
                    var root = translatedDocument?.RootElement ?? compactDocument.RootElement;

                    var info = _fileSystem.GetFileInfo(path);
                    var saveName = SaveMetadataParser.GetSaveName(root, string.Empty);
                    if (string.IsNullOrWhiteSpace(saveName))
                    {
                        var isResearchCandidate =
                            _productionMap.LooksCompact(compactDocument.RootElement) &&
                            info.Length >= 128 * 1024;
                        if (!isResearchCandidate)
                        {
                            // Small metadata/account containers are intentionally excluded.
                            continue;
                        }

                        unresolvedNumber++;
                        saveName = $"WGS candidate {unresolvedNumber}";
                    }

                    var gameMode = SaveMetadataParser.GetGameMode(root);
                    var slotLabel = string.IsNullOrWhiteSpace(gameMode)
                        ? "Cloud save"
                        : $"Cloud save • {gameMode}";
                    var accountId = $"xbox-{PathRedactor.AccountToken(accountDirectory)}";
                    var containerToken = PathRedactor.AccountToken(containerDirectory);

                    var provisional = new SaveCharacter(
                        Id: $"xbox-{PathRedactor.AccountToken(path)}",
                        AccountId: accountId,
                        DisplayName: saveName,
                        SlotLabel: slotLabel,
                        Platform: SavePlatform.XboxGamePass,
                        SourcePath: path,
                        LastModifiedUtc: info.LastWriteTimeUtc,
                        FileSize: info.Length,
                        Revisions:
                        [
                            new SaveRevision(
                                $"revision-{PathRedactor.AccountToken(path)}",
                                "Read-only revision",
                                path,
                                info.LastWriteTimeUtc,
                                info.Length,
                                containerToken)
                        ],
                        IsAutomaticallyResolved: translatedDocument is not null,
                        IsPlayableCharacterState: SaveMetadataParser.HasPlayableCharacterState(root));

                    var report = _analyzer.Analyze(root, provisional);
                    resolvedCandidates.Add(provisional with
                    {
                        DiscoveryCount = report.DiscoveryCount,
                        PetCount = SummaryInt(report, "pets"),
                        ExactMatchCount = report.MatchCount
                    });
                }
                catch
                {
                    // Unreadable metadata/revision blobs are ignored. No file is changed.
                }
            }
        }

        return _grouper.Group(resolvedCandidates);
    }

    private JsonDocument? TranslateWhenSupported(JsonElement root)
    {
        if (!_productionMap.Supports(root)) return null;
        return _translator.Translate(root, _productionMap.Mapping);
    }

    private static int SummaryInt(AnalysisReport report, string key)
    {
        if (!report.Summary.TryGetValue(key, out var value) || value is null) return 0;
        return Convert.ToInt32(value);
    }

    private static string BuildAccountDisplayName(IReadOnlyList<SaveCharacter> characters, int accountNumber)
    {
        var allNamed = characters
            .Select(character => character.DisplayName)
            .Where(name => !name.StartsWith("Unnamed Character", StringComparison.OrdinalIgnoreCase))
            .Where(name => !name.StartsWith("Research candidate", StringComparison.OrdinalIgnoreCase))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var shown = allNamed.Take(3).ToArray();
        var unnamedCount = characters.Count(character =>
            character.DisplayName.StartsWith("Unnamed Character", StringComparison.OrdinalIgnoreCase));
        var researchCount = characters.Count(character =>
            character.DisplayName.StartsWith("Research candidate", StringComparison.OrdinalIgnoreCase));

        if (shown.Length == 0 && unnamedCount == 0)
            return $"Xbox / Game Pass Account {accountNumber}";

        var display = string.Join(", ", shown);
        var extras = new List<string>();
        var remainingNamed = allNamed.Length - shown.Length;
        if (remainingNamed > 0) extras.Add($"{remainingNamed} more");
        if (unnamedCount > 0) extras.Add($"{unnamedCount} unnamed");
        if (researchCount > 0) extras.Add($"{researchCount} research");

        return extras.Count == 0
            ? display
            : $"{display}{(display.Length > 0 ? " " : string.Empty)}+{string.Join(" +", extras)}";
    }
}
