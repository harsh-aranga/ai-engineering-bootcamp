# Note 1: Why Hallucinations Happen and Why They're Hard to Catch

## The Core Problem

An LLM hallucination is when the model generates text that isn't grounded in its input, retrieved context, or verifiable reality — and presents it with confidence. This is different from "being wrong" in a conventional sense:

|Being Wrong|Hallucinating|
|---|---|
|Misinterpreting data|Fabricating data|
|Calculation error|Inventing facts|
|Outdated information|Creating citations that don't exist|
|Incomplete answer|Confident answer when should abstain|

The dangerous part: hallucinations often _look_ more plausible than correct answers. They flow naturally, use appropriate jargon, and carry the same confident tone as accurate responses.

```
User: "What's the refund policy in my company handbook?"

Retrieved Context: "Refunds must be requested within 30 days of purchase."

Hallucinated Answer: "According to your company handbook (Section 4.2.1), 
refunds must be requested within 30 days of purchase, and processing 
typically takes 3-5 business days. For orders over $500, manager 
approval is required."

What's wrong:
- Section 4.2.1 doesn't exist (fabricated citation)
- 3-5 business days not in context (invented detail)
- $500 threshold not in context (extrapolated rule)
- Only the 30-day part is accurate
```

This answer is 75% hallucination but reads as completely authoritative.

---

## Why LLMs Hallucinate: The Mechanistic View

Understanding _why_ hallucinations occur helps you design effective detection and mitigation. LLMs hallucinate because of how they fundamentally work, not because of bugs or insufficient training.

### 1. Trained for Plausibility, Not Truth

LLMs are trained to predict the next most likely token given previous tokens. The training objective is:

```
Maximize P(next_token | previous_tokens)
```

This optimizes for **what text typically follows**, not **what is factually correct**. The model learns:

- Patterns in how humans write
- Typical sentence structures
- Common associations between concepts

It does NOT learn:

- A verified knowledge base
- How to check facts
- When it doesn't know something

**Analogy**: An LLM is like someone who has read millions of documents and learned to write convincingly in any style — but has no way to verify whether what they're writing is true. They produce text that _sounds like_ expert analysis without having expert knowledge.

### 2. No Internal Verification Mechanism

When you ask a question, the model doesn't:

1. Search an internal database
2. Verify the answer against sources
3. Check for logical consistency
4. Recognize uncertainty

It simply generates tokens that are statistically likely given the prompt. There's no internal "fact-checking" step.

```
Internal Model Process (Simplified):

Input: "The capital of France is"
       ↓
[Pattern matching across billions of parameters]
       ↓
Output probability: "Paris" (0.98), "Lyon" (0.001), "the" (0.0001)...
       ↓
Select: "Paris"

This works for "capital of France" because training data 
overwhelmingly associates France→Paris.

But for: "The 2024 Q3 revenue for Company X was"

The model has no verified data, so it pattern-matches:
- "Q3 revenue" often followed by "$X million" or "$X billion"
- Company sizes suggest certain ranges
- Generates plausible-sounding number

No verification. Just plausible completion.
```

### 3. Compression Artifacts from Training

LLMs compress massive amounts of text into fixed-size parameters. This compression is lossy:

- Rare facts may be stored imprecisely
- Similar concepts can blur together
- Edge cases and exceptions get smoothed out
- The model "remembers" general patterns better than specific details

```
Training data might include:
- "Company A was founded in 1995"
- "Company B was founded in 1996"  
- "Company C was founded in 1994"

Model learns pattern: "tech companies founded in mid-1990s"

When asked about Company D (also mid-90s):
Model might generate "1995" or "1996" even if actual year was 1997
— the specific detail is lost in compression
```

### 4. Out-of-Distribution Triggers Pattern-Matching

When a query is outside what the model saw during training (or rarely seen), it doesn't recognize this and abstain. Instead, it falls back to pattern-matching:

```
Query: "What did the CEO say in yesterday's earnings call?"

Model reasoning (not actual, illustrative):
- "Earnings call" → executives discuss financial performance
- Typical phrases: "strong quarter", "beat expectations", "headwinds"
- Generate plausible earnings call language

Output: "The CEO highlighted strong performance in the enterprise 
segment while acknowledging macroeconomic headwinds..."

This sounds exactly like an earnings call summary.
It's completely fabricated.
The model has no access to yesterday's actual call.
```

---

## Hallucination Types in RAG Systems

RAG introduces retrieved context, which creates new hallucination categories:

### Type 1: Intrinsic Hallucination (Contradiction)

The answer directly contradicts the retrieved context.

```
Context: "The warranty period is 12 months from date of purchase."

Answer: "Your product has a 24-month warranty."

Detection difficulty: EASIER
- Direct contradiction is relatively detectable
- Compare claims against context
```

### Type 2: Extrinsic Hallucination (Unsupported Addition)

The answer adds information not present in the context.

```
Context: "The warranty covers manufacturing defects."

Answer: "The warranty covers manufacturing defects. Accidental 
damage is also covered for the first 30 days."

Detection difficulty: HARDER
- First sentence is supported
- Second sentence is invented
- Requires checking each claim individually
- Sounds like natural elaboration
```

### Type 3: Fabricated Sources

The model invents citations, quotes, or references.

```
Context: [Contains policy information, no section numbers]

Answer: "According to Section 5.3.2 of the policy document, 
employees must submit requests within 48 hours."

Detection difficulty: MODERATE
- Can check if cited section exists
- But model might cite real sections with wrong content
- Quoted text might be paraphrased (hard to verify exact match)
```

### Type 4: Confident Uncertainty

The model answers when it should say "I don't know."

```
Context: [Information about product A pricing]

Query: "What's the pricing for product B?"

Answer: "Product B is priced at $99/month for the basic tier 
and $199/month for the enterprise tier."

Context says nothing about Product B.
Model should abstain: "I don't have information about Product B pricing."
Instead: generates plausible pricing (probably based on Product A or general patterns)

Detection difficulty: HARDEST
- Answer might be internally consistent
- No contradiction (topic isn't in context at all)
- Requires detecting that context doesn't support query
```

---

## Why RAG Doesn't Eliminate Hallucination

A common misconception: "If we give the model the right documents, it won't hallucinate."

RAG helps significantly but doesn't solve the problem:

### Problem 1: Model Can Ignore Context

```
Prompt: "Based on the context below, answer the question.

Context: [Retrieved documents about company policy]

Question: What's the refund policy?"

The model might:
- Draw on its parametric knowledge instead of context
- Blend context with general knowledge
- "Improve" context with additional (invented) details

This is especially common when:
- Context is ambiguous
- Question seems simple (model "knows" the answer)
- Context contradicts model's training data
```

### Problem 2: Blending Context with Parametric Knowledge

```
Context: "Our product supports Python and JavaScript."

Question: "What programming languages are supported?"

Possible hallucination: "Our product supports Python, JavaScript, 
and TypeScript. Ruby integration is in beta."

Model blended:
- Factual (Python, JavaScript from context)
- Plausible inference (TypeScript often paired with JavaScript)
- Fabrication (Ruby beta — not in context)

This blending is hard to detect because some parts are correct.
```

### Problem 3: Extrapolation Beyond Context

```
Context: "Enterprise plan includes SSO and dedicated support."

Question: "What support response time can I expect on Enterprise?"

Hallucination: "Enterprise customers receive dedicated support 
with a guaranteed 4-hour response time for critical issues."

Context says "dedicated support" — says nothing about response time.
Model extrapolates what "dedicated support" typically means.
Extrapolation might be wrong for this specific company.
```

### Problem 4: Garbage In, Garbage Out

If retrieval returns irrelevant chunks, the model faces an impossible task:

```
Query: "What's the PTO policy?"

Retrieved (bad retrieval): 
- Chunk about office locations
- Chunk about dress code
- Chunk about meeting room booking

Model options:
1. Say "I don't have information about PTO" (correct, rare)
2. Fabricate a PTO policy (sounds helpful, completely wrong)
3. Vaguely discuss HR policies (evasive, unhelpful)

Most models choose option 2 or 3.
```

---

## Why Detection Is Hard

### No Ground Truth

In classification, you have labels: image is cat or not cat. You can measure accuracy.

In hallucination detection:

- There's no pre-labeled "ground truth" for arbitrary queries
- You're checking free-form text against free-form context
- "Supported" vs "not supported" is often fuzzy

```
Context: "Revenue grew substantially in Q3."
Answer: "Q3 saw a 15% revenue increase."

Is this hallucinated?
- "Substantially" doesn't specify 15%
- But 15% is substantial
- Is this extrapolation or hallucination?
- Depends on your threshold
```

### Subtle Hallucinations Look Plausible

The most dangerous hallucinations are:

- Mostly correct with one wrong detail
- Plausible extensions of actual facts
- Correct format and tone with invented content

```
Context: "The API rate limit is 1000 requests per minute."

Answer: "The API rate limit is 1000 requests per minute. 
Exceeding this limit results in a 429 error, and your 
client should implement exponential backoff. The rate 
limit resets at the top of each minute."

Only first sentence is from context.
Rest is plausible (HTTP 429 is real, backoff is standard practice).
But: maybe this API uses different behavior.
A human expert might not catch this without checking docs.
```

### Checker Can Also Hallucinate

If you use an LLM to check for hallucinations (LLM-as-Judge), that LLM can also hallucinate:

```
Scenario: Answer contains a hallucinated claim.

Checker LLM might:
- Hallucinate that the claim IS in the context
- Miss subtle contradictions
- Apply its own knowledge instead of checking context

This is the recursive problem: using a hallucination-prone tool
to detect hallucinations.
```

This doesn't make LLM-as-Judge useless — it's still effective. But it means:

- Use specific, constrained prompts
- Don't expect perfect detection
- Consider multiple detection methods
- Test your checker on known examples

### Requires Deep Understanding

Effective detection requires understanding both the context and the answer semantically, not just string matching:

```
Context: "The process takes approximately two weeks."
Answer: "Expect a turnaround time of 10-14 business days."

String matching: No overlap, looks unsupported.
Semantic understanding: These say roughly the same thing.
This is NOT hallucination.

vs.

Context: "The process takes approximately two weeks."
Answer: "The standard processing time is two weeks, but 
expedited processing is available for $50."

String matching: "two weeks" matches.
Semantic understanding: Expedited option is not in context.
This IS hallucination.
```

---

## The Cost of Hallucination

### User Trust Erosion

```
Interaction 1: User asks question, gets accurate answer. Trust builds.
Interaction 2: User asks question, gets accurate answer. Trust builds.
Interaction 3: User asks question, gets hallucinated answer.
              User discovers error from another source.
              
Result: User no longer trusts ANY answers.
        Even accurate ones are now doubted.
        System becomes useless regardless of average accuracy.
```

Trust is asymmetric: many correct answers to build, one wrong answer to destroy.

### Downstream Decision Errors

```
Research Assistant answers: "The competitor's product doesn't 
support multi-tenancy."

User bases strategy on this, decides not to target enterprise.

Reality: Competitor added multi-tenancy 6 months ago.

Cost: Missed market opportunity based on false information.
```

Hallucinations don't just fail to help — they actively mislead. A system that says "I don't know" is safer than one that confidently lies.

### Legal and Compliance Risk

In regulated domains, hallucinations create liability:

```
Healthcare: Hallucinated drug interaction information
Finance: Fabricated investment performance data
Legal: Invented case citations
HR: Made-up policy that contradicts actual policy

These aren't just "oops" moments — they're potential lawsuits.
```

---

## Key Takeaways

1. **Hallucination is architectural**: LLMs are designed to generate plausible text, not verified facts. Hallucination isn't a bug — it's a consequence of the training objective.
    
2. **RAG reduces but doesn't eliminate**: Giving the model relevant context helps, but the model can ignore, blend, or extrapolate beyond that context.
    
3. **Four types in RAG systems**: Intrinsic (contradiction), extrinsic (unsupported addition), fabricated sources, and confident uncertainty. Each requires different detection approaches.
    
4. **Detection is fundamentally hard**: No ground truth, subtle hallucinations look plausible, and your checker can also hallucinate. This is why multiple detection strategies and human oversight remain important.
    
5. **Cost is high and asymmetric**: One hallucination can destroy trust built over many correct interactions. In regulated domains, hallucinations create legal liability.
    

---

## What's Next

Note 2 covers detection techniques: how to actually catch these hallucinations, including LLM-as-Judge approaches, claim extraction, and faithfulness scoring.