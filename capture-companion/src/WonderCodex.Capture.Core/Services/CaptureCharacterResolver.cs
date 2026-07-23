using WonderCodex.Capture.Core.Models;
using WonderCodex.Importer.Core.Models;

namespace WonderCodex.Capture.Core.Services;

public static class CaptureCharacterResolver
{
    public static SaveCharacter? Resolve(
        CaptureCharacterSelection selection,
        IEnumerable<SaveAccount> accounts)
    {
        var candidates = accounts
            .Where(account => account.Platform == selection.Platform)
            .SelectMany(account => account.Characters)
            .ToArray();

        if (!string.IsNullOrWhiteSpace(selection.SlotKey))
        {
            var slot = candidates.FirstOrDefault(character =>
                string.Equals(character.SlotKey, selection.SlotKey, StringComparison.Ordinal));
            if (slot is not null) return slot;
        }

        var exact = candidates.FirstOrDefault(character =>
            string.Equals(character.Id, selection.CharacterId, StringComparison.Ordinal));
        if (exact is not null) return exact;

        var named = candidates
            .Where(character => string.Equals(
                character.DisplayName,
                selection.DisplayName,
                StringComparison.OrdinalIgnoreCase))
            .ToArray();
        return named.Length == 1 ? named[0] : null;
    }
}
