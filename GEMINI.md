# LLM CONTEXT RULES

Always follow these guidelines to optimize API costs, token usage, and latency:

1. **Never send raw HTML** unless absolutely necessary.
2. **Never send an entire website/article collection** to one LLM request.
3. **Process one trend item** or a very small bounded batch at a time.
4. **Store structured results immediately** in the database.
5. **Use hashes** to avoid reprocessing unchanged content.
6. **Cache enrichment results**.
7. **Retrieve candidates from the DB** before invoking an LLM for reranking.
8. **Never send more than top-K candidates** to the reranker.
9. **Pass compact candidate representations**, not full article bodies.
10. **Keep generation and reranking separate**.
11. **Use structured JSON output** and Pydantic validation.
12. **Retry malformed JSON** at most once.
13. **Fail gracefully** rather than repeatedly calling the LLM.
14. **Never send the entire DB** into context.
15. **Never use the LLM to perform deterministic filtering** that SQL can perform.
16. **Never ask the LLM to calculate basic scores** that Python can calculate.
17. **Never ask the LLM to fabricate** missing evidence.
