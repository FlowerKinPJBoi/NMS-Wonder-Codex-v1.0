using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed class SaveDiscoveryService
{
    private readonly SteamSaveScanner _steam;
    private readonly XboxWgsSaveScanner _xbox;

    public SaveDiscoveryService(SteamSaveScanner steam, XboxWgsSaveScanner xbox)
    {
        _steam = steam;
        _xbox = xbox;
    }

    public async Task<ScanResult> ScanDefaultLocationsAsync(
        IProgress<string>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var accounts = new List<SaveAccount>();
        var warnings = new List<string>();

        try
        {
            accounts.AddRange(await _xbox.ScanAsync(progress, cancellationToken));
        }
        catch (UnauthorizedAccessException)
        {
            warnings.Add("Windows denied access to one Xbox / Game Pass folder.");
        }
        catch (Exception error)
        {
            warnings.Add($"Xbox / Game Pass scan warning: {error.Message}");
        }

        try
        {
            accounts.AddRange(await _steam.ScanAsync(progress, cancellationToken));
        }
        catch (UnauthorizedAccessException)
        {
            warnings.Add("Windows denied access to one Steam folder.");
        }
        catch (Exception error)
        {
            warnings.Add($"Steam scan warning: {error.Message}");
        }

        return new ScanResult(
            accounts.OrderBy(account => account.Platform).ThenBy(account => account.DisplayName).ToArray(),
            warnings);
    }
}
