using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;
using WonderCodex.PegasusTransit.Core.Models;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class TransitCoordinator
{
    private readonly HgSaveDecoder _decoder;
    private readonly UniverseAddressPatcher _patcher;
    private readonly SteamTransitWriter _steam;
    private readonly XboxWgsTransitWriter _xbox;

    public TransitCoordinator(
        HgSaveDecoder decoder,
        UniverseAddressPatcher patcher,
        SteamTransitWriter steam,
        XboxWgsTransitWriter xbox)
    {
        _decoder = decoder;
        _patcher = patcher;
        _steam = steam;
        _xbox = xbox;
    }

    public async Task<TransitPlan> PrepareAsync(
        SaveCharacter character,
        TransitDestination destination,
        string operatorName,
        string? wonderRecordId,
        CancellationToken cancellationToken = default)
    {
        if (!character.IsPlayableCharacterState)
            throw new InvalidOperationException("The selected file is not a confirmed playable character save.");
        if (character.Platform is not SavePlatform.Steam and not SavePlatform.XboxGamePass)
            throw new NotSupportedException("Pegasus Transit currently supports Steam and Xbox / Game Pass PC saves.");
        if (string.IsNullOrWhiteSpace(operatorName))
            throw new InvalidOperationException("An authorized operator name is required.");

        if (character.Platform == SavePlatform.XboxGamePass)
            character = _xbox.SelectManualRevision(character);

        using var document = await _decoder.DecodeAsync(character.SourcePath, cancellationToken);
        var current = _patcher.ReadLocation(document);
        _ = _patcher.CreatePatch(document, destination);
        var hash = character.Platform == SavePlatform.XboxGamePass
            ? await _xbox.ComputeSourceLockAsync(character, cancellationToken)
            : await FileHash.Sha256Async(character.SourcePath, cancellationToken);
        return new TransitPlan(
            character,
            destination,
            current,
            hash,
            DateTimeOffset.UtcNow,
            operatorName.Trim(),
            string.IsNullOrWhiteSpace(wonderRecordId) ? null : wonderRecordId.Trim().ToUpperInvariant());
    }

    public async Task<TransitExecutionResult> ExecuteAsync(
        TransitPlan plan,
        CancellationToken cancellationToken = default)
    {
        GameProcessGuard.ThrowIfNoMansSkyIsRunning();
        var currentHash = plan.Character.Platform == SavePlatform.XboxGamePass
            ? await _xbox.ComputeSourceLockAsync(plan.Character, cancellationToken)
            : await FileHash.Sha256Async(plan.Character.SourcePath, cancellationToken);
        if (!string.Equals(currentHash, plan.SourceSha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(
                "The selected save changed after preview. Rescan and preview again; no file was written.");

        return plan.Character.Platform switch
        {
            SavePlatform.Steam => await _steam.ExecuteAsync(plan, cancellationToken),
            SavePlatform.XboxGamePass => await _xbox.ExecuteAsync(plan, cancellationToken),
            _ => throw new NotSupportedException("This platform is not supported by Pegasus Transit.")
        };
    }
}
