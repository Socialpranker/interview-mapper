# Why it's built this way — the evidence base

The skill is designed from research findings (2023–2025). Briefly, why each mechanism exists.

## Verbatim ≠ support (two orthogonal tests)
A quote may be verbatim in the source, yet the conclusion may not follow from it. Empirically: a system with
verbatim quotes scored only 0.033 on entailment; up to 57% of LLM quotes are "post-rationalization"
(the model leans on its own knowledge and back-fills the quote afterward). That's why S2 checks both
verbatim (script) and support (judge model).
Sources: ALCE (EMNLP'23), "Correctness is not Faithfulness in RAG" (SIGIR ICTIR'25).

## Quotes — "regeneration", not extraction
~7.7% of generated quotes aren't found verbatim in the original; many have fillers removed and
punctuation changed, which alters the meaning. Hence `verify_quotes.py`: normalization + fuzzy + a coverage
threshold, not "trust" in the model. Omissions are more dangerous than fabrications (omission 3.45% vs hallucination 1.47%)
→ a mandatory omission check.
Sources: Learning Analytics (CEUR), npj Digital Medicine 2025 (via uintent).

## Multiple runs + consensus
Correct conclusions converge across runs, errors are scattered (self-consistency: +6–18% on benchmarks,
ICLR'23). Multi-agent debate reduces hallucinations (ICML'24). But consensus for open text is
AGREEMENT, not an exact match (Universal Self-Consistency), so `consensus.py` votes
by label and doesn't count paraphrase wordings as disagreement.

## Flag for a human, not an auto-judge
A single LLM judge is unreliable: flip-rate up to 56%, systematic biases (position, length, self-
preference). So disputed cells are NOT decided automatically — they go to a human. This is confirmed
directly on the qual task: "human-in-the-loop necessary"; escalating rare/disputed codes to an expert raises
κ with little manual editing (LAK'26).

## Star model + re-grounding
Multi-turn dialogue accumulates error (~30% in HalluHard), "the model believes itself". So each run is a
fresh context, with the transcript fed anew rather than the chat history.

## Latent constructs — the LLM's limit
On context-heavy codes (tone, intent, power, eNPS) κ drops almost to 0, whereas on
surface ones (sentiment) κ is 0.91–0.95. That's why analytical labels are honestly marked as
candidates for a human.
Sources: PERC'25, AI&Society 2025, mental-health TA (2507.08002).

## Implementation precedents (reuse, don't reinvent)
- **LLMCode**: exact → Levenshtein<5 → rapidfuzz ratio≥90, transfer the annotation onto the verbatim original; unsalvageable — discard.
- **DeTAILS**: not verbatim — discard.
- **Deterministic Quoting**: don't trust the quote text, take it by reference.
Our `verify_quotes.py` is a hybrid: it fixes (fuzzy transfer) + flags/discards + logs everything transparently.

Full references — in `06_Desk-research/interview-mapping-methods/` (landscape + quote-verification).
