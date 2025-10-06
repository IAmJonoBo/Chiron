package chiron.workflows

job_by_name(workflow, name) = job {
  job := workflow.jobs[name]
}

step_names(job) = names {
  names := [step.name | step := job.steps[_]; step.name]
}

job_exists_with_step(workflow, job_name, step_name) {
  job := job_by_name(workflow, job_name)
  step_names(job)[_] == step_name
}

deny[msg] {
  input.name == "CI"
  not job_exists_with_step(input, "policy", "Run OPA policies")
  msg := "CI workflow must include policy job with OPA enforcement"
}

deny[msg] {
  input.name == "Quality Gates"
  not job_exists_with_step(input, "policy-gate", "Run OPA policies")
  msg := "Quality Gates workflow must enforce OPA policies"
}
