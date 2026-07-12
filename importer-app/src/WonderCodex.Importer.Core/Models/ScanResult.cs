namespace WonderCodex.Importer.Core.Models;

public sealed record ScanResult(
    IReadOnlyList<SaveAccount> Accounts,
    IReadOnlyList<string> Warnings)
{
    public int CharacterCount => Accounts.Sum(account => account.Characters.Count);
}
