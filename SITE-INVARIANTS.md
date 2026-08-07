# Wonder Codex public-site invariants

These rules are release blockers, not optional copy suggestions.

1. **Preserve stays visible.** The public identity must continue to say
   “Preserve the procedural universe” (or a grammatically equivalent sentence
   using the word “preserve”).
2. **Evidence class stays visible.** Representative and synthetic imagery must
   never be presented as an exact discovered specimen.
3. **Exact screenshots win.** An approved discovery screenshot always takes
   precedence over Forge or archetype artwork.
4. **Forge representatives do not complete image evidence.** Showing a family
   representative must not change a discovery's `image_status` or create an
   approved image contribution.
5. **Synthetic variants are gallery-only.** A
   `NMS_PARTS_AUTHENTIC_SYNTHETIC_VARIANT` must never be assigned to a discovery
   record without new, repeatable exact-specimen evidence.
6. **Private data stays private.** Public pages may display evidence summaries
   and stable references, but not raw private save data or hidden VP values.
7. **Screenshot Find stays easy to reach.** Public navigation must retain a
   direct path to the exact-specimen screenshot contribution form.
8. **Forge controls stay evidence-backed.** A part selector may offer only
   certified rendered recipes or isolated layers present in the public Forge
   catalog; an unavailable composite must not be presented as generated.
9. **Forge holograms retain their galactic stage.** Transparent Forge renders
   must remain legible over a visibly starry, irregular deep-space backdrop at
   both card and record sizes.
10. **Screenshot Find reports only queued evidence as success.** Browser
    autofill must not populate the hidden spam check, and an image submission
    is successful only when the API returns a pending review reference.
11. **Screenshot Find never has a silent dead button.** Before submission, the
    primary action remains clickable and reports the first missing requirement;
    visible record text is not treated as a selection without a confirmed
    catalog record.
12. **Expedition components stay components.** Starship, freighter, and
    multi-tool part previews may appear in the Forge Component Vault but may not
    become a complete catalog specimen image.
13. **Record imagery must identify the visual variant.** A Forge image may be
    assigned only through an explicit privacy-safe discovery/asset identity
    selector or an observed descriptor-profile selector. Category, asset type,
    fauna family, VP1 cohort, and deterministic hashing are insufficient.
    Unbound forms—including clean front-facing forms—remain gallery-only until
    the Expedition records the selector that produced them.
14. **The museum mission stays visible.** Public mission language continues to
    describe Wonder Codex as “an interactive, user-contributed museum of the
    galaxies.”
15. **Precision matching survives API rollout gaps.** Database, discovery, and
    asset pages load the public ringless Forge manifest as a client-side fallback
    when the API does not return matched-image metadata. The fallback must
    enforce the same explicit-selector requirement and exact-image precedence as
    the API; otherwise it must show the neutral image-needed state.
16. **Missing is safer than misleading.** A record without an exact screenshot
    or evidence-matched Forge reconstruction must not display a broad family,
    category, biome, or asset-type placeholder as though it helps identify the
    in-game find.
