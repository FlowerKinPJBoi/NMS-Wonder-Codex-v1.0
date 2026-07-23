using WonderCodex.Capture.Core.Models;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

namespace WonderCodex.Capture.Core.Services;

public sealed class NormalizedDiscoveryReader
{
    private readonly ImporterCompositionRoot _importer;

    public NormalizedDiscoveryReader(ImporterCompositionRoot importer)
    {
        _importer = importer;
    }

    public async Task<NormalizedDiscoveryReadResult> ReadAsync(
        SaveCharacter character,
        CancellationToken cancellationToken = default)
    {
        using var document = await _importer.Loader.LoadAsync(character, cancellationToken);
        var report = _importer.Analyzer.Analyze(document.RootElement, character);

        if ((report.DiscoveryCount > 0 || report.MatchCount > 0) ||
            !_importer.ProductionKeyMap.TryGetSchema(document.RootElement, out var schema))
        {
            return new NormalizedDiscoveryReadResult(character, report, false, null);
        }

        using var translated = _importer.KeyTranslator.Translate(
            document.RootElement,
            _importer.ProductionKeyMap.Mapping);

        var translatedName = SaveMetadataParser.GetSaveName(
            translated.RootElement,
            character.DisplayName);
        var translatedCharacter = character with { DisplayName = translatedName };
        report = _importer.Analyzer.Analyze(translated.RootElement, translatedCharacter);

        return new NormalizedDiscoveryReadResult(
            translatedCharacter,
            report,
            true,
            schema.SchemaId);
    }
}
