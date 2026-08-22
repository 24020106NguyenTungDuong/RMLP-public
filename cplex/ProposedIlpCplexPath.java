/**
 * Radio Mean Labeling solver: ILP model via CPLEX (Java Concert
 * Technology), using the paper's proposed literal pairwise-boolean
 * Radio-mean constraint, plus path-specific symmetry breaking (sound only
 * for path graphs, whose sole non-trivial automorphism is the end-to-end
 * reflection):
 *
 *   h(0) <= h(n-1)     (break the end-to-end reflection)
 *
 * Do not reuse this file's constraint set for cycle or general graphs.
 *
 * Build:
 *   javac -cp <CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar ProposedIlpCplexPath.java
 * Run:
 *   java -cp .:<CPLEX_STUDIO_DIR>/cplex/lib/cplex.jar \
 *        -Djava.library.path=<CPLEX_STUDIO_DIR>/cplex/bin/x86-64_linux \
 *        ProposedIlpCplexPath [timeLimitSeconds] < input.txt
 */

import ilog.concert.IloIntVar;
import ilog.concert.IloLinearNumExpr;
import ilog.cplex.IloCplex;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.StreamTokenizer;
import java.util.ArrayDeque;
import java.util.Arrays;

public class ProposedIlpCplexPath {
    static long startTime;

    public static void main(String[] args) throws Exception {
        StreamTokenizer st = new StreamTokenizer(new BufferedReader(new InputStreamReader(System.in)));

        int n = nextInt(st);
        int[][] adj = new int[n][n];
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                adj[i][j] = nextInt(st);
        int ub = nextInt(st);

        double timeLimit = args.length > 0 ? Double.parseDouble(args[0]) : 900.0;

        startTime = System.nanoTime();

        int[][] dist = allPairsBfs(adj, n);
        int diam = 0;
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                if (dist[i][j] > diam) diam = dist[i][j];

        IloCplex cplex = new IloCplex();
        cplex.setOut(null);
        cplex.setParam(IloCplex.Param.TimeLimit, timeLimit);

        IloIntVar[][] x = new IloIntVar[n][ub];
        for (int v = 0; v < n; v++)
            for (int l = 0; l < ub; l++)
                x[v][l] = cplex.boolVar("x_" + v + "_" + l);

        IloIntVar lmax = cplex.intVar(1, ub, "l_max");

        IloLinearNumExpr[] h = new IloLinearNumExpr[n];
        for (int v = 0; v < n; v++) {
            IloLinearNumExpr expr = cplex.linearNumExpr();
            for (int l = 0; l < ub; l++)
                expr.addTerm(l + 1, x[v][l]);
            h[v] = expr;
        }

        for (int v = 0; v < n; v++) {
            IloLinearNumExpr sum = cplex.linearNumExpr();
            for (int l = 0; l < ub; l++)
                sum.addTerm(1.0, x[v][l]);
            cplex.addEq(sum, 1.0);
        }

        for (int l = 0; l < ub; l++) {
            IloLinearNumExpr sum = cplex.linearNumExpr();
            for (int v = 0; v < n; v++)
                sum.addTerm(1.0, x[v][l]);
            cplex.addLe(sum, 1.0);
        }

        // Literal Radio-mean: x[u][l1] + x[v][l2] <= 1 for l1+l2 < H(u,v).
        // l1, l2 here are 0-indexed label slots (label value = l1+1, l2+1).
        for (int u = 0; u < n; u++) {
            for (int v = u + 1; v < n; v++) {
                int hUv = 2 * (diam - dist[u][v]) + 1;
                for (int l1 = 0; l1 < ub; l1++) {
                    for (int l2 = 0; l2 < ub; l2++) {
                        if ((l1 + 1) + (l2 + 1) < hUv) {
                            IloLinearNumExpr sum = cplex.linearNumExpr();
                            sum.addTerm(1.0, x[u][l1]);
                            sum.addTerm(1.0, x[v][l2]);
                            cplex.addLe(sum, 1.0);
                        }
                    }
                }
            }
        }

        for (int v = 0; v < n; v++)
            cplex.addGe(lmax, h[v]);

        if (n > 1)
            cplex.addLe(h[0], h[n - 1]);

        cplex.addMinimize(lmax);

        final double[] bestSeen = {Double.POSITIVE_INFINITY};
        cplex.use(context -> {
            if (context.getId() == IloCplex.Callback.Context.Id.Candidate && context.isCandidatePoint()) {
                double obj = context.getCandidateObjective();
                if (obj < bestSeen[0] - 1e-6) {
                    bestSeen[0] = obj;
                    double t = (System.nanoTime() - startTime) / 1e9;
                    System.out.println("rmn(G) <= " + Math.round(obj));
                    System.out.printf("Execution time: %.6f s%n", t);
                    System.out.println();
                    System.out.flush();
                }
            }
        }, IloCplex.Callback.Context.Id.Candidate);

        boolean solved = cplex.solve();
        double t = (System.nanoTime() - startTime) / 1e9;

        if (solved) {
            long k = Math.round(cplex.getObjValue());
            boolean proven = cplex.getCplexStatus() == IloCplex.CplexStatus.Optimal;
            if (proven) {
                System.out.println("rmn(G) = " + k);
            } else {
                System.out.println("rmn(G) <= " + k + " (time limit reached)");
            }
            System.out.printf("Execution time: %.6f s%n", t);

            for (int v = 0; v < n; v++) {
                for (int l = 0; l < ub; l++) {
                    if (cplex.getValue(x[v][l]) > 0.5) {
                        System.out.println("h(" + v + ") = " + (l + 1));
                        break;
                    }
                }
            }
        } else {
            System.out.println("No solution found.");
            System.out.printf("Execution time: %.6f s%n", t);
        }

        cplex.end();
    }

    static int nextInt(StreamTokenizer st) throws IOException {
        st.nextToken();
        return (int) st.nval;
    }

    static int[][] allPairsBfs(int[][] adj, int n) {
        int inf = Integer.MAX_VALUE / 2;
        int[][] dist = new int[n][n];
        for (int[] row : dist) Arrays.fill(row, inf);
        for (int s = 0; s < n; s++) {
            dist[s][s] = 0;
            ArrayDeque<Integer> queue = new ArrayDeque<>();
            queue.add(s);
            while (!queue.isEmpty()) {
                int u = queue.poll();
                for (int v = 0; v < n; v++) {
                    if (adj[u][v] != 0 && dist[s][v] == inf) {
                        dist[s][v] = dist[s][u] + 1;
                        queue.add(v);
                    }
                }
            }
        }
        return dist;
    }
}
