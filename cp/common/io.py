def read_graph():
    n = int(input())
    adj_matrix = [list(map(int, input().split())) for _ in range(n)]
    return n, adj_matrix


def read_upper_bound():
    return int(input())
