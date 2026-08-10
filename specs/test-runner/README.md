# Test runner specifications

The test runner owns one hardware-test invocation from validated configuration
through cleanup, evidence capture, and child-result publication. It may be run
directly by an operator or as an assignment launched by the lab orchestrator.

The runner does not schedule the lab, arbitrate shared devices, deploy a build
for an entire gate, or publish the aggregate parent gate. See the canonical
[specification index](../INDEX.md) for its feature slices and lifecycle state.

When a runner feature changes, reconcile the feature's five documents and any
related orchestrator contract before checking acceptance evidence.
