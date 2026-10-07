package nomanssave;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.Deque;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Read-only, allow-list extraction for the Wonder Codex contribution review.
 * Adapted from WonderAnalyzer/PegasusAssetAnalyzer in Wonder-Codex-Importer.
 * Neither account identifiers, file paths, inventories nor the player's current
 * position enter a contribution record. An owned procedural seed is never a location claim.
 */
public final class WCEditorCodexScan {
    private static final BigInteger MAX64 = BigInteger.ONE.shiftLeft(64).subtract(BigInteger.ONE);
    private static final BigInteger MAX_UA = BigInteger.ONE.shiftLeft(56).subtract(BigInteger.ONE);
    private static final int MAX_NODES = 2000000;
    private WCEditorCodexScan() { }

    public static final class Row {
        public final String id, key, category, name, summary, detail, reason, recordType;
        public final boolean eligible, wonderAffiliated;
        public final eY recordContent;
        private Row(String id, String category, String name, String summary,
                    boolean eligible, String reason, String recordType, eY recordContent) {
            this.id = id; this.key = id; this.category = category; this.name = name;
            this.summary = summary; this.detail = summary; this.eligible = eligible;
            this.reason = reason; this.recordType = recordType; this.recordContent = recordContent;
            // Save data does not attest membership in a community or organization.
            this.wonderAffiliated = false;
        }
    }

    public static final class Result {
        public final List<Row> rows;
        public final List<String> warnings;
        public final Map<String, Integer> counts;
        public final String summary;
        public final int eligibleCount, discoveryCount, assetCount;
        private Result(List<Row> input, List<String> warnings) {
            this.rows = Collections.unmodifiableList(new ArrayList<Row>(input));
            this.warnings = Collections.unmodifiableList(new ArrayList<String>(warnings));
            Map<String, Integer> totals = new LinkedHashMap<String, Integer>();
            int eligible = 0, discoveries = 0, assets = 0;
            for (Row row : rows) {
                totals.put(row.category, totals.containsKey(row.category) ? totals.get(row.category) + 1 : 1);
                if (row.eligible) eligible++;
                if ("discovery".equals(row.recordType)) discoveries++; else assets++;
            }
            this.counts = Collections.unmodifiableMap(totals);
            this.eligibleCount = eligible; this.discoveryCount = discoveries; this.assetCount = assets;
            this.summary = rows.size() + " records found: " + discoveries + " discoveries and "
                    + assets + " owned-asset records. " + eligible + " can be submitted; "
                    + (rows.size() - eligible) + " are available for local review only.";
        }
    }

    public static Result scan(eY root) {
        if (root == null) throw new IllegalArgumentException("Choose a game save first.");
        Builder builder = new Builder();
        Deque<Node> queue = new ArrayDeque<Node>();
        IdentityHashMap<Object, Boolean> visited = new IdentityHashMap<Object, Boolean>();
        queue.add(new Node(root, "", -1));
        int nodes = 0;
        while (!queue.isEmpty()) {
            if (Thread.currentThread().isInterrupted()) throw new IllegalStateException("Scan cancelled.");
            Node node = queue.removeFirst();
            if (!(node.value instanceof eY) && !(node.value instanceof eV)) continue;
            if (visited.put(node.value, Boolean.TRUE) != null) continue;
            if (++nodes > MAX_NODES) {
                builder.warn("The save exceeds the scan size limit. Results are incomplete.");
                break;
            }
            if (node.value instanceof eV) {
                eV array = (eV)node.value;
                for (int i = 0; i < array.size(); i++) {
                    Object child = array.get(i);
                    if (child instanceof eY || child instanceof eV) queue.addLast(new Node(child, node.collection, i));
                }
                continue;
            }
            eY value = (eY)node.value;
            Object dd = value.get("DD");
            if (dd instanceof eY && ((eY)dd).get("UA") != null && ((eY)dd).get("DT") != null
                    && ((eY)dd).get("VP") instanceof eV) builder.discovery(value, (eY)dd);
            if (looksLikePet(value)) builder.pets.add(node);
            eY resource = object(value.get("Resource"));
            String filename = resource == null ? "" : text(resource.get("Filename"));
            String upper = filename.toUpperCase(Locale.ROOT);
            if (upper.contains("/SPACECRAFT/") && (value.get("Inventory") instanceof eY
                    || value.get("Inventory_TechOnly") instanceof eY || value.get("Inventory_Cargo") instanceof eY)) {
                builder.ship(node, resource);
            }
            if (upper.contains("/WEAPONS/MULTITOOL/") && value.get("Store") instanceof eY)
                builder.multitool(node, resource);
            if (value.get("ResourceSeed") != null && value.get("FrigateClass") instanceof eY
                    && value.get("InventoryClass") instanceof eY && value.get("Stats") instanceof eV)
                builder.frigate(node);
            if (value.get("CurrentFreighter") instanceof eY) builder.freighter(value, (eY)value.get("CurrentFreighter"));
            if (value.get("Id") != null && value.get("Amount") != null && value.get("Type") instanceof eY)
                builder.inventory(value);
            for (int i = 0; i < value.length; i++) {
                String property = value.names[i];
                Object child = value.get(property);
                if (child instanceof eY || child instanceof eV)
                    queue.addLast(new Node(child, child instanceof eV ? property : node.collection, node.ordinal));
            }
        }
        builder.finishPets();
        builder.finishInventory();
        if (builder.discoveries.isEmpty()) builder.warn("No readable DD/UA/DT/VP discovery records were found in this save.");
        if (builder.duplicateDiscoveries > 0) builder.warn(builder.duplicateDiscoveries + " repeated discovery records were combined by exact identity.");
        List<Row> rows = new ArrayList<Row>();
        for (Discovery discovery : builder.discoveries.values()) rows.add(discovery.row());
        rows.addAll(builder.assets.values());
        return new Result(rows, builder.warnings);
    }

    private static final class Node {
        final Object value; final String collection; final int ordinal;
        Node(Object value, String collection, int ordinal) { this.value = value; this.collection = collection; this.ordinal = ordinal; }
    }
    private static final class Discovery {
        String id, category, name, reason, ua, petKey;
        eY recordContent;
        boolean eligible;
        Row row() {
            String location = ua.isEmpty() ? "Address unavailable" : locationSummary(ua);
            return new Row(id, category, name, location + (eligible ? " · discovery record" : " · " + reason),
                    eligible, reason, "discovery", recordContent);
        }
    }
    private static final class Item {
        final String id, type; int count;
        Item(String id, String type) { this.id = id; this.type = type; }
    }

    private static final class Builder {
        final Map<String, Discovery> discoveries = new LinkedHashMap<String, Discovery>();
        final Map<String, Row> assets = new LinkedHashMap<String, Row>();
        final Map<String, Item> items = new LinkedHashMap<String, Item>();
        final List<Node> pets = new ArrayList<Node>();
        final List<String> warnings = new ArrayList<String>();
        int duplicateDiscoveries;
        void warn(String warning) { if (warnings.size() < 100 && !warnings.contains(warning)) warnings.add(warning); }

        void discovery(eY source, eY dd) {
            String dt = discoveryType(text(dd.get("DT")));
            String category = category(dt);
            String ua = unsignedHex(dd.get("UA"), true);
            eV vpRaw = (eV)dd.get("VP");
            eV vp = new eV();
            boolean validVp = vpRaw.size() <= 32;
            for (int i = 0; i < Math.min(vpRaw.size(), 32); i++) {
                String seed = unsignedHex(vpRaw.get(i), false);
                if (seed.isEmpty()) validVp = false;
                // Null preserves a malformed position for local review; never substitute zero.
                vp.add(seed.isEmpty() ? null : seed);
            }
            String reason = "";
            if (ua.isEmpty()) reason = "Missing or invalid unsigned 56-bit discovery address.";
            else if (!validVp) reason = "Invalid procedural value or unsupported VP length; no values were replaced.";
            else if ("Animal".equals(dt) && vp.size() < 3) reason = "Fauna requires at least three procedural values.";
            else if (("Flora".equals(dt) || "Mineral".equals(dt)) && vp.size() < 2) reason = "Flora and mineral discoveries require at least two procedural values.";
            else if (!supportedDiscovery(dt)) reason = "This discovery type is not supported by the current Codex import service.";
            String canonical = dt.toUpperCase(Locale.ROOT) + "|" + (ua.isEmpty() ? safeScalar(dd.get("UA")) : ua);
            for (int i = 0; i < vpRaw.size(); i++) {
                String normalized = unsignedHex(vpRaw.get(i), false);
                canonical += "|" + (normalized.isEmpty() ? "invalid:" + safeScalar(vpRaw.get(i)) : normalized);
            }
            String id = "WCI-DISC-" + hash(canonical).substring(0, 20).toUpperCase(Locale.ROOT);
            if (discoveries.containsKey(id)) { duplicateDiscoveries++; return; }
            eY recordContent = new eY();
            recordContent.put("DT", dt); recordContent.put("UA", ua); recordContent.put("VP", vp);
            String name = clean(nested(source, "DM", "CN"), 200);
            if (!name.isEmpty()) recordContent.put("CustomName", name);
            Discovery discovery = new Discovery();
            discovery.id = id; discovery.category = category; discovery.ua = ua;
            discovery.name = name.isEmpty() ? category + " " + (discoveries.size() + 1) : name;
            discovery.recordContent = recordContent; discovery.reason = reason; discovery.eligible = reason.isEmpty();
            if ("Animal".equals(dt) && !ua.isEmpty() && validVp && vp.size() >= 4)
                discovery.petKey = join(ua, text(vp.get(0)), text(vp.get(2)), text(vp.get(3)));
            discoveries.put(id, discovery);
        }

        void ship(Node node, eY resource) {
            eY ship = (eY)node.value;
            String filename = gameResource(resource.get("Filename"));
            String seed = seedHex(ship.get("Seed"));
            if (isZero(seed)) seed = seedHex(resource.get("Seed"));
            boolean corvette = filename.toUpperCase(Locale.ROOT).contains("/BIGGS/");
            String assetClass = inventoryClass(ship, "Inventory");
            if (assetClass.isEmpty()) assetClass = inventoryClass(ship, "Inventory_Cargo");
            eY recordContent = baseAsset("Starship", node, clean(ship.get("Name"), 200), assetClass);
            recordContent.put("resourceFilename", filename); recordContent.put("seed", seed);
            String reason = !validResource(filename) ? "Missing or invalid game resource path." : isZero(seed)
                    ? "No usable procedural seed was found." : corvette
                    ? "Corvette assemblies need a separate build identity; their shared seed cannot safely identify a build." : "";
            asset(corvette ? "Corvette" : "Starship", "starship", filename + "|" + seed, recordContent, reason,
                    corvette ? "Owned Corvette · build data remains local" : "Owned starship · original location and native class are unknown");
        }

        void multitool(Node node, eY resource) {
            eY tool = (eY)node.value;
            String filename = gameResource(resource.get("Filename"));
            String seed = seedHex(tool.get("Seed"));
            String assetClass = inventoryClass(tool, "Store");
            if (assetClass.isEmpty()) assetClass = clean(nested(tool, "ArchivedInventoryClass", "InventoryClass"), 4);
            String name = clean(tool.get("Name"), 200);
            if (name.isEmpty()) name = clean(tool.get("ArchivedName"), 200);
            eY recordContent = baseAsset("Multitool", node, name, assetClass);
            recordContent.put("resourceFilename", filename); recordContent.put("seed", seed);
            asset("Multitool", "multitool", filename + "|" + seed, recordContent,
                    !validResource(filename) ? "Missing or invalid game resource path." : isZero(seed) ? "No usable procedural seed was found." : "",
                    "Owned multitool · original location and native class are unknown");
        }

        void freighter(eY parent, eY resource) {
            String filename = gameResource(resource.get("Filename"));
            String seed = seedHex(resource.get("Seed"));
            // Empty CurrentFreighter is a normal unused slot, not a discovered asset.
            if (filename.isEmpty() && isZero(seed)) return;
            Node node = new Node(resource, "CurrentFreighter", -1);
            eY recordContent = baseAsset("Freighter", node, clean(parent.get("PlayerFreighterName"), 200), inventoryClass(parent, "FreighterInventory"));
            recordContent.put("sourceRole", "current"); recordContent.put("resourceFilename", filename); recordContent.put("seed", seed);
            asset("Freighter", "freighter", filename + "|" + seed, recordContent,
                    !validResource(filename) ? "Missing or invalid game resource path." : isZero(seed) ? "No usable procedural seed was found." : "",
                    "Owned freighter · current class only; no original location claim");
        }

        void frigate(Node node) {
            eY frigate = (eY)node.value;
            String seed = seedHex(frigate.get("ResourceSeed"));
            String type = clean(nested(frigate, "FrigateClass", "FrigateClass"), 60);
            if (!type.matches("[A-Za-z0-9_ -]*")) type = "";
            eY recordContent = baseAsset("Frigate", node, clean(frigate.get("CustomName"), 200), clean(nested(frigate, "InventoryClass", "InventoryClass"), 4));
            recordContent.put("resourceSeed", seed); recordContent.put("frigateClass", type);
            asset("Frigate", "frigate", seed + "|" + type, recordContent,
                    isZero(seed) ? "No usable procedural seed was found." : type.isEmpty() ? "Frigate type is missing." : "",
                    "Owned frigate · current fleet class only; no original location claim");
        }

        void asset(String category, String type, String identity, eY recordContent, String reason, String summary) {
            String id = "PGA-" + type.toUpperCase(Locale.ROOT) + "-" + hash(type + "|" + identity).substring(0, 16).toUpperCase(Locale.ROOT);
            // Different Corvette builds can share a generic resource seed: do not collapse their local rows.
            if ("Corvette".equals(category)) id += "-LOCAL-" + assets.size();
            if (assets.containsKey(id)) return;
            String name = text(recordContent.get("displayName"));
            if (name.isEmpty()) name = category + " " + (assets.size() + 1);
            if (!reason.isEmpty()) summary += " · " + reason;
            assets.put(id, new Row(id, category, name, summary, reason.isEmpty(), reason, "asset", recordContent));
        }

        void finishPets() {
            Map<String, List<Discovery>> matches = new LinkedHashMap<String, List<Discovery>>();
            for (Discovery discovery : discoveries.values()) if (discovery.petKey != null && discovery.eligible) {
                if (!matches.containsKey(discovery.petKey)) matches.put(discovery.petKey, new ArrayList<Discovery>());
                matches.get(discovery.petKey).add(discovery);
            }
            Map<String, List<eY>> petsByKey = new LinkedHashMap<String, List<eY>>();
            for (Node node : pets) {
                eY pet = (eY)node.value;
                String ua = unsignedHex(pet.get("UA"), true), creature = seedHex(pet.get("CreatureSeed"));
                String species = unsignedHex(pet.get("SpeciesSeed"), false), genus = unsignedHex(pet.get("GenusSeed"), false);
                String key = join(ua, creature, species, genus);
                if (!ua.isEmpty() && !creature.isEmpty() && !species.isEmpty() && !genus.isEmpty()) {
                    if (!petsByKey.containsKey(key)) petsByKey.put(key, new ArrayList<eY>());
                    petsByKey.get(key).add(pet);
                }
                String creatureId = token(pet.get("CreatureID"), 120);
                eY recordContent = baseAsset("CompanionPet", node, clean(pet.get("CustomName"), 200), "");
                recordContent.put("creatureID", creatureId); recordContent.put("creatureType", clean(nested(pet, "CreatureType", "CreatureType"), 120));
                recordContent.put("ua", ua); recordContent.put("creatureSeed", creature); recordContent.put("speciesSeed", species); recordContent.put("genusSeed", genus);
                recordContent.put("secondarySeed", seedHex(pet.get("CreatureSecondarySeed")));
                recordContent.put("descriptors", descriptors(pet.get("Descriptors")));
                recordContent.put("eggModified", Boolean.TRUE.equals(pet.get("EggModified")));
                boolean override = Boolean.TRUE.equals(pet.get("PetBattlerUseCoreStatClassOverrides"));
                recordContent.put("battleClassOverride", override);
                recordContent.put("battleClassSource", override ? "explicit_save_override" : "game_derived_not_stored");
                if (override) recordContent.put("battleClasses", battleClasses(pet.get("PetBattlerCoreStatClassOverrides")));
                List<Discovery> candidates = matches.get(key);
                String state = candidates == null ? "none" : candidates.size() == 1 ? "unique" : "ambiguous";
                recordContent.put("exactDiscoveryMatch", state);
                recordContent.put("exactDiscoveryMatchCount", candidates == null ? 0 : candidates.size());
                recordContent.put("nameRelationship", "pet_and_discovery_names_are_independent");
                recordContent.put("appearanceSeedLocationStatus", "not_a_location_claim");
                asset("CompanionPet", "pet", join(creatureId, ua, creature, species, genus), recordContent,
                        "Companion assets are local review only. A unique fauna discovery match is enriched and can be submitted separately.",
                        "Owned companion · " + state + " exact discovery match");
            }
            for (Map.Entry<String, List<eY>> entry : petsByKey.entrySet()) {
                List<Discovery> candidates = matches.get(entry.getKey());
                if (candidates == null) continue;
                if (candidates.size() != 1) { warn("Some companions have ambiguous discovery matches; those fauna records were not enriched."); continue; }
                eY first = entry.getValue().get(0);
                String signature = petClassification(first);
                boolean identical = true;
                for (eY pet : entry.getValue()) if (!signature.equals(petClassification(pet))) identical = false;
                if (!identical) { warn("Conflicting companion classifications share an exact discovery identity; those fauna records were not enriched."); continue; }
                eY recordContent = candidates.get(0).recordContent;
                String id = token(first.get("CreatureID"), 120), type = clean(nested(first, "CreatureType", "CreatureType"), 120);
                if (!id.isEmpty()) recordContent.put("CreatureID", id);
                if (!type.isEmpty()) recordContent.put("CreatureType", type);
                recordContent.put("Descriptors", descriptors(first.get("Descriptors")));
            }
        }

        void inventory(eY slot) {
            String id = token(slot.get("Id"), 120);
            String type = clean(nested(slot, "Type", "InventoryType"), 120);
            if (id.isEmpty() || "Technology".equalsIgnoreCase(type)) return;
            String key = type + "|" + id;
            Item item = items.get(key);
            if (item == null) { item = new Item(id, type); items.put(key, item); }
            item.count++;
        }
        void finishInventory() {
            List<Item> sorted = new ArrayList<Item>(items.values());
            Collections.sort(sorted, new Comparator<Item>() { public int compare(Item a, Item b) { return a.id.compareTo(b.id); } });
            for (Item item : sorted) {
                boolean egg = false;
                for (String keyword : new String[]{"EGG", "CHILD", "HATCH", "COMPANION", "JELLY", "HORROR", "SANDWORM"})
                    if (item.id.contains(keyword)) egg = true;
                eY recordContent = new eY(); recordContent.put("assetType", "InventoryItem"); recordContent.put("displayName", item.id);
                recordContent.put("itemID", item.id); recordContent.put("inventoryType", item.type); recordContent.put("occurrences", item.count); recordContent.put("eggLikeSignal", egg);
                asset("InventoryItem", "inventory-item", item.type + "|" + item.id, recordContent,
                        "Inventory catalog contributions are not supported by the current Codex import service.", "Owned inventory identifier · no quantities or inventory coordinates included");
                if (egg) {
                    eY eggRecordContent = recordContent.bE(); eggRecordContent.put("assetType", "CreatureEggSignal"); eggRecordContent.put("detection", "item identifier heuristic");
                    asset("CreatureEggSignal", "egg-signal", item.type + "|" + item.id, eggRecordContent,
                            "Egg-like item identifiers are a heuristic, not an identified creature. Local review only.", "Possible companion egg signal");
                }
            }
        }
    }

    private static eY baseAsset(String type, Node node, String name, String assetClass) {
        eY recordContent = new eY(); recordContent.put("assetType", type);
        if (!name.isEmpty()) recordContent.put("displayName", name);
        if (assetClass.matches("[CBAS]")) recordContent.put("class", assetClass);
        recordContent.put("sourceRole", sourceRole(type, node.collection));
        String collection = node.collection.matches("[A-Za-z0-9_]{1,120}") ? node.collection : "";
        if (!collection.isEmpty()) recordContent.put("sourceCollection", collection);
        if (node.ordinal >= 0 && node.ordinal <= 10000) recordContent.put("sourceOrdinal", node.ordinal);
        return recordContent;
    }
    private static String sourceRole(String type, String collection) {
        String value = collection.toLowerCase(Locale.ROOT);
        if (value.contains("archived")) return "archived";
        if (value.contains("squadron")) return "squadron_member";
        if (value.contains("histor")) return "historical";
        if (value.contains("template")) return "template";
        if ("Frigate".equals(type) && value.contains("fleet")) return "fleet_member";
        if ("Starship".equals(type) && value.contains("shipownership")) return "owned_slot";
        if ("Multitool".equals(type) && value.contains("multitool")) return "owned_slot";
        if ("CompanionPet".equals(type) && (value.contains("pet") || value.contains("companion"))) return "owned_slot";
        return "unknown";
    }
    private static String unsignedHex(Object value, boolean address) {
        try {
            BigInteger exact;
            if (value instanceof BigInteger) exact = (BigInteger)value;
            else if (value instanceof BigDecimal) exact = ((BigDecimal)value).toBigIntegerExact();
            else if (value instanceof Byte || value instanceof Short || value instanceof Integer || value instanceof Long)
                exact = BigInteger.valueOf(((Number)value).longValue());
            else if (value instanceof String) {
                String text = ((String)value).trim();
                if (text.matches("(?i)0x[0-9a-f]{1,16}")) exact = new BigInteger(text.substring(2), 16);
                else if (text.matches("[0-9]{1,20}")) exact = new BigInteger(text, 10);
                else return "";
            } else return ""; // Binary floating point is never accepted for identity data.
            if (exact.signum() < 0 || exact.compareTo(address ? MAX_UA : MAX64) > 0) return "";
            String digits = exact.toString(16).toUpperCase(Locale.ROOT);
            StringBuilder result = new StringBuilder("0x");
            for (int i = digits.length(); i < 16; i++) result.append('0');
            return result.append(digits).toString();
        } catch (RuntimeException invalid) { return ""; }
    }
    private static String seedHex(Object value) {
        if (value instanceof eV) {
            eV pair = (eV)value;
            if (pair.size() < 2 || !Boolean.TRUE.equals(pair.get(0))) return "";
            return unsignedHex(pair.get(1), false);
        }
        return unsignedHex(value, false);
    }
    private static boolean isZero(String seed) { return seed.isEmpty() || "0x0000000000000000".equals(seed); }
    private static eY object(Object value) { return value instanceof eY ? (eY)value : null; }
    private static Object nested(eY value, String parent, String property) {
        eY nested = object(value.get(parent));
        return nested == null ? value.get(parent) instanceof String ? value.get(parent) : null : nested.get(property);
    }
    private static String inventoryClass(eY value, String field) {
        eY inventory = object(value.get(field));
        return inventory == null ? "" : clean(nested(inventory, "Class", "InventoryClass"), 4);
    }
    private static String text(Object value) { return value instanceof String ? (String)value : ""; }
    private static String clean(Object value, int limit) {
        String text = text(value).trim();
        while (text.startsWith("^")) text = text.substring(1);
        if (text.length() > limit) return "";
        for (int i = 0; i < text.length(); i++) if (Character.isISOControl(text.charAt(i))) return "";
        return text;
    }
    private static String token(Object value, int limit) {
        String token = clean(value, limit).toUpperCase(Locale.ROOT);
        return token.matches("[A-Z0-9_]+") ? token : "";
    }
    private static String gameResource(Object value) {
        String path = clean(value, 240).replace('\\', '/').toUpperCase(Locale.ROOT);
        return validResource(path) ? path : "";
    }
    private static boolean validResource(String value) {
        return value.length() <= 240 && value.matches("MODELS/(?:[A-Z0-9_]+/)*[A-Z0-9_]+\\.SCENE\\.MBIN");
    }
    private static String safeScalar(Object value) {
        return value instanceof String || value instanceof Number || value instanceof Boolean ? String.valueOf(value) : "(non-scalar)";
    }
    private static boolean looksLikePet(eY value) {
        return !token(value.get("CreatureID"), 120).isEmpty() && value.get("CreatureSeed") != null
                && value.get("SpeciesSeed") != null && value.get("GenusSeed") != null && value.get("UA") != null;
    }
    private static eV descriptors(Object value) {
        Set<String> tokens = new LinkedHashSet<String>();
        if (value instanceof eV) {
            eV values = (eV)value;
            for (int i = 0; i < values.size() && tokens.size() < 100; i++) {
                String token = clean(values.get(i), 160).toUpperCase(Locale.ROOT);
                if (token.matches("[A-Z0-9_-]{1,159}")) tokens.add(token);
            }
        }
        List<String> sorted = new ArrayList<String>(tokens); Collections.sort(sorted);
        eV result = new eV(); for (String token : sorted) result.add(token); return result;
    }
    private static eV battleClasses(Object value) {
        eV result = new eV();
        if (value instanceof eV) {
            eV values = (eV)value;
            for (int i = 0; i < Math.min(16, values.size()); i++) {
                Object entry = values.get(i);
                String token = entry instanceof eY ? clean(((eY)entry).get("InventoryClass"), 4) : clean(entry, 4);
                if (token.matches("[CBAS]")) result.add(token);
            }
        }
        return result;
    }
    private static String petClassification(eY pet) {
        return join(token(pet.get("CreatureID"), 120), clean(nested(pet, "CreatureType", "CreatureType"), 120), descriptors(pet.get("Descriptors")).toString());
    }
    private static boolean supportedDiscovery(String type) {
        return "Animal".equals(type) || "Flora".equals(type) || "Mineral".equals(type) || "Planet".equals(type) || "SolarSystem".equals(type);
    }
    private static String discoveryType(String input) {
        for (String type : new String[]{"Animal", "Flora", "Mineral", "Planet", "SolarSystem"}) if (type.equalsIgnoreCase(input)) return type;
        String result = clean(input, 120); return result.isEmpty() ? "Other" : result;
    }
    private static String category(String type) { return "Animal".equals(type) ? "Fauna" : "SolarSystem".equals(type) ? "System" : supportedDiscovery(type) ? type : "Other"; }
    private static String locationSummary(String ua) {
        String digits = ua.substring(4); // 16 hex -> the actual 14-digit universal-address layout.
        String portal = digits.substring(0, 4) + digits.substring(6);
        int galaxy = Integer.parseInt(digits.substring(4, 6), 16) + 1;
        return "Galaxy " + galaxy + " · " + portal;
    }
    private static String join(String... values) { return String.join("|", values); }
    private static String hash(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder();
            for (byte b : digest) result.append(String.format(Locale.ROOT, "%02x", b & 255));
            return result.toString();
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
}
