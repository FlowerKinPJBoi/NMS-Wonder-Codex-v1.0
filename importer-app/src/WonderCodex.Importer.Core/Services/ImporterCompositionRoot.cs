namespace WonderCodex.Importer.Core.Services;

public sealed class ImporterCompositionRoot
{
    public IReadOnlyFileSystem FileSystem { get; }
    public HgSaveDecoder Decoder { get; }
    public SaveDiscoveryService Discovery { get; }
    public SaveLoader Loader { get; }
    public WonderAnalyzer Analyzer { get; }
    public PegasusAssetAnalyzer PegasusAssetAnalyzer { get; }
    public DecodedJsonLoader DecodedJsonLoader { get; }
    public MatchedPairProfiler PairProfiler { get; }
    public JsonKeyTranslator KeyTranslator { get; }
    public ProductionKeyMapProvider ProductionKeyMap { get; }
    public CharacterRevisionGrouper RevisionGrouper { get; }
    public WonderSubmissionClient SubmissionClient { get; }
    public ContributionPackageBuilder ContributionBuilder { get; }
    public ContributionPackageValidator ContributionValidator { get; }
    public ContributionPackageExporter ContributionExporter { get; }

    public ImporterCompositionRoot()
    {
        FileSystem = new ReadOnlyFileSystem();
        Decoder = new HgSaveDecoder(FileSystem);
        Analyzer = new WonderAnalyzer();
        PegasusAssetAnalyzer = new PegasusAssetAnalyzer();
        DecodedJsonLoader = new DecodedJsonLoader();
        PairProfiler = new MatchedPairProfiler();
        KeyTranslator = new JsonKeyTranslator();
        ProductionKeyMap = new ProductionKeyMapProvider();
        RevisionGrouper = new CharacterRevisionGrouper();
        Discovery = new SaveDiscoveryService(
            new SteamSaveScanner(
                FileSystem,
                Decoder,
                KeyTranslator,
                ProductionKeyMap,
                Analyzer,
                RevisionGrouper),
            new XboxWgsSaveScanner(
                FileSystem,
                Decoder,
                KeyTranslator,
                ProductionKeyMap,
                Analyzer,
                RevisionGrouper));
        Loader = new SaveLoader(FileSystem, Decoder);
        SubmissionClient = new WonderSubmissionClient();
        ContributionBuilder = new ContributionPackageBuilder();
        ContributionValidator = new ContributionPackageValidator();
        ContributionExporter = new ContributionPackageExporter(ContributionValidator);
    }
}
