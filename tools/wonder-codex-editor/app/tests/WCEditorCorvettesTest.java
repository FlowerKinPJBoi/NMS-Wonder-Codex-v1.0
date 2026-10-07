package nomanssave;

import java.nio.file.Paths;
import java.lang.reflect.Field;

/** Runs on the provided Cosmos donor; reads only, never writes a save. */
public final class WCEditorCorvettesTest {
    private static int checks;
    private static void check(boolean ok,String message){checks++;if(!ok)throw new AssertionError(message);}
    private static void blocked(Runnable r,String message){boolean failed=false;try{r.run();}catch(IllegalArgumentException|IllegalStateException expected){failed=true;}check(failed,message);}
    public static void main(String[] args)throws Exception {
        eY fixture=WCCosmosModel.readJson(Paths.get(args[0]),false);
        check(WCEditorCorvettes.list(fixture).size()==1,"one donor Corvette");
        WCEditorCorvettes.Entry entry=WCEditorCorvettes.list(fixture).get(0);
        check(entry.index==1,"index matches real donor");
        check(entry.buildSummary().contains("77 parts"),"donor build linkage");
        String original=fixture.toString();
        eY root=fixture.bE();entry=WCEditorCorvettes.list(root).get(0);
        eY ship=entry.ship; eY inv=ship.H("Inventory");eY tech=ship.H("Inventory_TechOnly");
        eV bases=entry.player.d("PersistentPlayerBases");String baseSnapshot=bases.toString();
        String originalName=entry.name(),originalClass=entry.inventoryClass();
        WCEditorCorvettes.Plan plan=WCEditorCorvettes.plan(entry,"Codex Corvette","S");
        check(plan.changes.size()==4,"name and three class changes");plan.apply(root);
        check(ship==entry.player.d("ShipOwnership").get(1),"ship reference retained");
        check(inv==ship.H("Inventory")&&tech==ship.H("Inventory_TechOnly"),"native inventory references retained");
        check(bases==entry.player.d("PersistentPlayerBases"),"base references retained");
        check(baseSnapshot.equals(bases.toString()),"all bases, owners, root identity and transforms preserved");
        check("Codex Corvette".equals(entry.name()),"name changed");
        for(String k:new String[]{"Inventory","Inventory_TechOnly","Inventory_Cargo"})check("S".equals(ship.getValueAsString(k+".Class.InventoryClass")),k+" class changed");
        WCEditorCorvettes.plan(entry,originalName,originalClass).apply(root);
        check(original.equals(root.toString()),"entire donor round trip unchanged outside editable leaves");
        check(WCEditorCorvettes.plan(entry,originalName,originalClass).changes.isEmpty(),"unchanged edit no-op");
        final WCEditorCorvettes.Entry e=entry;
        blocked(()->WCEditorCorvettes.plan(e,"x","X"),"invalid class");
        blocked(()->WCEditorCorvettes.plan(e,"bad\nname","S"),"multiline name");
        plan=WCEditorCorvettes.plan(entry,"A","A");
        final WCEditorCorvettes.Plan conflict=plan;
        entry.ship.put("Name","Changed elsewhere");String beforeConflict=root.toString();
        final eY r=root; blocked(()->conflict.apply(r),"stale name blocked");
        check(beforeConflict.equals(root.toString()),"stale edit makes no partial writes");
        plan=WCEditorCorvettes.plan(entry,"B","B");
        final WCEditorCorvettes.Plan changedInventory=plan;
        entry.ship.H("Inventory_TechOnly.Class").put("InventoryClass","A");beforeConflict=root.toString();
        blocked(()->changedInventory.apply(r),"stale class blocked");check(beforeConflict.equals(root.toString()),"stale class makes no partial writes");
        plan=WCEditorCorvettes.plan(entry,"C","B"); final WCEditorCorvettes.Plan switched=plan;
        blocked(()->switched.apply(fixture),"different loaded save blocked");
        entry.ship.H("Inventory").put("FuturePreservedProperty","sentinel");
        plan.apply(root);check("sentinel".equals(entry.ship.H("Inventory").get("FuturePreservedProperty")),"concurrent unrelated edit retained");
        final eY future=fixture.bE();future.put("Version",9999);
        blocked(()->WCEditorCorvettes.plan(WCEditorCorvettes.list(future).get(0),"Future","S"),"future save blocked");
        eY season=fixture.bE();eY savedMain=season.H("BaseContext").bE();season.put("ExpeditionContext",savedMain);season.put("ActiveContext","Season");
        String baseBefore=season.H("BaseContext").toString();entry=WCEditorCorvettes.list(season).get(0);WCEditorCorvettes.plan(entry,"Season only","A").apply(season);
        check(baseBefore.equals(season.H("BaseContext").toString()),"inactive Main context retained");
        check("Season only".equals(season.getValueAsString("ExpeditionContext.PlayerStateData.ShipOwnership[1].Name")),"active season only");
        eY empty=WCCosmosModel.readJson(Paths.get(args[1]),false);check(WCEditorCorvettes.list(empty).isEmpty(),"FFC no Corvette");
        check(original.equals(fixture.toString()),"test never mutates source fixture");
        // Exercise the inherited ship models on the real donor without constructing a window.
        Class<?> unsafeType=Class.forName("sun.misc.Unsafe"); Field uf=unsafeType.getDeclaredField("theUnsafe");uf.setAccessible(true);
        Object unsafe=uf.get(null); Application app=(Application)unsafeType.getMethod("allocateInstance",Class.class).invoke(unsafe,Application.class);
        Field singleton=Application.class.getDeclaredField("L");singleton.setAccessible(true);Object oldApp=singleton.get(null);
        Field save=Application.class.getDeclaredField("aK");save.setAccessible(true);
        eY inherited=WCCosmosModel.afterRead(fixture.bE());save.set(app,inherited);singleton.set(null,app);
        try {
            String before=inherited.toString();gH[] nativeShips=gH.C(WCEditorCorvettes.player(inherited));
            check(before.equals(inherited.toString()),"native ship/inventory constructors are read-only on Cosmos donor");
            gH corvette=null;for(gH g:nativeShips)if(WCEditorCorvettes.RESOURCE.equals(g.cT()))corvette=g;
            check(corvette!=null,"inherited ship model recognises Corvette");
            String n=corvette.getName(),c=corvette.cW();corvette.setName("Native change");corvette.aj("S");
            corvette.setName(n);corvette.aj(c);
            check(before.equals(inherited.toString()),"inherited name/class setters preserve all other Cosmos data");
        } finally {singleton.set(null,oldApp);}
        System.out.println("CORVETTE_MODEL_TEST passed="+checks);
    }
}
