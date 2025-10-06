package chiron.dependencies

context_input {
  input.kind == "context"
}

sbom_required {
  context_input
  input.dependencies.staged
}

sbom_required {
  context_input
  input.dependencies.baseline_diff
}

deny[msg] {
  context_input
  not input.sbom.exists
  msg := "SBOM artifacts missing; run 'syft . -o cyclonedx-json=sbom.json'"
}

deny[msg] {
  context_input
  sbom_required
  input.sbom.exists
  not input.sbom.staged
  not input.sbom.fresh_vs_dependencies
  msg := "Dependency manifest changed but SBOM was not regenerated"
}

deny[msg] {
  context_input
  sbom_required
  input.sbom.exists
  input.sbom.older_than_dependencies
  msg := "SBOM older than dependency files; rerun SBOM generation"
}

deny[msg] {
  context_input
  input.sbom.exists
  not input.sbom.fresh_within_days
  msg := "SBOM older than freshness threshold (7 days)"
}
