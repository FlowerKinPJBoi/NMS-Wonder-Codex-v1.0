using System.Net.Http.Json;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Importer.Core.Services;

public sealed class WonderSubmissionClient
{
    private readonly HttpClient _httpClient;
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = false
    };

    public WonderSubmissionClient(HttpClient? httpClient = null)
    {
        _httpClient = httpClient ?? new HttpClient
        {
            BaseAddress = new Uri("https://wondercodex.com/"),
            Timeout = TimeSpan.FromMinutes(5)
        };
        _httpClient.DefaultRequestHeaders.UserAgent.ParseAdd("WonderCodexImporter/0.2.1-beta");
    }

    public async Task<SubmissionResult> SubmitAsync(
        AnalysisReport report,
        CancellationToken cancellationToken = default)
    {
        using var response = await _httpClient.PostAsJsonAsync(
            "api/submissions",
            report,
            _jsonOptions,
            cancellationToken);

        if (!response.IsSuccessStatusCode)
        {
            var detail = await ReadErrorDetailAsync(response, cancellationToken);
            throw new InvalidOperationException(detail ?? $"Wonder Codex returned HTTP {(int)response.StatusCode}.");
        }

        var result = await response.Content.ReadFromJsonAsync<SubmissionResult>(_jsonOptions, cancellationToken);
        return result ?? throw new InvalidOperationException("Wonder Codex returned an empty submission response.");
    }

    private static async Task<string?> ReadErrorDetailAsync(
        HttpResponseMessage response,
        CancellationToken cancellationToken)
    {
        try
        {
            using var document = await JsonDocument.ParseAsync(
                await response.Content.ReadAsStreamAsync(cancellationToken),
                cancellationToken: cancellationToken);
            if (document.RootElement.TryGetProperty("detail", out var detail))
                return detail.GetString();
        }
        catch
        {
            // Fall through to generic HTTP status handling.
        }
        return null;
    }
}
