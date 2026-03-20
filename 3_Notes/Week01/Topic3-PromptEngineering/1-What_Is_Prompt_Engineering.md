# What is Prompt Engineering? Why is it needed?
Prompt engineering is the process where you guide generative artificial intelligence (generative AI) solutions to generate desired outputs. Even though generative AI attempts to mimic humans, it requires detailed instructions to create high-quality and relevant output. In prompt engineering, you choose the most appropriate formats, phrases, words, and symbols that guide the AI to interact with your users more meaningfully. Prompt engineers use creativity plus trial and error to create a collection of input texts, so an application's generative AI works as expected.

Prompt engineering makes AI applications more efficient and effective. Application developers typically encapsulate open-ended user input inside a prompt before passing it to the AI model.

For example, consider AI chatbots. A user may enter an incomplete problem statement like,

>"Where to purchase a shirt." 

Internally, the application's code uses an engineered prompt that says, 

>"You are a sales assistant for a clothing company. A user, based in Alabama, United States, is asking you where to purchase a shirt. Respond with the three nearest store locations that currently stock a shirt." 

The chatbot then generates more relevant and accurate information.

---
# Benefits of Prompt Engineering
Next, we discuss some benefits of prompt engineering.
## **Greater developer control**
Prompt engineering gives developers more control over users' interactions with the AI. Effective prompts provide intent and establish context to the large language models. They help the AI refine the output and present it concisely in the required format.

They also prevent your users from misusing the AI or requesting something the AI does not know or cannot handle accurately. For instance, you may want to limit your users from generating inappropriate content in a business AI application.
## **Improved user experience**
Users avoid trial and error and still receive coherent, accurate, and relevant responses from AI tools. Prompt engineering makes it easy for users to obtain relevant results in the first prompt. It helps mitigate bias that may be present from existing human bias in the large language models’ training data.

Further, it enhances the user-AI interaction so the AI understands the user's intention even with minimal input. For example, requests to summarize a legal document and a news article get different results adjusted for style and tone. This is true even if both users just tell the application, _"Summarize this document."_
## **Increased flexibility**
Higher levels of abstraction improve AI models and allow organizations to create more flexible tools at scale. A prompt engineer can create prompts with domain-neutral instructions highlighting logical links and broad patterns. Organizations can rapidly reuse the prompts across the enterprise to expand their AI investments.

For example, to find opportunities for process optimization, the prompt engineer can create different prompts that train the AI model to find inefficiencies using broad signals rather than context-specific data. The prompts can then be used for diverse processes and business units.

---
# What you need for Prompt Engineering
Several key elements contribute to effective prompt engineering. Mastering these allows you to communicate effectively with AI models and unlock their full potential.
## Prompt format
The structure and style of your prompt play a significant role in guiding the AI's response. Different models may respond better to specific formats, such as:

The format of your prompt plays a significant role in how the AI interprets your request. Different models may respond better to specific formats, such as natural language questions, direct commands, or structured inputs with specific fields. Understanding the model's capabilities and preferred format is essential for crafting effective prompts.
## Context and examples
Providing context and relevant examples within your prompt helps the AI understand the desired task and generate more accurate and relevant outputs. For instance, if you're looking for a creative story, including a few sentences describing the desired tone or theme can significantly improve the results.
## Fine-tuning and adapting
Fine-tuning the AI model on specific tasks or domains using tailored prompts can enhance its performance. Additionally, adapting prompts based on user feedback or model outputs can further improve the model's responses over time.
## Multi-turn conversations
Designing prompts for multi-turn conversations allows users to engage in continuous and context-aware interactions with the AI model, enhancing the overall user experience.

---
# Common Prompt Engineering Techniques
Here are some more examples of techniques that prompt engineers use to improve their AI models' natural language processing (NLP) tasks.
## Direct prompts (Zero-shot)
Zero-shot prompting involves providing the model with a direct instruction or question without any additional context or examples. 

An example of this is idea generation, where the model is prompted to generate creative ideas or brainstorming solutions. Another example is summarization, or translation, where the model is asked to summarize or translate some piece of content.
## One-, few- and multi-shot prompts
This method involves providing the model with one or more examples of the desired input-output pairs before presenting the actual prompt. This can help the model better understand the task and generate more accurate responses.
## Chain-of-thought prompting
Chain-of-thought prompting is a technique that breaks down a complex question into smaller, logical parts that mimic a train of thought. This helps the model solve problems in a series of intermediate steps rather than directly answering the question. This enhances its reasoning ability.

You can perform several chain-of-though rollouts for complex tasks and choose the most commonly reached conclusion. If the rollouts disagree significantly, a person can be consulted to correct the chain of thought.

For example, if the question is "What is the capital of France?" the model might perform several rollouts leading to answers like "Paris", "The capital of France is Paris" and "Paris is the capital of France." Since all rollouts lead to the same conclusion, "Paris" would be selected as the final answer.
## Tree-of-thought prompting
The tree-of-thought technique generalizes chain-of-thought prompting. It prompts the model to generate one or more possible next steps. Then it runs the model on each possible next step using a tree search method.

For example, if the question is _"What are the effects of climate change?"_ the model might first generate possible next steps like _"List the environmental effects__"_ and _"List the social effects."_It would then elaborate on each of these in subsequent steps.

## Maieutic prompting
Maieutic prompting is similar to tree-of-thought prompting. The model is prompted to answer a question with an explanation. The model is then prompted to explain parts of the explanation,. Inconsistent explanation trees are pruned or discarded. This improves performance on complex commonsense reasoning.

For example, if the question is _"Why is the sky blue?"_ the model might first answer, "The sky appears blue to the human eye because the short waves of blue light are scattered in all directions by the gases and particles in the Earth's atmosphere." 
It might then expand on parts of this explanation, such as why blue light is scattered more than other colors and what the Earth's atmosphere is composed of.
## Complexity-based prompting
This prompt-engineering technique involves performing several chain-of-thought rollouts. It chooses the rollouts with the longest chains of thought then chooses the most commonly reached conclusion.

For example, if the question is a complex math problem, the model might perform several rollouts, each involving multiple steps of calculations. It would consider the rollouts with the longest chain of thought, which for this example would be the most steps of calculations. The rollouts that reach a common conclusion with other rollouts would be selected as the final answer.
## Generated knowledge prompting
This technique involves prompting the model to first generate relevant facts needed to complete the prompt. Then it proceeds to complete the prompt. This often results in higher completion quality as the model is conditioned on relevant facts.

For example, imagine a user prompts the model to write an essay on the effects of deforestation. The model might first generate facts like__"deforestation contributes to climate change"__and__"deforestation leads to loss of biodiversity."__ Then it would elaborate on the points in the essay.
## Least-to-most prompting
In this prompt engineering technique, the model is prompted first to list the subproblems of a problem, and then solve them in sequence. This approach ensures that later subproblems can be solved with the help of answers to previous subproblems.

For example, imagine that a user prompts the model with a math problem like _"Solve for x in equation 2x + 3 = 11_." The model might first list the subproblems as _"Subtract 3 from both sides"_ and _"Divide by 2"_. It would then solve them in sequence to get the final answer.
## Self-refine prompting
In this technique, the model is prompted to solve the problem, critique its solution, and then resolve the problem considering the problem, solution, and critique. The problem-solving process repeats until a it reaches a predetermined reason to stop. For example, it could run out of tokens or time, or the model could output a stop token.

For example, imagine a user prompts a model, _"Write a short essay on literature."_ The model might draft an essay, critique it for lack of specific examples, and rewrite the essay to include specific examples. This process would repeat until the essay is deemed satisfactory or a stop criterion is met.
## Directional-stimulus prompting
This prompt engineering technique includes a hint or cue, such as desired keywords, to guide the language model toward the desired output.

For example, if the prompt is to write a poem about love, the prompt engineer may craft prompts that include _"heart,"__"passion,"_ and _"eternal."_ The model might be prompted, _"Write a poem about love that includes the words 'heart,' 'passion,' and 'eternal'."_This would guide the model to craft a poem with these keywords.

---
# What are some prompt engineering best practices?
Good prompt engineering requires you to communicate instructions with context, scope, and expected response. Next, we share some best practices.
## Unambiguous prompts
Clearly define the desired response in your prompt to avoid misinterpretation by the AI. For instance, if you are asking for a novel summary, clearly state that you are looking for a summary, not a detailed analysis. This helps the AI to focus only on your request and provide a response that aligns with your objective.
## Adequate context within the prompt
Provide adequate context within the prompt and include output requirements in your prompt input, confining it to a specific format. For instance, say you want a list of the most popular movies of the 1990s in a table. To get the exact result, you should explicitly state how many movies you want to be listed and ask for table formatting.
## Balance between targeted information and desired output
Balance simplicity and complexity in your prompt to avoid vague, unrelated, or unexpected answers. A prompt that is too simple may lack context, while a prompt that is too complex may confuse the AI. This is especially important for complex topics or domain-specific language, which may be less familiar to the AI. Instead, use simple language and reduce the prompt size to make your question more understandable.
## Experiment and refine the prompt
Prompt engineering is an iterative process. It's essential to experiment with different ideas and test the AI prompts to see the results. You may need multiple tries to optimize for accuracy and relevance. Continuous testing and iteration reduce the prompt size and help the model generate better output. There are no fixed rules for how the AI outputs information, so flexibility and adaptability are essential.

---
