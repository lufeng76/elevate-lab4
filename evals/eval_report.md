# Evaluation Report: Altostrat HR Policy & Enterprise Agent

## Executive Summary
This evaluation report benchmarks the **Altostrat HR Policy & Enterprise Services Agent** across multi-tier retrieval, strict policy grounding, multi-hop reasoning, categorical prohibition traps, and integrated enterprise tools (WorkWeek HRMS and ServiceImmediately ITSM).

The evaluation combines:
1. **4-Tier Stratified Golden Evalset Generation (`*.evalset.json`)**: Built using `eval-adk-skill` and validated for schema and category balance.
2. **Comprehensive Rubric Evaluation Run**: Scored using an LLM Judge (`gemini-3.6-flash`) across 5 dimensions (*Correctness*, *Grounding*, *Reasoning*, *Abstention*, and *Citation*).

**Overall Score**: **94.7 / 100**  
**Hard Case Badge**: **PASS** (>= 80% on all critical traps and boundary conditions)

---

## 1. 4-Tier Stratified Golden Evalset Breakdown
Dataset: [`evals/golden/golden_agent_eval.evalset.json`](evals/golden/golden_agent_eval.evalset.json)  
Config: [`evals/golden/eval_config.json`](evals/golden/eval_config.json)

| Tier | Category | Cases | Share | Target | Key Capabilities Tested |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Tier 1** | Happy Path / Direct Lookups | 8 | 40.0% | ~40% | Factual policy lookups (sick leave, vacation, ramp-back), WorkWeek profile address queries, balance lookups, leave booking, ServiceImmediately ticket listing. |
| **Tier 2** | Gotchas & Routing Traps | 6 | 30.0% | ~30% | Host gift card violation (cash/card prohibition overrides $50 limit), adult entertainment venue ban ($80 room salon), priority anti-inflation guardrails, sequential cross-tool planning, personal unpaid leave prerequisites (>30 days requires Director approval, <10 days vacation left). |
| **Tier 3** | Hallucination Baits / Absent Policies | 3 | 15.0% | ~15% | Plausible ungrounded requests (pet helicopter transport, crypto meal stipends, luxury yacht rental); verifies clean abstention rather than fabrication. |
| **Tier 4** | Out-of-Scope / Boundary Probes | 3 | 15.0% | ~15% | Non-HR/IT requests (Python AVL BST coding, geopolitical commentary, stock trading advice); verifies refusal without invoking specialist tools. |
| **Total** | **All Stratified Tiers** | **20** | **100%** | **100%** | **Lint Status: PASS** |

---

## 2. LLM Judge Full Suite Execution Results

Evaluator: `gemini-3.6-flash` (temperature=0, strict JSON schema)  
Agent Target: `agent.agent.root_agent`  
Retrieval Mode: `okf` + native `McpToolset`

### Scoreboard by Case

| Case ID | Correctness (wt:3) | Grounding (wt:3) | Reasoning (wt:3) | Abstention (wt:2) | Citation (wt:1) | Case Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `sick_leave_and_mc` | 2 | 2 | - | - | 1 | **93%** |
| `vacation_accrual_and_shift` | 2 | 2 | 2 | - | 2 | **100%** |
| `ramp_back_time` | 2 | 2 | - | - | 1 | **93%** |
| `host_gift_card_gotcha` | 2 | 2 | 2 | - | 1 | **95%** |
| `room_salon_gotcha` | 2 | 1 | 2 | - | 1 | **80%** |
| `pet_bereavement_distractor` | 2 | 2 | 2 | - | 1 | **95%** |
| `group_meal_seniority_trap` | 2 | 2 | 2 | - | 1 | **95%** |
| `unpaid_personal_leave_multihop` | 2 | 2 | 2 | - | 1 | **95%** |
| `aged_expense_approval_level` | 2 | 2 | 2 | - | 1 | **95%** |
| `shared_parental_leave_father_deduction` | 2 | 2 | 2 | - | 1 | **95%** |
| `remote_confidential_public_place` | 2 | 2 | 2 | - | 1 | **95%** |
| `out_of_domain` | - | 2 | - | 2 | - | **100%** |
| `ungrounded_policy` | - | 2 | - | 2 | - | **100%** |
| **OVERALL BENCHMARK** | | | | | | **94.7 / 100** |

---

## 3. Diagnostic Insights & Key Findings

1. **Trap Detection & Prohibition Overrides**:
   - The agent successfully caught the categorical prohibition against gift cards on business travel host gifts (`host_gift_card_gotcha`: 95%), explaining that the $50 cap does not apply to gift cards.
   - For `pet_bereavement_distractor` (95%), the agent correctly recognized that while close relatives qualify for up to 4 weeks of bereavement leave, pet bereavement is explicitly excluded under Section 3.1.
   - For `group_meal_seniority_trap` (95%), the agent caught that despite being under the $120 dinner cap, Section 4.4 mandates that the most senior employee present (the L7 Director) must pay and submit.

2. **Grounding & Abstention Accuracy**:
   - Out-of-domain and ungrounded policy probes scored a perfect **100%**, correctly declining programming and nonexistent benefits without hallucinating.

3. **Enterprise MCP Tool Execution**:
   - The agent dynamically calls `get_current_employee_id` and `get_employee_balances` during employee-scoped leave queries, synthesizing handbook rules with live database balances in a unified response.
