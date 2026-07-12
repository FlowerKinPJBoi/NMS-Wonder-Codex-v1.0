using System.Text;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

var failures = new List<string>();

await TestHgRoundTripAsync(failures);
TestWonderAnalyzer(failures);
TestReadOnlySourceContract(failures);

if (failures.Count > 0)
{
    Console.Error.WriteLine("Wonder Codex Importer self-test FAILED:");
    foreach (var failure in failures) Console.Error.WriteLine($" - {failure}");
    return 1;
}

Console.WriteLine("Wonder Codex Importer self-test passed.");
return 0;

static async Task TestHgRoundTripAsync(List<string> failures)
{
    const string json = "{\"CommonStateData\":{\"SaveName\":\"Self Test\"}}";
    var hg = HgSaveDecoder.CreateSyntheticHgForSelfTest(json);
    await using var stream = new MemoryStream(hg);
    using var document = await HgSaveDecoder.DecodeAsync(stream);
    var saveName = SaveMetadataParser.GetSaveName(document.RootElement, "missing");
    if (!string.Equals(saveName, "Self Test", StringComparison.Ordinal))
        failures.Add("HG/LZ4 decoder round-trip did not preserve SaveName.");
}

static void TestWonderAnalyzer(List<string> failures)
{
    const string json = """
    {
      "CommonStateData": {"SaveName": "Hermit Test"},
      "Pets": [
        {
          "CreatureID": "^HERMITCRAB",
          "CreatureSeed": [false, "0x8B2F6257A61D786A"],
          "CreatureSecondarySeed": [false, "0x0"],
          "SpeciesSeed": "0x2C2A0FDEEC550BF0",
          "GenusSeed": "0x7481E0DD61B52A01",
          "UA": "0x54020E0313D92D",
          "CreatureType": {"CreatureType": "Prey"}
        }
      ],
      "DiscoveryManagerData": [
        {
          "DD": {
            "UA": "0x54020E0313D92D",
            "DT": "Animal",
            "VP": [
              "0x8B2F6257A61D786A",
              "0x05FA296DBC7FF044",
              "0x2C2A0FDEEC550BF0",
              "0x7481E0DD61B52A01"
            ]
          },
          "OWS": {"USN": "self-test", "PTK": "ST"}
        }
      ]
    }
    """;

    using var document = JsonDocument.Parse(json);
    var character = new SaveCharacter(
        "test-character",
        "test-account",
        "Hermit Test",
        "Self-test slot",
        SavePlatform.Steam,
        "<memory>",
        DateTimeOffset.UtcNow,
        Encoding.UTF8.GetByteCount(json));

    var report = new WonderAnalyzer().Analyze(document.RootElement, character);
    if (report.DiscoveryCount != 1) failures.Add("Analyzer did not find the synthetic discovery.");
    if (report.MatchCount != 1) failures.Add("Analyzer did not match the synthetic pet.");

    var expected = "LdkTAw4CVAADAAAAAwAAAGp4HaZXYi+LRPB/vG0p+gXwC1Xs3g8qLA==";
    var actual = report.Discoveries[0]["MessageID"]?.ToString();
    if (!string.Equals(actual, expected, StringComparison.Ordinal))
        failures.Add($"Message ID mismatch. Expected {expected}, got {actual}.");
}

static void TestReadOnlySourceContract(List<string> failures)
{
    var sourceRoot = FindRepositoryRoot();
    var sourceFiles = Directory.EnumerateFiles(
        Path.Combine(sourceRoot, "src"),
        "*.cs",
        SearchOption.AllDirectories);

    var forbidden = new[]
    {
        "File.WriteAll",
        "File.OpenWrite",
        "File.Create(",
        "File.Delete(",
        "File.Move(",
        "Directory.Delete(",
        "FileAccess.Write",
        "FileMode.Create",
        "FileMode.Truncate",
        "FileMode.Append"
    };

    foreach (var path in sourceFiles)
    {
        var text = File.ReadAllText(path);
        foreach (var marker in forbidden)
        {
            if (text.Contains(marker, StringComparison.Ordinal))
                failures.Add($"Read-only contract violation: {marker} found in {Path.GetFileName(path)}.");
        }
    }
}

static string FindRepositoryRoot()
{
    DirectoryInfo? directory = new(AppContext.BaseDirectory);
    while (directory is not null)
    {
        if (Directory.Exists(Path.Combine(directory.FullName, "src"))) return directory.FullName;
        directory = directory.Parent;
    }
    return Directory.GetCurrentDirectory();
}
