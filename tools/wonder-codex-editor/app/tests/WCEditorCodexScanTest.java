package nomanssave;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/** Synthetic, read-only fixtures: no real save data, network access or account identifiers. */
public final class WCEditorCodexScanTest {
    private static int checks;
    private static void check(boolean value, String label) { checks++; if (!value) throw new AssertionError(label); }
    private static eY json(String text) throws Exception { return ff.b(text.getBytes(StandardCharsets.UTF_8)); }
    private static eY discovery(String type, String ua, String vp, String name) throws Exception {
        return json("{\"DD\":{\"DT\":\"" + type + "\",\"UA\":" + ua + ",\"VP\":" + vp
                + "},\"DM\":{\"CN\":\"" + name + "\"},\"OWS\":{\"USN\":\"private owner\",\"UID\":\"private account\"},\"Path\":\"C:/private/save.json\"}");
    }
    private static eY withRecords(eY... values) { eY root = new eY(), manager = new eY(); eV records = new eV(); for(eY value:values)records.add(value); manager.put("Records",records);root.put("DiscoveryManagerData",manager);return root; }
    private static List<WCEditorCodexScan.Row> category(WCEditorCodexScan.Result result, String category) {
        List<WCEditorCodexScan.Row> rows = new ArrayList<WCEditorCodexScan.Row>();
        for (WCEditorCodexScan.Row row:result.rows) if(category.equals(row.category))rows.add(row); return rows;
    }
    private static WCEditorCodexScan.Row one(WCEditorCodexScan.Result result, String category) { List<WCEditorCodexScan.Row> rows=category(result,category);check(rows.size()==1,"one "+category+" row, got "+rows.size());return rows.get(0); }
    private static void noPrivateRecordContent(WCEditorCodexScan.Result result) {
        for(WCEditorCodexScan.Row row:result.rows) {
            String serialized=row.recordContent.bz();
            for(String forbidden:new String[]{"private owner","private account","C:/private","OWS","PlayerStateData","CurrentUniverseAddress","FreighterUniverseAddress","PersistentPlayerBases","InventoriedPersonalSecret"})
                check(!serialized.contains(forbidden),"no private field "+forbidden+" in "+row.category);
        }
    }
    public static void main(String[] args)throws Exception {
        String ua="\"0x00112302ABCDEF01\"";
        eY fauna=discovery("Animal",ua,"[18446744073709551615,9223372036854775808,3,4,5]","Wonder is only a name");
        eY root=withRecords(fauna,discovery("Flora",ua,"[1,2]","Plant"),discovery("Mineral",ua,"[5,6]","Stone"),
                discovery("Planet",ua,"[]","Planet"),discovery("SolarSystem",ua,"[]","System"));
        String before=root.bz(); WCEditorCodexScan.Result result=WCEditorCodexScan.scan(root);
        check(before.equals(root.bz()),"scan never mutates source");check(result.rows.size()==5,"all supported discovery types");check(result.eligibleCount==5,"all valid discoveries eligible");
        WCEditorCodexScan.Row animal=one(result,"Fauna");
        check(!animal.wonderAffiliated,"a Wonder name does not assert affiliation");
        check("0xFFFFFFFFFFFFFFFF".equals(animal.recordContent.d("VP").get(0)),"unsigned 64-bit maximum exact");
        check("0x8000000000000000".equals(animal.recordContent.d("VP").get(1)),"high bit exact");
        check(animal.summary.contains("Galaxy 3")&&animal.summary.contains("1123ABCDEF01"),"UA RR removal and galaxy are exact");
        check("Wonder is only a name".equals(animal.recordContent.get("CustomName")),"user discovery name preserved separately");
        noPrivateRecordContent(result);

        eY duplicate=withRecords(fauna,fauna.bE()); result=WCEditorCodexScan.scan(duplicate);
        check(result.discoveryCount==1,"exact duplicate discovery collapsed");check(!result.warnings.isEmpty(),"duplicate dedup explained");
        eY decimal=fauna.bE();decimal.H("DD").put("UA",new java.math.BigDecimal("4823563287326465"));
        eY hexa=fauna.bE();hexa.H("DD").put("UA","0x00112302ABCDEF01");
        // Equivalent decimal and hex compare by value, not display representation.
        decimal.H("DD").put("UA",new java.math.BigDecimal(new java.math.BigInteger("112302ABCDEF01",16)));
        result=WCEditorCodexScan.scan(withRecords(decimal,hexa));check(result.discoveryCount==1,"decimal and hexadecimal deduplicate exactly");

        result=WCEditorCodexScan.scan(withRecords(
                discovery("Animal",ua,"[18446744073709551616,2,3,4]","overflow"),
                discovery("Animal",ua,"[1.1,2,3,4]","fraction"),
                discovery("Animal",ua,"[-1,2,3,4]","negative"),
                discovery("Animal",ua,"[\"bad\",2,3,4]","bad string"),
                discovery("Animal","18446744073709551615","[1,2,3,4]","wide address"),
                discovery("Flora",ua,"[1]","too few"),
                discovery("Building",ua,"[1,2]","Wonder unsupported")));
        check(result.rows.size()==7&&result.eligibleCount==0,"malformed identities not uploaded");
        for(WCEditorCodexScan.Row row:result.rows)check(!row.reason.isEmpty(),"ineligible reason available");
        check(result.rows.get(0).recordContent.d("VP").get(0)==null,"bad procedural value not replaced with zero");
        eV tooMany=new eV();for(int i=0;i<33;i++)tooMany.add(i);eY excessive=fauna.bE();excessive.H("DD").put("VP",tooMany);
        check(WCEditorCodexScan.scan(withRecords(excessive)).eligibleCount==0,"VP >32 rejected");
        eY wide=fauna.bE();wide.H("DD").put("VP",new eV());for(int i=0;i<32;i++)wide.H("DD").d("VP").add(i);
        check(WCEditorCodexScan.scan(withRecords(wide)).eligibleCount==1,"full 32-position VP retained");

        eY pet=json("{\"CreatureID\":\"^CAT\",\"CreatureType\":{\"CreatureType\":\"Cat\"},\"UA\":\"0x00112302ABCDEF01\",\"CreatureSeed\":[true,18446744073709551615],\"SpeciesSeed\":3,\"GenusSeed\":4,\"CreatureSecondarySeed\":[true,5],\"Descriptors\":[\"^HEAD_A\",\"^BODY_B\",\"^HEAD_A\"],\"CustomName\":\"My pet name\",\"PetBattlerUseCoreStatClassOverrides\":false,\"PetBattlerCoreStatClassOverrides\":[{\"InventoryClass\":\"S\"}],\"Owner\":\"private owner\"}");
        eY player=new eY(); eV pets=new eV();pets.add(pet);player.put("Pets",pets);root.put("PlayerStateData",player);
        result=WCEditorCodexScan.scan(root);animal=one(result,"Fauna");
        check("CAT".equals(animal.recordContent.get("CreatureID")),"exact pet/discovery join enriches fauna");
        check(animal.recordContent.d("Descriptors").size()==2,"descriptors normalized and deduplicated");
        check("Wonder is only a name".equals(animal.recordContent.get("CustomName")),"pet name never replaces discovery name");
        WCEditorCodexScan.Row companion=one(result,"CompanionPet");
        check(!companion.eligible,"owned companion not falsely submitted as public location");
        check("unique".equals(companion.recordContent.get("exactDiscoveryMatch")),"pet exact match recorded locally");
        check(companion.recordContent.get("battleClasses")==null,"dormant battle-class overrides are not exported");noPrivateRecordContent(result);
        pet.put("PetBattlerUseCoreStatClassOverrides",true);result=WCEditorCodexScan.scan(root);
        check(one(result,"CompanionPet").recordContent.d("battleClasses").size()==1,"active battle override exported locally");
        eY alternate=fauna.bE();alternate.H("DD").d("VP").set(1,7);eY ambiguous=withRecords(fauna,alternate);ambiguous.put("PlayerStateData",player);
        result=WCEditorCodexScan.scan(ambiguous);for(WCEditorCodexScan.Row row:category(result,"Fauna"))check(row.recordContent.get("CreatureID")==null,"ambiguous pet join not guessed");
        check("ambiguous".equals(one(result,"CompanionPet").recordContent.get("exactDiscoveryMatch")),"ambiguous match displayed");
        eY conflicting=pet.bE();conflicting.put("CreatureID","^DOG");pets.add(conflicting);result=WCEditorCodexScan.scan(root);
        check(one(result,"Fauna").recordContent.get("CreatureID")==null,"conflicting pet classification withheld");pets.remove(1);

        eY assets=json("{\"PlayerStateData\":{\"ShipOwnership\":[{\"Name\":\"Wonder Ship\",\"Resource\":{\"Filename\":\"MODELS/COMMON/SPACECRAFT/FIGHTERS/FIGHTER.SCENE.MBIN\",\"Seed\":[true,18446744073709551615]},\"Inventory\":{\"Class\":{\"InventoryClass\":\"S\"},\"Slots\":[{\"Id\":\"^ALIEN_EGG\",\"Amount\":9,\"Type\":{\"InventoryType\":\"Product\"},\"Index\":{\"X\":1,\"Y\":2}},{\"Id\":\"^FUEL1\",\"Amount\":500,\"Type\":{\"InventoryType\":\"Substance\"}},{\"Id\":\"^TECH1\",\"Amount\":1,\"Type\":{\"InventoryType\":\"Technology\"}}]},\"HomeSystemSeed\":[true,123],\"InventoriedPersonalSecret\":\"private owner\"},{\"Name\":\"Corvette\",\"Resource\":{\"Filename\":\"MODELS/COMMON/SPACECRAFT/BIGGS/BIGGS.SCENE.MBIN\",\"Seed\":[true,1]},\"Inventory\":{\"Class\":{\"InventoryClass\":\"A\"}}}],\"Multitools\":[{\"Name\":\"Tool\",\"Seed\":[true,88],\"Resource\":{\"Filename\":\"MODELS/COMMON/WEAPONS/MULTITOOL/MULTITOOL.SCENE.MBIN\",\"Seed\":[true,55]},\"Store\":{\"Class\":{\"InventoryClass\":\"A\"}}}],\"CurrentFreighter\":{\"Filename\":\"MODELS/COMMON/SPACECRAFT/INDUSTRIAL/FREIGHTER.SCENE.MBIN\",\"Seed\":[true,44]},\"PlayerFreighterName\":\"Freighter\",\"FreighterInventory\":{\"Class\":{\"InventoryClass\":\"B\"}},\"FreighterUniverseAddress\":{\"RealityIndex\":0,\"GalacticAddress\":{\"VoxelX\":123}},\"FleetFrigates\":[{\"CustomName\":\"Frigate\",\"ResourceSeed\":[true,42],\"FrigateClass\":{\"FrigateClass\":\"Combat\"},\"InventoryClass\":{\"InventoryClass\":\"S\"},\"Stats\":[1,2,3],\"HomeSystemSeed\":[true,43]}]}}");
        before=assets.bz();result=WCEditorCodexScan.scan(assets);check(before.equals(assets.bz()),"asset scan never mutates source");
        check(result.eligibleCount==4,"four supported asset categories eligible without original location");
        WCEditorCodexScan.Row ship=one(result,"Starship");check(ship.eligible,"unlocated starship is an eligible owned specimen");
        check("0xFFFFFFFFFFFFFFFF".equals(ship.recordContent.get("seed")),"owned-asset seed exact maximum");check(!ship.wonderAffiliated,"Wonder asset name not affiliation");
        check("owned_slot".equals(ship.recordContent.get("sourceRole")),"owned source role");
        check(one(result,"Multitool").eligible,"multitool supported");check("0x0000000000000058".equals(one(result,"Multitool").recordContent.get("seed")),"multitool own seed overrides resource seed");check(one(result,"Freighter").eligible,"freighter supported");
        check("fleet_member".equals(one(result,"Frigate").recordContent.get("sourceRole")),"frigate source role");
        check(!one(result,"Corvette").eligible,"Corvette generic seed never used as complete assembly identity");
        WCEditorCodexScan.Row egg=one(result,"CreatureEggSignal");check(!egg.eligible&&"item identifier heuristic".equals(egg.recordContent.get("detection")),"egg signals remain explicit heuristic");
        check(category(result,"InventoryItem").size()==2,"technology omitted; other item identifiers reviewed");
        for(WCEditorCodexScan.Row item:category(result,"InventoryItem"))check(item.recordContent.get("amount")==null&&item.recordContent.get("Index")==null,"inventory quantities and slot coordinates omitted");
        noPrivateRecordContent(result);

        eY cosmos=new eY(), base=new eY(), expedition=new eY();base.put("PlayerStateData",assets.H("PlayerStateData"));expedition.put("PlayerStateData",player);
        cosmos.put("BaseContext",base);cosmos.put("ExpeditionContext",expedition);cosmos.put("ActiveContext","Season");
        cosmos.put("DiscoveryManagerData",root.H("DiscoveryManagerData"));
        before=cosmos.bz();result=WCEditorCodexScan.scan(cosmos);check(before.equals(cosmos.bz()),"Cosmos all-context scan read-only");
        check(one(result,"Starship").eligible&&one(result,"Fauna").eligible,"root discoveries plus both Cosmos contexts scanned");
        check("CAT".equals(one(result,"Fauna").recordContent.get("CreatureID")),"Expedition companion joins common discovery");
        eY duplicatedCosmos=cosmos.bE();duplicatedCosmos.put("PlayerStateData",base.H("PlayerStateData"));
        check(category(WCEditorCodexScan.scan(duplicatedCosmos),"Starship").size()==1,"virtual root mirror deduplicates procedural assets");

        eY invalidAsset=assets.bE();invalidAsset.H("PlayerStateData").d("ShipOwnership").get(0);
        ((eY)invalidAsset.H("PlayerStateData").d("ShipOwnership").get(0)).H("Resource").put("Filename","MODELS/COMMON/SPACECRAFT/../../private/secret.MBIN");
        result=WCEditorCodexScan.scan(invalidAsset);ship=one(result,"Starship");check(!ship.eligible&&"".equals(ship.recordContent.get("resourceFilename")),"game-path traversal omitted and blocked");
        eY empty=new eY();result=WCEditorCodexScan.scan(empty);check(result.rows.isEmpty()&&!result.warnings.isEmpty(),"empty save produces useful warning");
        if (args.length == 1) {
            eY contract = new eY(); contract.put("schema", "wonder-codex-editor-import/1"); contract.put("client_version", "test"); contract.put("platform", "Unknown");
            eV discoveryRecordContents = new eV(), assetRecordContents = new eV();
            for (WCEditorCodexScan.Row row : WCEditorCodexScan.scan(cosmos).rows) if (row.eligible) {
                if ("discovery".equals(row.recordType)) discoveryRecordContents.add(row.recordContent.bE()); else assetRecordContents.add(row.recordContent.bE());
            }
            contract.put("discoveries", discoveryRecordContents); contract.put("assets", assetRecordContents);
            java.nio.file.Files.write(java.nio.file.Paths.get(args[0]), contract.bz().getBytes(StandardCharsets.UTF_8));
        }
        System.out.println("CODEX_SCAN_TEST PASS checks="+checks+"; exact integers, supported categories, contexts, joins, sanitization and no mutation");
    }
}
