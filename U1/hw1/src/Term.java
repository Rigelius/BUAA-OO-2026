import java.math.BigInteger;
import java.util.ArrayList;

public class Term {

    private ArrayList<Factor> factors = new ArrayList<>();

    private boolean negative = false;

    public Term() {
    }

    public void addFactor(Factor factor) {
        factors.add(factor);
    }

    public void negate() {
        negative = !negative;
    }

    public Poly toPoly() {
        Poly p = new Poly(new Mono(BigInteger.ONE, 0));
        for (Factor factor : factors) {
            p = p.multiply(factor.toPoly());
        }
        if (negative) {
            p = p.negate();
        }
        return p;
    }
}