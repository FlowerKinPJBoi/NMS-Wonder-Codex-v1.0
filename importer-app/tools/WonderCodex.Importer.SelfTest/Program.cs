using System.IO.Compression;
using System.Text;
using System.Text.Json;
using WonderCodex.Importer.Core.Models;
using WonderCodex.Importer.Core.Services;

var failures = new List<string>();

await TestHgRoundTripAsync(failures);
TestWonderAnalyzer(failures);
TestContributionPackage(failures);
TestMatchedPairProfiler(failures);
TestProductionKeyMap(failures);
TestCharacterRevisionGrouping(failures);
TestPlayableCharacterDetection(failures);
TestSteamSlotRecognition(failures);
TestPegasusAssetCollection(failures);
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

static void TestContributionPackage(List<string> failures)
{
    const string json = """
    {
      "CommonStateData": {"SaveName": "WCCP Fixture"},
      "Pets": [
        {
          "CreatureID": "^FLOATSPIDER",
          "CreatureSeed": [false, "0x2C7571A6CABCE9E0"],
          "SpeciesSeed": "0x30E0C84130BAF3CC",
          "GenusSeed": "0x61E22115C9E58459",
          "UA": "0x208010F8006FF5",
          "CreatureType": {"CreatureType": "Passive"}
        },
        {
          "CreatureID": "^SIXLEGCOW",
          "CreatureSeed": [false, "0xEB4B8E1720B0A4E5"],
          "CreatureSecondarySeed": [false, "0x87871631A70CE592"],
          "SpeciesSeed": "0xA1AEBC7BB79CFE67",
          "GenusSeed": "0xB73128B2A96F90AC",
          "UA": "0x208010F8006FF5",
          "CreatureType": {"CreatureType": "Prey"}
        }
      ],
      "DiscoveryManagerData": [
        {
          "DD": {
            "UA": "0x208010F8006FF5",
            "DT": "Animal",
            "VP": [
              "0x2C7571A6CABCE9E0",
              "0x18FC9D37A0D18140",
              "0x30E0C84130BAF3CC",
              "0x61E22115C9E58459"
            ]
          },
          "OWS": {
            "LID": "private-platform-id",
            "UID": "private-user-id",
            "USN": "PrivateOwnerName",
            "PTK": "ST",
            "TS": 1784040000
          }
        },
        {
          "DD": {
            "UA": "0x208010F8006FF5",
            "DT": "Animal",
            "VP": [
              "0xEB4B8E1720B0A4E5",
              "0x9CCAC82F0C886CCA",
              "0xA1AEBC7BB79CFE67",
              "0xB73128B2A96F90AC",
              "0x87871631A70CE592"
            ]
          },
          "OWS": {
            "LID": "private-platform-id-2",
            "UID": "private-user-id-2",
            "USN": "AnotherPrivateOwner",
            "PTK": "XB",
            "TS": 1784040001
          }
        }
      ]
    }
    """;

    using var document = JsonDocument.Parse(json);
    var character = new SaveCharacter(
        "private-character-id",
        "private-account-id",
        "WCCP Fixture",
        "Private slot",
        SavePlatform.Steam,
        @"C:\Users\PrivatePlayer\AppData\Roaming\HelloGames\NMS\save.hg",
        DateTimeOffset.UtcNow,
        Encoding.UTF8.GetByteCount(json));

    var report = new WonderAnalyzer().Analyze(document.RootElement, character);
    if (report.ContributionRecords.Count != 2)
        failures.Add("WCCP source extraction did not retain both fauna discoveries.");

    var builder = new ContributionPackageBuilder();
    var preview = builder.Preview(report);
    if (preview.RecordCount != 2 || preview.ConfirmedFaunaProjectorCount != 2)
        failures.Add("WCCP export preview counts are incorrect.");

    var draft = builder.Build(
        report,
        contributorDisplayName: null,
        anonymous: true,
        createdUtc: new DateTimeOffset(2026, 7, 14, 18, 0, 0, TimeSpan.Zero),
        submissionId: "WC-SUB-20260714-FAUNA-SELFTEST");

    var crossSaveDraft = builder.Build(
        report,
        contributorDisplayName: null,
        anonymous: true,
        sourcePlatformFamily: "nintendo",
        officialCrossSaveToPc: true,
        createdUtc: new DateTimeOffset(2026, 7, 14, 18, 0, 0, TimeSpan.Zero),
        submissionId: "WC-SUB-20260714-SWITCH-SELFTEST");
    if (!string.Equals(crossSaveDraft.Manifest.Source.PlatformFamily, "nintendo", StringComparison.Ordinal) ||
        !string.Equals(
            crossSaveDraft.Manifest.Source.AcquisitionMethod,
            "official_cross_save_to_pc",
            StringComparison.Ordinal))
        failures.Add("WCCP Nintendo Switch cross-save provenance was not recorded correctly.");

    try
    {
        builder.Build(
            report,
            contributorDisplayName: null,
            anonymous: true,
            sourcePlatformFamily: "nintendo",
            officialCrossSaveToPc: false);
        failures.Add("WCCP accepted a Nintendo Switch origin without cross-save confirmation.");
    }
    catch (InvalidOperationException)
    {
        // Expected: the importer can only read a console-origin save after official cross-save reaches PC.
    }

    var validator = new ContributionPackageValidator();
    var exporter = new ContributionPackageExporter(validator);
    var package = exporter.CreatePackage(draft);
    var validation = validator.Validate(package);
    if (!validation.IsValid)
        failures.Add("WCCP package failed self-validation: " + string.Join(" ", validation.Errors));

    var crossSavePackage = exporter.CreatePackage(crossSaveDraft);
    var crossSaveValidation = validator.Validate(crossSavePackage);
    if (!crossSaveValidation.IsValid)
        failures.Add(
            "WCCP Nintendo Switch cross-save package failed self-validation: " +
            string.Join(" ", crossSaveValidation.Errors));

    using var archiveStream = new MemoryStream(package, writable: false);
    using var archive = new ZipArchive(archiveStream, ZipArchiveMode.Read);
    var names = archive.Entries.Select(entry => entry.FullName).OrderBy(value => value).ToArray();
    var expectedNames = new[] { "checksums.json", "discoveries.json", "manifest.json" };
    if (!names.SequenceEqual(expectedNames))
        failures.Add("WCCP ZIP did not contain exactly the three required root files.");

    var manifestJson = ReadZipText(archive, "manifest.json");
    var discoveriesJson = ReadZipText(archive, "discoveries.json");
    var allJson = manifestJson + discoveriesJson + ReadZipText(archive, "checksums.json");
    var forbidden = new[]
    {
        "private-platform-id",
        "private-user-id",
        "PrivateOwnerName",
        "AnotherPrivateOwner",
        "PrivatePlayer",
        "save.hg",
        "\"LID\"",
        "\"UID\"",
        "\"USN\"",
        "\"PTK\"",
        "\"TS\"",
        "\"OWS\""
    };
    foreach (var value in forbidden)
    {
        if (allJson.Contains(value, StringComparison.Ordinal))
            failures.Add($"WCCP privacy regression: package contained {value}.");
    }

    using var manifestDocument = JsonDocument.Parse(manifestJson);
    var attribution = manifestDocument.RootElement.GetProperty("attribution");
    if (!string.Equals(attribution.GetProperty("preference").GetString(), "anonymous", StringComparison.Ordinal) ||
        attribution.GetProperty("displayName").ValueKind != JsonValueKind.Null)
        failures.Add("WCCP anonymous attribution was not normalized correctly.");

    using var discoveriesDocument = JsonDocument.Parse(discoveriesJson);
    var records = discoveriesDocument.RootElement.GetProperty("records").EnumerateArray().ToArray();
    var floatSpider = records.Single(record =>
        string.Equals(
            record.GetProperty("classification").GetProperty("creatureId").GetString(),
            "FLOATSPIDER",
            StringComparison.Ordinal));
    var sixLegCow = records.Single(record =>
        string.Equals(
            record.GetProperty("classification").GetProperty("creatureId").GetString(),
            "SIXLEGCOW",
            StringComparison.Ordinal));

    AssertFixture(
        floatSpider,
        "9W8A+BCAIAADAAAAAwAAAODpvMqmcXUsQIHRoDed/BjM87owQcjgMA==",
        "f2d8781fe11a458207893fcb78e50eef7cd424a92de6c5cefaadf0a1ca6cd77d",
        failures);
    AssertFixture(
        sixLegCow,
        "9W8A+BCAIAADAAAAAwAAAOWksCAXjkvrymyIDC/Iypxn/py3e7yuoQ==",
        "1500932fd93a43508d5bd3de5edc5560d41f435d7a959f737751af9cdaa72469",
        failures);

    var secondary = sixLegCow
        .GetProperty("procedural")
        .GetProperty("seedMappings")
        .GetProperty("secondarySeed");
    if (secondary.GetProperty("vpIndex").GetInt32() != 4 ||
        !string.Equals(secondary.GetProperty("confidence").GetString(), "likely", StringComparison.Ordinal))
        failures.Add("WCCP VP4 was not retained as a likely secondary seed.");
}

static void AssertFixture(
    JsonElement record,
    string expectedMessageId,
    string expectedFingerprint,
    List<string> failures)
{
    var location = record.GetProperty("location");
    if (!string.Equals(location.GetProperty("universalAddress").GetString(), "0x208010F8006FF5", StringComparison.Ordinal) ||
        !string.Equals(location.GetProperty("portalAddressHex").GetString(), "2080F8006FF5", StringComparison.Ordinal))
        failures.Add("WCCP fixture UA or portal conversion mismatch.");

    var projector = record.GetProperty("projector");
    if (!string.Equals(projector.GetProperty("messageId").GetString(), expectedMessageId, StringComparison.Ordinal) ||
        projector.GetProperty("payloadBytes").GetInt32() != 40)
        failures.Add("WCCP confirmed fauna Message ID fixture mismatch.");

    var fingerprint = record.GetProperty("deduplication").GetProperty("scientificFingerprint").GetString();
    if (!string.Equals(fingerprint, expectedFingerprint, StringComparison.Ordinal))
        failures.Add("WCCP scientific fingerprint fixture mismatch.");
}

static string ReadZipText(ZipArchive archive, string name)
{
    var entry = archive.GetEntry(name) ?? throw new InvalidDataException($"Missing WCCP entry {name}.");
    using var stream = entry.Open();
    using var reader = new StreamReader(stream, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
    return reader.ReadToEnd();
}


static void TestMatchedPairProfiler(List<string> failures)
{
    const string compactJson = """
    {
      "a": 4733,
      "b": "XBX|Final",
      "c": "Main",
      "d": {
        "e": "Self Test",
        "f": [
          {"g": "0x123", "h": "Animal"},
          {"g": "0x456", "h": "Flora"}
        ]
      }
    }
    """;

    const string readableJson = """
    {
      "Version": 4733,
      "Platform": "XBX|Final",
      "ActiveContext": "Main",
      "CommonStateData": {
        "SaveName": "Self Test",
        "DiscoveryManagerData": [
          {"UA": "0x123", "DT": "Animal"},
          {"UA": "0x456", "DT": "Flora"}
        ]
      }
    }
    """;

    using var compact = JsonDocument.Parse(compactJson);
    using var readable = JsonDocument.Parse(readableJson);
    var profile = new MatchedPairProfiler().Profile(compact.RootElement, readable.RootElement);

    var expected = new Dictionary<string, string>
    {
        ["a"] = "Version",
        ["b"] = "Platform",
        ["c"] = "ActiveContext",
        ["d"] = "CommonStateData",
        ["e"] = "SaveName",
        ["f"] = "DiscoveryManagerData",
        ["g"] = "UA",
        ["h"] = "DT"
    };

    foreach (var pair in expected)
    {
        if (!profile.Mapping.TryGetValue(pair.Key, out var actual) ||
            !string.Equals(actual, pair.Value, StringComparison.Ordinal))
            failures.Add($"Matched-pair profiler failed to map {pair.Key} to {pair.Value}.");
    }

    using var translated = new JsonKeyTranslator().Translate(compact.RootElement, profile.Mapping);
    var saveName = SaveMetadataParser.GetSaveName(translated.RootElement, "missing");
    if (!string.Equals(saveName, "Self Test", StringComparison.Ordinal))
        failures.Add("Provisional key translation did not expose SaveName.");
}


static void TestProductionKeyMap(List<string> failures)
{
    const string compactJson = """
    {
      "F2P": 4733,
      "8>q": "XBX|Final",
      "XTp": "Main",
      "<h0": {"Pk4": "Production Map Test"},
      "Mcl": [
        {
          "XID": "^HERMITCRAB",
          "WTp": [false, "0x8B2F6257A61D786A"],
          "1p=": [false, "0x0"],
          "m9o": "0x2C2A0FDEEC550BF0",
          "JrL": "0x7481E0DD61B52A01",
          "5L6": "0x54020E0313D92D"
        }
      ],
      "fDu": [
        {
          "8P3": {
            "5L6": "0x54020E0313D92D",
            "<Dn": "Animal",
            "bEr": [
              "0x8B2F6257A61D786A",
              "0x05FA296DBC7FF044",
              "0x2C2A0FDEEC550BF0",
              "0x7481E0DD61B52A01"
            ]
          },
          "ksu": {"V?:": "self-test", "D6b": "ST"}
        }
      ]
    }
    """;

    using var compact = JsonDocument.Parse(compactJson);
    var provider = new ProductionKeyMapProvider();

    if (!provider.Supports(compact.RootElement))
        failures.Add("Production key map did not recognize supported save version 4733.");

    if (!provider.TryGetSchema(compact.RootElement, out var currentSchema) ||
        currentSchema.SchemaId != ProductionKeyMapProvider.CurrentSchemaId)
        failures.Add("Production key map did not select the 4733 production schema.");

    using var legacyCompact = JsonDocument.Parse("{\"F2P\":4720}");
    if (!provider.TryGetSchema(legacyCompact.RootElement, out var legacySchema) ||
        legacySchema.SchemaId != ProductionKeyMapProvider.LegacySchemaId ||
        legacySchema.AcceptedEvidenceMappings != 848)
        failures.Add("Production key map did not recognize the corroborated 4720 schema.");

    using var unsupportedCompact = JsonDocument.Parse("{\"F2P\":4719}");
    if (provider.Supports(unsupportedCompact.RootElement))
        failures.Add("Production key map accepted an unsupported save version.");

    if (provider.Mapping.Count != ProductionKeyMapProvider.PersistedTranslations)
        failures.Add("Production key map count does not match its declared persisted translation count.");

    var critical = new Dictionary<string, string>
    {
        ["F2P"] = "Version",
        ["<h0"] = "CommonStateData",
        ["Pk4"] = "SaveName",
        ["Mcl"] = "Pets",
        ["fDu"] = "DiscoveryManagerData",
        ["8P3"] = "DD",
        ["5L6"] = "UA",
        ["<Dn"] = "DT",
        ["bEr"] = "VP",
        ["WTp"] = "CreatureSeed",
        ["m9o"] = "SpeciesSeed",
        ["JrL"] = "GenusSeed",
        ["bQN"] = "ActiveSpaceBattleLevel",
        ["eoL"] = "FloatValue",
        ["kVv"] = "TSrec"
    };

    foreach (var pair in critical)
    {
        if (!provider.Mapping.TryGetValue(pair.Key, out var actual) ||
            !string.Equals(actual, pair.Value, StringComparison.Ordinal))
            failures.Add($"Production key map is missing {pair.Key} -> {pair.Value}.");
    }

    using var translated = new JsonKeyTranslator().Translate(compact.RootElement, provider.Mapping);
    var saveName = SaveMetadataParser.GetSaveName(translated.RootElement, "missing");
    if (!string.Equals(saveName, "Production Map Test", StringComparison.Ordinal))
        failures.Add("Production key map did not expose SaveName.");

    var character = new SaveCharacter(
        "production-map-test",
        "test-account",
        "WGS candidate",
        "Self-test slot",
        SavePlatform.XboxGamePass,
        "<memory>",
        DateTimeOffset.UtcNow,
        Encoding.UTF8.GetByteCount(compactJson));

    var report = new WonderAnalyzer().Analyze(translated.RootElement, character);
    if (report.DiscoveryCount != 1)
        failures.Add("Production key map did not expose the synthetic discovery.");
    if (report.MatchCount != 1)
        failures.Add("Production key map did not expose the synthetic pet match.");
}


static void TestCharacterRevisionGrouping(List<string> failures)
{
    var accountId = "xbox-test-account";
    var older = DateTimeOffset.Parse("2026-07-12T20:00:00Z");
    var newer = older.AddMinutes(2);

    var candidates = new[]
    {
        new SaveCharacter(
            "flower-auto", accountId, "Flower-Kin", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/flower-auto", older, 5_000_000,
            Revisions: [new SaveRevision("flower-auto-rev", "Read-only revision", "C:/read-only/flower-auto", older, 5_000_000, "AUTO")],
            DiscoveryCount: 3207, PetCount: 34, ExactMatchCount: 9, IsAutomaticallyResolved: true),
        new SaveCharacter(
            "flower-manual", accountId, "Flower-Kin", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/flower-manual", newer, 5_100_000,
            Revisions: [new SaveRevision("flower-manual-rev", "Read-only revision", "C:/read-only/flower-manual", newer, 5_100_000, "MANUAL")],
            DiscoveryCount: 3208, PetCount: 34, ExactMatchCount: 9, IsAutomaticallyResolved: true),
        new SaveCharacter(
            "pj", accountId, "PJ's Explorer", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/pj", newer, 950_000, DiscoveryCount: 528, PetCount: 11, ExactMatchCount: 9),
        new SaveCharacter(
            "unnamed-a", accountId, "WGS candidate 1", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/unnamed-a", older, 588_100, IsPlayableCharacterState: true),
        new SaveCharacter(
            "unnamed-b", accountId, "WGS candidate 2", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/unnamed-b", newer, 587_700, IsPlayableCharacterState: true),
        new SaveCharacter(
            "metadata", accountId, "WGS candidate 99", "Cloud save", SavePlatform.XboxGamePass,
            "C:/read-only/metadata", newer, 140_000)
    };

    var grouped = new CharacterRevisionGrouper().Group(candidates);
    if (grouped.Count != 4)
        failures.Add($"Character revision grouping expected 2 named characters, 1 unnamed slot, and 1 research candidate; found {grouped.Count}.");

    var flower = grouped.SingleOrDefault(character => character.DisplayName == "Flower-Kin");
    if (flower is null)
    {
        failures.Add("Character revision grouping did not preserve Flower-Kin.");
        return;
    }

    if (flower.RevisionCount != 2)
        failures.Add($"Flower-Kin expected 2 grouped revisions, found {flower.RevisionCount}.");
    if (flower.SourcePath != "C:/read-only/flower-manual")
        failures.Add("Character revision grouping did not select the newest revision.");
    if (flower.DiscoveryCount != 3208 || flower.PetCount != 34 || flower.ExactMatchCount != 9)
        failures.Add("Character revision grouping did not retain the preferred revision summary.");
    if (flower.ReadOnlyRevisions.Count == 0 || !flower.ReadOnlyRevisions[0].IsPreferred)
        failures.Add("Character revision grouping did not mark the preferred revision.");

    var unnamed = grouped.SingleOrDefault(character => character.DisplayName == "Unnamed Character");
    if (unnamed is null || unnamed.RevisionCount != 2)
        failures.Add("Unnamed character revisions were not grouped into one slot.");

    if (!grouped.Any(character => character.DisplayName == "Research candidate 1"))
        failures.Add("Non-character zero-signal data was not retained as a research candidate.");

    if (unnamed is not null && (unnamed.DiscoveryCount != 0 || unnamed.PetCount != 0 || unnamed.ExactMatchCount != 0))
        failures.Add("Zero-catalog unnamed character revisions should remain a valid grouped character slot.");

    var steamCandidates = new[]
    {
        new SaveCharacter(
            "steam-slot-1-auto", "steam-account", "Boots", "Steam slot 1", SavePlatform.Steam,
            "C:/read-only/save.hg", older, 2_000_000, SlotKey: "steam-slot-1"),
        new SaveCharacter(
            "steam-slot-1-manual", "steam-account", "Boots", "Steam slot 1", SavePlatform.Steam,
            "C:/read-only/mf_save.hg", newer, 2_010_000, SlotKey: "steam-slot-1"),
        new SaveCharacter(
            "steam-slot-2", "steam-account", "Boots", "Steam slot 2", SavePlatform.Steam,
            "C:/read-only/save2.hg", newer, 1_500_000, SlotKey: "steam-slot-2")
    };

    var groupedSteam = new CharacterRevisionGrouper().Group(steamCandidates);
    if (groupedSteam.Count != 2)
        failures.Add("Steam slots with the same SaveName were incorrectly merged across slot numbers.");
    if (groupedSteam.Single(character => character.SlotKey == "steam-slot-1").RevisionCount != 2)
        failures.Add("Steam automatic and manual revisions were not grouped by slot.");
}


static void TestPlayableCharacterDetection(List<string> failures)
{
    using var playable = JsonDocument.Parse(
        """
        {
          "PlayerStateData": {},
          "CommonStateData": {},
          "DiscoveryManagerData": {}
        }
        """);
    using var metadata = JsonDocument.Parse(
        """
        {
          "AccountData": {},
          "Settings": {}
        }
        """);
    using var nestedPlayable = JsonDocument.Parse(
        """
        {
          "BaseContext": {
            "PlayerStateData": {
              "UniverseAddress": {},
              "PreviousUniverseAddress": {}
            }
          }
        }
        """);

    if (!SaveMetadataParser.HasPlayableCharacterState(playable.RootElement))
        failures.Add("Playable character-state structure was not recognized.");
    if (!SaveMetadataParser.HasPlayableCharacterState(nestedPlayable.RootElement))
        failures.Add("BaseContext character-state structure was not recognized for transit.");
    if (SaveMetadataParser.HasPlayableCharacterState(metadata.RootElement))
        failures.Add("Metadata-only structure was incorrectly recognized as a playable character.");
}

static void TestSteamSlotRecognition(List<string> failures)
{
    var cases = new[]
    {
        (File: "save.hg", Slot: 1, Label: "save revision"),
        (File: "mf_save.hg", Slot: 1, Label: "mf_save revision"),
        (File: "save2.hg", Slot: 2, Label: "save revision"),
        (File: "mf_save12.hg", Slot: 12, Label: "mf_save revision")
    };

    foreach (var item in cases)
    {
        if (!SteamSaveScanner.TryDescribeSlotFile(item.File, out var slot, out var label) ||
            slot != item.Slot || !string.Equals(label, item.Label, StringComparison.Ordinal))
            failures.Add($"Steam slot parser failed for {item.File}.");
    }

    if (SteamSaveScanner.TryDescribeSlotFile("accountdata.hg", out _, out _))
        failures.Add("Steam slot parser accepted accountdata.hg as a character save.");
}

static void TestPegasusAssetCollection(List<string> failures)
{
    const string json = """
    {
      "CommonStateData": {"SaveName": "Pegasus Self Test"},
      "Pets": [
        {
          "CreatureID": "^FLOATSPIDER",
          "CreatureSeed": [true, "0x100"],
          "CreatureSecondarySeed": [false, "0x0"],
          "SpeciesSeed": "0x200",
          "GenusSeed": "0x300",
          "UA": "0x400",
          "CreatureType": {"CreatureType": "Passive"},
          "PetBattlerUseCoreStatClassOverrides": true,
          "PetBattlerCoreStatClassOverrides": [
            {"InventoryClass": "A"},
            {"InventoryClass": "B"},
            {"InventoryClass": "S"}
          ],
          "PetBattlerMoves": ["^ATTACK_AFF"],
          "CustomName": "Private Pet Name"
        }
      ],
      "ShipOwnership": [
        {
          "Name": "Private Ship Name",
          "Resource": {
            "Filename": "MODELS/COMMON/SPACECRAFT/FIGHTERS/FIGHTER_PROC.SCENE.MBIN",
            "Seed": [true, "0x500"]
          },
          "Inventory": {
            "Class": {"InventoryClass": "S"},
            "BaseStatValues": [{"BaseStatID": "^SHIP_DAMAGE", "Value": 50.0}]
          }
        }
      ],
      "CurrentFreighter": {
        "Filename": "MODELS/COMMON/SPACECRAFT/INDUSTRIAL/PIRATEFREIGHTER.SCENE.MBIN",
        "Seed": [true, "0x600"]
      },
      "FreighterInventory": {
        "Class": {"InventoryClass": "A"},
        "BaseStatValues": []
      },
      "FleetFrigates": [
        {
          "ResourceSeed": [true, "0x700"],
          "HomeSystemSeed": [true, "0x701"],
          "FrigateClass": {"FrigateClass": "Combat"},
          "InventoryClass": {"InventoryClass": "S"},
          "Race": {"AlienRace": "Gek"},
          "Stats": [1,2,3],
          "TraitIDs": ["^TRAIT_A"]
        }
      ],
      "Multitools": [
        {
          "Name": "Private Tool Name",
          "Seed": [true, "0x800"],
          "Store": {
            "Class": {"InventoryClass": "A"},
            "BaseStatValues": []
          },
          "WeaponClass": {"WeaponStatClass": "Rifle"},
          "Resource": {
            "Filename": "MODELS/COMMON/WEAPONS/MULTITOOL/MULTITOOL.SCENE.MBIN",
            "Seed": [false, "0x0"]
          }
        }
      ],
      "Inventory": {
        "Slots": [
          {
            "Type": {"InventoryType": "Product"},
            "Id": "^F_JELLYCHILD",
            "Amount": 3
          },
          {
            "Type": {"InventoryType": "Product"},
            "Id": "^TRADE_ITEM",
            "Amount": 20
          }
        ]
      }
    }
    """;

    using var document = JsonDocument.Parse(json);
    var analyzer = new PegasusAssetAnalyzer();
    var report = analyzer.Analyze(
        document.RootElement,
        "Pegasus Self Test",
        "Self-test",
        new PegasusCollectionOptions());

    if (report.Count("CompanionPet") != 1) failures.Add("Pegasus beta did not extract the companion pet.");
    if (report.Count("CreatureEggSignal") != 1) failures.Add("Pegasus beta did not identify the egg-like inventory signal.");
    if (report.Count("Starship") != 1) failures.Add("Pegasus beta did not extract the starship seed.");
    if (report.Count("Freighter") != 1) failures.Add("Pegasus beta did not extract the current freighter.");
    if (report.Count("Frigate") != 1) failures.Add("Pegasus beta did not extract the frigate record.");
    if (report.Count("Multitool") != 1) failures.Add("Pegasus beta did not extract the multitool seed.");
    if (report.Count("InventoryItem") != 0) failures.Add("Inventory catalog should remain off by default.");
    if (report.Schema != "wonder-codex-pegasus-asset-manifest/v0.2.1-beta")
        failures.Add("Pegasus asset manifest did not use the v0.2.1 provenance schema.");
    if (report.Assets.Single(asset => asset.AssetType == "Starship").SourceRole != "owned_slot")
        failures.Add("Pegasus starship provenance did not retain the ShipOwnership role.");
    if (report.Assets.Single(asset => asset.AssetType == "Frigate").SourceRole != "fleet_member")
        failures.Add("Pegasus frigate provenance did not retain the fleet-member role.");
    if (report.Assets.Single(asset => asset.AssetType == "Freighter").SourceRole != "current")
        failures.Add("Pegasus current freighter provenance was not classified.");
    if (report.Assets.Single(asset => asset.AssetType == "Multitool").SourceRole != "owned_slot")
        failures.Add("Pegasus multi-tool provenance did not retain the owned-slot role.");

    var serialized = JsonSerializer.Serialize(report);
    if (serialized.Contains("Private Pet Name", StringComparison.Ordinal) ||
        serialized.Contains("Private Ship Name", StringComparison.Ordinal) ||
        serialized.Contains("Private Tool Name", StringComparison.Ordinal))
        failures.Add("Pegasus beta included custom asset names without opt-in.");
    if (serialized.Contains("\"amount\":3", StringComparison.Ordinal))
        failures.Add("Pegasus beta included inventory quantities without opt-in.");

    var optedIn = analyzer.Analyze(
        document.RootElement,
        "Pegasus Self Test",
        "Self-test",
        new PegasusCollectionOptions(
            IncludeInventoryCatalog: true,
            IncludeInventoryAmounts: true,
            IncludeCustomNames: true));

    if (optedIn.Count("InventoryItem") != 2)
        failures.Add("Pegasus beta inventory opt-in did not return normalized item identifiers.");
    var optedInSerialized = JsonSerializer.Serialize(optedIn);
    if (!optedInSerialized.Contains("Private Pet Name", StringComparison.Ordinal) ||
        !optedInSerialized.Contains("\"amount\":3", StringComparison.Ordinal))
        failures.Add("Pegasus beta opt-in fields were not included after explicit selection.");
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
