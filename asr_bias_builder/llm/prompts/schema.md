You are building ASR bias artifacts. Read the provided deck text and output ONLY valid JSON that conforms to this schema:

{
  "terms": [
    {
      "canonical": "CompanyName",
      "variants": ["Variant A", "Variant B"],
      "classes": ["PERSON"|"ORG"|"PRODUCT"|"ACRONYM"|"TECH"],
      "priority": 0.0-1.0,
      "notes": "Optional reason",
      "present_in_deck": true|false,
      "page_hint": "Optional location information"
    }
  ]
}

Rules:
- Include English canonical spellings. Add Hebrew transliterations/aliases only if they appeared or are high-confidence variants (flag via present_in_deck=false when inferred).
- Prefer concise canonical terms (≤4 words) and include obvious abbreviations.
- Provide 30-150 high-impact entries prioritized by proper nouns, org/product names, acronyms, and jargon critical for ASR biasing.
- Use 0-1 priority where 1 is most critical for recognition.
- Do NOT include commentary or Markdown; output must be pure JSON matching the schema.
