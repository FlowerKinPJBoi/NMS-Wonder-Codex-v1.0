package nomanssave;

import java.lang.reflect.Field;
import java.math.BigInteger;
import java.util.List;
import java.util.Locale;

/** Exact address conversion using the pinned native editor's coordinate codec. */
public final class WCEditorAddress {
    private static final BigInteger MAX_UNSIGNED_LONG = BigInteger.ONE.shiftLeft(64).subtract(BigInteger.ONE);
    private WCEditorAddress() {}

    public static String portalText(String value) {
        return value == null ? "" : value.trim().replaceAll("\\s+", "").toUpperCase(Locale.ROOT);
    }
    public static hl portal(String value, int galaxy) {
        checkGalaxy(galaxy);
        String text = portalText(value);
        if (!text.matches("[0-9A-F]{12}"))
            throw new IllegalArgumentException("Enter all 12 portal characters using 0–9 and A–F, or click 12 glyphs.");
        return checked(hl.e(text, galaxy));
    }
    public static hl galactic(String value, int galaxy) {
        checkGalaxy(galaxy);
        String text = portalText(value);
        if (!text.matches("[0-9A-F]{4}(:[0-9A-F]{4}){3}"))
            throw new IllegalArgumentException("Use galactic coordinates XXXX:YYYY:ZZZZ:PSSS.");
        try { return checked(hl.e(text, galaxy)); }
        catch (RuntimeException ex) { throw new IllegalArgumentException("Galactic coordinates are outside the supported range.", ex); }
    }
    public static hl universal(String value) {
        String text = value == null ? "" : value.trim();
        BigInteger exact;
        if (text.matches("(?i)0x[0-9a-f]{1,16}")) exact = new BigInteger(text.substring(2), 16);
        else if (text.matches("[0-9]{1,20}")) exact = new BigInteger(text, 10);
        else throw new IllegalArgumentException("Use an unsigned decimal universe address, or 0x followed by 1–16 hex characters.");
        if (exact.signum() < 0 || exact.compareTo(MAX_UNSIGNED_LONG) > 0)
            throw new IllegalArgumentException("Universe address exceeds the unsigned 64-bit range.");
        hl address = checked(hl.n(Long.valueOf(exact.longValue())));
        // The native encoder reserves the high byte. Reject it rather than truncate it.
        BigInteger encoded = new BigInteger(Long.toUnsignedString(address.ex()));
        if (!exact.equals(encoded)) throw new IllegalArgumentException("Universe address contains unsupported high bits; no value was truncated.");
        return address;
    }
    public static String universalHex(hl address) {
        checked(address);
        return "0x" + Long.toHexString(address.ex()).toUpperCase(Locale.ROOT);
    }
    public static String universalDecimal(hl address) {
        checked(address);
        return Long.toUnsignedString(address.ex());
    }
    public static String galacticText(hl address) {
        checked(address);
        // Native four-part coordinates cannot represent the signed minimum voxel.
        if (address.ev() == -2048 || address.et() == -128 || address.eu() == -2048) return "";
        return address.ez();
    }
    public static String[] galaxies() {
        String[] names = new String[256];
        try {
            Field field = aj.class.getDeclaredField("bW");
            field.setAccessible(true);
            List<?> nativeNames = (List<?>) field.get(null);
            for (int i = 0; i < names.length; i++)
                names[i] = (i + 1) + " · " + (i < nativeNames.size() ? String.valueOf(nativeNames.get(i)) : "Galaxy " + (i + 1));
        } catch (ReflectiveOperationException ex) {
            throw new IllegalStateException("The native editor's galaxy catalogue could not be loaded.", ex);
        }
        return names;
    }
    private static void checkGalaxy(int galaxy) {
        if (galaxy < 0 || galaxy > 255) throw new IllegalArgumentException("Galaxy index must be 0–255.");
    }
    private static hl checked(hl address) {
        if (address == null) throw new IllegalArgumentException("Address could not be decoded.");
        WCCosmosModel.validateAddress(address.ew());
        return address;
    }
}
