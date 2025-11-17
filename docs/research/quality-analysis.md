# Output Quality Analysis: ASR Bias Artifacts Pipeline
**Date:** November 17, 2025  
**Test Deck:** `examples/basic/sample_deck.pdf`  
**Status:** ⚠️ **NEEDS MAJOR IMPROVEMENTS**

---

## Executive Summary

The pipeline successfully ran end-to-end (74 seconds), but the output quality is **severely degraded** by noise pollution. While the LLM extracted 77 high-quality terms, the final artifacts contain **thousands of low-value entries** dominated by:
- Stop words ("All", "Also", "The", "This")
- Raw numbers ("2025", "23", "06", "03")
- UI detritus (Slack IDs, file paths, code snippets)
- OCR errors ("Liam Nguyn", "Dyson Spher", "Dyson Sphere Al")

**Root cause:** The deterministic seed mining stage is flooding the pipeline with garbage that overwhelms the LLM's curated output.

---

## Output Files Analysis

### ✅ LLM Output Quality: EXCELLENT

**File:** `out/lmm_candidates.json`  
**Count:** 77 terms  
**Quality:** ⭐⭐⭐⭐⭐ (5/5)

Claude extracted **exactly the right terms** with proper classification:

**Top 10 LLM terms:**
1. ✅ Dyson Sphere AI (ORG/PRODUCT, priority 1.0)
2. ✅ Dyson Sphere (PRODUCT, priority 0.95)
3. ✅ Dr. Liam Nguyen (PERSON, priority 0.9)
4. ✅ Sakshi Gupta (PERSON, priority 0.9)
5. ✅ Dr. Amelia Hawking (PERSON, priority 0.88)
6. ✅ Samantha Zhao (PERSON, priority 0.85)
7. ✅ Elon Jatinder (PERSON, priority 0.85)
8. ✅ AI Compute Infrastructure (TECH, priority 0.82)
9. ✅ Solar Collectors (TECH, priority 0.8)
10. ✅ Advanced Thermal Management (TECH, priority 0.78)

**LLM did its job perfectly:** Names, products, companies, technical terms—all properly identified with context and priority.

---

### ❌ Seed Mining Output: POLLUTED

**File:** `out/seeds.json`  
**Count:** 2,333 terms  
**Quality:** ⭐ (1/5)

The deterministic extraction is producing **30x more terms** than the LLM, and most are garbage:

**Top 10 seed terms by frequency:**
1. ❌ "2025" (27 occurrences) - Year from copyright footer
2. ❌ "All" (20) - Stop word from "All rights reserved"
3. ⚠️ "Dyson Sphere Al" (19) - OCR error (should be "Dyson Sphere AI")
4. ❌ "Confidential" (19) - Legal boilerplate
5. ❌ "23" (19) - Issue number from Slack screenshot
6. ✅ "Dyson Sphere" (16) - Legitimate
7. ❌ "PM" (15) - Slack timestamp
8. ✅ "SWE" (12) - Legitimate
9. ✅ "Engineering Manager" (8) - Legitimate
10. ❌ "Also" (8) - Stop word

**Noise ratio:** ~70% of top seeds are garbage.

**Categories of pollution:**

| Category | Examples | Count (est.) | Impact |
|----------|----------|--------------|--------|
| Stop words | All, Also, The, This, See, No, Just, It, On, Last | ~200 | High |
| Numbers | 2025, 23, 06, 03, 21, 2024, 20, 00, 33, 950, 742, 714 | ~300 | High |
| Legal boilerplate | Confidential, proprietary, Linked slide | ~50 | Medium |
| Slack UI | PM (timestamp), Thread, Messages, Reply, Unread, Today | ~100 | High |
| Code artifacts | globals(), parser.py, dangerous-globals-use, virtualenv | ~150 | Medium |
| Slack IDs | U/C090CHWCT89, T08SQ3GKIJAU, demo1-sampledeck_23 | ~50 | Low |
| OCR errors | Liam Nguyn, Dyson Spher, Dyson Sphere Al, Aa, nonma | ~100 | High |
| Generic terms | Add, Prepare, Preparing, Check, See | ~200 | Medium |

**Total garbage estimate:** ~1,150 out of 2,333 terms (49%)

---

### ❌ Final Artifacts: DILUTED

#### `out/deck_terms.txt` (Whisper prompt)
**Count:** 121 terms  
**Quality:** ⭐⭐ (2/5)

**Good terms (top ~30):**
```
Dyson Sphere, AI Compute, Solar Collectors, Integrated Energy Storage, 
Autonomous Maintenance, Advanced Thermal Management, Dr. Liam Nguyen, 
Sakshi Gupta, Dr. Amelia Hawking, Samantha Zhao, Elon Jatinder
```

**Garbage terms (next ~90):**
```
All, Also, The, This, See, Reply, 2025, 23, 06, 03, 21, 2024,
PM, globals(), dangerous-globals-use, parser.py, demo1-sampledeck_23,
Liam Nguyn, Dyson Spher, Dyson Sphere Al, Aa, Thread, Messages, Add, Preparing
```

**Problem:** 
- Top 30 terms are good (from LLM)
- Next 90 are noise (from seeds overwhelming LLM priority)
- Whisper will mostly see the noise in its ~224 token window

#### `out/phrase_set.json` (Google STT)
**Count:** 1,452 phrases  
**Quality:** ⭐ (1/5)

**Issue:** Same terms as `deck_terms.txt` but **no filtering at all**—just dumps everything with boost=8.0.

**Problems:**
1. **Scale:** 1,452 phrases is excessive; Google recommends <1000 for performance
2. **Noise ratio:** ~70% garbage (stop words, numbers, code, Slack UI)
3. **No differentiation:** Everything gets boost=8.0 regardless of value
4. **OCR pollution:** Multiple variants of same term (Dyson Sphere/Dyson Spher/Dyson Sphere Al) get separate entries

---

## Root Cause Analysis

### Problem 1: Seed Mining Has No Quality Filters

**Current behavior:**
```python
# mine_terms.py extracts EVERYTHING matching patterns:
- Proper-Case multiwords → "All", "Also", "Reply" ✅ but also stop words
- ALLCAPS → "PM", "APP" ✅ but also timestamps
- Numbers with context → "2025", "23" ❌ always noise
```

**Missing filters:**
1. ❌ No stop word list (English common words)
2. ❌ No numeric filtering (standalone numbers)
3. ❌ No minimum length requirements
4. ❌ No part-of-speech validation (keep only nouns, proper nouns)
5. ❌ No semantic filtering (is this a meaningful term?)

### Problem 2: Seeds Overwhelm LLM Priority

**Current merging logic:**
```python
# verify_terms.py merges seeds + LLM but doesn't properly prioritize
score = (llm_priority * 0.6) + (frequency_score * 0.4)
```

**Problem:**
- High-frequency noise ("2025" appears 27×, "All" appears 20×)
- Gets scored higher than low-frequency but valuable LLM terms
- LLM priority (0-1.0) gets diluted by raw frequency

**Example:**
- "2025" (seed only, freq=27) → score = 0.4 × 0.9 = **0.36**
- "Autonomous Maintenance" (LLM priority=0.75, freq=2) → score = 0.75 × 0.6 + 0.05 × 0.4 = **0.47**

But then sorting by (source, score) puts seed+llm terms first, so high-freq garbage from seeds pushes out low-freq LLM terms.

### Problem 3: No OCR Normalization

**Current behavior:**
```
"Dyson Sphere" (16×)
"Dyson Sphere Al" (19×)  ← OCR error: "AI" → "Al"
"Dyson Spher" (appears in text)  ← OCR error: "i" → "l"
"Liam Nguyn" (appears)  ← OCR error: "i" → "l"
```

**All become separate terms** instead of being normalized to canonical forms.

### Problem 4: Artifact Builders Don't Filter

**Current behavior:**
```python
# build_prompt_list.py
- Takes top N terms by score
- No filtering for quality, no class restrictions
- Result: includes stop words, numbers, code snippets

# build_phrase_set.py  
- Takes ALL verified terms (no limit!)
- Applies same boost=8.0 to everything
- Result: 1,452 phrases, mostly garbage
```

---

## Impact on ASR Systems

### Whisper Impact: MEDIUM-HIGH

**Issue:** Whisper's `initial_prompt` effectively uses ~last 224 tokens
- With 121 terms, only ~40-60 will be "seen"
- Current list has good terms at top but noise in middle
- **Actual impact:** ~50% of effective prompt window wasted on garbage

**Example of wasted tokens:**
```
... globals(), dangerous-globals-use, parser.py, demo1-sampledeck_23,
Liam Nguyn, Dyson Spher, Thread, Messages, 2025, 23, PM ...
```

### Google STT Impact: HIGH

**Issue:** 1,452 phrases with uniform boost=8.0
- Google recommends <1000 phrases for performance
- Noise phrases compete with legitimate terms for recognition
- **Actual impact:** Dilutes the bias signal, may slow recognition

**What happens:**
- ASR system tries to boost "All", "Also", "The" alongside "Dyson Sphere", "Liam Nguyen"
- Generic words get false positive boosts in transcription
- Real terms don't get sufficient differentiation

---

## Recommendations for Dramatic Improvement

### 🎯 Priority 1: Add Stop Word Filtering (CRITICAL)

**Implementation:**
```python
# Add to mine_terms.py
STOP_WORDS = {
    "all", "also", "the", "this", "that", "these", "those",
    "see", "reply", "add", "today", "last", "just", "it",
    "on", "no", "end", "check", "prepare", "preparing",
    # ... comprehensive English stop word list
}

def is_stopword(term: str) -> bool:
    return term.lower() in STOP_WORDS
```

**Expected impact:** Removes ~200 garbage terms (9% reduction)

---

### 🎯 Priority 2: Filter Raw Numbers and Dates (CRITICAL)

**Implementation:**
```python
# Add to mine_terms.py
import re

def is_standalone_number(term: str) -> bool:
    """Reject pure numbers, years, dates."""
    # Reject: "2025", "23", "06", "03", "2024", "20-30"
    # Keep: "C#", "V3", "SOC2" (alphanumeric)
    return bool(re.fullmatch(r'\d+|\d{4}|\d{2}[-/]\d{2}', term))
```

**Expected impact:** Removes ~300 garbage terms (13% reduction)

---

### 🎯 Priority 3: OCR Error Normalization (HIGH)

**Implementation:**
```python
# Add to verify_terms.py
import unicodedata
from difflib import SequenceMatcher

def normalize_ocr(term: str) -> str:
    """Fix common OCR errors."""
    # Common OCR substitutions
    fixes = {
        'Al': 'AI',   # lowercase L → I
        'l': 'I',     # in certain contexts
        'Liam Nguyn': 'Liam Nguyen',
        'Dyson Spher': 'Dyson Sphere',
    }
    for wrong, right in fixes.items():
        term = term.replace(wrong, right)
    return term

def fuzzy_match_canonical(term: str, canonicals: List[str], threshold=0.9) -> Optional[str]:
    """Match OCR variants to canonical forms."""
    for canonical in canonicals:
        ratio = SequenceMatcher(None, term.lower(), canonical.lower()).ratio()
        if ratio >= threshold:
            return canonical
    return None
```

**Expected impact:** 
- Collapses 5-10 OCR variants into canonical forms
- Improves frequency counts for real terms

---

### 🎯 Priority 4: Class-Based Filtering (HIGH)

**Implementation:**
```python
# Add to build_prompt_list.py and build_phrase_set.py
HIGH_VALUE_CLASSES = {"PERSON", "ORG", "PRODUCT", "TECH"}

def is_high_value_term(term_dict: Dict) -> bool:
    """Only keep terms with high-value semantic classes."""
    classes = set(term_dict.get("classes", []))
    
    # Must have at least one high-value class
    if not classes.intersection(HIGH_VALUE_CLASSES):
        return False
    
    # Additional filters
    canonical = term_dict["canonical"]
    
    # Reject if looks like code/path
    if "/" in canonical or "." in canonical and len(canonical) < 20:
        return False
    
    # Reject if contains parentheses (function calls)
    if "(" in canonical:
        return False
    
    # Reject Slack/UI patterns
    if canonical.startswith(("U/", "T0", "#")):
        return False
    
    return True
```

**Expected impact:** 
- Removes ~150 code artifacts
- Removes ~100 UI/Slack terms
- Keeps only PERSON, ORG, PRODUCT, TECH classes

---

### 🎯 Priority 5: Fix Priority Weighting (HIGH)

**Current problem:**
```python
# Seeds with high frequency outscore low-freq LLM terms
score = (llm_priority * 0.6) + (frequency_score * 0.4)
```

**Recommended fix:**
```python
def calculate_score(term_dict: Dict) -> float:
    """Heavily favor LLM-identified terms."""
    source = term_dict["source"]
    priority = term_dict.get("priority", 0.5)
    frequency = term_dict.get("frequency", 1)
    classes = set(term_dict.get("classes", []))
    
    # Base score from LLM priority (if present)
    if "llm" in source:
        base_score = priority  # 0.0-1.0
    else:
        base_score = 0.3  # Seeds start lower
    
    # Boost for frequency (logarithmic, not linear)
    freq_boost = min(0.2, math.log10(frequency + 1) * 0.1)
    
    # Boost for high-value classes
    class_boost = 0.1 if classes.intersection(HIGH_VALUE_CLASSES) else 0.0
    
    return base_score + freq_boost + class_boost
```

**Expected impact:**
- LLM terms (priority 0.7-1.0) score 0.7-1.0
- Seed-only garbage scores <0.5
- Clear separation between signal and noise

---

### 🎯 Priority 6: Cap PhraseSet Size (MEDIUM)

**Implementation:**
```python
# Add to build_phrase_set.py
MAX_PHRASES = 500  # Google recommendation: <1000
MIN_SCORE_THRESHOLD = 0.6  # Only high-quality terms

def build_phrase_set(verified_terms: List[Dict], max_phrases: int = MAX_PHRASES) -> Dict:
    """Build Google STT PhraseSet with quality caps."""
    # Filter and sort
    high_quality = [
        t for t in verified_terms 
        if t["score"] >= MIN_SCORE_THRESHOLD and is_high_value_term(t)
    ]
    high_quality.sort(key=lambda x: x["score"], reverse=True)
    
    # Take top N
    top_terms = high_quality[:max_phrases]
    
    # Variable boost based on score
    phrases = []
    for term in top_terms:
        boost = 8.0 if term["score"] >= 0.9 else \
                10.0 if term["score"] >= 0.95 else \
                6.0
        phrases.append({"value": term["canonical"], "boost": boost})
    
    return {"phraseSets": [{"phrases": phrases}]}
```

**Expected impact:**
- Reduces from 1,452 → ~200-300 high-quality phrases
- Uses variable boost (6.0-10.0) for differentiation
- Focuses on PERSON, ORG, PRODUCT, TECH only

---

### 🎯 Priority 7: Add Minimum Length Requirements (LOW)

**Implementation:**
```python
# Add to mine_terms.py and verify_terms.py
MIN_TERM_LENGTH = 2  # Reject "Al", "On", "No", "It"
MAX_TERM_LENGTH = 50  # Reject overly long garbage

def is_valid_length(term: str) -> bool:
    return MIN_TERM_LENGTH <= len(term) <= MAX_TERM_LENGTH
```

**Expected impact:** Removes ~50 single/double char noise terms

---

## Proposed Pipeline Changes

### Phase 1: Quick Wins (1-2 hours)

1. ✅ Add stop word filter to `mine_terms.py`
2. ✅ Add number filter to `mine_terms.py`
3. ✅ Add class filter to `build_prompt_list.py` and `build_phrase_set.py`
4. ✅ Cap PhraseSet to 500 terms in `build_phrase_set.py`

**Expected result:** 
- `deck_terms.txt`: 121 → ~40 high-quality terms
- `phrase_set.json`: 1,452 → ~300 high-quality phrases
- Noise reduction: 70% → ~10%

### Phase 2: Quality Improvements (2-4 hours)

5. ✅ Add OCR normalization to `verify_terms.py`
6. ✅ Fix priority weighting in `verify_terms.py`
7. ✅ Add fuzzy deduplication
8. ✅ Add length requirements

**Expected result:**
- Canonical forms properly consolidated
- LLM terms properly prioritized over seed noise
- OCR variants collapsed

### Phase 3: Advanced (future)

9. ⏳ Add NLP-based part-of-speech filtering (spaCy/NLTK)
10. ⏳ Add semantic filtering (embeddings-based)
11. ⏳ Add manual allowlist/denylist support via config

---

## Success Metrics

### Current State:
- LLM quality: ⭐⭐⭐⭐⭐ (5/5) - 77 excellent terms
- Seed quality: ⭐ (1/5) - 2,333 terms, ~70% noise
- Final quality: ⭐⭐ (2/5) - diluted by noise

### Target State (after Phase 1+2):
- LLM quality: ⭐⭐⭐⭐⭐ (5/5) - unchanged
- Seed quality: ⭐⭐⭐⭐ (4/5) - ~200 filtered terms, ~10% noise
- Final quality: ⭐⭐⭐⭐⭐ (5/5) - clean, high-value only

### Measurable Goals:
- `deck_terms.txt`: <50 terms, all PERSON/ORG/PRODUCT/TECH
- `phrase_set.json`: <500 phrases, no stop words, no numbers
- Zero stop words in final output
- Zero standalone numbers in final output
- Zero code artifacts (globals(), parser.py) in final output
- All OCR variants collapsed to canonical forms

---

## Conclusion

**The LLM is doing great work** (77 high-quality terms with proper classification). 

**The problem is the deterministic seed mining** is producing 30× more terms, mostly garbage, and the current merge/filter logic doesn't properly separate signal from noise.

**Quick fix strategy:**
1. Add aggressive filtering to seed mining (stop words, numbers)
2. Add class-based filtering to artifact builders (PERSON/ORG/PRODUCT/TECH only)
3. Fix priority weighting to favor LLM over high-freq noise
4. Cap output sizes and add OCR normalization

**Expected outcome:** Transform from 2/5 quality → 5/5 quality with ~4 hours of work, primarily adding filter functions.

---

**Prepared by:** AI Code Assistant  
**Date:** November 17, 2025  
**Next step:** Implement Phase 1 quick wins (stop words + numbers + class filtering)
