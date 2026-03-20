# Similarity Search: Approximate Nearest Neighbor (ANN) Algorithms

## The Problem: Exact Search Doesn't Scale

The key operation of vector databases is similarity search, which involves finding the nearest neighbors in the database to a query vector. A naive method would calculate the distance from the query vector to every vector stored in the database and take the top-K closest. However, this clearly does not scale as the size of the database grows.

If we did a brute-force approach to find the top k closest neighbours for a given vector, we would have to do this search in O(N) time, as we need to compute the pairwise distance between the query vector and every other vector.

The math is brutal:

- 1 million vectors × 1536 dimensions × 4 bytes = ~6GB just to scan
- Every query touches every vector
- Query latency grows linearly with data size

In practice, a naive similarity search is practical only for databases with fewer than around 1 million vectors.

---

## The Trade-off: Speed vs Accuracy

Using approximate nearest neighbour (ANN) index search instead of exact search offers a significant advantage in terms of computational efficiency, especially at scale. In an exact search, every query involves scanning the entire dataset to find the closest neighbors, leading to a time complexity of O(N), where N is the size of the dataset.

ANN algorithms accept a trade-off: **you might not get the mathematically perfect top-k, but you'll get very close results very fast.**

|Approach|Time Complexity|Accuracy|Use Case|
|---|---|---|---|
|Exact (brute force)|O(N)|100%|Small datasets (<1M vectors)|
|ANN (HNSW, IVF, etc.)|O(log N)|95-99%+|Production scale|

We will see later that HNSW allows us to do this in O(log N).

---

## Categories of ANN Algorithms

Approximate nearest-neighbor search (ANN) can be divided into three primary categories, each defined by its foundational data structures: trees, hashes, and graphs. Trees hierarchically organize data, allowing for binary decisions at each node to navigate closer to the query point. Hashes convert data points into codes in a lower-dimensional space, grouping similar items into the same buckets for faster retrieval. Graphs create a network of points where edges connect neighbors based on similarity measures.

|Category|Examples|Idea|
|---|---|---|
|**Tree-based**|KD-Tree, Ball Tree|Partition space recursively, prune branches|
|**Hash-based**|LSH (Locality Sensitive Hashing)|Hash similar vectors to same bucket|
|**Graph-based**|HNSW, NSW|Navigate graph of connected neighbors|
|**Cluster-based**|IVF (Inverted File)|Cluster vectors, search relevant clusters only|

**HNSW (Hierarchical Navigable Small Worlds)** is the dominant choice in modern vector databases.

---

## HNSW: The Mental Model

Hierarchical Navigable Small World (HNSW) graphs are among the top-performing indexes for vector similarity search. HNSW is a hugely popular technology that time and time again produces state-of-the-art performance with super fast search speeds and fantastic recall.

The Hierarchical navigable small world (HNSW) algorithm is a graph-based approximate nearest neighbor search technique used in many vector databases.

### Building Block 1: Navigable Small World (NSW)

Imagine your vectors as cities. Instead of checking every city to find the closest one to your destination, you build roads between nearby cities:

NSW is a graph-based algorithm that finds approximate nearest neighbors in a dataset. The general idea is first to imagine many nodes in a network. Each node will have short-, medium-, and long-range connections to other nodes. When performing a vector search, we'll begin at some pre-defined entry point. From there, we'll evaluate connections to other nodes and jump to the one closest to the one we hope to find. This process repeats until we've found our nearest neighbor. This type of search is called greedy search.

**Greedy search:** At each step, jump to the neighbor that's closest to your target. Repeat until you can't improve.

### Building Block 2: The Hierarchy (Skip List Concept)

Plain NSW breaks down at scale. HNSW adds **layers**:

HNSW extends NSW by borrowing from the concept of skip lists. Like the skip list, HNSW maintains multiple layers (hence the term Hierarchical Navigable Small World), only of NSWs instead of linked lists. The uppermost layer of an HNSW graph has few nodes and the longest links, while the bottommost layer has all nodes and the shortest links.

```
Layer 3:  [A] -------- [E] -------------------- [M]     (few nodes, long jumps)
           |            |                        |
Layer 2:  [A] --- [C] - [E] -------- [H] ------ [M]     (more nodes)
           |       |     |            |          |
Layer 1:  [A]-[B]-[C]-[D][E]-[F]-[G]-[H]-[I]-...-[M]    (all nodes, short links)
```

The hierarchical structure of HNSW is fundamentally a set of layered graphs, each representing the dataset with varying degrees of abstraction. The top layer has the fewest nodes and serves as the entry point for search queries, facilitating rapid traversal across the data space.

### How Search Works

Starting the search: The ANN search begins at the top layer of the HNSW graph, which has the fewest nodes (vectors). The aim is to find a node that serves as a good entry point because it's close to the query vector in the vector space.

1. **Start at top layer** — few nodes, big jumps, rough approximation
2. **Greedy descent** — at each layer, navigate to the closest neighbor to your query
3. **Drop down** — once you can't improve in current layer, descend to next layer
4. **Bottom layer** — all nodes present, fine-grained search
5. **Return top-k** — the closest candidates found

Gathering candidates: As the search progresses to lower layers, it's not just about finding a single vector closest to the query. The algorithm collects a set of candidate vectors that are close to the query vector, effectively gathering a "pool" of potential nearest neighbours.

---

## Key HNSW Parameters

### Construction Parameters

|Parameter|What It Does|
|---|---|
|`M`|Number of connections per node. Higher = better recall, more memory/slower build|
|`ef_construction`|Size of dynamic candidate list during build. Higher = better graph quality, slower build|
##### `ef_construction` Explained

Think of building a road network between cities.

**The scenario:** You're adding a new city (vector) to your map. You need to decide which existing cities to connect it to with roads (graph edges).

**The naive approach:** Check every existing city, find the closest ones, connect to those. Works perfectly, but if you have 1 million cities, that's 1 million distance calculations per insertion. Too slow.

**The `ef_construction` approach:** Instead of checking every city, you maintain a "candidate shortlist" of size `ef_construction`. As you explore the graph looking for good neighbors:

- You keep the best `ef_construction` candidates you've found so far
- When you find a better candidate, it bumps out the worst one on your list
- You stop exploring when your shortlist stops improving

**Concrete example:**

`ef_construction = 16`:

- You explore the graph, keeping track of the 16 best neighbor candidates
- Once you can't find anything better than your worst candidate, you stop
- You connect to the top M of those 16 (say, M=8)

`ef_construction = 200`:

- You keep 200 candidates in your shortlist
- You explore much more of the graph before giving up
- You're more likely to find the _truly_ best neighbors, not just locally-good ones
- But you did way more work to get there

**The trade-off:**

| `ef_construction` | Graph Quality                                   | Build Time |
| ----------------- | ----------------------------------------------- | ---------- |
| Low (16-32)       | May miss good connections, search later suffers | Fast       |
| High (100-200)    | Better connections found, search more accurate  | Slow       |

**Why "graph quality" matters:** If you connect a new node to suboptimal neighbors during construction, every future search that passes through that node has worse options to explore. Bad early decisions compound.

It's like building highways — if you rush and connect cities to merely "pretty close" neighbors instead of the _best_ neighbors, navigation through your network is forever slightly worse.
### Search Parameters

|Parameter|What It Does|
|---|---|
|`ef_search` (or `ef`)|Size of candidate list during query. Higher = better accuracy, slower search|

Higher ef_search: Increases the search accuracy because the algorithm considers more candidate nodes. However, this also increases the search time since more nodes are being evaluated. Lower ef_search: Speeds up the search but might decrease accuracy.

**The tuning knob:** `ef_search` is your accuracy/speed dial at query time.

---

## ChromaDB and HNSW

ChromaDB uses HNSW by default. You can configure it at collection creation:

```python
collection = client.create_collection(
    name="my_collection",
    metadata={
        "hnsw:space": "cosine",        # Distance metric
        "hnsw:M": 16,                   # Connections per node
        "hnsw:ef_construction": 100     # Build-time candidate list size
    }
)
```

Chroma uses its own fork of HNSW lib for indexing and searching embeddings. In addition to HNSW, Chroma also uses a Brute Force index, which acts as a buffer (prior to updating the HNSW graph) and performs exhaustive search using the same distance metric as the HNSW index.

This buffer behavior matters: very recent additions might not be in the HNSW graph yet.

---
## IVF (Inverted File Index): The Clustering Approach

Instead of building a graph, IVF **partitions** your vectors into clusters upfront.

### How It Works

**Build phase:**

1. Run k-means on your vectors to create `nlist` centroids (cluster centers)
2. Assign each vector to its nearest centroid
3. Store vectors grouped by cluster

**Query phase:**

1. Find the `nprobe` closest centroids to your query vector
2. Search only the vectors in those clusters
3. Return top-k from that subset

```
┌─────────────────────────────────────────────────────────┐
│                    Vector Space                         │
│                                                         │
│     ┌──────┐      ┌──────┐      ┌──────┐               │
│     │  C1  │      │  C2  │      │  C3  │   ← Centroids │
│     │ •••• │      │ •••  │      │•••••••│              │
│     │  ••  │      │••••  │      │ ••••  │              │
│     └──────┘      └──────┘      └──────┘               │
│                                                         │
│  Query: Find nearest to Q                               │
│  Step 1: Q is closest to C2 and C3 (nprobe=2)          │
│  Step 2: Search only vectors in C2 and C3              │
└─────────────────────────────────────────────────────────┘
```

### Key Parameters

|Parameter|What It Does|
|---|---|
|`nlist`|Number of clusters. Higher = more partitions, faster search, risk of missing neighbors at cluster boundaries|
|`nprobe`|Clusters to search at query time. Higher = better recall, slower search|

**Rule of thumb:** `nlist` ≈ sqrt(N) where N is vector count. `nprobe` is your accuracy/speed knob at query time (like `ef_search` in HNSW).

### IVF vs HNSW Trade-offs

|Aspect|IVF|HNSW|
|---|---|---|
|Build time|Faster (k-means + assignment)|Slower (graph construction)|
|Memory|Lower (just centroids + assignments)|Higher (graph edges)|
|Update handling|Poor (re-clustering needed)|Good (incremental inserts)|
|Recall at same speed|Lower|Higher|
|Predictability|More predictable latency|Can vary with graph structure|

**When to use IVF:**

- Very large datasets where HNSW memory is prohibitive
- Static data (no frequent updates)
- Combined with quantization (IVF-PQ) for compression

**When to use HNSW:**

- Default choice for most use cases
- Data changes frequently
- Need best recall/speed ratio

ChromaDB uses HNSW. You'll encounter IVF in FAISS and Pinecone (often as IVF-PQ).

---

## Flat Index: The Baseline

"Flat" means no index — brute force exact search.

```python
# In FAISS
index = faiss.IndexFlatL2(dimension)  # Exact search, O(N) every query
```

Use flat index when:

- Dataset is small (<100K vectors)
- You need guaranteed 100% recall
- You're debugging and want ground truth

---

## Why "Approximate" Is Usually Fine

Total hit count is not accurate: Technically, all vectors in the searchable index are neighbors. There is no strict boundary between a match and no match.

In RAG and semantic search:

- You're grabbing top-5 or top-10 chunks to feed an LLM
- Whether you get the #1 and #3 most similar vs #1 and #2 rarely matters
- 95% recall at 10ms beats 100% recall at 500ms

The semantic similarity scores themselves are fuzzy — obsessing over exact top-k is misplaced precision.

---

## When Approximate Fails

Watch out for:

- **Small datasets** — ANN overhead not worth it; use flat
- **Extreme filtering** — if metadata filters eliminate most vectors, you might miss good candidates
- **Very high-k queries** — retrieving top-1000 is harder to approximate than top-10

The HNSW greedy search algorithm is sublinear (close to log(N) where N is the number of vectors in the graph). Still, flat scaling helps scale document volume, and increasing indexing throughput as vectors are partitioned randomly over a set of nodes.

---

## Summary: The Trade-off in One Picture

```
                    Accuracy
                       ↑
                       │
        Exact Search   │  ████████████████  (100% recall)
        (Flat/Brute)   │                     O(N) time
                       │
        HNSW (high ef) │  ██████████████    (~99% recall)
                       │                     O(log N) time
                       │
        HNSW (low ef)  │  ████████████      (~95% recall)
                       │                     O(log N) faster
                       │
                       └──────────────────→ Speed
```

**The key insight:** ANN algorithms like HNSW don't search less data — they **organize** data so you can navigate to relevant regions without scanning everything. The hierarchy lets you skip irrelevant neighborhoods entirely.

---
## Side Notes

### 1. ef_construction vs ef_search: The Library Analogy

Imagine you're building a library with a special navigation system.
#### ef_construction (Build Time)

You're **organizing the library**. For each new book you shelve, you need to decide which other books to connect it to (via index cards that say "see also...").

`ef_construction` = how many candidate books you consider before deciding on connections.

- **Low ef_construction (say 64):** You glance at 64 nearby books, pick the best connections, move on. Fast to build, but you might miss some ideal connections.
- **High ef_construction (say 200):** You examine 200 books carefully before choosing connections. Slower to build, but the "see also" links are higher quality.

Once the library is built, **these connections are permanent**. You can't improve them without rebuilding.

#### ef_search (Query Time)

A visitor walks in looking for a specific topic. They start at the entrance and follow "see also" links.

`ef_search` = how many candidate books they keep track of while navigating.

- **Low ef_search (say 10):** They maintain a short list of 10 promising books as they walk. Fast, but they might miss a better book because they pruned their list too aggressively.
- **High ef_search (say 100):** They track 100 candidates as they explore. Slower, but more likely to find the true best matches.

#### The Key Difference

|Parameter|When It Matters|What It Affects|Can Be Changed?|
|---|---|---|---|
|`ef_construction`|Index build time|Quality of graph connections|No — baked into index|
|`ef_search`|Query time|Accuracy of each search|Yes — per query|

**ef_construction sets the ceiling.** If you built a sloppy graph (low ef_construction), no amount of ef_search will fix it — the good paths simply don't exist.

**ef_search operates within that ceiling.** Given a well-built graph, you choose how carefully to explore it per query.

---

### 2. Why Is ef_construction Set During Construction?

It's not a "search parameter set during construction" — it's a **construction parameter** that determines how thoroughly you build the graph.

Think of it this way:

```
ef_construction = 200
```

This means: "When inserting vector X, find its 200 nearest candidate neighbors, then pick the best M to actually link to."

The search happens _during construction_ to find good neighbors for the new node. It's not the same as the user's query-time search — it's an internal search the algorithm runs while building.

**Why not just use brute force during construction?**

You could — but construction would be O(N²) instead of O(N log N). The whole point is that HNSW uses its own graph-in-progress to find neighbors for new insertions. ef_construction controls how hard it looks.

---
#### The Mental Model

```
BUILD PHASE (once):
┌─────────────────────────────────────────────────────────┐
│  For each vector being inserted:                        │
│    1. Search existing graph for neighbors               │
│       (search quality controlled by ef_construction)    │
│    2. Create links to best M neighbors                  │
│    3. Graph gets better, next insert benefits           │
└─────────────────────────────────────────────────────────┘
         │
         ▼
    FROZEN GRAPH (the index)
         │
         ▼
QUERY PHASE (many times):
┌─────────────────────────────────────────────────────────┐
│  For each user query:                                   │
│    1. Navigate frozen graph toward query vector         │
│       (exploration width controlled by ef_search)       │
│    2. Return top-k candidates found                     │
└─────────────────────────────────────────────────────────┘
```

**ef_construction** = how carefully you wired the building.

**ef_search** = how carefully you explore that building when looking for something.

You can't rewire the building at query time — but you can choose to search more thoroughly within whatever wiring exists.