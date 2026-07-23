using WonderCodex.Capture.Core.Models;
using WonderCodex.Capture.Core.Services;
using WonderCodex.Importer.Core.Models;

var failures = new List<string>();
TestDiscoveryDiff(failures);
TestPairing(failures);
TestCharacterResolution(failures);

if (failures.Count > 0)
{
    Console.Error.WriteLine("Wonder Capture Companion self-tests failed:");
    foreach (var failure in failures) Console.Error.WriteLine($"- {failure}");
    return 1;
}

Console.WriteLine("Wonder Capture Companion self-tests passed.");
return 0;

static void TestDiscoveryDiff(List<string> failures)
{
    var service = new DiscoverySnapshotService();
    var first = Report(
        Source("Animal", 0x0011223344556677UL, 1, 2, 3));
    var second = Report(
        Source("Animal", 0x0011223344556677UL, 1, 2, 3),
        Source("Flora", 0x0077665544332211UL, 4, 5));

    var baseline = service.Build("test-character", first, DateTimeOffset.Parse("2026-07-15T12:00:00Z"));
    var current = service.Build("test-character", second, DateTimeOffset.Parse("2026-07-15T12:01:00Z"));
    var added = service.FindAdded(baseline, current);

    if (baseline.Count != 1) failures.Add("Baseline count was not deterministic.");
    if (added.Count != 1 || added[0].DiscoveryType != "Flora")
        failures.Add("Discovery diff did not isolate the added flora record.");

    var repeated = DiscoverySnapshotService.Fingerprint(first.ContributionRecords[0]);
    if (repeated != baseline.Records.Keys.Single())
        failures.Add("Scientific discovery fingerprint was not deterministic.");
}

static void TestPairing(List<string> failures)
{
    var detected = DateTimeOffset.Parse("2026-07-15T12:00:30Z");
    var discovery = new CaptureDiscovery(
        "fingerprint",
        "Animal",
        "0011223344556677",
        "message",
        "TREX",
        "Trex",
        detected);
    var near = new ScreenshotCandidate(
        "C:/screens/near.png",
        "near.png",
        detected.AddSeconds(-18),
        detected.AddSeconds(-18),
        1000);
    var far = new ScreenshotCandidate(
        "C:/screens/far.png",
        "far.png",
        detected.AddMinutes(-10),
        detected.AddMinutes(-10),
        1000);

    var pairs = new CapturePairingService().Propose([discovery], [far, near]);
    if (pairs.Count != 1 || pairs[0].Screenshot.FileName != "near.png")
        failures.Add("Pairing did not choose the nearest screenshot inside the safety window.");
    if (pairs.Count == 1 && pairs[0].Confirmed)
        failures.Add("A timestamp proposal was incorrectly auto-confirmed.");
}

static void TestCharacterResolution(List<string> failures)
{
    var character = new SaveCharacter(
        "revision-new",
        "account-1",
        "Boots",
        "Steam slot 2",
        SavePlatform.Steam,
        "C:/read-only/save2.hg",
        DateTimeOffset.UtcNow,
        900,
        SlotKey: "steam-slot-2");
    var selection = new CaptureCharacterSelection(
        "account-1",
        "revision-old",
        "Boots",
        SavePlatform.Steam,
        "Steam slot 2",
        "steam-slot-2");
    var account = new SaveAccount("account-1", "Boots", SavePlatform.Steam, [character]);

    if (CaptureCharacterResolver.Resolve(selection, [account]) != character)
        failures.Add("A new save revision did not resolve by stable Steam slot key.");
}

static AnalysisReport Report(params ContributionSourceRecord[] records)
{
    var report = new AnalysisReport();
    report.ContributionRecords.AddRange(records);
    return report;
}

static ContributionSourceRecord Source(string type, ulong ua, params ulong[] vp)
    => new()
    {
        DiscoveryType = type,
        UniversalAddress = ua,
        Vp = [.. vp]
    };
