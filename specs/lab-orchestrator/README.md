# Lab orchestrator specifications

The lab orchestrator turns trusted source events into durable gate runs,
arbitrates shared lab resources, optionally deploys exact firmware, launches
test-runner assignments, and publishes one aggregate parent gate.

It does not implement hardware test cases or duplicate their detailed evidence.
Each assignment delegates that work to `miner-test` and retains the resulting
child identifier/link. The runner is maintained in
[`mining-qa-testcode`](https://github.com/johnny9/mining-qa-testcode), and the
process boundary is defined by
[orchestration contract v1](../../contracts/orchestration-v1.md). See the
canonical [specification index](../INDEX.md).

Changes that cross this boundary must reconcile the related runner and
orchestrator specifications in both repositories.
