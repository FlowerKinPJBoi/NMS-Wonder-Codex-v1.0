package nomanssave;

import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.charset.StandardCharsets;

/** Runs only on an in-memory copy of the supplied save fixture. */
public final class WCEditorBasesTest {
    private static int checks;
    private static void check(boolean value, String label) {
        checks++; if (!value) throw new AssertionError(label);
    }
    private static void rejects(Runnable operation, String label) {
        boolean rejected = false;
        try { operation.run(); } catch (RuntimeException expected) { rejected = true; }
        check(rejected, label);
    }
    private static boolean anchor(eY item) { return "^BASE_FLAG".equals(item.get("ObjectID")) || "^U_PARAGON".equals(item.get("ObjectID")); }
    public static void main(String[] args) throws Exception {
        eY root = ff.b(Files.readAllBytes(Paths.get(args[0])));
        eV bases = WCEditorBasesPanel.Model.bases(root);
        check(bases.size() > 0, "real fixture contains bases");
        for (int i = 0; i < bases.size(); i++) {
            eY base = (eY)bases.get(i);
            WCEditorBasesPanel.Model.validate(base);
            WCEditorBasesPanel.Model.Plan unchanged = WCEditorBasesPanel.Model.prepare(base, WCEditorBasesPanel.Model.parse(base.bz()));
            check(unchanged.changed.isEmpty(), "real base exact native-number round trip " + i);
        }
        eY selected = (eY)bases.get(0);
        String selectedBefore = selected.toString();
        eY originalRoot = root.bE();
        eY before = selected.bE();
        eY incoming = selected.bE();
        incoming.put("Name", "WC offline base test");
        incoming.put("Owner", ff.b("{\"UID\":\"different owner\"}".getBytes(StandardCharsets.UTF_8)));
        incoming.put("GalacticAddress", "0x00000000000000");
        incoming.put("Position", new eV(999, 999, 999));
        incoming.put("UnknownMetadata", "must not transfer");
        eV items = (eV)incoming.get("Objects");
        for (int i = 0; i < items.size(); i++) if (anchor((eY)items.get(i))) {
            ((eY)items.get(i)).put("Position", new eV(100, 200, 300));
            ((eY)items.get(i)).put("UserData", 1);
        }
        eY part = ff.b(("{\"ObjectID\":\"^T_FLOOR\",\"UserData\":18446744073709551615," +
            "\"Timestamp\":1791046108,\"Position\":[1.234567890123456789,0,0],\"Up\":[0,1,0],\"At\":[0,0,1],\"FutureProperty\":9007199254740993}").getBytes(StandardCharsets.UTF_8));
        items.add(part);
        WCEditorBasesPanel.Model.Plan plan = WCEditorBasesPanel.Model.prepare(selected, incoming);
        check(plan.changed.size() == 2, "name and objects only are changed");
        check(plan.retained.contains("Owner") && plan.retained.contains("Position"), "preview lists retained metadata");
        check(selected.toString().equals(selectedBefore), "prepare is immutable");
        plan.apply(selected);
        check(bases.get(0) == selected, "native base reference retained");
        check("WC offline base test".equals(selected.get("Name")), "name staged");
        check(!selected.contains("UnknownMetadata"), "unrecognized incoming metadata not copied");
        for (Object key : before.names()) if (!WCEditorBasesPanel.Model.CONTENT.contains((String)key))
            check(String.valueOf(before.get((String)key)).equals(String.valueOf(selected.get((String)key))), "preserved header " + key);
        eV originalItems = (eV)before.get("Objects");
        eV resultItems = (eV)selected.get("Objects");
        for (int i = 0; i < originalItems.size(); i++) if (anchor((eY)originalItems.get(i)))
            check(originalItems.get(i).toString().equals(resultItems.get(i).toString()), "protected anchor exact " + i);
        eY resultPart = (eY)resultItems.get(resultItems.size() - 1);
        check("18446744073709551615".equals(resultPart.get("UserData").toString()), "uint64 exact");
        check("9007199254740993".equals(resultPart.get("FutureProperty").toString()), "unknown object value preserved exactly");
        check("1.234567890123456789".equals(((eV)resultPart.get("Position")).get(0).toString()), "decimal precision exact");
        eY exportRoundTrip = WCEditorBasesPanel.Model.parse(selected.bz());
        check(exportRoundTrip.toString().equals(selected.toString()), "export reparse exact");
        eV originalBases = WCEditorBasesPanel.Model.bases(originalRoot);
        for (int i = 1; i < bases.size(); i++) check(bases.get(i).toString().equals(originalBases.get(i).toString()), "other base unchanged " + i);
        ((eV)WCEditorBasesPanel.Model.bases(originalRoot)).set(0, selected.bE());
        check(originalRoot.toString().equals(root.toString()), "no unrelated save edits");
        WCEditorBasesPanel.Model.checkCurrent(root, root, bases, 0, selected, selected.toString());
        rejects(() -> WCEditorBasesPanel.Model.checkCurrent(root.bE(), root, bases, 0, selected, selected.toString()), "different root rejected");
        rejects(() -> WCEditorBasesPanel.Model.checkCurrent(root, root, bases, 0, selected, selectedBefore), "stale content rejected");
        rejects(() -> WCEditorBasesPanel.Model.checkCurrent(root, root, bases, 1, selected, selected.toString()), "changed base selection rejected");
        rejects(() -> plan.apply(selected), "stale plan cannot be applied twice");
        for (String invalid : new String[]{"null", "[]", "{}", "{\"Objects\":null}", "{\"Objects\":[null]}",
            "{\"Objects\":[],\"Name\":false}", "{\"Objects\":[]}junk", "{\"Objects\":[],\"Objects\":[]}",
            "{\"Objects\":[{\"ObjectID\":\"^PART\",\"Position\":[0,0],\"Up\":[0,1,0],\"At\":[0,0,1],\"UserData\":1}]}"}) {
            final String input = invalid;
            rejects(() -> WCEditorBasesPanel.Model.parse(input), "invalid input rejected " + invalid);
        }
        eY onlyObjects = ff.b("{\"Objects\":[]}".getBytes(StandardCharsets.UTF_8));
        WCEditorBasesPanel.Model.Plan emptied = WCEditorBasesPanel.Model.prepare(selected, onlyObjects);
        check("WC offline base test".equals(emptied.after.get("Name")), "omitted Name retained");
        int anchors = 0;
        for (int i = 0; i < resultItems.size(); i++) if (anchor((eY)resultItems.get(i))) anchors++;
        check(WCEditorBasesPanel.Model.objectCount(emptied.after) == anchors, "missing source anchors restored");
        System.out.println("WCEditorBasesTest passed " + checks + " checks; in-memory fixture only.");
    }
}
