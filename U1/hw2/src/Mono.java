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

    public static final Mono ZERO = new Mono(BigInteger.ZERO, BigInteger.ZERO, Poly.ZERO);
    public static final Mono ONE = new Mono(BigInteger.ONE, BigInteger.ZERO, Poly.ZERO);
    private static final Pattern CONST_PATTERN = Pattern.compile("-?\\d+");
    private static final Pattern X_PATTERN = Pattern.compile("x(\\^\\d+)?");
    private static final BigInteger TWO = BigInteger.valueOf(2);

    private final BigInteger coefficient;
    private final BigInteger exponent;
    private final Poly expPoly;
    private final int hashCache;
    private final Sign signCache;

    private static final HashMap<Poly, String> memTop = new HashMap<>();
    private static final HashMap<Poly, String> memNested = new HashMap<>();

    public Mono(BigInteger coefficient, BigInteger exponent, Poly expPoly) {
        this.coefficient = coefficient;
        this.exponent = exponent;
        this.expPoly = expPoly;
        int h = 1;
        h = 31 * h + coefficient.hashCode();
        h = 31 * h + exponent.hashCode();
        if (expPoly != null) {
            h = 31 * h + expPoly.hashCode();
        } else {
            h = 31 * h + 0;
        }
        this.hashCache = h;
        this.signCache = new Sign(exponent, expPoly);
    }

    public BigInteger getCoefficient() {
        return coefficient;
    }

    public BigInteger getExponent() {
        return exponent;
    }

    public Poly getExpPoly() {
        return expPoly;
    }

    public Sign getSign() {
        return signCache;
    }

    public Mono multiply(Mono other) {
        BigInteger c = coefficient.multiply(other.coefficient);
        BigInteger e = exponent.add(other.exponent);
        Poly p;
        if (this.expPoly.isZero()) {
            p = other.expPoly;
        } else if (other.expPoly.isZero()) {
            p = this.expPoly;
        } else {
            p = this.expPoly.add(other.expPoly);
        }
        return new Mono(c, e, p);
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
        if (!this.exponent.equals(other.exponent)) {
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

    private boolean isSingleExp(Poly poly) {
        if (poly == null) {
            return false;
        }
        List<Mono> monos = poly.getMonos();
        if (monos.size() != 1) {
            return false;
        }
        Mono innerMono = monos.get(0);
        return innerMono.coefficient.equals(BigInteger.ONE)
            && innerMono.exponent.signum() == 0
            && innerMono.expPoly != null
            && !innerMono.expPoly.isZero();
    }

    private BigInteger pollardRho(BigInteger n) {
        if (n.remainder(TWO).signum() == 0) {
            return TWO;
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
                    m.getCoefficient().divide(gcd), m.getExponent(), m.getExpPoly()
                ));
            }
        }
        String inner = basePoly.toOptimalString(true);
        StringBuilder sb = new StringBuilder();
        if (CONST_PATTERN.matcher(inner).matches() || X_PATTERN.matcher(inner).matches()
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

    private String getBestExpPoly(Poly poly, boolean isNested) {
        if (poly.isZero()) {
            return "1";
        }
        Map<Poly, String> mem = isNested ? memNested : memTop;
        if (mem.containsKey(poly)) {
            return mem.get(poly);
        }
        BigInteger gcd = BigInteger.ZERO;
        List<Mono> monos = poly.getMonos();
        for (Mono mono : monos) {
            if (!mono.isZero()) {
                gcd = gcd.gcd(mono.coefficient.abs());
            }
        }
        if (gcd.signum() == 0) {
            gcd = BigInteger.ONE;
        }
        String best = getBestExp(poly, gcd);
        int size = monos.size();
        if (size > 1 && size <= 12) {
            int maxMask = (1 << size) - 1;
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
                String part1 = getBestExpPoly(subset1, isNested);
                String part2 = getBestExpPoly(subset2, isNested);
                String combined = part1 + "*" + part2;
                int delta = isNested ? 2 : 0;
                if (combined.length() + delta < best.length()) {
                    best = combined;
                }
            }
        }
        mem.put(poly, best);
        return best;
    }

    @Override
    public String toString() {
        return toOptimalString(false);
    }

    public String toOptimalString(boolean isNested) {
        if (coefficient.signum() == 0) {
            return "0";
        }
        boolean hasX = exponent.signum() > 0;
        boolean hasExp = (expPoly != null && !expPoly.isZero());
        if (!hasX && !hasExp) {
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
            if (exponent.compareTo(BigInteger.ONE) > 0) {
                sb.append('^').append(exponent);
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

    public static class Sign {
        private final BigInteger exponent;
        private final Poly expPoly;
        private final int hashCache;

        public Sign(BigInteger exponent, Poly expPoly) {
            this.exponent = exponent;
            this.expPoly = expPoly;
            int h = 1;
            h = 31 * h + exponent.hashCode();
            if (expPoly != null) {
                h = 31 * h + expPoly.hashCode();
            } else {
                h = 31 * h;
            }
            this.hashCache = h;
        }

        @Override
        public boolean equals(Object obj) {
            if (this == obj) {
                return true;
            }
            if (obj == null || getClass() != obj.getClass()) {
                return false;
            }
            Sign other = (Sign) obj;
            if (this.hashCache != other.hashCache) {
                return false;
            }
            if (!this.exponent.equals(other.exponent)) {
                return false;
            }
            return Objects.equals(this.expPoly, other.expPoly);
        }

        @Override
        public int hashCode() {
            return hashCache;
        }
    }
}