# 1. Before prompt engineering
Have the following before starting to prompt engineer
1. A clear definition of the success criteria for your use case
2. Some ways to empirically test against those criteria
3. A first draft prompt you want to improve

---
# 2. Use Prompt Templates
There are few prompt template patterns that are useful to get better output based on the scenario in hand. Check [[5-Prompt_Structure_Templates]] for more details

---
# 3. Use Prompt Improver
Common LLMs provide prompt improver(Claude) or you can use the LLM itself to improve your prompts and suggest better prompts.
## For example:
### Prompt Before Improver(Claude)
```text
From the following list of Wikipedia article titles, identify which article this sentence came from.
Respond with just the article title and nothing else.

Article titles:
{{titles}}

Sentence to classify:
{{sentence}}
```
### Prompt After Improver (Claude)
```text
You are an intelligent text classification system specialized in matching sentences to Wikipedia article titles. Your task is to identify which Wikipedia article a given sentence most likely belongs to, based on a provided list of article titles.

First, review the following list of Wikipedia article titles:
<article_titles>
{{titles}}
</article_titles>

Now, consider this sentence that needs to be classified:
<sentence_to_classify>
{{sentence}}
</sentence_to_classify>

Your goal is to determine which article title from the provided list best matches the given sentence. Follow these steps:

1. List the key concepts from the sentence
2. Compare each key concept with the article titles
3. Rank the top 3 most relevant titles and explain why they are relevant
4. Select the most appropriate article title that best encompasses or relates to the sentence's content

Wrap your analysis in <analysis> tags. Include the following:
- List of key concepts from the sentence
- Comparison of each key concept with the article titles
- Ranking of top 3 most relevant titles with explanations
- Your final choice and reasoning

After your analysis, provide your final answer: the single most appropriate Wikipedia article title from the list.

Output only the chosen article title, without any additional text or explanation.
```

---
# 4. Be clear and direct (specific vs vague)
When interacting with LLMs, think of it as a brilliant but very new employee (with amnesia) who needs explicit instructions. Like any new employee, LLMs does not have context on your norms, styles, guidelines, or preferred ways of working. The more precisely you explain what you want, the better LLM's response will be.
## How to be clear, contextual, and specific
- **Give LLM contextual information:** Just like you might be able to better perform on a task if you knew more context, LLLM will perform better if it has more contextual information. Some examples of contextual information:
    - What the task results will be used for
    - What audience the output is meant for
    - What workflow the task is a part of, and where this task belongs in that workflow
    - The end goal of the task, or what a successful task completion looks like
- **Be specific about what you want LLM to do:** For example, if you want LLM to output only code and nothing else, say so.
- **Provide instructions as sequential steps:** Use numbered lists or bullet points to better ensure that LLM carries out the task the exact way you want it to.
## Examples
### Example 1: Anonymize Customer Feedback

| Role                          | Unclear Prompt                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Clear Prompt                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User                          | Please remove all personally identifiable information from these customer feedback messages: {{FEEDBACK_DATA}}                                                                                                                                                                                                                                                                                                                                                        | Your task is to anonymize customer feedback for our quarterly review.  <br>  <br>Instructions:  <br>1. Replace all customer names with "CUSTOMER_[ID]" (e.g., "Jane Doe" → "CUSTOMER_001").  <br>2. Replace email addresses with "EMAIL_[ID]@example.com".  <br>3. Redact phone numbers as "PHONE_[ID]".  <br>4. If a message mentions a specific product (e.g., "AcmeCloud"), leave it intact.  <br>5. If no PII is found, copy the message verbatim.  <br>6. Output only the processed messages, separated by "---".  <br>  <br>Data to process: {{FEEDBACK_DATA}} |
| Assistant (Claude's response) | Here are the anonymized customer feedback messages:  <br>1. I've been using your software for years, and it's been great. But lately, AcmeCloud has been crashing a lot. Fix it!  <br>2. XXX, your customer support rep, was incredibly helpful. He guided me through the whole process. My email is XXX if you want to send a survey.  <br>3. I'm John Smith, and I'm not happy. I've been on hold for 2 hours trying to reach someone at XXX. This is unacceptable! | CUSTOMER_001: I've been using your software for years, and it's been great. But lately, AcmeCloud has been crashing a lot. Fix it!  <br>---  <br>CUSTOMER_002: CUSTOMER_SERVICE_001, your customer support rep, was incredibly helpful. He guided me through the whole process. My email is [EMAIL_002@example.com](mailto:EMAIL_002@example.com) if you want to send a survey.  <br>---  <br>CUSTOMER_003: I'm CUSTOMER_003, and I'm not happy. I've been on hold for 2 hours trying to reach someone at PHONE_001. This is unacceptable!                           |
### Example 2: Incident Response

| Role                          | Vague Prompt                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Detailed Prompt                                                                                                                                                                                                                                                                                                      |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User                          | Analyze this AcmeCloud outage report and summarize the key points.  <br>  <br>{{REPORT}}                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | Analyze this AcmeCloud outage report. Skip the preamble. Keep your response terse and write only the bare bones necessary information. List only:  <br>1) Cause  <br>2) Duration  <br>3) Impacted services  <br>4) Number of affected users  <br>5) Estimated revenue loss.  <br>  <br>Here's the report: {{REPORT}} |
| Assistant (Claude's response) | Here's a summary of the key points from the AcmeCloud outage report:  <br>  <br>On May 15th, a misconfigured load balancer update caused significant traffic routing issues, resulting in a service outage from 09<br><br>to 13<br><br>UTC. The 4-hour 37-minute disruption impacted our core file syncing service and admin dashboard, rendering them inaccessible. Additionally, the mobile app experienced partial functionality loss. Approximately 68% of our user base, totaling 1.3 million users, were affected. Based on our Service Level Agreements (SLAs) and average revenue per user, we estimate a financial impact of $420,000 in service credits and potential customer churn. | 1) Cause: Misconfigured load balancer update  <br>2) Duration: 4h 37m (09:15-13<br><br>UTC, May 15)  <br>3) Impacted: Core sync, admin dashboard (down); mobile app (partial)  <br>4) Affected users: 1.3M (68% of base)  <br>5) Est. revenue loss: $420,000                                                         |

---
# 5. Use Multi-Shot Prompting
Wherever possible use one, few or multi-shot prompting to make the LLM answers better.
By providing a few well-crafted examples in your prompt, you can dramatically improve the accuracy, consistency, and quality of LLM's outputs. This technique, known as few-shot or multi-shot prompting, is particularly effective for tasks that require structured outputs or adherence to specific formats.

>***Power up your prompts**: Include 3-5 diverse, relevant examples to show LLMs exactly what you want. More examples = better performance, especially for complex tasks.*

## Example: Analyzing Customer Feedback
Notice that in the "no examples" version, LLM does not list multiple options for each category, despite its written analysis indicating that there are multiple categories for certain feedback. It also includes a long explanation when we may not want it to.

|Role|No Examples|With Examples|
|---|---|---|
|User|Analyze this customer feedback and categorize the issues. Use these categories: UI/UX, Performance, Feature Request, Integration, Pricing, and Other. Also rate the sentiment (Positive/Neutral/Negative) and priority (High/Medium/Low).  <br>  <br>Here is the feedback: {{FEEDBACK}}|Our CS team is overwhelmed with unstructured feedback. Your task is to analyze feedback and categorize issues for our product and engineering teams. Use these categories: UI/UX, Performance, Feature Request, Integration, Pricing, and Other. Also rate the sentiment (Positive/Neutral/Negative) and priority (High/Medium/Low). Here is an example:  <br>  <br><example>  <br>Input: The new dashboard is a mess! It takes forever to load, and I can't find the export button. Fix this ASAP!  <br>Category: UI/UX, Performance  <br>Sentiment: Negative  <br>Priority: High</example>  <br>  <br>Now, analyze this feedback: {{FEEDBACK}}|
|Assistant (Claude's response)|Here's the analysis of the customer feedback:  <br>  <br>Issue: UI/UX  <br>Sentiment: Negative  <br>Priority: High  <br>The customer is frustrated with the new dashboard design, which they find cluttered and slow to load. They specifically call out the missing "export" button, which is likely a critical feature. This issue needs to be addressed as a high priority.  <br>  <br>Issue: Integration  <br>Sentiment: Positive  <br>Priority: Medium  <br>The customer is pleased with the existing Salesforce integration but would like to see support for Hubspot as well. This is a feature request that could be considered for a future product update.  <br>  <br>Issue: Pricing  <br>Sentiment: Negative  <br>Priority: High  <br>The customer finds the pricing to be unreasonable, especially for the basic features. They are threatening to switch to a competitor, so this is a high-priority issue that needs to be reviewed.  <br>  <br>Issue: Performance  <br>Sentiment Negative  <br>Priority: High  <br>The customer is experiencing critical issues with the mobile app, where large file uploads consistently result in crashes. This is a significant problem that impacts the customer's ability to use the product effectively and should be addressed as a high priority.  <br>  <br>Issue: UI/UX  <br>Sentiment: Positive  <br>Priority: Low  <br>The customer is overall satisfied with the product, specifically calling out the intuitive UI and excellent customer support. This is a positive piece of feedback that does not require any immediate action.|Here's the analysis of the customer feedback:  <br>  <br>1. The new dashboard is a mess! It takes forever to load, and I can't find the export button. Fix this ASAP!  <br>Category: UI/UX, Performance  <br>Sentiment: Negative  <br>Priority: High  <br>  <br>2. Love the Salesforce integration! But it'd be great if you could add Hubspot too.  <br>Category: Integration, Feature Request  <br>Sentiment: Positive  <br>Priority: Medium  <br>  <br>3. Your pricing is ridiculous! $99/mo for basic features? I'm switching to Competitor X.  <br>Category: Pricing  <br>Sentiment: Negative  <br>Priority: High  <br>  <br>4. The mobile app keeps crashing when I try to upload large files (>50MB). This is critical for our field agents.  <br>Category: Performance  <br>Sentiment: Negative  <br>Priority: High  <br>  <br>5. Overall, I'm happy with the product. The UI is intuitive, and the customer support is top-notch. Keep it up!  <br>Category: UI/UX, Other (Customer Support)  <br>Sentiment: Positive  <br>Priority: Low|

---
# 6. Chain of Thought Prompting
When faced with complex tasks like research, analysis, or problem-solving, giving LLMs space to think can dramatically improve its performance. This technique, known as chain of thought (CoT) prompting, encourages LLMs to break down problems step-by-step, leading to more accurate and nuanced outputs.
Check [[2_Major_Types_Of_Prompting_Techniques#Chain-of-Thought Prompting?]] for more details.

---
# 7. Use XML tags to structure your prompts
When your prompts involve multiple components like context, instructions, and examples, XML tags can be a game-changer. They help LLMs parse your prompts more accurately, leading to higher-quality outputs.

>***XML tip**: Use tags like `<instructions>`, `<example>`, and `<formatting>` to clearly separate different parts of your prompt. This prevents LLMs from mixing up instructions with examples or context.*
## Why use XML tags?
- **Clarity:** Clearly separate different parts of your prompt and ensure your prompt is well structured.
- **Accuracy:** Reduce errors caused by LLMs misinterpreting parts of your prompt.
- **Flexibility:** Easily find, add, remove, or modify parts of your prompt without rewriting everything.
- **Parseability:** Having LLMs use XML tags in its output makes it easier to extract specific parts of its response by post-processing.
## Tagging best practices
1. **Be consistent**: Use the same tag names throughout your prompts, and refer to those tag names when talking about the content (e.g, `Using the contract in <contract> tags...`).
2. **Nest tags**: You should nest tags `<outer><inner></inner></outer>` for hierarchical content.

>***Power user tip**: Combine XML tags with other techniques like multishot prompting (`<examples>`) or chain of thought (`<thinking>`, `<answer>`). This creates super-structured, high-performance prompts.*

## Example: Generating Financial Reports
Without XML tags, LLMs misunderstands the task and generates a report that doesn't match the required structure or tone. After substitution, there is also a chance that LLM misunderstands where one section (like the the Q1 report example) stops and another begins.

| Role      | No XML Tags                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | With XML Tags                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User      | You're a financial analyst at AcmeCorp. Generate a Q2 financial report for our investors. Include sections on Revenue Growth, Profit Margins, and Cash Flow, like with this example from last year: {{Q1_REPORT}}. Use data points from this spreadsheet: {{SPREADSHEET_DATA}}. The report should be extremely concise, to the point, professional, and in list format. It should and highlight both strengths and areas for improvement.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | You're a financial analyst at AcmeCorp. Generate a Q2 financial report for our investors.  <br>  <br>AcmeCorp is a B2B SaaS company. Our investors value transparency and actionable insights.  <br>  <br>Use this data for your report:<data>{{SPREADSHEET_DATA}}</data>  <br>  <br><instructions>  <br>1. Include sections: Revenue Growth, Profit Margins, Cash Flow.  <br>2. Highlight strengths and areas for improvement.  <br></instructions>  <br>  <br>Make your tone concise and professional. Follow this structure:  <br><formatting_example>{{Q1_REPORT}}</formatting_example>                                                                                                                                                                                                                   |
| Assistant | Q2 Financial Report for AcmeCorp Investors  <br>  <br>Dear Valued Investors,  <br>  <br>I am pleased to present our Q2 financial report, showcasing AcmeCorp's continued growth and resilience in the B2B SaaS market.  <br>  <br>1. Revenue Growth:  <br>Our Q2 revenue reached $15.2M, a 22% YoY increase. This growth is primarily driven by a 30% expansion in our enterprise client base. However, our SMB segment saw a slight decline of 5%, which we aim to address through targeted marketing initiatives in Q3.  <br>  <br>2. Profit Margins:  <br>Gross margin improved to 72% (up 3% from Q1) due to infrastructure optimizations. EBITDA margin, however, dipped to 18% (down 2%) as we invested heavily in R&D for our upcoming AI-driven features.  <br>  <br>3. Cash Flow:  <br>Operating cash flow remains strong at $4.1M. Our cash reserves stand at $28M, providing a 15-month runway at current burn rate. We did see a 20% increase in customer acquisition costs, which we're addressing through more efficient sales strategies.  <br>  <br>In summary, AcmeCorp's core financials remain robust. We're balancing growth investments with prudent cash management. Our focus for Q3 will be revitalizing SMB growth and optimizing sales efficiency.  <br>  <br>Thank you for your continued trust.  <br>  <br>Sincerely,  <br>CFO, AcmeCorp | Q2 Financial Report for AcmeCorp Investors</output>  <br>  <br>Revenue Growth:  <br>- Q2 revenue: $15.2M (22% YoY ↑)  <br>- Enterprise clients: 30% ↑  <br>- SMB segment: 5% ↓  <br>Action: Targeted Q3 marketing  <br>  <br>Profit Margins:  <br>- Gross margin: 72% (3% ↑ from Q1)  <br>Reason: Infrastructure optimizations  <br>- EBITDA margin: 18% (2% ↓)  <br>Reason: R&D investment in AI features  <br>  <br>Cash Flow:  <br>- Operating cash flow: $4.1M (strong)  <br>- Cash reserves: $28M (15-month runway)  <br>- Customer acquisition cost: 20% ↑  <br>Action: Optimize sales strategies  <br>  <br>Outlook:  <br>- Core financials: Robust  <br>- Q3 focus: Revitalize SMB, optimize sales  <br>  <br>Management remains committed to balancing growth investments with financial discipline. |

---
# 8. Giving LLM a role with a system prompt
When using LLMs, you can dramatically improve its performance by using the `system` parameter to give it a role. This technique, known as role prompting, is the most powerful way to use system prompts with LLMs.
The right role can turn LLMs from a general assistant into your virtual domain expert!

>***System prompt tips**: Use the `system` parameter to set LLM's role. Put everything else, like task-specific instructions, in the `user` turn instead.*
## Why use role prompting?
- **Enhanced accuracy:** In complex scenarios like legal analysis or financial modeling, role prompting can significantly boost Claude's performance.
- **Tailored tone:** Whether you need a CFO's brevity or a copywriter's flair, role prompting adjusts Claude's communication style.
- **Improved focus:** By setting the role context, Claude stays more within the bounds of your task's specific requirements.
## Example:
### Part 1: Without Role Assignment
|Role|Content|
|---|---|
|User|Analyze this software licensing agreement for potential risks:  <br><contract>  <br>{{CONTRACT}}  <br></contract>  <br>  <br>Focus on indemnification, liability, and IP ownership.|
|Assistant|Here's a summary of the key points in the software licensing agreement:  <br>  <br>1. Indemnification (Section 8):  <br>- We indemnify the vendor against claims arising from our use.  <br>  <br>2. Limitation of Liability (Section 9):  <br>- Damages capped at $500.  <br>  <br>3. IP Ownership (Section 12):  <br>- We retain ownership of our modifications.  <br>  <br>Overall, the agreement seems standard. The indemnification and liability clauses are typical, and we maintain our IP rights.|
### Part 2: With Role Assignment
| Role      | Content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User      | You are the General Counsel of a Fortune 500 tech company. We're considering this software licensing agreement for our core data infrastructure:  <br><contract>  <br>{{CONTRACT}}  <br></contract>  <br>  <br>Analyze it for potential risks, focusing on indemnification, liability, and IP ownership. Give your professional opinion.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Assistant | I've reviewed the software licensing agreement, and I have serious concerns that could expose our company to significant risks:  <br>  <br>1. Indemnification (Section 8):  <br>- Critical Issue: We indemnify the vendor against "any and all claims" arising from our use.  <br>- Risk: This could hold us liable even for the vendor's negligence or product defects.  <br>- Recommendation: Reject. Limit our indemnity to claims arising from our violation of the agreement.  <br>  <br>2. Limitation of Liability (Section 9):  <br>- Critical Issue: Damages capped at $500, including direct damages.  <br>- Risk: Grossly inadequate. A critical failure in our data infrastructure could cost us millions in lost revenue and reputational damage.  <br>- Recommendation: Reject. Negotiate for cap at 12 months of fees for direct damages, and carve-outs for data breaches.  <br>  <br>3. IP Ownership (Section 12):  <br>- Critical Issue: Vendor gains joint ownership of our modifications and integrations.  <br>- Risk: They could use or sell our proprietary algorithms or data insights to competitors.  <br>- Recommendation: Reject. We must retain full ownership of our work.  <br>  <br>Professional Opinion: Do not sign this agreement. It is grossly unfavorable and exposes us to unacceptable levels of risk. If the vendor refuses to renegotiate these terms, I strongly advise exploring alternative providers or accelerating our in-house solution. The potential costs of proceeding with this agreement far outweigh any short-term gains. |

---
# 9. Prefill LLM's response for greater output control
When using LLMs, you have the unique ability to guide its responses by prefilling the `Assistant` message. This powerful technique allows you to direct LLM's actions, skip preambles, enforce specific formats like JSON or XML, and even help LLMs maintain character consistency in role-play scenarios.
In some cases where LLMs is not performing as expected, a few prefilled sentences can vastly improve LLM's performance. A little prefilling goes a long way!
## Example: Controlling output formatting and skipping the preamble
### Part 1: Without prefilling
| Role      | Content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User      | Extract the name, size, price, and color from this product description as a JSON object:  <br>  <br><description>  <br>The SmartHome Mini is a compact smart home assistant available in black or white for only $49.99. At just 5 inches wide, it lets you control lights, thermostats, and other connected devices via voice or app—no matter where you place it in your home. This affordable little hub brings convenient hands-free control to your smart devices.  <br></description>                                                                                                                       |
| Assistant | Here's the extracted information in JSON format:  <br>  <br>```json  <br>{  <br>"name": "SmartHome Mini",  <br>"size": "5 inches wide",  <br>"price": "$49.99",  <br>"colors": ["black", "white"]  <br>}  <br>```  <br>  <br>I've extracted the following details from the product description:  <br>- **Name**: SmartHome Mini  <br>- **Size**: 5 inches wide  <br>- **Price**: $49.99  <br>- **Colors**: Available in black and white  <br>  <br>The JSON object provides a structured format that's easy for programs to parse and use. Let me know if you need any modifications or have any other questions! |
### Part 2: With prefilling
| Role                          | Content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| User                          | Extract the name, size, price, and color from this product description as a JSON object:  <br>  <br><description>  <br>The SmartHome Mini is a compact smart home assistant available in black or white for only $49.99. At just 5 inches wide, it lets you control lights, thermostats, and other connected devices via voice or app—no matter where you place it in your home. This affordable little hub brings convenient hands-free control to your smart devices.  <br></description> |
| Assistant (prefill)           | {                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Assistant (Claude's response) | "name": "SmartHome Mini",  <br>"size": "5 inches wide",  <br>"price": "$49.99",  <br>"colors": [  <br>"black",  <br>"white"  <br>]  <br>}                                                                                                                                                                                                                                                                                                                                                   |

---
# 10. Chain Complex Prompts
When working with complex tasks, LLMs can sometimes drop the ball if you try to handle everything in a single prompt. Chain of thought (CoT) prompting is great, but what if your task has multiple distinct steps that each require in-depth thought?
Enter prompt chaining: breaking down complex tasks into smaller, manageable subtasks.
## When to chain prompts
Use prompt chaining for multi-step tasks like research synthesis, document analysis, or iterative content creation. When a task involves multiple transformations, citations, or instructions, chaining prevents Claude from dropping or mishandling steps.
**Remember:** Each link in the chain gets Claude's full attention!
## How to chain prompts

1. **Identify subtasks**: Break your task into distinct, sequential steps.
2. **Structure with XML for clear handoffs**: Use XML tags to pass outputs between prompts.
3. **Have a single-task goal**: Each subtask should have a single, clear objective.
4. **Iterate**: Refine subtasks based on Claude's performance.

---
# 11. Long context prompting tips
# LLM-Agnostic Long-Context Prompting Tips

Large context windows increase *capacity*, not *precision*. As prompts grow longer, attention diffuses, instruction adherence weakens, and irrelevant details begin to dominate. The patterns below are **model-agnostic** techniques to restore signal, control, and predictability when working with long inputs. These apply across GPT-style models, Claude, and open-source LLMs.
## 1. Put Instructions First
**What it is**
Place task instructions before any long content.

**What it does**
Ensures intent and constraints are established before attention is consumed by large inputs.

**Example**
```text
Task: Summarize for senior engineers. Avoid simplification.

Input:
<<<
<long document>
>>>
```
## 2. Delimit and Label Sections
**What it is**
Split long inputs into clearly labeled sections.

**What it does**
Creates attention anchors and reduces cross-section contamination.

**Example**
```text
### Incident Report
...
### Root Cause
...
### Mitigations
...
```
## 3. State Relevance Explicitly
**What it is**
Tell the model which parts of the context matter.

**What it does**
Prevents the model from treating all context as equally important.

**Example**
```text
Use only the "Root Cause" section. Ignore historical background.
```
## 4. Prefer Multi-Pass Over Single-Pass
**What it is**
Break long-context tasks into multiple prompts.

**What it does**
Improves signal-to-noise ratio and reduces hallucination.

**Example**
```text
Prompt 1: Summarize key technical facts.
Prompt 2: Evaluate risks based on the summary.
```
## 5. Restate the Goal Near the End (When Needed)
**What it is**
Briefly repeat the task after the long input.

**What it does**
Reinforces intent after traversing a large context window.

**Example**
```text
<large input>

Reminder: Produce a concise risk assessment in bullets.
```
## 6. Avoid Implicit Recall
**What it is**
Do not assume the model will reliably recall buried details.

**What it does**
Encourages explicit extraction before reasoning.

**Example**
```text
First extract all configuration limits. Then analyze impact.
```
## 7. Compress Before You Reason
**What it is**
Summarize or extract before analytical tasks.

**What it does**
Restores precision lost to attention dilution.

**Example**
```text
Step 1: Summarize failure patterns.
Step 2: Propose mitigations.
```
## Closing Principle
Long context expands what a model *can see*, not what it *can reason about*. Precision comes from **structure, prioritization, and staged execution**, not raw token count.

---
