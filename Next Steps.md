## Next Steps

Alright Jonathan—here’s a concrete, copy-ready playbook that you can actually run. I’ve tuned it for “evidence-gated” refactors at scale (monorepos and multi-service orgs), with quality gates that map to recognised standards and a pragmatic toolchain you can automate end-to-end.

Executive summary

Refactoring “intelligently” means: (1) pick the few changes that cut the most future cost/risk, (2) prove no behavioural drift, (3) gate merges on standards-backed quality, and (4) mechanise everything. In practice: use hotspot targeting (complexity × churn), wrap each change with characterisation tests, run codemods (OpenRewrite/Refaster/etc.), and block merges with quality gates (e.g., ISO 5055-aligned findings + Cognitive Complexity caps). Large-scale changes (LSCs) must land incrementally, not as big-bangs.  ￼

Auto-Expert framing

Classification: Software engineering process & tooling (large-scale code modernisation).
Personas & methods (pre-registered):
	•	Code Quality Researcher: optimises against ISO 25010 product quality characteristics; enforces ISO 5055 structural weakness caps; validates Cognitive Complexity effects.  ￼
	•	DevEx/Tooling Engineer: codemods with OpenRewrite/Refaster; CI quality gates (Sonar*); refactoring detection (RefactoringMiner).  ￼
	•	Software Architect: plans LSCs with Mikado + strangler-fig, increments via trunk-compatible slices.  ￼

Analysis plan:
	1.	Build a hotspot map (complexity × change frequency). 2) For each candidate, add/extend characterisation tests to freeze behaviour. 3) Select codemod recipes + migration patterns. 4) Enforce quality gates on “New Code” and fail CI on regressions. 5) Ship as a sequence of safe, reversible slices (LSC discipline).  ￼

The backbone: factors, metrics, principles, methods

What to optimise (factors) & how to measure (metrics)
	•	Product quality model: Use ISO/IEC 25010 to anchor non-functional goals (reliability, performance efficiency, security, maintainability, etc.). This is your “why”.  ￼
	•	Structural quality (automatable): Use ISO/IEC 5055 (CISQ). It defines 138 severe weaknesses across four factors (Security, Reliability, Performance Efficiency, Maintainability) with detection patterns you can gate on in CI. This is your “what exactly”.  ￼
	•	Understandability proxy: Cognitive Complexity (Sonar) for functions/methods; cap it and trend it down on hotspots. This is your “how readable”.  ￼
	•	“Where to start”: Hotspots = complexity × churn. Prioritise files/methods that are both complex and frequently changed; that’s where refactors repay fastest. This is your “where”.  ￼

Principles that keep you honest
	•	Behaviour-preserving by test: lock current behaviour with characterisation / approval tests before editing; treat diffs as suspect.  ￼
	•	LSCs as sequences, not big-bangs: land in small, reviewable, revertible steps; codemods + CI gates + owners reviews.  ￼
	•	Mikado + strangler-fig: plan dependencies backward (Mikado); where replacing components, route traffic via a strangler seam.  ￼

Methods & tooling (industry-standard)
	•	Codemods:
	•	OpenRewrite recipes (Java/XML/Gradle/Maven); YAML or imperative recipes; composition for framework migrations.  ￼
	•	Refaster / Error Prone for exact Java AST rewrites.  ￼
	•	Refactor detection: RefactoringMiner surfaces detected refactorings in a PR/commit; use for audit & analytics.  ￼
	•	Quality gates in CI: Sonar* quality gates (fail merges on thresholds; decorate PRs).  ￼
	•	Mutation testing (risk lens): PIT (JVM), Stryker (JS/TS/C#/others) for a small, budgeted slice of hotspots.  ￼

“If it were flawless, what would the tool look like?”

Capabilities checklist (north star):
	1.	Hotspot radar: native git mining + static analysis; ranks methods/files by (Cognitive Complexity, LOC) × (commit churn, ownership/knowledge risk).  ￼
	2.	Change planner: Mikado graph + suggested sequences; flags dependency breakpoints and proposes seams (adapters/anti-corruption layers).  ￼
	3.	Recipe engine: first-class codemods with preview diffs; supports OpenRewrite/Refaster rules + per-language ASTs; safe mode enforces preconditions.  ￼
	4.	Behaviour net: generates characterisation tests from execution traces/snapshots; runs mutation testing to score test adequacy for the changed slice.  ￼
	5.	Standards gate: live evaluation against ISO 5055 (weakness counts/density) and Cognitive Complexity deltas; PR fails if “New Code” regresses.  ￼
	6.	LSC orchestrator: splits large transforms into mergeable chunks; tracks review owner sets; retries failed chunks; produces progress burndowns.  ￼

Concrete starter pack (drop-in)

A. Hotspot targeting (bash + one small Python join)
	1.	Churn (past 12 months):

git log --since="12 months ago" --name-only --pretty=format: \
| awk 'NF' | sort | uniq -c | sort -nr > churn.txt

	2.	Cyclomatic complexity (multi-language) → CSV: pipx install lizard then:

lizard -o complexity.csv -CSV .

	3.	Join & rank (Python):

import csv, math
cc = {r['filename']: int(r['NLOC'])+int(r['CCN']) for r in csv.DictReader(open('complexity.csv'))}
ch = {f.strip(): int(c.split()[0]) for c,*f in (l.split(maxsplit=1) for l in open('churn.txt'))}
rows = [(f, cc.get(f,0), ch.get(f,0), cc.get(f,0)*ch.get(f,0)) for f in set(cc)|set(ch)]
rows.sort(key=lambda r: r[3], reverse=True)
with open('hotspots.csv','w',newline='') as o:
    w=csv.writer(o); w.writerow(['file','complexity_score','churn','hotspot'])
    w.writerows(rows)
print("Top 20:"); [print(r) for r in rows[:20]]

Interpretation: focus on top 5–10 files first; confirm with Cognitive Complexity at function level.  ￼

B. Safety net: characterisation tests (pattern)
	•	For data-in/data-out code, add snapshot/approval tests: record outputs for varied inputs → approve → refactor → compare.
Example libraries: ApprovalTests (many languages).  ￼

C. Quality gates (SonarQube/Cloud)

Policy (New Code only):
	•	No new Blocker/Critical issues; Coverage ≥ 80% on New Code; Duplications ≤ 1%; Cognitive Complexity per method ≤ 15 (or down from baseline); Security Hotspots reviewed. (Tune per repo.)

CI (GitHub Actions) excerpt:

jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: '21' }
      - name: Build & test
        run: ./mvnw -B -DskipITs=false test
      - name: Sonar scan (wait for QG)
        uses: SonarSource/sonarcloud-github-action@v2
        with:
          args: >
            -Dsonar.projectKey=acme_app
            -Dsonar.organization=acme
            -Dsonar.qualitygate.wait=true

This waits for the server-side Quality Gate result and fails the job if it doesn’t pass.  ￼

D. RefactoringMiner in CI (audit the change)

  refactoringminer:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - name: Run RefactoringMiner on PR
        run: |
          curl -L -o rm.jar https://github.com/tsantalis/RefactoringMiner/releases/latest/download/RefactoringMiner-*-all.jar
          base=$(jq -r .pull_request.base.sha <<< "${{ toJson(github.event) }}")
          head=$(jq -r .pull_request.head.sha <<< "${{ toJson(github.event) }}")
          java -jar rm.jar -bc $base -gc $head -json refactorings.json
          jq '.[0] | {refactorings: .refactorings | length}' refactorings.json || true
      - uses: actions/upload-artifact@v4
        with: { name: refactorings, path: refactorings.json }

Use the JSON to spot unintended refactors (e.g., “Extract Method” in risky areas).  ￼

E. OpenRewrite skeleton (Java)

rewrite.yml (example: rename method + format):

type: specs.openrewrite.org/v1beta/recipe
name: com.acme.SpringRenames
displayName: Spring API renames + formatting
recipeList:
  - org.openrewrite.java.ChangeMethodName:
      methodPattern: "com.acme.LegacyService doThing(..)"
      newMethodName: "execute"
  - org.openrewrite.java.format.AutoFormat

Maven plugin:

<plugin>
  <groupId>org.openrewrite.maven</groupId>
  <artifactId>rewrite-maven-plugin</artifactId>
  <version>${rewrite.version}</version>
  <configuration>
    <activeRecipes>
      <recipe>com.acme.SpringRenames</recipe>
    </activeRecipes>
  </configuration>
</plugin>

Run: mvn -Drewrite.activeRecipes=com.acme.SpringRenames rewrite:run.  ￼

F. Mutation-testing budget (target top hotspots only)
	•	Java: PIT mvn org.pitest:pitest-maven:mutationCoverage -DtargetTests=... -Dmutators=STRONGER -DtimeoutConst=4000 -Dthreads=4
	•	JS/TS: Stryker: in stryker.conf.json, set "mutate": ["src/hotspot/**.ts"], run npx stryker run. Treat mutation score as guardrail (raise slowly).  ￼

G. Change-management pattern (LSCs)
	•	For each slice: Mikado checklist (sketch goal → list prerequisites → spike → revert → implement leaves first) and, where replacing components, strangler seam that routes traffic to new code behind identical contracts. Merge each slice under the same Quality Gate.  ￼

Risk controls and anti-patterns
	•	Do not attempt monolithic “rename everything” PRs. Google’s experience is clear: LSCs scale when automated, owner-reviewed, and chunked.  ￼
	•	Do not rely on Cyclomatic Complexity alone; pair it with Cognitive Complexity (readability) and churn (economic signal) to prioritise.  ￼
	•	Do not skip the behaviour net. Characterisation tests are the cheapest insurance for legacy code.  ￼

Evidence-gated protocol (what makes this “best practice”?)

Data → ISO 25010 model; ISO 5055 structural weakness catalogue & detection patterns; Cognitive Complexity spec & empirical work; Google LSC practices; OpenRewrite/Refaster codemods; RefactoringMiner detector; hotspot method from behavioural code analysis.  ￼
Methods → Prioritise by hotspots; freeze behaviour; scripted codemods; gated CI; incremental LSCs.
Key results → Fewer risky edits (hotspot focus), documented refactors (miner JSON), and merges blocked on standards-aligned gates (no silent regressions).
Uncertainty → ISO 5055 coverage varies by tool; Cognitive Complexity correlates with understandability but isn’t perfect; mutation testing is time-consuming—apply sparingly.  ￼
Safer alternative → If inputs (tests, telemetry, build stability) are weak, start with non-semantic refactors (formatting, imports, naming, dead code), enforce gates on New Code only, then widen scope.

Where to go deeper next
	•	Plug your repo into this pipeline and we’ll produce a first hotspots.csv, then pick three candidates and run the OpenRewrite + tests + quality gate loop.

This is deliberately strict and dull—the kind of dull that prevents scary surprises in production.

## Risks / Notes
- Remaining gaps now centre on live Pact validation against deployed services; the new `--contracts` gate exercises the local mock-service flow but production rollouts should still trial full telemetry pipelines before release.
- Pact-related warnings remain noisy but accepted for now; dynamic port allocation reduces flake risk but HTTP-level validation is still outstanding.
- Pact contract tests now auto-skip when the mock service cannot start; run `pact-mock-service` locally to exercise full interactions before release sign-off.
- New QA toolbox accelerates iteration but coverage hotspots highlighted (deps.verify, service routes) still require targeted tests.
- Bandit informational findings (3 medium, 81 low) stem from packaging/semgrep helpers and will be triaged with security owners.
- Diataxis overview depends on `docs/diataxis.json`; keep the mapping updated when adding or renaming guides to avoid stale navigation.
- Coverage sits at 83.67% after the enhanced refactor heuristics; continue targeting high-branch modules to regain margin.
- Refactor heuristics flag hotspots automatically; future passes should feed live complexity metrics into roadmap prioritisation.
