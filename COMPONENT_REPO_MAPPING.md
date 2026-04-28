# RHOAI Component → Repository Mapping

## Overview

This document maps RHOAI/ODH components to their repositories for test coverage analysis. For comprehensive coverage, we analyze **BOTH upstream (opendatahub-io) and downstream (red-hat-data-services)** repositories when both exist.

**Source**: Architecture context from `architecture-context/architecture/rhoai-3.3/PLATFORM.md`

---

## Component Categories

### Platform Control Plane

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **rhods-operator** | ✅ red-hat-data-services/rhods-operator | ❌ N/A | Platform | Downstream only |
| **odh-dashboard** | red-hat-data-services/odh-dashboard | ✅ opendatahub-io/odh-dashboard | **AI Core Dashboard** | **Analyze upstream** |
| **kube-auth-proxy** | ✅ red-hat-data-services/kube-auth-proxy | ❌ N/A | Auth | Downstream only |

### Model Serving

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **kserve** | ✅ red-hat-data-services/kserve | ❓ opendatahub-io/kserve? | Model Serving | Check if upstream exists |
| **odh-model-controller** | red-hat-data-services/odh-model-controller | ✅ opendatahub-io/odh-model-controller | Model Serving | **Analyze upstream** |
| **openvino_model_server** | ✅ red-hat-data-services/openvino_model_server | ❌ N/A | Inference | Downstream only |
| **vllm-cpu** | ✅ red-hat-data-services/vllm-cpu | ❌ N/A | Inference | Downstream only |
| **vllm-gaudi** | ✅ red-hat-data-services/vllm-gaudi | ❌ N/A | Inference | Downstream only |
| **MLServer** | ✅ red-hat-data-services/MLServer | ❌ N/A | Inference | Downstream only |
| **llm-d-inference-scheduler** | ✅ red-hat-data-services/llm-d-inference-scheduler | ❌ N/A | Inference | Downstream only |
| **models-as-a-service** | ✅ red-hat-data-services/models-as-a-service | ❌ N/A | MaaS | Downstream only |

### Model Training

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **training-operator** | ✅ red-hat-data-services/training-operator | ❓ opendatahub-io/training-operator? | Distributed Workloads | Check if upstream exists |
| **trainer** | ✅ red-hat-data-services/trainer | ❌ N/A | Training | Downstream only |
| **distributed-workloads** | ✅ red-hat-data-services/distributed-workloads | ❌ N/A | Training Images | Downstream only |
| **kuberay** | red-hat-data-services/kuberay | ❌ ray-project/kuberay | Ray | **True upstream: ray-project** |

### AI Pipelines

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **data-science-pipelines-operator** | ✅ red-hat-data-services/data-science-pipelines-operator | ❓ opendatahub-io/data-science-pipelines-operator? | Pipelines | Check if upstream exists |
| **data-science-pipelines** | ✅ red-hat-data-services/data-science-pipelines | ❓ opendatahub-io/data-science-pipelines? | Pipelines | Check if upstream exists |
| **argo-workflows** | ✅ red-hat-data-services/argo-workflows | ❌ N/A | Pipelines | Downstream only |
| **ml-metadata** | ✅ red-hat-data-services/ml-metadata | ❌ N/A | Metadata | Downstream only |

### Model Registry & Catalog

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **model-registry-operator** | ✅ red-hat-data-services/model-registry-operator | ✅ opendatahub-io/model-registry-operator | **AI Hub** | **Analyze both** |
| **model-registry** | red-hat-data-services/model-registry | ✅ opendatahub-io/model-registry | **AI Hub** | **Analyze upstream** |
| **model-metadata-collection** | red-hat-data-services/model-metadata-collection | ✅ opendatahub-io/model-metadata-collection | **AI Hub** | **Analyze upstream** |

### Experiment Tracking & Feature Store

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **mlflow** | ✅ red-hat-data-services/mlflow | ❌ N/A | MLflow | Downstream only |
| **mlflow-operator** | ✅ red-hat-data-services/mlflow-operator | ❌ N/A | MLflow | Downstream only |
| **feast** | ✅ red-hat-data-services/feast | ❓ opendatahub-io/feast? | Feature Store | Check if upstream exists |

### AI Safety & Trustworthiness

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **trustyai-service-operator** | ✅ red-hat-data-services/trustyai-service-operator | ❓ opendatahub-io/trustyai-service-operator? | TrustyAI | Check if upstream exists |
| **trustyai-explainability** | ✅ red-hat-data-services/trustyai-explainability | ❌ N/A | TrustyAI | Downstream only |
| **fms-guardrails-orchestrator** | ✅ red-hat-data-services/fms-guardrails-orchestrator | ❌ N/A | Guardrails | Downstream only |
| **guardrails-detectors** | ✅ red-hat-data-services/guardrails-detectors | ❌ N/A | Guardrails | Downstream only |
| **guardrails-regex-detector** | ✅ red-hat-data-services/guardrails-regex-detector | ❌ N/A | Guardrails | Downstream only |
| **NeMo-Guardrails** | ✅ red-hat-data-services/NeMo-Guardrails | ❌ N/A | Guardrails | Downstream only |
| **vllm-orchestrator-gateway** | ✅ red-hat-data-services/vllm-orchestrator-gateway | ❌ N/A | Guardrails | Downstream only |
| **lm-evaluation-harness** | ✅ red-hat-data-services/lm-evaluation-harness | ❌ N/A | Evaluation | Downstream only |

### Llama Stack

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **llama-stack-k8s-operator** | ✅ red-hat-data-services/llama-stack-k8s-operator | ❌ N/A | LlamaStack | Downstream only |
| **llama-stack-distribution** | ✅ red-hat-data-services/llama-stack-distribution | ❌ N/A | LlamaStack | Downstream only |
| **llama-stack-provider-ragas** | ✅ red-hat-data-services/llama-stack-provider-ragas | ❌ N/A | LlamaStack | Downstream only |
| **llama-stack-provider-trustyai-garak** | ✅ red-hat-data-services/llama-stack-provider-trustyai-garak | ❌ N/A | LlamaStack | Downstream only |

### Workbenches

| Component | Downstream (RHOAI) | Upstream (ODH) | Jira Component | Notes |
|-----------|-------------------|----------------|----------------|-------|
| **kubeflow** (notebook-controller) | ✅ red-hat-data-services/kubeflow | ❓ opendatahub-io/kubeflow? | Workbenches | Check if upstream exists |
| **notebooks** | red-hat-data-services/notebooks | ✅ opendatahub-io/notebooks | **Workbenches** | **Analyze upstream** |

### External Upstream (Not ODH/RHOAI)

| Component | Repository | Jira Component | Notes |
|-----------|-----------|----------------|-------|
| **kuberay** | ✅ ray-project/kuberay | Ray | True upstream from Ray project |
| **kueue** | ✅ kubernetes-sigs/kueue | Queueing | True upstream from k8s-sigs |

---

## Repository Status in qualityTigerTeam/

### Already Cloned (Upstream)

- ✅ opendatahub-io/odh-dashboard
- ✅ opendatahub-io/notebooks
- ✅ opendatahub-io/odh-model-controller
- ✅ opendatahub-io/model-registry
- ✅ opendatahub-io/model-metadata-collection
- ✅ opendatahub-io/codeflare-operator
- ✅ opendatahub-io/architecture-context

### Already Cloned (Downstream)

- ✅ red-hat-data-services/data-science-pipelines-operator
- ✅ red-hat-data-services/kserve
- ✅ red-hat-data-services/feast
- ✅ red-hat-data-services/model-registry-operator
- ✅ red-hat-data-services/training-operator
- ✅ red-hat-data-services/trustyai-service-operator
- ✅ red-hat-data-services/rhods-operator
- ✅ red-hat-data-services/llama-stack-k8s-operator
- ✅ red-hat-data-services/mlflow-operator
- ✅ red-hat-data-services/spark-operator
- ✅ red-hat-data-services/models-as-a-service
- ✅ red-hat-data-services/trainer

### Already Cloned (External Upstream)

- ✅ ray-project/kuberay
- ✅ kubernetes-sigs/kueue

---

## Test Coverage Analysis Strategy

### Priority 1: Components with Both Upstream & Downstream

For comprehensive coverage, analyze **BOTH** repositories:

1. **odh-dashboard**
   - Upstream: `opendatahub-io/odh-dashboard` ⭐
   - Downstream: `red-hat-data-services/odh-dashboard`
   - Jira: "AI Core Dashboard"

2. **model-registry** (AI Hub)
   - Upstream: `opendatahub-io/model-registry` ⭐
   - Upstream: `opendatahub-io/model-metadata-collection` ⭐
   - Downstream: `red-hat-data-services/model-registry-operator` ✅ cloned

3. **notebooks**
   - Upstream: `opendatahub-io/notebooks` ⭐
   - Downstream: `red-hat-data-services/notebooks`
   - Jira: "Workbenches"

4. **odh-model-controller**
   - Upstream: `opendatahub-io/odh-model-controller` ⭐
   - Downstream: `red-hat-data-services/odh-model-controller`
   - Jira: "Model Serving"

### Priority 2: Downstream-Only Components

Analyze downstream repositories:

- rhods-operator
- kube-auth-proxy
- training-operator
- data-science-pipelines-operator
- kserve
- trustyai-service-operator
- All inference runtimes (vllm, OVMS, MLServer, etc.)
- All LlamaStack components
- All guardrails components

### Priority 3: External Upstream

Analyze external upstream repositories:

- ray-project/kuberay
- kubernetes-sigs/kueue

---

## Next Steps for Test Coverage

1. **Verify which components need upstream cloning**:
   - Check if opendatahub-io versions exist for: kserve, training-operator, data-science-pipelines, feast, kubeflow, trustyai
   
2. **Run historical bug coverage on all Model Registry repos**:
   - opendatahub-io/model-registry
   - opendatahub-io/model-metadata-collection  
   - red-hat-data-services/model-registry-operator (already analyzed - WRONG one)

3. **Set up Jira credentials** to enable analysis

4. **Create aggregated coverage reports** combining upstream + downstream results

---

## Jira Component → Repository Mapping (Known)

| Jira Component | Repositories to Analyze |
|----------------|------------------------|
| **AI Core Dashboard** | opendatahub-io/odh-dashboard |
| **AI Hub** (Model Registry) | opendatahub-io/model-registry + opendatahub-io/model-metadata-collection + opendatahub-io/model-registry-operator |
| **Workbenches** | opendatahub-io/notebooks |
| **Model Serving** | opendatahub-io/odh-model-controller + red-hat-data-services/kserve |
| **Distributed Workloads** | opendatahub-io/codeflare-operator + red-hat-data-services/training-operator + ray-project/kuberay |

---

*Generated: 2026-04-14*
*Source: architecture-context/architecture/rhoai-3.3/PLATFORM.md*
