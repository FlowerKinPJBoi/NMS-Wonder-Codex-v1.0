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

    public string CharacterSummary => Characters.Count == 0
        ? "No readable characters"
        : string.Join(", ", Characters.Take(3).Select(character => character.DisplayName)) +
          (Characters.Count > 3 ? $" +{Characters.Count - 3} more" : string.Empty);
}
