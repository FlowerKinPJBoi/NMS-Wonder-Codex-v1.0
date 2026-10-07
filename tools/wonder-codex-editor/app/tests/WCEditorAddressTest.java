package nomanssave;

import java.util.Random;

public final class WCEditorAddressTest {
    private static int assertions;
    private static void yes(boolean pass, String message) { assertions++; if (!pass) throw new AssertionError(message); }
    private static void equal(Object expected, Object actual, String message) { yes(expected.equals(actual), message + " expected=" + expected + " actual=" + actual); }
    private static void rejects(Runnable action, String message) {
        boolean rejected = false;
        try { action.run(); } catch (IllegalArgumentException ex) { rejected = true; }
        yes(rejected, message);
    }
    private static eY object(Object... pairs) {
        eY json = new eY();
        for (int i = 0; i < pairs.length; i += 2) json.put((String)pairs[i], pairs[i + 1]);
        return json;
    }
    private static eY context(String portal, int galaxy) {
        return object("PlayerStateData", object("SaveName", "Test", "UniverseAddress", WCEditorAddress.portal(portal, galaxy).ew(), "PreviousUniverseAddress", WCEditorAddress.portal("100000000001", 1).ew(), "PreservedInteger", Long.valueOf(9007199254740993L)), "SpawnStateData", object("LastKnownPlayerState", "OnFoot", "Unchanged", "marker"));
    }
    public static void main(String[] args) {
        hl example = WCEditorAddress.portal("1030 09ab bcde", 9);
        equal("103009ABBCDE", example.ey(), "portal normalization");
        equal("04DD:0088:02BA:1030", WCEditorAddress.galacticText(example), "known coordinate vector");
        equal(Integer.valueOf(-802), Integer.valueOf(example.ev()), "signed X");
        equal(Integer.valueOf(-1349), Integer.valueOf(example.eu()), "signed Z");
        equal(example, WCEditorAddress.galactic("04DD:0088:02BA:1030", 9), "galactic vector");
        equal(example, WCEditorAddress.universal(WCEditorAddress.universalHex(example)), "hex UA");
        equal(example, WCEditorAddress.universal(WCEditorAddress.universalDecimal(example)), "decimal UA");
        equal("07FF:007F:07FF:0000", WCEditorAddress.galacticText(WCEditorAddress.portal("000000000000", 0)), "origin galactic");
        equal("0x0", WCEditorAddress.universalHex(WCEditorAddress.universal("0")), "origin universal");
        equal("FFFFFFFFFFFF", WCEditorAddress.universal("72057594037927935").ey(), "largest supported UA");
        equal(Integer.valueOf(255), Integer.valueOf(WCEditorAddress.universal("0xFFFFFFFFFFFFFF").es()), "largest galaxy");
        equal("1 · Euclid", WCEditorAddress.galaxies()[0], "native galaxy start");
        equal("10 · Eissentam", WCEditorAddress.galaxies()[9], "native galaxy Eissentam");
        equal(Integer.valueOf(256), Integer.valueOf(WCEditorAddress.galaxies().length), "supported galaxy count");
        for (String s : new String[]{"", "123", "123456789ABG", "123456789ABCD", "-123456789AB"}) rejects(() -> WCEditorAddress.portal(s, 0), "invalid portal " + s);
        rejects(() -> WCEditorAddress.portal("000000000000", -1), "negative galaxy");
        rejects(() -> WCEditorAddress.portal("000000000000", 256), "too large galaxy");
        for (String s : new String[]{"FFFF:007F:07FF:0000", "07FF:FFFF:07FF:0000", "07FF:007F:FFFF:0000", "07FF007F07FF0000"}) rejects(() -> WCEditorAddress.galactic(s, 0), "invalid galactic " + s);
        for (String s : new String[]{"18446744073709551616", "-1", "1.5", "1e8", "0xFFFFFFFFFFFFFFFF", "0x100000000000000", "0x10000000000000000", "+1", "0xZZ"}) rejects(() -> WCEditorAddress.universal(s), "invalid exact UA " + s);
        Random random = new Random(4872391L);
        for (int i = 0; i < 500; i++) {
            long value = random.nextLong() & 0x00FFFFFFFFFFFFFFL;
            hl location = WCEditorAddress.universal(Long.toString(value));
            equal(location, WCEditorAddress.portal(location.ey(), location.es()), "portal roundtrip");
            equal(location, WCEditorAddress.universal(WCEditorAddress.universalHex(location)), "hex roundtrip");
            equal(Long.toString(value), WCEditorAddress.universalDecimal(location), "decimal precision roundtrip");
            String coords = WCEditorAddress.galacticText(location);
            if (!coords.isEmpty()) equal(location, WCEditorAddress.galactic(coords, location.es()), "galactic roundtrip");
        }
        for (String edge : new String[]{"000000000800", "000080000000", "000000800000"}) {
            hl location = WCEditorAddress.portal(edge, 255);
            equal("", WCEditorAddress.galacticText(location), "minimum voxel does not print malformed native galactic coordinates");
            equal(location, WCEditorAddress.universal(WCEditorAddress.universalHex(location)), "minimum voxel UA preservation");
        }
        eY base = context("103009ABBCDE", 9), season = context("20123456789A", 1);
        eY root = object("ActiveContext", "Main", "Version", Integer.valueOf(4739), "BaseContext", base, "ExpeditionContext", season, "Unrelated", "untouched");
        eY player = (eY)base.get("PlayerStateData");
        String previous = ((eY)player.get("UniverseAddress")).toString();
        String seasonBefore = season.toString();
        eY report = WCCosmosModel.stageWarp(root, WCEditorAddress.portal("F0123456789A", 255).ew());
        hl changed = hl.n(player.get("UniverseAddress"));
        equal("00123456789A", changed.ey(), "system warp resets planet digit");
        equal(Integer.valueOf(255), Integer.valueOf(changed.es()), "system warp destination galaxy");
        equal(previous, ((eY)player.get("PreviousUniverseAddress")).toString(), "previous address recorded");
        equal("InShip", ((eY)base.get("SpawnStateData")).get("LastKnownPlayerState"), "space arrival");
        equal(seasonBefore, season.toString(), "inactive expedition untouched");
        equal(Long.valueOf(9007199254740993L), player.get("PreservedInteger"), "large unrelated integer preserved");
        equal("marker", ((eY)base.get("SpawnStateData")).get("Unchanged"), "spawn extra field preserved");
        equal("untouched", root.get("Unrelated"), "root extra field preserved");
        equal("BaseContext", report.get("context"), "report context");
        String staged = root.toString();
        eY bad = WCEditorAddress.portal("000000000000", 0).ew(); bad.put("RealityIndex", Integer.valueOf(256));
        rejects(() -> WCCosmosModel.stageWarp(root, bad), "bad warp blocked");
        equal(staged, root.toString(), "bad warp makes no mutation");
        root.put("ActiveContext", "Season");
        String baseBefore = base.toString();
        WCCosmosModel.stageWarp(root, WCEditorAddress.portal("0123456789AB", 1).ew());
        equal(baseBefore, base.toString(), "main untouched by season warp");
        equal("0123456789AB", hl.n(((eY)season.get("PlayerStateData")).get("UniverseAddress")).ey(), "season updated");
        root.put("ActiveContext", "Unknown");
        String unsupportedBefore = root.toString();
        rejects(() -> WCCosmosModel.stageWarp(root, WCEditorAddress.portal("000000000000", 0).ew()), "unknown context blocked");
        equal(unsupportedBefore, root.toString(), "unknown context no mutation");
        System.out.println("WCEditorAddressTest PASS " + assertions + " assertions");
    }
}
