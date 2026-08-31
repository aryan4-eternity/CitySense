"""
planning/
=========
Phase 3 – Urban Planning Intelligence & Decision Engine for CitySense.

Modules
-------
intervention_catalog.yaml   Data-driven knowledge base (edit to add interventions).
knowledge_base              Loads the catalog; resolves single/multi-condition lookups.
priority_engine             Priority Score (0–100) and Priority Label per cell.
intervention_engine         Intervention selection and confidence scoring.
planning_summary            Assembles the final Planning Profile dict.
decision_engine             Top-level orchestrator; runs all modules over the dataset.
generate_planning_profiles  Pipeline stage; writes data/planning_profiles.json.
"""
