# Sprint 2

Sprint 2 extended the offline MVP into a live search and retrieve workflow.

## Goal

Find current papers from live sources, normalize them, rank them transparently,
store the research run, and export the result.

## Implemented Scope

- arXiv live search
- Semantic Scholar fallback
- Local cache fallback
- Embedded demo-data fallback
- Metadata normalization
- Deduplication by stable IDs
- Transparent ranking based on title, abstract, topic relevance, and recency
- Memory storage
- Markdown export

## Demo Value

Sprint 2 demonstrates that the agent can retrieve real papers while remaining
stable when APIs are unavailable.
