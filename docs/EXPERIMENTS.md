# Experiment plan and release gates

Prepared 2026-10-28. These are proposed steps, not completed experiments or time guarantees.

## Completed baseline

An offline task pack, deterministic environment, state-based grader, two scripted retry controllers, and trace replay. See `results/demo.json` for the complete artifact and dataset hash. Counts are 12 independent scenarios and 24 translated task variants. No model has been evaluated.

## First live experiment

1. Choose a provider, model configuration, and total spending limit with the user. Any OpenAI API access must follow the credential-selection workflow before API-dependent implementation.
2. Connect a host-owned tool dispatcher to an existing runner where practical. Give the agent instructions, the public slot catalogue, tool schemas, and observations; withhold structured requests, fault schedules, and gold state.
3. Freeze the dataset hash and tool contract. Use the same case set, call budget, reasoning settings where comparable, and run conditions for each system. Record provider-specific differences rather than implying perfect equivalence.
4. Start with one model and two instruction/tool-use strategies. Run each translated task at least five times (120 runs per configuration). This is an initial diagnostic design, not proof that the sample is statistically sufficient. Treat translations as paired variants, not independent cases.
5. Record final-state success, extra/missing bookings, unrelated changes, correctly reported outcomes, tool calls, actual provider usage, wall-clock timing, configuration, errors, and reproducible run IDs. Separate provider timeouts, harness errors, and task failures.
6. Inspect every failure manually. Calibrate a subset of accepted traces too, to look for false positives. Use scenario-clustered analysis if calculating uncertainty; do not claim general Japanese-language capability from twelve scenarios.

## Before a public model comparison

- Verify agent-visible observations do not include expected answers or fault phase.
- Add human-reviewed task variants without structured-request shortcuts; consider datetime changes, clarification, and corrections only after the baseline is stable.
- Preserve repeated runs and unsuccessful attempts. Fix grader errors and re-run affected comparisons rather than quietly deleting failures.
- Include the exact model version, actual usage, cost assumptions with date/currency, raw traces with secrets removed, and limitations.
- Pin the runner/dependencies. Confirm dataset licenses if integrating third-party tasks. The current fixtures are original and synthetic.

## Publication package

Public repository: [masaakisakamoto/stateful-tool-lab](https://github.com/masaakisakamoto/stateful-tool-lab), created 2026-10-29. The initial source snapshot contains code, task pack, English/Japanese README, research notes, and raw offline results. Hosted validation is recorded in Actions. A short failure walkthrough, screen recording, and live-model experiment remain next milestones before presenting the work as a mature AI engineering portfolio entry.

## Longer-term portfolio

Keep the first project narrow until a reproducible result and failure analysis exist. Then choose one complementary axis: Japanese voice-agent regression, local structured generation on Apple Silicon, or evidence-linked document extraction. Recheck primary sources and competition before choosing that next project.
