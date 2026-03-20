# What is temperature?
The `temperature` parameter controls the randomness of the generated text. Adjusting the temperature changes how the model selects the next word in a sequence, influencing the creativity and predictability of the output. Low temperatures render outputs that are predictable and repetitive. Conversely, high temperatures encourage LLMs to produce more random, creative responses.

---
# How does Temperature work?
Before generating each token, an LLM will consider different options. These options have weighted likelihoods. For example, imagine an output: `I went to the zoo and saw` .

For the next token, an LLM might consider likely options like `lions (0.2)`, `hipp (0.13)` (starting token for hippo), and `croc (0.11)` (crocodile). It’ll also consider less likely options like `meer (0.004)` (meerkat),  `mice (0.003)`, and `squid (0.003)`.

Temperature regulates how an LLM weights these likelihoods. A moderate or default temperature will treat them at face value. A low temperature will optimize for higher likelihoods—increasing the net probability of `lion` or `hipp`. A high temperature will do the opposite, boosting the odds of `meer` and `mice`.

This control happens through a process called **SoftMax**, which helps the model decide which word is the best fit based on probability.

---
# How does the SoftMax function work?

When the model is deciding what words (or tokens) to pick next, it looks at raw scores called **`logits.`**The **SoftMax function** function then converts this set of raw scores (**_logits_**) into probabilities. It basically takes a vector of numbers and converts them into a probability distribution, where the sum of all probabilities is equal to 1.

This allows the model to make decisions based on the relative likelihood of different token options.

**Let’s look at an example:**

Imagine an LLM is trying to predict the next word in a sentence. The model might assign the following **_logits_** to three possible words:

```javascript
“cat” = 2.0
“dog” = 1.5
“fish” = 0.5
```

The SoftMax function converts these into probabilities:

```javascript
“cat” = 0.57
“dog” = 0.31
“fish” = 0.12
```

The model is most likely to choose “cat” because it has the highest probability.

So with the temperature parameter this translates to:

**Low temperature**: Makes the SoftMax distribution sharper, favoring the highest probability words more strongly (less randomness).

**High temperature**: Flattens the distribution, making less likely words more probable (more randomness).

---
# What are the three major temperature settings?
There are three primary types of temperature settings.
## Low Temperature (less than `1.0`)
On most LLMs, a low temperature is a temperature below `1.0`. This will result in more robotic text with significantly less variance. This is ideal for applications that prioritize predictability.
## Medium Temperature (`1.0`)
A temperature of `1.0` serves as a benchmark of average randomness and creativity. This is the default setting on most LLMs, and many applications will consequently use a temperature of `1.0` .
## High Temperature (more than `1.0`)
A temperature above `1.0` increases the “creativity” of a model by adding more randomness to the outputs. There are always significantly more low likelihood tokens than high likelihood tokens; therefore, by tipping the scale, we give equal fighting chance to the low likelihood tokens.

---
# When to use Temperature?
Temperature is one of the most common tweaked settings when programmatically interfacing with an LLM.
There are some scenarios where temperature is particularly helpful:
- When generating tutorials or documentation, a low temperature is preferred to keep language and format consistent
- When generating creative writing or poetry, a high temperature is ideal to generate varying responses
- When customer chatbot applications, a moderate-to-high temperature is often preferred to give the conversation personality. Conversely, if customers want more robotic answers, a lower temperature is better.

---
# What are alternatives to Temperature?
There are some other settings that provide similar, but distinct features to temperature. These could serve as good alternatives in niche scenarios.
## What is Top P?
Top P, also known as _nuclear sampling_, filters the tokens that should be considered for each iteration. Top P defines the probabilistic sum that the chosen token’s likelihoods should add up to. Notably, Top P is _not_ a percentage of tokens; a Top P of 10% defines the minimum quantity of tokens needed to sum to 10% of the net likelihoods.

Top P can be mixed with temperature, but that is typically not advisable. While temperature is typically used over Top P, Top P is useful when token options aren’t as long-tailed.
## What is Top K?
Top K is similar to Top P, but instead defines a quantity of the most probable tokens that should be considered. For example, a Top K of `3` would instruct the LLM to only consider the three most likely tokens. A Top K of `1` would force the LLM to only consider the most likely token.

A low Top K is similar to a low temperature. However, Top K is a more crude metric because it doesn’t account for the relative probabilities between the options. It’s also not as well-supported, notably missing from OpenAI’s API.

---
# Proper Example Using Temperature and GPT

```python
from openai import OpenAI

client = OpenAI()

prompt = "Describe a completely fictional animal found in a magical forest."

temperatures = [0.0, 0.7, 1.2]

for temp in temperatures:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
        max_tokens=150
    )
    reply = response.choices[0].message.content.strip()
    print(f"\nTemperature: {temp}")
    print(f"Response: {reply}\n")
```

In this code, you first define your `prompt` and a list of three `temperature` values: `0.0`, `0.7`, and `1.2`. For each `temperature`, you send the `prompt` to the model and print out the response. The only thing that changes between each run is the `temperature` value.
## Output code
When you run this code, you might see output like the following (your results may vary):

```json
Temperature: 0.0
Response: The Glimmerfox is a small, agile creature with shimmering silver fur and bright blue eyes. It is known for its ability to blend into the moonlit mist of the magical forest, making it nearly invisible to predators and travelers alike.

Temperature: 0.7
Response: The Glimmerfox is a rare animal with iridescent fur that changes color depending on its mood. It has long, feathery ears and a tail that glows softly in the dark. The Glimmerfox is said to bring good luck to anyone who spots it in the magical forest.

Temperature: 1.2
Response: Deep in the magical forest lives the Whimsyhorn, a floating, jelly-like creature with rainbow stripes and a single spiraled antler. It sings lullabies to the trees at night and leaves trails of sparkling dust wherever it drifts.
```

Notice how the response at `temperature` `0.0` is very straightforward and safe, while the response at `0.7` adds more creative details. At `1.2`, the model invents a completely new animal with imaginative features. This shows how increasing the `temperature` leads to more diverse and creative outputs.