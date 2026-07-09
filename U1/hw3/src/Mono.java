import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;
import java.util.Map;
import java.util.HashMap;
import java.util.concurrent.ThreadLocalRandom;
import java.util.regex.Pattern;

public class Mono {

    public static final Mono ONE = new Mono(
        BigInteger.ONE, BigInteger.ZERO, BigInteger.ZERO, Poly.ZERO
    );
    private static final Pattern CONST_PATTERN = Pattern.compile("-?\\d+");
    private static final Pattern X_PATTERN = Pattern.compile("x(\\^\\d+)?");
    private static final Pattern Y_PATTERN = Pattern.compile("y(\\^\\d+)?");
    private static final HashMap<Poly, String> memTop = new HashMap<>();
    private static final HashMap<Poly, String> memNested = new HashMap<>();
    private final BigInteger coefficient;
    private final BigInteger exponentX;
    private final BigInteger exponentY;
    private final Poly expPoly;
    private final int hashCache;
    private final Sign signCache;

    public Mono(BigInteger coefficient, BigInteger exponentX, BigInteger exponentY, Poly expPoly) {
        this.coefficient = coefficient;
        this.exponentX = exponentX;
        this.exponentY = exponentY;
        this.expPoly = expPoly;
        int h = 1;
        h = 31 * h + coefficient.hashCode();
        h = 31 * h + exponentX.hashCode();
        h = 31 * h + exponentY.hashCode();
        if (expPoly != null) {
            h = 31 * h + expPoly.hashCode();
        } else {
            h = 31 * h;
        }
        this.hashCache = h;
        this.signCache = new Sign(exponentX, exponentY, expPoly);
    }

    public static boolean isSingleExp(Poly poly) {
        if (poly == null) {
            return false;
        }
        List<Mono> monos = poly.getMonos();
        if (monos.size() != 1) {
            return false;
        }
        Mono innerMono = monos.get(0);
        return innerMono.getCoefficient().equals(BigInteger.ONE)
            && innerMono.getExponentX().signum() == 0
            && innerMono.getExponentY().signum() == 0
            && innerMono.getExpPoly() != null
            && !innerMono.getExpPoly().isZero();
    }

    public BigInteger getCoefficient() {
        return coefficient;
    }

    public BigInteger getExponentX() {
        return exponentX;
    }

    public BigInteger getExponentY() {
        return exponentY;
    }

    public Poly getExpPoly() {
        return expPoly;
    }

    public Sign getSign() {
        return signCache;
    }

    public Mono multiply(Mono other) {
        BigInteger c = coefficient.multiply(other.coefficient);
        BigInteger xe = exponentX.add(other.exponentX);
        BigInteger ye = exponentY.add(other.exponentY);
        Poly p;
        if (this.expPoly.isZero()) {
            p = other.expPoly;
        } else if (other.expPoly.isZero()) {
            p = this.expPoly;
        } else {
            p = this.expPoly.add(other.expPoly);
        }
        return new Mono(c, xe, ye, p);
    }

    public boolean hasVar(String varName) {
        if ("x".equals(varName) && exponentX.signum() > 0) {
            return true;
        }
        if ("y".equals(varName) && exponentY.signum() > 0) {
            return true;
        }
        if (expPoly != null && expPoly.hasVar(varName)) {
            return true;
        }
        return false;
    }

    public Poly derive(String varName) {
        Poly ans = Poly.ZERO;
        if ("x".equals(varName)) {
            ans = new Poly(new Mono(
                coefficient.multiply(exponentX),
                exponentX.subtract(BigInteger.ONE),
                exponentY,
                expPoly));
        } else if ("y".equals(varName)) {
            ans = new Poly(new Mono(
                coefficient.multiply(exponentY),
                exponentX,
                exponentY.subtract(BigInteger.ONE),
                expPoly));
        }
        if (expPoly != null && expPoly.hasVar(varName)) {
            ans = ans.add(new Poly(this).multiply(expPoly.derive(varName)));
        }
        return ans;
    }

    public boolean isZero() {
        return coefficient.signum() == 0;
    }

    public boolean isPositive() {
        return coefficient.signum() > 0;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (obj == null || getClass() != obj.getClass()) {
            return false;
        }
        Mono other = (Mono) obj;
        if (this.hashCache != other.hashCache) {
            return false;
        }
        if (!this.exponentX.equals(other.exponentX)) {
            return false;
        }
        if (!this.exponentY.equals(other.exponentY)) {
            return false;
        }
        if (!this.coefficient.equals(other.coefficient)) {
            return false;
        }
        return Objects.equals(this.expPoly, other.expPoly);
    }

    @Override
    public int hashCode() {
        return hashCache;
    }

    private BigInteger pollardRho(BigInteger n) {
        if (n.remainder(BigInteger.valueOf(2)).signum() == 0) {
            return BigInteger.valueOf(2);
        }
        BigInteger x = new BigInteger(n.bitLength(), ThreadLocalRandom.current()).mod(n);
        BigInteger y = x;
        BigInteger c = new BigInteger(n.bitLength(), ThreadLocalRandom.current()).mod(n);
        BigInteger d = BigInteger.ONE;
        int steps = 0;
        while (d.equals(BigInteger.ONE)) {
            if (steps++ > 10000) {
                return n;
            }
            x = x.multiply(x).add(c).remainder(n);
            y = y.multiply(y).add(c).remainder(n);
            y = y.multiply(y).add(c).remainder(n);
            d = x.subtract(y).abs().gcd(n);
            if (d.equals(n)) {
                return n;
            }
        }
        return d;
    }

    private void factorize(BigInteger n, List<BigInteger> primes) {
        if (n.compareTo(BigInteger.ONE) <= 0) {
            return;
        }
        if (n.isProbablePrime(20)) {
            primes.add(n);
            return;
        }
        BigInteger divisor = pollardRho(n);
        if (divisor.equals(n)) {
            primes.add(n);
            return;
        }
        factorize(divisor, primes);
        factorize(n.divide(divisor), primes);
    }

    private List<BigInteger> getDivisors(BigInteger n) {
        if (n.compareTo(BigInteger.ONE) <= 0) {
            return java.util.Collections.emptyList();
        }
        List<BigInteger> rawPrimes = new ArrayList<>();
        factorize(n, rawPrimes);
        java.util.Collections.sort(rawPrimes);
        List<BigInteger> primes = new ArrayList<>();
        List<Integer> counts = new ArrayList<>();
        for (BigInteger p : rawPrimes) {
            if (primes.isEmpty() || !primes.get(primes.size() - 1).equals(p)) {
                primes.add(p);
                counts.add(1);
            } else {
                int last = counts.size() - 1;
                counts.set(last, counts.get(last) + 1);
            }
        }
        List<BigInteger> divisors = new ArrayList<>();
        dfs(0, BigInteger.ONE, primes, counts, divisors);
        if (divisors.size() > 256) {
            return Arrays.asList(BigInteger.ONE, n);
        }
        return divisors;
    }

    private void dfs(int index, BigInteger now, List<BigInteger> primes,
                     List<Integer> counts, List<BigInteger> result) {
        if (index == primes.size()) {
            result.add(now);
            return;
        }
        BigInteger p = primes.get(index);
        int maxPow = counts.get(index);
        BigInteger mult = BigInteger.ONE;
        for (int i = 0; i <= maxPow; i++) {
            dfs(index + 1, now.multiply(mult), primes, counts, result);
            mult = mult.multiply(p);
        }
    }

    private boolean isSingleFactor(String s) {
        if (!s.startsWith("exp(")) {
            return false;
        }
        int depth = 0;
        int end = -1;
        for (int i = 3; i < s.length(); i++) {
            if (s.charAt(i) == '(') {
                depth++;
            } else if (s.charAt(i) == ')') {
                depth--;
                if (depth == 0) {
                    end = i;
                    break;
                }
            }
        }
        if (end == s.length() - 1) {
            return true;
        }
        if (end != -1 && end + 1 < s.length() && s.charAt(end + 1) == '^') {
            String t = s.substring(end + 2);
            return CONST_PATTERN.matcher(t).matches();
        }
        return false;
    }

    private String formatExp(Poly poly, BigInteger gcd) {
        Poly basePoly = new Poly();
        if (gcd.equals(BigInteger.ONE)) {
            basePoly = poly;
        } else {
            for (Mono m : poly.getMonos()) {
                basePoly.addMono(new Mono(
                    m.getCoefficient().divide(gcd),
                    m.getExponentX(),
                    m.getExponentY(),
                    m.getExpPoly()
                ));
            }
        }
        String inner = basePoly.toOptimalString(true);
        StringBuilder sb = new StringBuilder();
        if (CONST_PATTERN.matcher(inner).matches()
            || X_PATTERN.matcher(inner).matches() || Y_PATTERN.matcher(inner).matches()
            || (isSingleExp(basePoly) && isSingleFactor(inner))) {
            sb.append("exp(").append(inner).append(")");
        } else {
            sb.append("exp((").append(inner).append("))");
        }
        if (!gcd.equals(BigInteger.ONE)) {
            sb.append("^").append(gcd);
        }
        return sb.toString();
    }

    private String getBestExp(Poly poly, BigInteger maxGcd) {
        String minStr = formatExp(poly, BigInteger.ONE);
        if (maxGcd.compareTo(BigInteger.ONE) > 0) {
            List<BigInteger> divisors = getDivisors(maxGcd);
            for (BigInteger div : divisors) {
                if (div.equals(BigInteger.ONE)) {
                    continue;
                }
                String tmp = formatExp(poly, div);
                if (tmp.length() < minStr.length()) {
                    minStr = tmp;
                }
            }
        }
        return minStr;
    }

    private String getBestExpPoly(Poly poly, boolean needsPenalty) {
        if (poly.isZero()) {
            return "1";
        }
        Map<Poly, String> mem = needsPenalty ? memNested : memTop;
        if (mem.containsKey(poly)) {
            return mem.get(poly);
        }

        BigInteger gcd = BigInteger.ZERO;
        List<Mono> monos = poly.getMonos();
        for (Mono mono : monos) {
            if (!mono.isZero()) {
                gcd = gcd.gcd(mono.getCoefficient().abs());
            }
        }
        if (gcd.signum() == 0) {
            gcd = BigInteger.ONE;
        }

        String best = getBestExp(poly, gcd);
        int size = monos.size();

        if (size > 1 && size <= 10) {
            best = dpSearch(monos, best, needsPenalty);
        } else if (size > 10 && size <= 40) {
            best = greedySearch(monos, best, needsPenalty);
        }

        mem.put(poly, best);
        return best;
    }

    private String dpSearch(List<Mono> monos, String best, boolean needsPenalty) {
        int size = monos.size();
        int maxMask = (1 << size) - 1;
        int delta = needsPenalty ? 2 : 0;
        String curBest = best;

        for (int mask = 1; mask <= maxMask / 2; mask++) {
            Poly subset1 = new Poly();
            Poly subset2 = new Poly();
            for (int i = 0; i < size; i++) {
                if ((mask & (1 << i)) != 0) {
                    subset1.addMono(monos.get(i));
                } else {
                    subset2.addMono(monos.get(i));
                }
            }
            String part1 = getBestExpPoly(subset1, false);
            String part2 = getBestExpPoly(subset2, false);
            String combined = part1 + "*" + part2;

            if (combined.length() + delta < curBest.length()) {
                curBest = combined;
            }
        }
        return curBest;
    }

    private String greedySearch(List<Mono> monos, String best, boolean needsPenalty) {
        int size = monos.size();
        int delta = needsPenalty ? 2 : 0;
        String curBest = best;

        for (int i = 0; i < size; i++) {
            for (int j = i; j < size; j++) {
                Poly subset1 = new Poly();
                Poly subset2 = new Poly();
                for (int k = 0; k < size; k++) {
                    if (k == i || k == j) {
                        subset1.addMono(monos.get(k));
                    } else {
                        subset2.addMono(monos.get(k));
                    }
                }

                BigInteger subGcd = BigInteger.ZERO;
                for (Mono m : subset2.getMonos()) {
                    subGcd = subGcd.gcd(m.getCoefficient().abs());
                }

                if (subGcd.compareTo(BigInteger.ONE) > 0) {
                    String part1 = getBestExp(subset1, BigInteger.ONE);
                    String part2 = getBestExp(subset2, subGcd);
                    String combined = part1 + "*" + part2;
                    
                    if (combined.length() + delta < curBest.length()) {
                        curBest = combined;
                    }
                }
            }
        }
        return curBest;
    }

    @Override
    public String toString() {
        return toOptimalString(false);
    }

    public String toOptimalString(boolean isNested) {
        if (coefficient.signum() == 0) {
            return "0";
        }
        boolean hasX = exponentX.signum() > 0;
        boolean hasY = exponentY.signum() > 0;
        boolean hasExp = (expPoly != null && !expPoly.isZero());
        if (!hasX && !hasY && !hasExp) {
            return String.valueOf(coefficient);
        }
        StringBuilder sb = new StringBuilder();
        if (coefficient.equals(BigInteger.valueOf(-1))) {
            sb.append("-");
        } else if (!coefficient.equals(BigInteger.ONE)) {
            sb.append(coefficient).append("*");
        }
        if (hasX) {
            sb.append('x');
            if (exponentX.compareTo(BigInteger.ONE) > 0) {
                sb.append('^').append(exponentX);
            }
        }
        if (hasY) {
            if (sb.length() > 0 && !sb.toString().equals("-") && !sb.toString().endsWith("*")) {
                sb.append("*");
            }
            sb.append('y');
            if (exponentY.compareTo(BigInteger.ONE) > 0) {
                sb.append('^').append(exponentY);
            }
        }
        if (hasExp) {
            if (sb.length() > 0 && !sb.toString().equals("-") && !sb.toString().endsWith("*")) {
                sb.append("*");
            }
            sb.append(getBestExpPoly(expPoly, isNested));
        }
        if (sb.length() == 0) {
            return "1";
        }
        if (sb.toString().equals("-")) {
            return "-1";
        }
        return sb.toString();
    }
}