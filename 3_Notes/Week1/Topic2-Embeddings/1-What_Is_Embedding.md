# What is Embedding?
Embeddings are representations of values or objects like text, images, and audio that are designed to be consumed by machine learning models and semantic search algorithms. They translate objects like these into a mathematical form according to the factors or traits each one may or may not have, and the categories they belong to.

Essentially, embeddings enable machine learning models to find similar objects. Given a photo or a document, a machine learning model that uses embeddings could find a similar photo or document. Since embeddings make it possible for computers to understand the relationships between words and other objects, they are foundational for artificial intelligence (AI).

Technically, embeddings are _vectors_ created by machine learning models for the purpose of capturing meaningful data about each object.
**For example,** 
1. The documents in the upper right of this two-dimensional space may be relevant to each other:
![[Pasted image 20251221091333.png]]

2. A bird-nest and a lion-den are analogous pairs, while day-night are opposite terms. Embeddings convert real-world objects into complex mathematical representations that capture inherent properties and relationships between real-world data.
---
# How do embeddings work?
Most machine learning algorithms can only take low-dimensional numerical data as inputs. Therefore, it is necessary to convert the data into a numerical format. This can involve things like creating a “bag of words” representation for text data, converting images into pixel values or transforming graph data into a numerical matrix.

Objects that come into an embedding model are output as embeddings, represented as vectors. A vector is an array of numbers (e.g. 1489, 22… 3, 777), where each number indicates where an object is along a specified dimension. The number of dimensions can reach a thousand or more depending on the input data’s complexity. The closer an embedding is to other embeddings in this n-dimensional space, the more similar they are. Distribution similarity is determined by the length of the vector points from one object to the other (measured by Euclidean, cosine or other).

Here is how two words, “dad” and “mom” would be represented as vectors:

 “dad”=[0.1548,0.4848,…,1.864] 

 “mom”=[0.8785,0.8974,…,2.794] 

Although there is some similarity between these two words, we would expect that “father” would live in much closer proximity to “dad” in the vector space, resulting in a higher dot product (_a measure of the relative direction of two vectors and how closely they align in the direction they point_).

A more complex example is recommendation embedding, which works by representing users and items (e.g., movies, products, articles) as high-dimensional vectors in a continuous vector space. These embeddings capture latent features that reflect users' preferences and item characteristics. The idea is to learn a representation for each user and item in such a way that the dot product of their embeddings correlates with the user's preference for that item.

Each user and item is associated with an embedding vector. These vectors are typically learned through a recommendation model during a training process. The user embeddings and item embeddings are organized into matrices. The rows of the user matrix represent users, and the rows of the item matrix represent items.

The recommendation score for a user-item pair can be computed by taking the dot product of the user's embedding vector and the item's embedding vector. The higher the dot product, the more likely the user is to be interested in the item.

RecommendationScore = UserEmbedding ⋅ ItemEmbedding 

The embedding matrices are learned through a training process using historical user-item interactions. The model aims to minimize the difference between predicted scores and actual user preferences (e.g., ratings, clicks, purchases).

Once the model is trained, it can be used to generate top-N recommendations for users. The items with the highest predicted scores for a user are recommended.

---
# Why use embedding?
Embeddings are used in various domains and applications due to their ability to transform high-dimensional and categorical data into continuous vector representations, capturing meaningful patterns, relationships and semantics. Below are a few reasons why embedding is used in data science:
## Semantic representation
By mapping entities (words, images, nodes in a graph, etc.) to vectors in a continuous space, embeddings capture semantic relationships and similarities, enabling models to understand and generalize better.
## Dimensionality reduction
High-dimensional data, such as text, images or graphs, can be transformed into lower-dimensional representations, making it computationally efficient and easier to work with.
## Improved generalization of models
By learning meaningful representations from data, models can generalize well to unseen examples, making embeddings crucial for tasks with limited labeled data.
## Effective visualization
Techniques like t-SNE can be applied to visualize high-dimensional embeddings in two or three dimensions, providing insights into the relationships and clusters in the data.
## Efficient training in neural networks
Embedding layers are commonly used in neural network architectures to map categorical inputs to continuous vectors, facilitating backpropagation and optimization.

---
# What objects can be embedded?
Embeddings are versatile representations that can be applied to a wide range of data types. Here are some of the most common objects that can be embedded:
## Words
Word embeddings capture the semantic relationships and contextual meanings of words based on their usage patterns in a given language corpus. Each word is represented as a fixed-sized dense vector of real numbers. It is the opposite of a sparse vector, such as one-hot encoding, which has many zero entries.
The use of word embedding has significantly improved the performance of natural language processing (NLP) models by providing a more meaningful and efficient representation of words. These embeddings enable machines to understand and process language in a way that captures semantic nuances and contextual relationships, making them valuable for a wide range of applications, including sentiment analysis, machine translation and information retrieval.
Popular word embedding models include Word2Vec, GloVe (Global Vectors for Word Representation), FastText and embeddings derived from transformer-based models like BERT (Bidirectional Encoder Representations from Transformers) and GPT (Generative Pre-trained Transformer).
## Text
Text embedding extends word embedding to represent entire sentences, paragraphs or documents in a continuous vector space. Text embeddings play a crucial role in various NLP applications, such as sentiment analysis, text classification, machine translation, question answering and information retrieval.
Models like Doc2Vec, USE (Universal Sentence Encoder), BERT and ELMO (Embeddings from Language Models) have been trained on massive amounts of pre-trained embedding corpora, such as Wikipedia and Google News.
## Images
Image embedding is designed to capture visual features and semantic information about the content of images. Image embeddings are particularly useful for various computer vision tasks, enabling the modeling of image similarities, image classification, object detection and other visual recognition tasks.
Popular Convolutional Neural Networks (CNNs) for image embeddings include models like VGG (Visual Geometry Group), ResNet (Residual Networks), Inception (GoogLeNet) and EfficientNet. These models have been pre-trained on large-scale image datasets and can be used as powerful feature extractors.
## Audio
Similar to image and text embeddings, audio embeddings are often generated using deep learning architectures, particularly recurrent neural networks (RNNs), convolutional neural networks (CNNs) or hybrid models that combine both. These embeddings capture the relevant features and characteristics of audio data, allowing for effective analysis, processing and similarity metrics. Audio embeddings are particularly useful in applications such as speech recognition, audio classification and music analysis, among others.
## Graphs
Graph embedding is essential for various tasks, including node classification, link prediction and community detection in complex networks. These embeddings find applications in social network analysis, recommendation systems, biological network analysis, fraud detection and various other domains where data can be represented as graphs.

---
# How embeddings are created
Embeddings are created through a process called "embedding learning." Although the specific method used depends on the type of data being embedded, embeddings are created following these general steps:
1. **Choose or train an embedding model:** Select a pre-existing embedding model suitable for your data and task, or train a new one if necessary. For text, you might choose Word2Vec, GloVe, or BERT. For images, you might use pre-trained CNNs like VGG or ResNet.  
2. **Prepare your data:** Format your data in a way that is compatible with the chosen embedding model. For text, this involves tokenization and possibly preprocessing. For images, you may need to resize and normalize the images.  
3. **Load or train the embedding model:** If using a pre-trained model, load the weights and architecture. If training a new model, provide your prepared training data to the algorithm.  
4. **Generate embeddings:** For each data point, use the trained or loaded model to generate embeddings. For example, if using a word embedding model, input a word to get its corresponding vector.     
5. **Integrate embeddings into your application:** Use the generated embeddings as features in your machine learning model, or for similarity search, recommendation, clustering, etc., depending on your specific task.  

In all embedding cases, the idea is to represent data in a continuous vector space where meaningful relationships are preserved. The training process involves adjusting the parameters of the model to minimize the difference between predicted and actual values based on the chosen objective function. Once trained, the embeddings can be used for various downstream tasks.

---
# Real-world examples of embedding
Embeddings are widely used in various real-world applications across different domains. Examples include:
## Natural Language Processing (NLP)
- **Word embeddings in sentiment analysis:** Word embeddings like Word2Vec or GloVe are used to represent words in a continuous vector space. Sentiment analysis models can leverage these embeddings to understand and classify the sentiment of a piece of text.  
- **BERT for question answering:** BERT embeddings are used in question-answering systems. The model can understand the context of the question and the document to extract relevant information.  
- **Text similarity with Doc2Vec:** Doc2Vec embeddings are applied in tasks like finding similar documents. Document embeddings are compared to measure semantic similarity between documents.
## Computer vision
- **Image classification with CNNs:** CNNs, such as VGG or ResNet, are employed for image classification tasks. The final layer or intermediate layers' features can serve as image embeddings.  
- **Image retrieval using CLIP:** The CLIP model learns joint embeddings for images and text. This enables applications like image retrieval based on natural language queries.  
- **Facial recognition with FaceNet:** FaceNet creates embeddings for faces that can be used for facial recognition. These embeddings are often used to measure the similarity between different faces.
## Recommender systems
- **Collaborative filtering with embeddings:** Embeddings are used to represent users and items in collaborative filtering models. Matrix factorization methods leverage these embeddings to make personalized recommendations.  
- **Product recommendations with word embeddings:** In e-commerce, product descriptions or reviews can be embedded using word embeddings. Similar products can be recommended based on the semantic similarity of their embeddings.
## Cross-modal applications
- **Multimodal translation with MUSE:** MUSE (Multilingual Universal Sentence Encoder) enables cross-lingual and cross-modal understanding. It can be used for tasks like translating text between languages or connecting images with corresponding descriptions.  
- **Cross-modal search using joint embeddings:** Joint embeddings are learned for different modalities, such as images and text. This allows for cross-modal search, where a query in one modality retrieves results in another modality.
## Anomaly detection
- **Network anomaly detection with graph embeddings:** Embeddings of network nodes can be used to detect anomalies. Changes in the embedding space might indicate unusual behavior.  
- **Fraud detection with transaction embeddings:** Embeddings of transaction data can help identify patterns associated with fraudulent activities. Unusual embeddings may indicate potentially fraudulent transactions.

These examples highlight the versatility of embeddings across diverse applications, showcasing their ability to capture meaningful representations and relationships in different types of data.