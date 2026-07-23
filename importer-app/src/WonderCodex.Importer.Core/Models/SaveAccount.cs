namespace WonderCodex.Importer.Core.Models;

public sealed record SaveAccount(
    string Id,
    string DisplayName,
    SavePlatform Platform,
    IReadOnlyList<SaveCharacter> Characters)
{
    public string PlatformLabel => Platform switch
    {
        SavePlatform.XboxGamePass => "Xbox / Game Pass PC",
        SavePlatform.Gog => "GOG",
        _ => "Steam"
    };

    public string CharacterSummary
    {
        get
        {
            if (Characters.Count == 0) return "No readable character slots";
            var revisions = Characters.Sum(character => character.RevisionCount);
            return $"{Characters.Count} character slot{(Characters.Count == 1 ? string.Empty : "s")} • " +
                   $"{revisions} read-only revision{(revisions == 1 ? string.Empty : "s")}";
        }
    }
}
