import java.math.BigInteger;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

public class Poly {

    public static final Poly ZERO = new Poly();
    public static final Poly ONE = new Poly(Mono.ONE);
    public static final Poly X =
        new Poly(new Mono(BigInteger.ONE, BigInteger.ONE, BigInteger.ZERO, Poly.ZERO));
    public static final Poly Y =
        new Poly(new Mono(BigInteger.ONE, BigInteger.ZERO, BigInteger.ONE, Poly.ZERO));
    private Map<Sign, Mono> monos = new HashMap<>();
    private Integer hashCache = null;

    public Poly() {
    }

    public Poly(Mono mono) {
        addMono(mono);
    }

    private Poly(int capacity) {
        monos = new HashMap<>(capacity);
    }

    public ArrayList<Mono> getMonos() {
        return new ArrayList<>(monos.values());
    }

    public boolean isZero() {
        return monos.isEmpty();
    }

    public void addMono(Mono mono) {
        if (mono.isZero()) {
            return;
        }
        hashCache = null;
        Sign sign = mono.getSign();
        Mono oldM = monos.get(sign);
        if (oldM == null) {
            monos.put(sign, mono);
        } else {
            Mono merged = new Mono(
                oldM.getCoefficient().add(mono.getCoefficient()),
                mono.getExponentX(),
                mono.getExponentY(),
                mono.getExpPoly()
            );
            if (merged.isZero()) {
                monos.remove(sign);
            } else {
                monos.put(sign, merged);
            }
        }
    }

    public Poly add(Poly other) {
        if (this.isZero()) {
            return other;
        }
        if (other.isZero()) {
            return this;
        }
        Poly ans = new Poly(this.monos.size() + other.monos.size());
        for (Mono mono : monos.values()) {
            ans.addMono(mono);
        }
        for (Mono mono : other.monos.values()) {
            ans.addMono(mono);
        }
        return ans;
    }

    public Poly negate() {
        if (this.isZero()) {
            return this;
        }
        Poly ans = new Poly();
        for (Mono mono : monos.values()) {
            ans.addMono(new Mono(
                mono.getCoefficient().negate(),
                mono.getExponentX(),
                mono.getExponentY(),
                mono.getExpPoly()
            ));
        }
        return ans;
    }

    public Poly subtract(Poly other) {
        if (other.isZero()) {
            return this;
        }
        if (this.isZero()) {
            return other.negate();
        }
        return add(other.negate());
    }

    public boolean hasVar(String varName) {
        if (isZero()) {
            return false;
        }
        for (Mono mono : monos.values()) {
            if (mono.hasVar(varName)) {
                return true;
            }
        }
        return false;
    }

    public Poly multiply(Poly other) {
        if (this.isZero() || other.isZero()) {
            return Poly.ZERO;
        }
        int capacity = Math.min(1024, Math.max(16, this.monos.size() * other.monos.size() / 2));
        Poly ans = new Poly(capacity);
        for (Mono mono1 : monos.values()) {
            for (Mono mono2 : other.monos.values()) {
                ans.addMono(mono1.multiply(mono2));
            }
        }
        return ans;
    }

    public Poly power(BigInteger exp) {
        if (exp.signum() == 0) {
            return Poly.ONE;
        }
        if (this.isZero()) {
            return Poly.ZERO;
        }
        Poly ans = Poly.ONE;
        Poly base = this;
        BigInteger e = exp;
        while (e.signum() > 0) {
            if (e.testBit(0)) {
                ans = ans.multiply(base);
            }
            e = e.shiftRight(1);
            if (e.signum() > 0) {
                base = base.multiply(base);
            }
        }
        return ans;
    }

    public Poly derive(String varName) {
        Poly ans = new Poly();
        for (Mono mono : monos.values()) {
            Poly derived = mono.derive(varName);
            for (Mono m : derived.getMonos()) {
                ans.addMono(m);
            }
        }
        return ans;
    }

    @Override
    public int hashCode() {
        if (hashCache == null) {
            hashCache = monos.hashCode();
        }
        return hashCache;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (obj == null || getClass() != obj.getClass()) {
            return false;
        }
        Poly other = (Poly) obj;
        if (this.monos.size() != other.monos.size()) {
            return false;
        }
        if (this.hashCode() != other.hashCode()) {
            return false;
        }
        for (Map.Entry<Sign, Mono> entry : this.monos.entrySet()) {
            Mono otherMono = other.monos.get(entry.getKey());
            if (otherMono == null) {
                return false;
            }
            if (!entry.getValue().getCoefficient().equals(otherMono.getCoefficient())) {
                return false;
            }
        }
        return true;
    }

    @Override
    public String toString() {
        return toOptimalString(false);
    }

    public String toOptimalString(boolean isNested) {
        if (isZero()) {
            return "0";
        }
        ArrayList<Mono> list = new ArrayList<>(monos.values());
        boolean isFirst = true;
        int firstPositive = -1;
        for (int i = 0; i < list.size(); i++) {
            if (list.get(i).isPositive()) {
                firstPositive = i;
                break;
            }
        }

        boolean needsPenalty = isNested && Mono.isSingleExp(this);

        StringBuilder sb = new StringBuilder();
        if (firstPositive != -1) {
            sb.append(list.get(firstPositive).toOptimalString(needsPenalty));
            isFirst = false;
        }
        for (int i = 0; i < list.size(); i++) {
            if (i != firstPositive && !list.get(i).isZero()) {
                String term = list.get(i).toOptimalString(needsPenalty);
                if (term.isEmpty()) {
                    continue;
                }
                if (isFirst) {
                    isFirst = false;
                } else if (list.get(i).isPositive()) {
                    sb.append("+");
                }
                sb.append(term);
            }
        }
        return sb.toString();
    }
}