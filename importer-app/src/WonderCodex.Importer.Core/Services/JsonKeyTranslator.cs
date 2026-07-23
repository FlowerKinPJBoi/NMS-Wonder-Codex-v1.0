using System.Text.Json;

namespace WonderCodex.Importer.Core.Services;

public sealed class JsonKeyTranslator
{
    public JsonDocument Translate(
        JsonElement compactRoot,
        IReadOnlyDictionary<string, string> mapping)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            WriteElement(writer, compactRoot, mapping);
            writer.Flush();
        }

        return JsonDocument.Parse(buffer.ToArray(), JsonOptions);
    }

    private static void WriteElement(
        Utf8JsonWriter writer,
        JsonElement element,
        IReadOnlyDictionary<string, string> mapping)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                writer.WriteStartObject();
                foreach (var property in element.EnumerateObject())
                {
                    var translatedName = mapping.TryGetValue(property.Name, out var readableName)
                        ? readableName
                        : property.Name;
                    writer.WritePropertyName(translatedName);
                    WriteElement(writer, property.Value, mapping);
                }
                writer.WriteEndObject();
                break;

            case JsonValueKind.Array:
                writer.WriteStartArray();
                foreach (var item in element.EnumerateArray())
                    WriteElement(writer, item, mapping);
                writer.WriteEndArray();
                break;

            default:
                element.WriteTo(writer);
                break;
        }
    }

    private static readonly JsonDocumentOptions JsonOptions = new()
    {
        AllowTrailingCommas = true,
        CommentHandling = JsonCommentHandling.Skip,
        MaxDepth = 512
    };
}
