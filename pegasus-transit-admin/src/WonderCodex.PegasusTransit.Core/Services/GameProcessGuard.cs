using System.Diagnostics;

namespace WonderCodex.PegasusTransit.Core.Services;

public static class GameProcessGuard
{
    public static void ThrowIfNoMansSkyIsRunning()
    {
        var processes = Process.GetProcessesByName("NMS");
        try
        {
            if (processes.Length > 0)
                throw new InvalidOperationException(
                    "No Man's Sky is still running. Close the game completely before engaging Pegasus Transit.");
        }
        finally
        {
            foreach (var process in processes) process.Dispose();
        }
    }
}
