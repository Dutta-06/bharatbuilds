# Dashboard design notes

An instrument panel, not a marketing page. The rules below keep new screens consistent.

- **Neutral UI, colour only for meaning.** Surfaces, text and controls are true-neutral greys (tokens in `src/styles.css`, light, dark and
  system via `data-theme`). Hue appears in two places: the cost scale (`--scale-low/mid/high`, cheaper to costlier) and state
  (`--good/--warn/--bad` on status LEDs and savings text). Primary actions are ink on paper, not an accent colour.
- **Type.** IBM Plex Sans for reading, IBM Plex Mono for every number, id, unit and label. Numbers use tabular figures so columns line up.
- **Shape.** 2 to 6 px corners. Hairline rules separate sections; a bordered panel is used only for forms, estimates and tables.
  `.readout` (with corner ticks) is reserved for the figures a page exists to show.
- **Time.** Show local time first (`src/time.js`), UTC on hover or one line below. Never show raw ISO strings to people.
- **Honest labels.** Modelled figures say modelled. A warning banner appears only when an input is genuinely not live.
- **Every colour-coded view has a table or text equivalent**; charts have an accessible name; the cost grid's keyboard route is the hour slider.
- **Phones.** One column, 16 px gutters, tables become lists (`.joblist`) or scroll inside their own container. Check at 390 px.
