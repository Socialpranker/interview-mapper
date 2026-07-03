# Contributing

Thanks for your interest! This project is a Claude/Cowork **skill** plus stdlib-only Python tooling.

## Principles (please preserve them)
1. **Every conclusion is grounded in a verbatim quote.** Don't add features that let the model assert without a source.
2. **Verbatim ≠ support.** Keep the two checks (`verify_quotes.py`, `check_support.py`) separate.
3. **Disputes go to a human.** The reliability council flags; it does not silently pick winners.
4. **A pattern needs triangulation** (≥k distinct interviews). No "everyone said X" from one loud respondent.
5. **Honesty over polish.** If thresholds are guessed or n is too small, the output must say so.

## Repo structure
- `interview-mapper/` (RU) and `interview-mapper-en/` (EN) are parallel — **keep them in sync**. A change to one usually needs the mirror change to the other.
- Scripts are **stdlib-only** by contract (`rapidfuzz` optional with `difflib` fallback). Don't add hard dependencies.
- Data field names / JSON keys are a contract shared between scripts — renaming one means updating all consumers.

## Dev checks
```bash
python -m py_compile interview-mapper*/scripts/*.py   # must pass
python interview-mapper-en/scripts/route.py --goal org --respondent employee --n 3   # smoke test
```

## Adding a lens or output
Before adding a template, check the two axes: is the task already covered by an existing `lens × output`? If yes, don't add a duplicate — extend routing in `references/intake.md` and `scripts/route.py`.

## Calibration
New matching/scoring thresholds must come with a note on how they were calibrated (`references/validation.md`), not hardcoded from a tutorial.
