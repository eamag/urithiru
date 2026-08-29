# Original logic and correction of the first rewrite

2026-08-28. This supersedes the infrastructure-heavy structure described in
[design.md](design.md). The research implementation remains unchanged.

**This is a historical record of the port.** A later pass on 2026-08-29 deliberately
diverged from parts of the mapping below; those divergences are listed at the end and
are the current behaviour where they conflict.

## What was read

The active implementation was read line by line: engine (752 lines), agent (455),
sandbox (319), models (459), beliefs (541), priors (143), deduplication (267),
diversity (32), tree (192), configuration (27), generators (30), LLM transport
(212), dataset loader (110), and package exports. The entry-point call graph,
not historical comments or unused helpers, determines which behavior is active.

## Concrete mistakes in the first rewrite

- It invented a Journal/Store architecture instead of keeping ordinary checkpoint files.
- It added submission receipts, reconciliation, leases, task-state layers and a large
  configuration surface before faithfully moving the scientific workflow.
- It omitted the EDA prohibition on hypothesis testing and fitted statistics in claims.
- It omitted active R_ICE, log R_ICE, normalized R_ICE, fidelity, incompatibility and
  expected-free-energy calculations, and confused preserving the reward with preserving
  the complete belief analysis.
- It dropped the original literature-search audit structure and restricted arbitrary
  extracted scientific metrics to a much narrower numeric list.
- It included terminal nodes in retrieved evidence although the original excludes them.
- It made a failed empirical execution abort unconditionally, whereas the original
  retains valid structured verification outcomes and separates execution validity,
  specification validity, direction and empirical support.
- It shortened prompts by deleting scientific instructions rather than extracting them.
- It changed embedding precision/batching and evidence formatting without establishing
  equivalence. The earlier numerical check covered belief means, KL, reward and UCT
  only; it did not establish workflow or prompt parity.

## Behavior mapping

| Original code | Behavior to retain | Destination responsibility |
| --- | --- | --- |
| engine 106–198 | Load run, select one leaf, freeze bounded sibling batch, evaluate, commit in submission order | Engine owns the run state; short methods for one step each |
| engine 200–287 | Construct execution/verification records; derive search/code beliefs; compute all diagnostics; gate external verification | Evaluation methods operating on one experiment |
| engine 305–357 | Regenerate at most twice when deduplication empties a leaf; terminalize exhaustion; elicit selected candidate's prior | Candidate acquisition with shared model/cache configuration |
| engine 359–448 | Add seed and realized external value in a single backpropagation; no external penalty for abstention | Engine and belief calculations |
| engine 450–586 | Ancestor/attempt context, EDA viability, generation audits, exact/semantic dedup, least-local-similarity selection | Agent prompts and candidate selection |
| engine 588–619 | Exclude terminal nodes; retain negative evidence; use external belief when present; preserve extracted findings | Evidence retrieval/formatting |
| engine 621–752 | Load/save JSON checkpoints and resolved run configuration; emit scientific summaries | Simple checkpoint functions and engine methods |
| tree 90–94, 157–192 | Actual UCT expression, progressive widening, terminal filtering, visit/value propagation | Stateful tree with a node registry/root |
| priors 31–91 | Five-category normalization, 30 pseudovotes, Beta(0.5, 0.5) update | Belief model/calculations |
| priors 99–135 | Skeptical prior elicitation before empirical execution | Prior method with shared LLM/configuration |
| beliefs 147–309, 397–461 | Binary/categorical surprise, three KLs, R_ICE variants, fidelity, three incompatibilities, EFE | Belief analysis holding prior/search/code as instance attributes |
| deduplication 197–267 | Exact dedup → Ward hierarchy → cached model merges; stable representatives and candidate audit mapping | Candidate selector with model/cache as instance attributes |
| diversity 10–32 | Mean top-k cosine similarity; original precision and ordering | Candidate selector |
| agent 43–165 | Data-blind Phase A; persisted search assessment; independent literature; mandatory empirical Phase B; four outcome booleans | Verification prompt and result parser |
| agent 167–264 | Literal-scope independent data search; primary estimand; search breadth; cost rubric; no belief if no defensible test | External prompt and result parser |
| agent 266–333 | Recover valid structured results, prefer persisted Phase A, diagnose timeout/parse/infrastructure failures | Agent result handling |
| agent 341–455 | Empirical viability; descriptive EDA only; no fitted statistics in claims; novel falsifiable declarations | Proposal prompt and result parser |
| sandbox 24–79, 117–319 | Write preflight, isolated workspace, streamed logs, timeout/grace, retained generated work | Sandbox runtime with shared execution settings |

## Deliberate exclusions and corrections

The active engine never calls the fallback posterior elicitation path, the H48
stratified retrieval helper, shadow/factorial code, or the standalone literature
provider. They are not silently presented as active features. UCT's old docstring
and unused policy arguments do not describe its executed formula. The constant
sensitivity score is not a measured sensitivity analysis.

The user explicitly requested CSV/Excel plus arbitrary metadata, so benchmark
metadata interpretation is replaced with plain file staging. Credentials are not
copied wholesale. Missing required data still fail instead of receiving invented
defaults. These are explicit boundary changes, not reasons to redesign the algorithm.

The user also explicitly removed streaming, the general Process wrapper and the
doctor command. Docker execution writes a log and waits for its subprocess.
Imports stay at module scope. Result types have separate small parsers rather
than an overloaded generic dispatcher.

## Simplification rule

Move the original logic into cohesive classes that own their shared state:
engine, tree, belief analysis, candidate selector, agent and sandbox. Methods
normally take zero, one or two domain arguments. Keep pure numerical helpers pure.
Do not pass configuration, paths, models, caches and run state through every call.

Persistence is checkpoint JSON plus ordinary output files. Google-specific code
uploads/downloads those files and launches/waits for worker jobs. There is no
generic storage protocol, journal, event system, or task-reconciliation product.
Each retained component must map to original behavior or a necessary Google adapter.

## Verification

Compare all active calculations, candidate decisions, retrieval ordering, outcome
handling and checkpoint restoration against saved original artifacts. Read the
prompt mapping explicitly. No new tests, paid model calls or cloud deployment are
authorized by this corrective pass.

## Later divergence, 2026-08-29

Faithful porting was the right goal for the first pass, and it is what made these
divergences safe to choose: each one is a decision made against a working baseline,
not a shortcut taken instead of understanding the original.

| Original behaviour | Now | Why |
| --- | --- | --- |
| One verification agent produced P_search then P_code in sequence, with a `p_search.json` write in between | Two agents, two containers, started together: `search` (never given the data) and `code` (never told the literature's answer) | The harness enforced Phase A by comparing file modification times against `p_search.json`. Separating the containers makes data-blindness a property of the filesystem, removes the forensics, halves the stage's wall clock, and turns `KL(P_code \|\| P_search)` from one agent's self-consistency into a disagreement between two sources |
| Belief analysis exported 13 diagnostics: three KLs, R_ICE, log R_ICE, normalized R_ICE, fidelity, three incompatibilities, EFE, binary KL, belief change, surprise flag | Six: `kl_search_param`, `kl_code_search`, `kl_code_param`, `r_ice_norm`, `belief_change`, `is_surprising` | Nothing read the other seven, and each duplicated a kept one: `fidelity` is `1 - reward`; `r_ice` and `log_r_ice` are monotone transforms of `r_ice_norm`; the binary KL re-measures the categorical KL's move; the three incompatibilities and EFE all restate `kl_search_param` or the code belief's own entropy. `kl_code_param` was promoted from an internal denominator to a reported number, so the three hops are now all visible |
| Deduplication: exact match, then Ward linkage over embeddings with a disjoint-set walk of scipy's merge order, asking the model at every merge | Exact match, then cosine similarity against the claims kept so far, asking the model only above a threshold | Same two-step decision, same cached model call, same "first of an equivalent group survives" outcome, without reconstructing scipy's cluster numbering; and it asks the model about pairs that could plausibly be duplicates rather than about every merge |
| `AgentExecutionResult` carried both beliefs and was validated by a separate `validate()` call | `Literature` and `Experiment`, each frozen and validating in `__post_init__` | The records now match the containers that produce them, and an unparseable agent result fails at the boundary rather than downstream |
| Two surprise thresholds, `surprisal_threshold` and `external_minimum_surprise` | One, `external_minimum_surprise` | Only the second gated anything; the first was stored on every evaluation and never read |
| `agent_env` forwarded declared credentials into the sandbox, and artifacts were scanned and redacted afterwards | Removed | It was configured empty in every profile, so the redaction pass always ran over an empty secret list. Sandboxes now carry the agent's model key and nothing else, and the literature prompts say so instead of describing keys that cannot be present |
