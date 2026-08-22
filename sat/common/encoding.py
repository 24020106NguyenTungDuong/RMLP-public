"""SAT clause generators for the Radio Mean Labeling encoding.

Two variable families are used across the solver variants:
  G(i, j): vertex i's label is >= j (a "thermometer": G(i, j+1) implies G(i, j),
           checked by monotonicity()).
  x(i, j): vertex i's label is exactly j (only in the "x_and_g" scheme; linked
           to G via x_to_G()).

Callers build get_var_G/get_var_x once (see var_G_only/var_G_with_x/var_x)
and pass them into these generators; this module has no notion of the graph
or which search bound is "current" versus "initial".
"""


def var_G_only(i, j, n):
    """G-only scheme: G is the sole variable family, no offset needed."""
    return (j - 1) * n + i + 1


def var_G_with_x(i, j, n, k_max):
    """x_and_g scheme: G is offset behind the n*k_max x variables.

    k_max must be the fixed initial search bound, not the current (shrinking)
    search bound -- SAT variable IDs must stay stable across the incremental
    solve.
    """
    return n * k_max + (j - 1) * n + i + 1


def var_x(i, j, n):
    return (j - 1) * n + i + 1


def monotonicity(n, k, get_var_G):
    result = []
    for i in range(n):
        for j in range(1, k + 1):
            result.append([get_var_G(i, j), -get_var_G(i, j + 1)])
    return result


def upper_bound(n, k, get_var_G):
    return [[-get_var_G(i, k + 1)] for i in range(n)]


def lower_bound(n, k, get_var_G):
    """Forces every vertex's label into the top window [k-n+1, k].

    Not a general necessary condition on its own -- it's a search heuristic
    used as a per-iteration assumption across most variants. Kept as-is.
    """
    return [[get_var_G(i, k - n + 1)] for i in range(n)]


def trivial_lower_bound(n, get_var_G):
    """The weaker 'every label >= 1' floor used by the cycle fix_1 variant,
    which relies on previous_label()/symmetry_breaking_cycle() instead of the
    top-window packing trick in lower_bound()."""
    return [[get_var_G(i, 1)] for i in range(n)]


def forbid_k(n, k, get_var_G):
    return [[-get_var_G(i, k)] for i in range(n)]


def injectivity_only_g(n, k, get_var_G):
    """No x variables: encode 'i1 and i2 can't both have label exactly j'
    directly on G as a 4-literal clause."""
    result = []
    for i1 in range(n):
        for i2 in range(i1 + 1, n):
            for j in range(1, k + 1):
                result.append([-get_var_G(i1, j), get_var_G(i1, j + 1),
                               -get_var_G(i2, j), get_var_G(i2, j + 1)])
    return result


def injectivity_x(n, k, get_var_x):
    result = []
    for i1 in range(n):
        for i2 in range(i1 + 1, n):
            for j in range(1, k + 1):
                result.append([-get_var_x(i1, j), -get_var_x(i2, j)])
    return result


def x_to_G(n, k, get_var_G, get_var_x):
    """x(i,j) <-> G(i,j) AND NOT G(i,j+1)."""
    result = []
    for i in range(n):
        for j in range(1, k + 1):
            result.append([-get_var_x(i, j), get_var_G(i, j)])
            result.append([-get_var_x(i, j), -get_var_G(i, j + 1)])
            result.append([-get_var_G(i, j), get_var_G(i, j + 1), get_var_x(i, j)])
    return result


def rml(n, k, diam, dist_matrix, get_var_G):
    """Forbid label pairs violating h(i1)+h(i2) >= 2*(diam-d)+1.

    Pairs at distance diam or diam-1 are skipped: the minimum sum of two
    distinct positive labels is 1+2=3, which already clears the threshold
    (<=2) at those distances, so the clause would be a tautology.
    """
    result = []
    for i1 in range(n):
        for i2 in range(i1 + 1, n):
            d = int(dist_matrix[i1][i2])
            if d >= diam - 1:
                continue
            h = 2 * (diam - d)
            for j in range(1, k + 1):
                if 1 <= h - j <= k:
                    result.append([get_var_G(i1, j + 1), get_var_G(i2, h - j + 1)])
    return result


def previous_label(n, k, diam, dist_matrix, get_var_G, get_var_x):
    """Strengthens rml() into direct implications for better unit propagation
    (the core improvement introduced by the cycle 'fix_1' variant)."""
    result = []
    for i in range(n):
        for j in range(i + 1, n):
            for l in range(1, k + 1):
                h = 2 * (diam - dist_matrix[i][j]) + 1 - l
                if h > k:
                    result.append([-get_var_x(i, l)])
                    result.append([-get_var_x(j, l)])
                elif 1 < h <= k:
                    result.append([-get_var_x(i, l), get_var_G(j, h)])
                    result.append([-get_var_x(j, l), get_var_G(i, h)])
    return result


def symmetry_breaking_cycle(n, k, get_var_G, anchor=1):
    """Only valid for cycle graphs: their full rotational/reflective
    automorphism group makes vertex `anchor` and vertex n-1 interchangeable.
    Do not use this for path or general graphs.
    """
    return [[-get_var_G(anchor, l), get_var_G(n - 1, l + 1)] for l in range(1, k)]


def order_lt(k, get_var_G, a, b):
    """Encodes h(a) < h(b): for l=1..k-1, G(a,l) -> G(b,l+1). Same clause
    shape symmetry_breaking_cycle() uses, generalized to an arbitrary pair.
    """
    return [[-get_var_G(a, l), get_var_G(b, l + 1)] for l in range(1, k)]


def symmetry_breaking_twins(k, get_var_G, twin_classes):
    """Breaks label-permutation symmetry among distance-twin vertices (see
    graph.find_distance_twins()): valid for any graph, since twins are
    derived from the actual distance matrix rather than an assumed
    structure. Within each class, chains adjacent members (sorted by vertex
    index) into h(v_1) < h(v_2) < ... < h(v_m) -- transitivity of < makes
    chaining adjacent pairs equivalent to a full pairwise order, in O(m)
    clauses instead of O(m^2).
    """
    result = []
    for cls in twin_classes:
        for a, b in zip(cls, cls[1:]):
            result.extend(order_lt(k, get_var_G, a, b))
    return result


def symmetry_breaking_path(n, k, get_var_G):
    """Only valid for path graphs: their sole non-trivial automorphism (the
    end-to-end reflection i -> n-1-i) makes vertex 0 and vertex n-1
    interchangeable -- reflecting any solution across the path's midpoint
    gives an equally valid labeling with the same span. Injectivity
    guarantees h(0) != h(n-1) (no tie to handle), so a single strict order
    between the two endpoints breaks the reflection without excluding any
    achievable k. Do not use this for cycle or general graphs.
    """
    return order_lt(k, get_var_G, 0, n - 1)
