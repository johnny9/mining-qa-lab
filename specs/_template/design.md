# {{FEATURE_NAME}} — design

Describe durable responsibilities and constraints, not a line-by-line source
walkthrough.

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| `{{COMPONENT}}` | {{RESPONSIBILITY}} | `{{MODULE_PATH_SYMBOL_OR_DOCUMENT}}` |

## Interfaces and contracts

### CLI

- {{COMMAND_ARGUMENT_EXIT_STATUS_OR_NONE}}

### Configuration

- {{TOML_YAML_SCHEMA_DEFAULT_OR_NONE}}

### Environment

- {{VARIABLE_SECRET_BOUNDARY_OR_NONE}}

### Python API

- {{EXTENSION_POINT_DATA_MODEL_OR_NONE}}

### HTTP or external protocols

- {{REST_STRATUM_WEBSOCKET_SERIAL_GITHUB_OR_NONE}}

### Files, artifacts, payloads, and persistent state

- {{FILE_FORMAT_DATABASE_TABLE_RESULT_POINTER_OR_NONE}}

## Contract constraints

### Required invariants

- {{REQUIRED_BEHAVIOR}}

### Forbidden behavior

- {{BEHAVIOR_THAT_MUST_NEVER_OCCUR}}

## Data and state

- {{PERSISTED_TRANSIENT_OR_DEVICE_STATE}}
- {{OWNERSHIP_LIFETIME_CONSISTENCY_OR_CONCURRENCY_RULE}}

## Control and data flow

1. {{INPUT_OR_TRIGGER}}
2. {{PROCESSING_OR_STATE_TRANSITION}}
3. {{OUTPUT_OR_SIDE_EFFECT}}

## Failure and recovery

- {{FAILURE_MODE}} → {{DETECTION_CONTAINMENT_RECOVERY_AND_OBSERVABLE_RESULT}}

## Compatibility and migration

- {{VERSIONING_ROLLOUT_DATA_MIGRATION_HARDWARE_REVISION_OR_BACKWARD_COMPATIBILITY}}

## Resource and operational constraints

- {{LATENCY_THROUGHPUT_MEMORY_STORAGE_POWER_IMAGE_SIZE_OR_DEPLOYMENT_CONSTRAINT}}

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [{{FEATURE}}](../../{{AREA}}/{{SLUG}}/SPEC.md) | {{DEPENDENCY_OR_INTERACTION}} |

## Verification approach

- {{TEST_ANALYSIS_SIMULATION_BENCHMARK_DEPLOYMENT_OR_HARDWARE_STRATEGY}}
