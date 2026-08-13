# Metrics glossary

| Metric | Definition |
|--------|------------|
| **MRR** | Sum of active subscription monthly recurring revenue, in dollars, at the account × month grain. |
| **MRR movement** | Each account-month classified vs the prior month: `new`, `expansion`, `contraction`, `churn`, `retained`. |
| **Gross Revenue Retention (GRR)** | Retained MRR ÷ starting MRR, with expansion capped at the prior amount. Range [0, 1]. |
| **Net Revenue Retention (NRR)** | Current MRR ÷ starting MRR for the prior-month cohort, including expansion. Can exceed 1. |
| **Feature adoption** | Distinct events per account per feature, with first/last used dates. |
| **Account health score** | Composite 0–100: usage volume (0–50) + support penalty (0–30) + paying status (0–20). |

All definitions live in code (dbt models) and are mirrored in
`text_to_metric/semantic_layer.yml` so the AI layer can only reference governed
metrics.