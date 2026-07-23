namespace WonderCodex.Importer.Core.Services;

public sealed class ReadOnlyFileSystem : IReadOnlyFileSystem
{
    public bool DirectoryExists(string path) => Directory.Exists(path);

    public bool FileExists(string path) => File.Exists(path);

    public IEnumerable<string> EnumerateDirectories(
        string path,
        string searchPattern = "*",
        SearchOption searchOption = SearchOption.TopDirectoryOnly)
        => Directory.Exists(path)
            ? Directory.EnumerateDirectories(path, searchPattern, searchOption)
            : [];

    public IEnumerable<string> EnumerateFiles(
        string path,
        string searchPattern = "*",
        SearchOption searchOption = SearchOption.TopDirectoryOnly)
        => Directory.Exists(path)
            ? Directory.EnumerateFiles(path, searchPattern, searchOption)
            : [];

    public FileInfo GetFileInfo(string path) => new(path);

    public Stream OpenRead(string path)
        => new FileStream(
            path,
            FileMode.Open,
            FileAccess.Read,
            FileShare.ReadWrite | FileShare.Delete,
            bufferSize: 128 * 1024,
            options: FileOptions.Asynchronous | FileOptions.SequentialScan);
}
