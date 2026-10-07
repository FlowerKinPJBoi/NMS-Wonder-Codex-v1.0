package nomanssave;

import java.awt.Image;
import java.awt.Window;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import javax.imageio.ImageIO;

/** Optional window branding; a missing image must never prevent opening a save. */
public final class WCEditorBranding {
    private static final int[] SIZES = {16, 24, 32, 48, 64, 128, 256};

    private WCEditorBranding() { }

    /** Uses bundled PNGs for the window and taskbar; the installer uses the ICO. */
    public static void apply(Window window) {
        if (window == null) return;
        try {
            List<Image> icons = loadIcons();
            if (!icons.isEmpty()) window.setIconImages(icons);
        } catch (RuntimeException ignored) {
            // Icons are cosmetic and must not interfere with the editor.
        }
    }

    static List<Image> loadIcons() {
        List<Image> result = new ArrayList<Image>();
        File assets = adjacentAssets();
        for (int size : SIZES) {
            String name = "WonderCodex-" + size + ".png";
            Image image = resourceImage("/assets/" + name);
            if (image == null && assets != null) {
                try {
                    File path = new File(assets, name);
                    if (path.isFile()) image = ImageIO.read(path);
                } catch (IOException ignored) {
                    // Try the next size if an optional asset is unreadable.
                } catch (SecurityException ignored) {
                    // Resource images still work if filesystem access is restricted.
                }
            }
            if (image != null && image.getWidth(null) == size
                    && image.getHeight(null) == size) result.add(image);
        }
        return result;
    }

    private static Image resourceImage(String name) {
        try (InputStream input = WCEditorBranding.class.getResourceAsStream(name)) {
            return input == null ? null : ImageIO.read(input);
        } catch (IOException ignored) {
            return null;
        } catch (RuntimeException ignored) {
            return null;
        }
    }

    private static File adjacentAssets() {
        try {
            URI location = WCEditorBranding.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI();
            if (!"file".equalsIgnoreCase(location.getScheme())) return null;
            File source = new File(location);
            File root = source.isFile() ? source.getParentFile() : source;
            return root == null ? null : new File(root, "assets");
        } catch (Exception ignored) {
            return null;
        }
    }
}
