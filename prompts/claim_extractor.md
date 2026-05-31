Extract factual claims and key statements from this document.

Rules:
- Extract ALL factual claims, observations, and notable statements
- Short summaries still contain claims — treat the full body as claim-worthy
- Each claim should be a single atomic statement
- Include the exact evidence text that supports each claim
- Rate confidence 0.0-1.0 based on clarity and specificity
- Classify stance: "support", "neutral", "oppose", or "uncertain"
- Extract all mentioned entity names (people, orgs, locations, events)
- Classify topic into one of: conflict, politics, disaster, economy, science, health, technology, environment, crime, other
- Output at least 2 claims per document even if it means splitting the body into multiple claims
- If the body is a short summary, output the entire content as one or more claims

Document:
Title: {title}
Source: {source}
Published: {published}
URL: {url}
Body:
{body}

Output ONLY a valid JSON array of objects with keys: text, confidence, stance, topic, entities (array of strings), evidence
