# What is a vector in machine learning?

In mathematics, a vector is an array of numbers that define a point in a dimensional space. In more practical terms, a vector is a list of numbers — like {1989, 22, 9, 180}. Each number indicates where the object is along a specified dimension.

In machine learning, the use of vectors makes it possible to search for similar objects. A vector-searching algorithm simply has to find two vectors that are close together in a vector database.

To understand this better, think about latitude and longitude. These two dimensions — north-south and east-west, respectively — can indicate the location of any place on Earth. The city of Vancouver, British Columbia, Canada can be represented as the latitude and longitude coordinates {49°15'40"N, 123°06'50"W}. This list of two values is a simple vector.

Now, imagine trying to find a city that is very near Vancouver. A person would just look at a map, while a machine learning model could instead look at the latitude and longitude (or vector) and find a place with a similar latitude and longitude. The city of Burnaby is at {49°16'N, 122°58'W} — very close to {49°15'40"N, 123°06'50"W}. Therefore, the model can conclude, correctly, that Burnaby is located near Vancouver.
## Adding more dimensions to vectors
Now, imagine trying to find a city that is not only close to Vancouver, but of similar size. To this model of locations, let us add a third "dimension" to latitude and longitude: population size. Population can be added to each city's vector, and population size can be treated like a Z-axis, with latitude and longitude as the Y- and X-axes.

The vector for Vancouver is now {49°15'40"N, 123°06'50"W, 662,248*}. With this third dimension added, Burnaby is no longer particularly close to Vancouver, as its population is only 249,125*. The model might instead find the city of Seattle, Washington, US, which has a vector of {47°36'35"N 122°19'59"W, 749,256**}.

_*As of 2021.  
**As of 2022._

This is a fairly simple example of how vectors and similarity search work. But to be of use, machine learning models may want to generate more than three dimensions, resulting in much more complex vectors.
## Even more multi-dimensional vectors
For instance, how can a model tell which TV shows are similar to each other, and therefore likely to be watched by the same people? There are any number of factors to take into account: episode length, number of episodes, genre classification, number of viewers in common, actors in each show, year each show debuted, and so on. All of these can be "dimensions," and each show represented as a point along each of these dimensions.

Multi-dimensional vectors can help us determine if the sitcom _Seinfeld_ is similar to the horror show _Wednesday_. _Seinfeld_ debuted in 1989, _Wednesday_ in 2022. The two shows have different episode lengths, with _Seinfeld_ at 22-24 minutes and _Wednesday_ at 46-57 minutes — and so on. By looking at their vectors, we can see that these shows likely occupy very different points in a dimensional representation of TV shows.

| TV show   | Genre  | Year debuted | Episode length | Seasons (through 2023) | Episodes (through 2023) |
| --------- | ------ | ------------ | -------------- | ---------------------- | ----------------------- |
| Seinfeld  | Sitcom | 1989         | 22-24          | 9                      | 180                     |
| Wednesday | Horror | 2022         | 46-57          | 1                      | 8                       |
We can express these as vectors, just as we did with latitude and longitude, but with more values:

_Seinfeld_ vector: {[Sitcom], 1989, 22-24, 9, 180}  
_Wednesday_ vector: {[Horror], 2022, 46-57, 1, 8}

A machine learning model might identify the sitcom _Cheers_ as being much more similar to _Seinfeld_. It is of the same genre, debuted in 1982, features an episode length of 21-25 minutes, has 11 seasons, and has 275 episodes.

_Seinfeld_ vector: {[Sitcom], 1989, 22-24, 9, 180}  
_Cheers_ vector: {[Sitcom], 1982, 21-25, 11, 275}

In our examples above, a city was a point along the two dimensions of latitude and longitude; we then added a third dimension of population. We also analyzed the location of these TV shows along five dimensions.

Instead of two, three, or five dimensions, a TV show within a machine learning model is a point along perhaps a hundred or a thousand dimensions — however many the model wants to include.

---
# What Are Vector Dimensions?
Every vector has **dimensions**. You can think of each dimension as a question that helps define the meaning of a word or sentence. In the above example, the vectors had five numbers so they were **five-dimensional**.
But real AI systems use **hundreds or thousands** of dimensions. For example:
- Some embedding models use 384 dimensions
- Others use 768 or even 1536 dimensions 

Each dimension captures a tiny part of the meaning. One might represent tone (positive or negative). Another might reflect time (past or future). Others might represent gender, formality, object types, actions, or abstract ideas.

The more dimensions we have, the better the AI can understand nuance and context.

---
# Explaining Vector Dimensions with an Analogy
Let’s imagine you are describing people using numbers. If we only had one number (one dimension), we might use height:
- Alice = 1.70
- Bob = 1.80
- Carla = 1.75 

But now let’s add another dimension: weight.  
Now we have:
- Alice = [1.70, 60] 
- Bob = [1.80, 85]
- Carla = [1.75, 70]

This gives us a better picture. Now imagine we add **1000 features** for each person  age, job, voice tone, favorite color, shoe size, etc. That is what a high-dimensional vector is. In AI, each sentence is described in this kind of space.
That is the idea of _Vector Dimensions in AI_. The AI builds a big mental map, where similar meanings are located close to each other, even if the words are totally different.

---
# Vector Dimensions Note

## Vector Dimensions in Text Embeddings
**Dimension count = length of the vector array**
- 384 dimensions = `[0.23, -0.15, ..., 0.42]` (384 numbers)
- 768 dimensions = array with 768 numbers
- 1536 dimensions = array with 1536 numbers (OpenAI `text-embedding-3-small`)
- 3072 dimensions = array with 3072 numbers (OpenAI `text-embedding-3-large`)
## The Trade-Off
**More dimensions = more nuance, but higher cost**

| Dimension Size | Accuracy | Speed   | Storage Cost | Use Case                              |
| -------------- | -------- | ------- | ------------ | ------------------------------------- |
| 384            | Lower    | Fast    | Cheap        | Basic similarity, large-scale systems |
| 768            | Medium   | Medium  | Medium       | Balanced performance                  |
| 1536           | Good     | Slower  | Higher       | Most production RAG systems           |
| 3072           | Best     | Slowest | Highest      | High-accuracy requirements            |
## Production Decision
When building RAG:
- **Storage:** 3072 numbers per document vs 384 numbers per document
- **Speed:** Comparing 3072-dim vectors takes longer than 384-dim
- **Accuracy:** Higher dimensions usually mean better retrieval quality
**Most teams start with 1536-dim (good balance), then optimize if needed.**

**Key insight:** Unlike the Cloudflare TV show example (5 hand-picked dimensions), text embeddings use hundreds/thousands of learned dimensions. You don't know what each dimension means — the model figured it out during training.

---
