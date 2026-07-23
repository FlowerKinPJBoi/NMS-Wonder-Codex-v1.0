using WonderCodex.Capture.Core.Models;

namespace WonderCodex.Capture.Core.Services;

public sealed class ScreenshotFolderWatcher : IDisposable
{
    private static readonly HashSet<string> SupportedExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".png", ".jpg", ".jpeg", ".webp", ".bmp"
    };

    private readonly FileSystemWatcher _watcher;
    private readonly object _gate = new();
    private readonly Dictionary<string, DateTimeOffset> _observed = new(StringComparer.OrdinalIgnoreCase);
    private bool _disposed;

    public ScreenshotFolderWatcher(string folderPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(folderPath);
        if (!Directory.Exists(folderPath))
            throw new DirectoryNotFoundException("The selected screenshot folder does not exist.");

        _watcher = new FileSystemWatcher(folderPath)
        {
            IncludeSubdirectories = false,
            NotifyFilter = NotifyFilters.FileName | NotifyFilters.CreationTime | NotifyFilters.LastWrite | NotifyFilters.Size,
            Filter = "*.*",
            EnableRaisingEvents = false
        };
        _watcher.Created += OnChanged;
        _watcher.Renamed += OnChanged;
    }

    public event EventHandler<ScreenshotCandidate>? ScreenshotObserved;

    public string FolderPath => _watcher.Path;

    public void Start() => _watcher.EnableRaisingEvents = true;

    public void Stop() => _watcher.EnableRaisingEvents = false;

    private void OnChanged(object sender, FileSystemEventArgs args)
    {
        var extension = Path.GetExtension(args.FullPath);
        if (!SupportedExtensions.Contains(extension)) return;

        var observedUtc = DateTimeOffset.UtcNow;
        lock (_gate)
        {
            if (_observed.TryGetValue(args.FullPath, out var previous) &&
                observedUtc - previous < TimeSpan.FromSeconds(2))
            {
                return;
            }
            _observed[args.FullPath] = observedUtc;
        }

        var info = new FileInfo(args.FullPath);
        var candidate = new ScreenshotCandidate(
            args.FullPath,
            Path.GetFileName(args.FullPath),
            observedUtc,
            info.Exists ? new DateTimeOffset(info.LastWriteTimeUtc, TimeSpan.Zero) : observedUtc,
            info.Exists ? info.Length : 0);
        ScreenshotObserved?.Invoke(this, candidate);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _watcher.EnableRaisingEvents = false;
        _watcher.Created -= OnChanged;
        _watcher.Renamed -= OnChanged;
        _watcher.Dispose();
    }
}
