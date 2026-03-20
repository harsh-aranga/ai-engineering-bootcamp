# Lost in the Middle: When Language Models Forget What You Told Them

## What Is "Lost in the Middle"?

Imagine you're at a conference listening to a three-hour presentation. Someone asks you afterwards, "What did the speaker say about supply chain optimization?" You'll probably remember the opening remarks quite clearly—they set the stage and grabbed your attention. You'll also remember the conclusion vividly because it was recent and impactful. But that crucial slide about supply chain optimization that appeared ninety minutes into the talk? There's a good chance you missed it or can't recall the details, even though you were technically present and paying attention when it was presented.

This is essentially what happens to large language models when they process long contexts. The phenomenon is called "lost in the middle," and it describes a model's tendency to pay more attention to information at the beginning and end of its context window while giving less weight to information buried in the middle. The model doesn't lose access to that middle content—it's still technically "there" in the model's context—but during the reasoning and generation process, that information receives less attention and is less likely to influence the final output.

## The Research Behind It

The "lost in the middle" phenomenon was formally documented by researchers at Stanford in 2023 through a paper titled "Lost in the Middle: How Language Models Use Long Contexts." The researchers conducted experiments where they placed a relevant document containing the answer to a question at different positions within a long context filled with many documents. What they found was striking: when the relevant document was placed at the very beginning or very end of the context, the model retrieved and used that information correctly most of the time. But when the exact same relevant document was placed in the middle positions—say, document fifteen out of thirty—the model's performance dropped significantly. The information was present and accessible, but the model was much less likely to use it.

This wasn't a problem with one specific model or context length. The researchers observed this pattern across different model architectures, different context window sizes, and different types of tasks. Whether the context was ten thousand tokens or a hundred thousand tokens, the U-shaped performance curve remained consistent: strong performance at the beginning, degraded performance in the middle, and recovery toward the end.

## Why Does This Happen?

To understand why models exhibit this behavior, we need to look at how they process information during inference. When a language model generates a response, it doesn't treat all input tokens equally. Instead, it uses attention mechanisms to dynamically weight different parts of the input based on their relevance to the task at hand.

Think of attention as the model's way of deciding what to focus on at each step of generation. When you ask the model a question, it scans through all the available context and assigns attention scores to different segments. In theory, the model should assign the highest attention to wherever the answer actually lives, regardless of position. In practice, however, there are systematic biases in how attention gets distributed across long contexts.

The beginning of the context receives what researchers call primacy bias. This makes intuitive sense—the opening information often contains important framing, instructions, or context-setting details. The model learns during training that early information is frequently crucial, so it naturally pays more attention there. Similarly, the end of the context receives recency bias, especially the portions closest to the actual user query. This also makes sense because the most recent information is often directly relevant to what's being asked.

The middle, however, falls into a kind of attention valley. It's far enough from the beginning that primacy bias has faded, but not close enough to the query for recency bias to kick in. The model hasn't forgotten this content, and if you specifically prompted the model to "look at document fifteen," it could access and use that information. But when the model is freely reasoning about how to answer a question, the attention mechanisms naturally gravitate toward the boundaries rather than the middle regions.

## Practical Examples of the Effect

Consider a customer support scenario where you're building a chatbot. At the start of the conversation, you provide a system prompt that says "Always check the user's account status before suggesting solutions." The customer and bot then have a lengthy back-and-forth conversation about various technical issues spanning twenty messages. Somewhere in the middle of that conversation, the customer mentions "By the way, I'm on the enterprise plan with custom SLA." Near the end of the conversation, you include a reminder that says "Prioritize solutions that minimize downtime."

When the bot generates its next response, it's much more likely to remember and act on that opening instruction about checking account status and the recent reminder about minimizing downtime. But that crucial detail about the enterprise plan and custom SLA mentioned in the middle of the conversation? There's a meaningful chance the bot will overlook it or give it less weight, even though that information should significantly change the support approach.

Another common example occurs when developers stuff multiple code files into a prompt for debugging. You might include ten different Python files in the context, with the buggy function buried in file number six. The model will naturally pay more attention to the first couple of files and the last couple of files near your actual question. That buggy function in file six is technically visible to the model, but it's sitting in that attention valley where the model is less likely to focus its reasoning.

## Why This Matters

Understanding the lost in the middle phenomenon is crucial for anyone building applications with large language models, and it has implications that go far beyond just being an interesting quirk of model behavior.

First, it fundamentally challenges a common assumption about context windows. When a model advertises a two-hundred-thousand-token context window, developers often assume this means they can utilize all two hundred thousand tokens equally. In reality, usable context is not the same as available context. Just because you can technically fit a hundred documents into the context window doesn't mean the model will effectively use all of them. The practical utility of that context window is much smaller than the advertised size would suggest.

Second, this phenomenon directly impacts how we should architect AI systems. If you're designing a retrieval system, a code analysis tool, a document QA system, or any application that involves long contexts, you need to think carefully about information placement. The architecture of your prompt matters just as much as the content of your prompt. Where you place critical information within the context window can be the difference between a system that works reliably and one that fails unpredictably.

Third, it reveals why certain production patterns have emerged in the AI engineering community. Techniques like context compression, strategic chunk ordering, and periodic instruction repetition aren't just best practices pulled out of thin air—they're direct responses to this underlying model behavior. Understanding lost in the middle helps you understand why these patterns exist and when to apply them.

Finally, this phenomenon teaches us something important about the nature of these models and how they differ from traditional software systems. In classical programming, if data is in memory, it's equally accessible regardless of where in memory it lives. But language models have attention-based access patterns that create uneven landscapes of accessibility. Building reliable systems on top of these models requires understanding these limitations and designing around them, rather than assuming uniform access to all context.

The lost in the middle problem isn't a bug that will be fixed in the next model release—it's a fundamental characteristic of how attention-based architectures process long sequences. As context windows continue to grow larger, understanding and working with this phenomenon becomes increasingly important for building production-grade AI systems that behave predictably and reliably.