# Metrics Framework

## 1. Methodology
- Use fixed message snapshots for repeatability.
- Run each benchmark scenario three times.
- Report median value and note min/max.
- Keep environment constant: Python version, model name, machine.

## 2. Core Metrics
### Testing Quality Metrics
- Pass Rate = passed / executed
- Fail Rate = failed / executed
- Blocked Rate = blocked / planned
- Defect Density = defects / tested feature count

### Accuracy Metrics
- Event Extraction Precision = TP / (TP + FP)
- Event Extraction Recall = TP / (TP + FN)
- Event Extraction F1 = 2PR / (P + R)
- Priority Agreement = matching labels / total labeled samples

### Performance Metrics
- Startup time (seconds)
- Sync latency (seconds)
- Summary generation median latency (seconds/message)
- Throughput (messages/minute)
- Timeout/Error rate (%)

## 3. Reporting Standards
- Always include timestamp and environment metadata.
- Record raw values before aggregation.
- Keep qualitative findings separate from quantitative metrics.

## 4. Comparison Strategy
- Baseline: deterministic extraction only.
- Candidate: hybrid extraction (deterministic + LLM fallback).
- Report deltas for precision, recall, and runtime.
