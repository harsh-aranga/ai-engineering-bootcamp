# What is a System Prompt?
System prompts serve as the foundational instructions that dictate an AI's behavior. They establish the framework for how the AI will interact and respond, similar to a job description for an employee. These prompts define the AI's role, its area of expertise, and the overall tone it should adopt.

Key elements of system prompts include:

- Behavioral Framing: Defining the AI's role, personality, or expertise.
- Constraint Setting: Establishing limitations or rules for the AI's responses.
- Context Provision: Providing background information or situational context.
- Ethical Guidance: Incorporating ethical guidelines or value alignments.

System prompts are typically defined by developers and remain consistent across multiple user interactions unless deliberately changed.

| Prompt Type   | Example                                                                                                   |
| ------------- | --------------------------------------------------------------------------------------------------------- |
| System Prompt | "You are a helpful and informative AI assistant that specializes in technology."                          |
| System Prompt | "You are an experienced customer service representative. Always maintain a polite and professional tone." |

---
# What is a User Prompt?
User prompts are the specific instructions or questions a user provides to an AI system to elicit a desired response. These prompts are dynamic and vary with each interaction, reflecting the user's immediate needs and goals. They can range from simple requests for information to complex instructions for generating creative content.

User prompts can be many things, but here are some of the most common types:

- Generation Prompts: These prompts instruct the AI to generate new content, such as text, images, or code. For example, a user might ask the AI to write a short story or generate a code snippet for a specific function.
- Conversation Prompts: These prompts initiate or continue a conversation with the AI, allowing for more interactive and dynamic exchanges. For example, a user might ask the AI a question and then follow up with clarifying questions or requests for more information.
- Classification Prompts: These prompts ask the AI to categorize input data based on predefined labels or categories. For example, a user might ask the AI to classify a product review as positive or negative.
- Extraction Prompts: These prompts ask the AI to extract specific information from a given text or dataset. For example, a user might ask the AI to extract all the names of people mentioned in a news article.

| Prompt Type | Example                                                                                                         |
| ----------- | --------------------------------------------------------------------------------------------------------------- |
| User Prompt | "Write a 500-word essay on the impact of social media on modern society, including the benefits and drawbacks." |
| User Prompt | "Generate a list of SEO keywords for a new restaurant in New York City that specializes in Italian food."       |

---
# What is Assistant Response?
The assistant response is:

> The model’s best possible output that satisfies  
> **System rules first**, then **user intent**, using **its internal knowledge**.

It is **not an independent actor**.  
It is a **constrained executor**.
## What the assistant actually “does” internally
At a high level, the assistant:
1. Reads **system constraints**
2. Parses **user intent**
3. Resolves conflicts
4. Plans an answer
5. Emits tokens that best satisfy all of the above

There is **no separate thinking agent** deciding this.
It’s a **single probabilistic generation process under constraints**.

---
# Common misconception (important)
**Wrong mental model:**

> System asks → User asks → Assistant answers

**Correct mental model:**

> System defines *the assistant itself*
> User gives *a task inside that world*
> Assistant emits *the only answer allowed in that world*

---
# Priority order (this is non-negotiable)

```
System > Developer (if present) > User > Assistant
```

So when conflicts occur:
* System vs User → **System wins**
* Earlier User vs Later User → **Later user wins**
* Assistant preference vs User → **User wins**
---
