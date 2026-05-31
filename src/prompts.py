"""Prompt management — load prompts from files with compiled-in fallbacks."""

from pathlib import Path


FALLBACKS: dict[str, str] = {
    "broadcast_writer": """You are objective03, a synthetic news analysis broadcast. Write in a cold, analytical tone for TTS output.

You MUST split your response into two parts:
1. <think>your internal analysis and reasoning</think> — think through the news first.
2. Then output the broadcast content. This is the most important part.

IMPORTANT: The broadcast content comes AFTER </think>. Do NOT end after </think>. The think block is just your internal reasoning — you MUST still write the full 800-1200 word broadcast.

Rules for the broadcast content:
- Use natural spoken language. Spell out numbers under 20.
- Expand abbreviations on first use (e.g. "Department of Defense" not "DoD").
- Avoid symbols %, &, $ — write as "percent", "and", "dollars".
- Use paragraph breaks for natural pauses.
- NEVER include stage directions, sound effects, or bracketed text like "[music]" or "[pause]".
- NEVER output error messages, tracebacks, or internal diagnostics — only broadcast prose.
- Output ONLY the spoken broadcast text after </think>. No metadata.

Structure (800-1200 words):
1. Opening — establish the current news landscape and key themes.
2. Top stories — 3-5 sentences per event. Cite specific claims, sources, and evidence.
3. Contradictions & uncertainty — highlight conflicting information across sources.
4. Narrative analysis — how framing has shifted or consolidated.
5. Closing statement that ties back to the opening.""",
    "claim_extractor": """Extract factual claims and key statements from this document.

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

Output ONLY a valid JSON array of objects with keys: text, confidence, stance, topic, entities (array of strings), evidence""",
    "entity_extractor": """Extract named entities from this text. For each entity, provide: name, type (person/organization/location/event/concept), and confidence.

Text: {text}

Output JSON array:
[{{"name": "...", "type": "...", "confidence": 0.95}}]""",
    "contradiction_detector": """Analyze if these two claims contradict each other.

Claim A: "{text_a}" (topic: {topic_a}, stance: {stance_a})
Claim B: "{text_b}" (topic: {topic_b}, stance: {stance_b})

Choose classification:
- DIRECT_CONTRADICTION: Opposite facts, cannot both be true
- NUMERICAL_DISCREPANCY: Different numbers/statistics
- FRAMING_DIFFERENCE: Different framing of same facts
- TEMPORAL_DISCREPANCY: Different timing claims
- COMPATIBLE: Both can be true simultaneously
- UNCERTAIN: Insufficient information

Output JSON: {{"type": "DIRECT_CONTRADICTION", "strength": 0.9, "reasoning": "..."}}""",
    "framing_analyzer": """Classify the framing of this news claim into one: positive, negative, neutral, alarmist, dismissive, analytical.

Claim: {text}
Framing:""",
    "narrative_analyzer": """Generate a concise label for this narrative thread (5 words max):
{texts}
Label:""",
}


def load_prompt(agent_name: str, prompts_dir: str | Path) -> str:
    """Load a prompt from file, falling back to compiled-in default."""
    path = Path(prompts_dir) / f"{agent_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return FALLBACKS.get(agent_name, "")
