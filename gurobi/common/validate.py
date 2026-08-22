import math


def decode_model(model, n, k, get_var_G, verbose=True):
    labels = [0] * n
    for i in range(n):
        for j in range(1, k + 1):
            if get_var_G(i, j) in model and -get_var_G(i, j + 1) in model:
                labels[i] = j
                if verbose:
                    print(f"h({i}) = {j}")
    return labels


def check_rml(h, n, diam, dist_matrix):
    for i in range(n):
        for j in range(i + 1, n):
            d = int(dist_matrix[i][j])
            m = 2 * (diam - d) + 1
            if (h[i] + h[j]) < m:
                print(f"Violation at h({i}) = {h[i]},h({j}) = {h[j]}: "
                      f"d={d}, {math.ceil((h[i] + h[j]) / 2)} < {m}")
                return False
    return True


def check_validation(model, n, k, diam, dist_matrix, get_var_G):
    h = decode_model(model, n, k, get_var_G, verbose=False)
    seen = [0] * (n + diam)
    for i in range(n):
        j = h[i]
        if j:
            if seen[j] == 0:
                seen[j] = 1
            else:
                print("Violate injectivity")
    if check_rml(h, n, diam, dist_matrix):
        print("Valid label")
    else:
        print("Invalid label")
