# Wonder Capture Companion — Phase 0 test plan

## Safety gate

- Use a normal backed-up test character.
- Confirm the Importer can already read that character.
- The companion must never request administrator privileges.
- Keep the game's own cloud-save/cross-save workflow unchanged.
- Stop immediately if any No Man's Sky save timestamp changes while the game itself is closed.

## Controlled test

1. Launch No Man's Sky and load the chosen character.
2. Launch Wonder Capture Companion.
3. Select **Scan supported saves** and choose the same character.
4. Select the exact folder where a new game screenshot will appear.
5. Select **Start read-only monitoring**. Record a screenshot of the baseline count.
6. In game, scan one previously undiscovered fauna, flora, or mineral specimen.
7. Take exactly one screenshot showing that specimen and its generated name if possible.
8. Trigger a normal in-game save, then wait up to 20 seconds.
9. Return to the companion and capture a screenshot of Session Telemetry and the Pairing Queue.
10. Confirm the pair only if the type and timing are plausible. Confirmation remains local in v0.1.0.
11. Stop monitoring before changing characters or screenshot folders.

## Return to PJ/Nova

- screenshot of the armed baseline;
- screenshot of the newly detected count;
- screenshot of the proposed pair, including timing;
- platform (Steam or Xbox / Game Pass PC);
- whether the discovery was fauna, flora, or mineral;
- whether the save update was detected without manually rescanning;
- whether the correct screenshot was proposed;
- any app error text copied exactly.

Do not send a raw save unless PJ explicitly requests a controlled clean-room diagnostic package.
