namespace WonderCodex.Importer.Core.Services;

public sealed class ImporterCompositionRoot
{
    public IReadOnlyFileSystem FileSystem { get; }
    public HgSaveDecoder Decoder { get; }
    public SaveDiscoveryService Discovery { get; }
    public SaveLoader Loader { get; }
    public WonderAnalyzer Analyzer { get; }
    public WonderSubmissionClient SubmissionClient { get; }

    public ImporterCompositionRoot()
    {
        FileSystem = new ReadOnlyFileSystem();
        Decoder = new HgSaveDecoder(FileSystem);
        Discovery = new SaveDiscoveryService(
            new SteamSaveScanner(FileSystem, Decoder),
            new XboxWgsSaveScanner(FileSystem, Decoder));
        Loader = new SaveLoader(FileSystem, Decoder);
        Analyzer = new WonderAnalyzer();
        SubmissionClient = new WonderSubmissionClient();
    }
}
