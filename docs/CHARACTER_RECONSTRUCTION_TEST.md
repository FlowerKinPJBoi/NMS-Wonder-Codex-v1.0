# v0.1.7 Character Reconstruction Test

## Expected account reconstruction for the current tester machine

### Account containing Flower-Kin

| Character | Expected grouped revisions | Known discoveries | Known pets | Known exact matches |
|---|---:|---:|---:|---:|
| Codex Hunter | 2 | 248 | 2 | 1 |
| PJ's Explorer | 2 | 528 | 11 | 9 |
| Flower-Kin | 2 | 3,208 | 34 | 9 |

### Account containing FFC Builder

| Character | Expected grouped revisions | Known discoveries | Known pets | Known exact matches |
|---|---:|---:|---:|---:|
| FFC Builder | 2 | 3,200 | 33 | 23 |
| FFC Builder II | 2 | 2,080 | 15 | 14 |

The small metadata/account container should not appear as a character.

## Pass criteria

- Five resolved character cards total.
- No raw `WGS candidate` names in normal mode for supported saves.
- Each known character pair is grouped into one card.
- Preferred revision analyzes successfully.
- Alternate revision remains available in Advanced details.
- Research panel remains hidden until Research mode is enabled.
- No raw save, decoded JSON, account path, or account ID is uploaded.

## Auto/manual naming

Do not infer Auto versus Manual from size, timestamp, folder order, or container token. v0.1.7 uses neutral preferred/alternate labels until the WGS index structure is independently verified.
