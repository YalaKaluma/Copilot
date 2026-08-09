# Pricing hypothesis evidence rules

These rules incorporate reviewed hypothesis and evidence feedback.

## Allowed hypotheses

- Evaluate increase price and decrease price internally for every SKU-retailer
  combination, but surface only the direction with the higher evidence-based
  confidence.
- Never display both directions for the same SKU-retailer combination.
- Promotion, trade terms, assortment, and mix are not pricing hypotheses.

## Evidence construction

- One evidence card must contain one coherent signal.
- Do not combine growth and share in one card when they point in different
  directions. Put them on different sides of the hypothesis or omit the
  ambiguous combination.
- Say `sales growth` or `volume growth`; do not use the vague term
  `performance`.
- Do not infer causality from coincident price, sales, or volume movements.

## Source roles

- Market Landscape: brand-level sales growth, volume growth, share, and market
  context. The API cannot group by SKU, but it can filter by `sku_ids`; use a
  selected-SKU-filtered brand row to compare SKU growth with total-brand growth.
- Price Ladder: primary evidence for competitive price positioning. Compare the
  selected retailer with several other retailers and state whether the price
  gap is consistent.
- Price Pack Curve: SKU growth and internal pack-price architecture. Compare the
  selected SKU with relevant same-brand pack sizes; inspect the SKU names and
  IDs behind each pack point for product, formulation, format, and pack
  differences. Do not analyze the selected point in isolation.

## Comparison hierarchy

- Lead with the selected retailer, then compare with the overall market and
  peer retailers.
- Explicitly label every observation as selected-retailer, overall-market, or
  peer-retailer evidence.
- Translate technical ladder fields into plain language. Instead of
  `retailer-gap contribution`, say the retailer prices the brand above or below
  its overall benchmark and state the magnitude and basis.
- If nearby same-brand pack prices bracket the selected price, describe upward
  headroom as limited. State that the architecture is inconsistent because the
  price sequence is not monotonic, and identify the exact higher and lower
  neighbors.

## Clarity

- State the exact relevant comparison and implication.
- Avoid double negatives and vague statements such as `not an unambiguous
  low-price position`.
- If ownership, mapping, or source coverage is uncertain, treat it as explicit
  counterevidence and lower confidence.
