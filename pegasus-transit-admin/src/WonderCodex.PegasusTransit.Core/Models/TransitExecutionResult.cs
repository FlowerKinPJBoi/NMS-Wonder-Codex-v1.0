namespace WonderCodex.PegasusTransit.Core.Models;

public sealed record TransitExecutionResult(
    bool Succeeded,
    string Platform,
    string BackupPath,
    TransitLocation VerifiedLocation,
    string Message,
    string? PostWriteSnapshotPath = null);
