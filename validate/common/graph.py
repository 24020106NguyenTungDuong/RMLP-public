import math
from collections import deque


def all_pairs_bfs(adj):
    n = len(adj)
    INF = math.inf
    dist = [[INF] * n for _ in range(n)]

    for s in range(n):
        queue = deque([s])
        dist[s][s] = 0

        while queue:
            u = queue.popleft()
            for v in range(n):
                if adj[u][v] != 0 and dist[s][v] == INF:
                    dist[s][v] = dist[s][u] + 1
                    queue.append(v)

    return dist


def diameter(dist_matrix):
    n = len(dist_matrix)
    diam = 0
    for i in range(n):
        for j in range(n):
            if dist_matrix[i][j] < math.inf:
                diam = max(diam, int(dist_matrix[i][j]))
    return diam


def find_distance_twins(dist_matrix):
    """Groups vertices into "distance twin" classes: u, v are twins if
    dist(u, w) == dist(v, w) for every other vertex w. RML's constraints
    depend only on pairwise distances, so any permutation of labels among
    twins yields an equally valid labeling with the same span -- a class can
    safely be given a canonical label order without excluding any achievable
    k. This is a sufficient but not necessary condition for interchangeability
    (it misses swaps induced by non-trivial automorphisms that aren't plain
    twins, e.g. a 5-cycle's reflection).

    Returns a list of classes, each a sorted list of >=2 vertex indices;
    vertices with no twin are omitted entirely.
    """
    n = len(dist_matrix)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for u in range(n):
        for v in range(u + 1, n):
            if all(dist_matrix[u][w] == dist_matrix[v][w]
                   for w in range(n) if w != u and w != v):
                union(u, v)

    classes = {}
    for v in range(n):
        classes.setdefault(find(v), []).append(v)

    return [sorted(c) for c in classes.values() if len(c) >= 2]
