using System.Net;
using System.Net.Http.Json;

namespace WonderCodex.PegasusTransit.Core.Services;

public sealed class AdminSessionClient
{
    private readonly HttpClient _client;

    public AdminSessionClient(HttpClient? client = null)
    {
        _client = client ?? new HttpClient { Timeout = TimeSpan.FromSeconds(15) };
    }

    public async Task AuthorizeAsync(
        Uri apiBase,
        string operatorName,
        string adminKey,
        CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(operatorName) || string.IsNullOrWhiteSpace(adminKey))
            throw new InvalidOperationException("Operator name and administrator key are required.");

        var endpoint = new Uri(apiBase, "admin/summary");
        using var request = new HttpRequestMessage(HttpMethod.Get, endpoint);
        request.Headers.Add("X-Admin-Key", adminKey.Trim());
        request.Headers.Add("X-Admin-Actor", operatorName.Trim());
        using var response = await _client.SendAsync(request, cancellationToken);
        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
            throw new UnauthorizedAccessException("The Wonder Codex administrator credentials were not accepted.");
        response.EnsureSuccessStatusCode();
        _ = await response.Content.ReadFromJsonAsync<Dictionary<string, object>>(cancellationToken: cancellationToken);
    }
}
