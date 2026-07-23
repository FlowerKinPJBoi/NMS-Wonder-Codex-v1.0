using System.Security.Cryptography;
using System.Text;

namespace WonderCodex.PegasusTransit.Core.Services;

public static class FileHash
{
    public static async Task<string> Sha256Async(string path, CancellationToken cancellationToken = default)
    {
        await using var stream = new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.Read,
            128 * 1024,
            FileOptions.Asynchronous | FileOptions.SequentialScan);
        var hash = await SHA256.HashDataAsync(stream, cancellationToken);
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public static async Task<string> CompositeSha256Async(
        IEnumerable<string> paths,
        CancellationToken cancellationToken = default)
    {
        var components = new List<string>();
        foreach (var path in paths.OrderBy(value => value, StringComparer.OrdinalIgnoreCase))
        {
            cancellationToken.ThrowIfCancellationRequested();
            components.Add($"{Path.GetFileName(path)}:{await Sha256Async(path, cancellationToken)}");
        }

        var hash = SHA256.HashData(Encoding.UTF8.GetBytes(string.Join("\n", components)));
        return Convert.ToHexString(hash).ToLowerInvariant();
    }
}
