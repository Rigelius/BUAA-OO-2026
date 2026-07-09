import java.math.BigInteger;
import java.util.HashMap;
import java.util.Map;

public class FuncFactor implements Factor {
    private static final Map<RecCacheKey, Poly> mem = new HashMap<>();
    private final Factor argument;
    private final Integer index;
    private final FuncReg registry;

    public FuncFactor(Factor argument, Integer index, FuncReg registry) {
        this.argument = argument;
        this.index = index;
        this.registry = registry;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly argPoly = argument.toPoly(vars);
        if (index == null) {
            Map<String, Poly> newVars = new HashMap<>();
            newVars.put("x", argPoly);
            return registry.getFuncDef().getBodyExpr().toPoly(newVars);
        }
        return solveRec(index, argPoly);
    }

    private Poly solveRec(int n, Poly poly) {
        RecCacheKey key = new RecCacheKey(n, poly);
        if (mem.containsKey(key)) {
            return mem.get(key);
        }

        FuncReg.RecDef d = registry.getRecDef();
        Map<String, Poly> newVars = new HashMap<>();
        newVars.put("x", poly);
        Poly ans;
        if (n == 0) {
            ans = d.getF0Body().toPoly(newVars);
        } else if (n == 1) {
            ans = d.getF1Body().toPoly(newVars);
        } else {
            Poly realArg1 = d.getArg1().toPoly(newVars);
            Poly term1 = solveRec(n - 1, realArg1).multiply(
                new Poly(new Mono(d.getC1(), BigInteger.ZERO, BigInteger.ZERO, Poly.ZERO))
            );
            Poly realArg2 = d.getArg2().toPoly(newVars);
            Poly term2 = solveRec(n - 2, realArg2).multiply(
                new Poly(new Mono(d.getC2(), BigInteger.ZERO, BigInteger.ZERO, Poly.ZERO))
            );
            ans = term1.add(term2);
            if (d.getExtraBody() != null) {
                ans = ans.add(d.getExtraBody().toPoly(newVars));
            }
        }
        mem.put(key, ans);
        return ans;
    }

    private static class RecCacheKey {
        private final int index;
        private final Poly poly;

        public RecCacheKey(int index, Poly poly) {
            this.index = index;
            this.poly = poly;
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) {
                return true;
            }
            if (obj == null || getClass() != obj.getClass()) {
                return false;
            }
            RecCacheKey other = (RecCacheKey) obj;
            return index == other.index && poly.equals(other.poly);
        }

        @Override
        public int hashCode() {
            return 31 * index + poly.hashCode();
        }
    }
}