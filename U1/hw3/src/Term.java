import java.util.ArrayList;
import java.util.Map;

public class Term {

    private ArrayList<Factor> factors = new ArrayList<>();

    private boolean negative = false;

    public void addFactor(Factor factor) {
        factors.add(factor);
    }

    public void negate() {
        negative = !negative;
    }

    public Poly toPoly(Map<String, Poly> vars) {
        Poly p = Poly.ONE;
        for (Factor factor : factors) {
            p = p.multiply(factor.toPoly(vars));
        }
        if (negative) {
            p = p.negate();
        }
        return p;
    }
}