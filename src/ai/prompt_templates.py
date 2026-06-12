"""
Reusable prompt templates for Gemini-powered retail insights.

Templates separate system instructions from user payloads so prompts can be
versioned, tested, and extended without changing client or generator logic.
"""

from __future__ import annotations

from string import Template

# System instruction: sets tone and output format for all insight requests.
EXECUTIVE_SUMMARY_SYSTEM_PROMPT = """\
You are a senior retail analytics consultant writing for C-level executives
and business stakeholders. Your audience cares about revenue impact, customer
loyalty, and actionable merchandising decisions — not technical jargon.

Guidelines:
- Write in clear, concise business language.
- Lead with the most important finding in each section.
- Quantify claims using the KPI data provided (percentages, counts, rankings).
- End with 3–5 specific, actionable business recommendations.
- Do not invent data not present in the KPI summary.
- Do not mention Spark, Parquet, pipelines, or internal tooling.
"""

# User prompt: injects structured KPI summary as JSON/text.
EXECUTIVE_SUMMARY_USER_TEMPLATE = Template(
    """\
Analyze the following Instacart retail gold-layer KPI summary and produce an
executive insights report.

=== KPI SUMMARY ===
$kpi_summary

=== REQUIRED SECTIONS ===
Write each section as a short paragraph (3–5 sentences). Use the exact headers below.

## Executive Summary
High-level overview of overall retail performance and the single most important insight.

## Top Performing Products
Which products drive the most order volume? What does reorder behavior suggest?

## Most Reordered Products
Which products show the strongest customer loyalty and repeat-purchase signals?

## Best Performing Departments
Which departments lead in sales volume and customer reach?

## Customer Purchasing Trends
What patterns emerge in order frequency, basket composition, and customer behavior?

## Basket Size Analysis
What does average basket size and distribution tell us about shopping behavior?

## Key Business Recommendations
Provide 3–5 numbered, specific recommendations for merchandising, marketing,
or inventory strategy based solely on the data above.
"""
)

# Focused template for regenerating a single section (extensibility / retries).
SECTION_REGENERATION_TEMPLATE = Template(
    """\
Using only the KPI data below, write the "$section_title" section for a retail
executive report. Keep it to 3–5 sentences. Do not invent data.

=== KPI SUMMARY ===
$kpi_summary
"""
)

# Short prompt used to validate API connectivity during pipeline startup.
HEALTH_CHECK_PROMPT = (
    "Reply with exactly: OK — retail analytics insights engine ready."
)
