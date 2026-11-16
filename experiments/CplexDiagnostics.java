/**
 * Where does CPLEX's optimality proof come from? (reviewer W1/W3; diagnostics,
 * not timings -- run only when no re-run batch is active.)
 *
 * Builds the same model as cplex/ProposedIlpCplex{Path,Cycle}.java (literal
 * pairwise radio-mean rows, family symmetry breaking, CPLEX defaults) for the
 * instance on stdin, solves it with CPLEX's log written to the file given as
 * args[1], and prints one summary line:
 *   rows cols nodes best_bound obj status runtime_s t_opt_incumbent_s
 * The log carries presolve reductions, the root relaxation, cut rounds and
 * the node log, each line prefixed with "[seconds] " since model construction
 * began; cplex_diagnostics.py parses both. The prefix gives the time of each
 * new incumbent ("*" lines) without a callback.
 *
 * Usage: java ... CplexDiagnostics <P|C> <logfile> <timeLimitSeconds> [mode] [threads] [seed] < instance.txt
 *   cb (default)  with the incumbent callback, as in the timed solver (Candidate context);
 *   nocb          without it, so CPLEX keeps the dual and crushing-form presolve
 *                 reductions the callback disables (t_opt_incumbent_s is then -1;
 *                 take the time from the log's timestamps);
 *   emptycb       a Candidate-context callback that does nothing (is registering it enough?);
 *   lazyparams    no callback, but the presolve settings CPLEX switches to when a
 *                 Candidate callback is present: Reduce=1 (primal only),
 *                 Reformulations=1 (none that interfere with crushing), Symmetry=0;
 *   progress      the incumbent time from a GlobalProgress-context callback, which
 *                 is informational and should not put CPLEX into lazy-constraint mode.
 *   Root-node tuning (W3, batch 17), each without a callback and one setting changed:
 *   tune-bound    MIP emphasis on moving the best bound (Emphasis.MIP=3);
 *   tune-cliques  very aggressive clique cuts (MIP.Cuts.Cliques=3);
 *   tune-probe    very aggressive probing (MIP.Strategy.Probe=3).
 *   threads       CPLEX Threads parameter, 0 (default) = all cores.
 *   seed          CPLEX RandomSeed; omitted = CPLEX's default seed (batches 14-17).
 *                 The timed solver uses 0.
 */

import ilog.concert.IloIntVar;
import ilog.concert.IloLinearNumExpr;
import ilog.cplex.IloCplex;

import java.io.BufferedOutputStream;
import java.io.BufferedReader;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.io.PrintStream;
import java.io.StreamTokenizer;

public class CplexDiagnostics {
    public static void main(String[] args) throws Exception {
        char fam = args[0].charAt(0);
        long start = System.nanoTime();
        PrintStream log = new PrintStream(new Timestamped(new BufferedOutputStream(new FileOutputStream(args[1])), start), true);
        double timeLimit = Double.parseDouble(args[2]);
        String mode = args.length > 3 ? args[3] : "cb";
        int threads = args.length > 4 ? Integer.parseInt(args[4]) : 0;
        Integer seed = args.length > 5 ? Integer.valueOf(args[5]) : null;

        StreamTokenizer st = new StreamTokenizer(new BufferedReader(new InputStreamReader(System.in)));
        int n = nextInt(st);
        for (int i = 0; i < n * n; i++)
            nextInt(st);                      // adjacency: P_n / C_n distances are computed directly
        int diam = fam == 'P' ? n - 1 : n / 2;
        int ub = n + diam - 1;

        IloCplex cplex = new IloCplex();
        cplex.setOut(log);
        cplex.setWarning(log);
        cplex.setParam(IloCplex.Param.TimeLimit, timeLimit);
        cplex.setParam(IloCplex.Param.Threads, threads);
        if (seed != null)
            cplex.setParam(IloCplex.Param.RandomSeed, seed);
        if (mode.equals("lazyparams")) {
            cplex.setParam(IloCplex.Param.Preprocessing.Reduce, 1);
            cplex.setParam(IloCplex.Param.Preprocessing.Reformulations, 1);
            cplex.setParam(IloCplex.Param.Preprocessing.Symmetry, 0);
        }
        if (mode.equals("tune-bound"))
            cplex.setParam(IloCplex.Param.Emphasis.MIP, 3);
        if (mode.equals("tune-cliques"))
            cplex.setParam(IloCplex.Param.MIP.Cuts.Cliques, 3);
        if (mode.equals("tune-probe"))
            cplex.setParam(IloCplex.Param.MIP.Strategy.Probe, 3);

        IloIntVar[][] x = new IloIntVar[n][ub];
        for (int v = 0; v < n; v++)
            for (int l = 0; l < ub; l++)
                x[v][l] = cplex.boolVar();
        IloIntVar lmax = cplex.intVar(1, ub);
        IloLinearNumExpr[] h = new IloLinearNumExpr[n];
        for (int v = 0; v < n; v++) {
            h[v] = cplex.linearNumExpr();
            IloLinearNumExpr row = cplex.linearNumExpr();
            for (int l = 0; l < ub; l++) {
                h[v].addTerm(l + 1, x[v][l]);
                row.addTerm(1.0, x[v][l]);
            }
            cplex.addEq(row, 1.0);
        }
        for (int l = 0; l < ub; l++) {
            IloLinearNumExpr row = cplex.linearNumExpr();
            for (int v = 0; v < n; v++)
                row.addTerm(1.0, x[v][l]);
            cplex.addLe(row, 1.0);
        }
        for (int u = 0; u < n; u++)
            for (int v = u + 1; v < n; v++) {
                int d = fam == 'P' ? v - u : Math.min(v - u, n - (v - u));
                int hUv = 2 * (diam - d) + 1;
                for (int l1 = 0; l1 < ub; l1++)
                    for (int l2 = 0; l2 < ub; l2++)
                        if ((l1 + 1) + (l2 + 1) < hUv) {
                            IloLinearNumExpr row = cplex.linearNumExpr();
                            row.addTerm(1.0, x[u][l1]);
                            row.addTerm(1.0, x[v][l2]);
                            cplex.addLe(row, 1.0);
                        }
            }
        for (int v = 0; v < n; v++)
            cplex.addGe(lmax, h[v]);
        if (fam == 'P') {
            cplex.addLe(h[0], h[n - 1]);
        } else {
            for (int v = 1; v < n; v++)
                cplex.addLe(h[0], h[v]);
            if (n > 2)
                cplex.addLe(h[1], h[n - 1]);
        }
        cplex.addMinimize(lmax);

        final double[] best = {Double.POSITIVE_INFINITY};
        final double[] tBest = {-1};
        if (mode.equals("cb")) cplex.use(context -> {
            if (context.isCandidatePoint()) {
                double obj = context.getCandidateObjective();
                if (obj < best[0] - 1e-6) {
                    best[0] = obj;
                    tBest[0] = (System.nanoTime() - start) / 1e9;
                }
            }
        }, IloCplex.Callback.Context.Id.Candidate);
        if (mode.equals("emptycb")) cplex.use(context -> { }, IloCplex.Callback.Context.Id.Candidate);
        if (mode.equals("progress")) cplex.use(context -> {
            if (context.getIntInfo(IloCplex.Callback.Context.Info.Feasible) != 0) {
                double obj = context.getIncumbentObjective();
                if (obj < best[0] - 1e-6) {
                    best[0] = obj;
                    tBest[0] = (System.nanoTime() - start) / 1e9;
                }
            }
        }, IloCplex.Callback.Context.Id.GlobalProgress);

        int rows = cplex.getNrows(), cols = cplex.getNcols();
        cplex.setParam(IloCplex.Param.TimeLimit,
                Math.max(1.0, timeLimit - (System.nanoTime() - start) / 1e9));
        boolean solved = cplex.solve();
        double runtime = (System.nanoTime() - start) / 1e9;
        System.out.printf("rows=%d cols=%d nodes=%d best_bound=%.4f obj=%s status=%s runtime_s=%.2f t_opt_incumbent_s=%.2f%n",
                rows, cols, cplex.getNnodes(), cplex.getBestObjValue(),
                solved ? String.valueOf(Math.round(cplex.getObjValue())) : "none",
                cplex.getCplexStatus(), runtime, tBest[0]);
        cplex.end();
        log.close();
    }

    /** Prefixes every line with the seconds elapsed since {@code start}. */
    static class Timestamped extends OutputStream {
        private final OutputStream out;
        private final long start;
        private boolean lineStart = true;

        Timestamped(OutputStream out, long start) {
            this.out = out;
            this.start = start;
        }

        @Override
        public void write(int b) throws IOException {
            if (lineStart) {
                out.write(String.format("[%9.2f] ", (System.nanoTime() - start) / 1e9).getBytes());
                lineStart = false;
            }
            out.write(b);
            if (b == '\n') {
                lineStart = true;
                out.flush();
            }
        }

        @Override
        public void flush() throws IOException {
            out.flush();
        }

        @Override
        public void close() throws IOException {
            out.close();
        }
    }

    static int nextInt(StreamTokenizer st) throws IOException {
        st.nextToken();
        return (int) st.nval;
    }
}
