"""Instances of the further graph families (Reviewer 3, Concern 1).

Same file format as datasets/path and datasets/cycle: the order N, the N x N adjacency
matrix, and the trivial upper bound N + diam(G) - 1. Files are named by the family
parameter m, which is not the order:

  wheel/m.txt            W_m = K_1 + C_m: hub 0, rim 1..m           N = m + 1,  diam 2 (m >= 4)
  subdivided_star/m.txt  S(K_{1,m}): every edge of the star K_{1,m}
                         subdivided once: centre 0, middle i, leaf m+i  N = 2m + 1, diam 4 (m >= 2)
  ladder/m.txt           L_m = P_m x P_2: vertex (i, j) -> 2i + j     N = 2m,     diam m
  grid/m.txt             P_m x P_m: vertex (i, j) -> m i + j          N = m^2,    diam 2m - 2
  caterpillar/m.txt      T_{m,d} of Saraswathi, Meera and Lin (2025), with d = ceil(m/2):
                         path v_1..v_{d+1}, the other m - d - 1 vertices
                         adjacent to v_2                              N = m,      diam d

  python3 gen_families.py            # writes every family, all sizes in SIZES
"""

import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))

# Sizes written (parameter m). Which of them run is decided by the batch (--min-n/--max-n).
SIZES = {"wheel": range(4, 50), "subdivided_star": range(2, 25), "ladder": range(2, 26),
         "grid": range(2, 8), "caterpillar": range(5, 51)}


def wheel(m):
    return m + 1, [(0, i) for i in range(1, m + 1)] + [(i, i % m + 1) for i in range(1, m + 1)]


def subdivided_star(m):
    return 2 * m + 1, [(0, i) for i in range(1, m + 1)] + [(i, m + i) for i in range(1, m + 1)]


def ladder(m):
    e = [(2 * i, 2 * i + 1) for i in range(m)]
    e += [(2 * i + j, 2 * (i + 1) + j) for i in range(m - 1) for j in (0, 1)]
    return 2 * m, e


def grid(m):
    e = [(m * i + j, m * i + j + 1) for i in range(m) for j in range(m - 1)]
    e += [(m * i + j, m * (i + 1) + j) for i in range(m - 1) for j in range(m)]
    return m * m, e


def caterpillar_d(m):
    return (m + 1) // 2


def caterpillar(m):
    d = caterpillar_d(m)
    return m, [(i, i + 1) for i in range(d)] + [(1, j) for j in range(d + 1, m)]


FAMILIES = {"wheel": wheel, "subdivided_star": subdivided_star, "ladder": ladder,
            "grid": grid, "caterpillar": caterpillar}


def adjacency(n, edges):
    adj = [[0] * n for _ in range(n)]
    for u, v in edges:
        assert u != v and not adj[u][v], (u, v)
        adj[u][v] = adj[v][u] = 1
    return adj


def distances(adj):
    n = len(adj)
    dist = []
    for s in range(n):
        d = [-1] * n
        d[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for v in range(n):
                if adj[u][v] and d[v] < 0:
                    d[v] = d[u] + 1
                    q.append(v)
        assert min(d) >= 0, "graph not connected"
        dist.append(d)
    return dist


def write(name, m):
    n, edges = FAMILIES[name](m)
    adj = adjacency(n, edges)
    diam = max(map(max, distances(adj)))
    os.makedirs(os.path.join(HERE, name), exist_ok=True)
    with open(os.path.join(HERE, name, f"{m}.txt"), "w") as f:
        f.write(f"{n}\n")
        for row in adj:
            f.write(" ".join(map(str, row)) + "\n")
        f.write(f"{n + diam - 1}\n")
    return n, len(edges), diam


def main():
    for name, sizes in SIZES.items():
        rows = [(m, *write(name, m)) for m in sizes]
        print(f"{name}: m = {sizes.start}..{sizes.stop - 1}, "
              f"order {rows[0][1]}..{rows[-1][1]}, diam {rows[0][3]}..{rows[-1][3]}")


if __name__ == "__main__":
    sys.exit(main())
