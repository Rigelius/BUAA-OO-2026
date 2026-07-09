import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Map;

public class Expr implements Factor {

    private ArrayList<Term> terms = new ArrayList<>();
    private BigInteger exponent = BigInteger.ONE;

    public Expr() {
    }

    public void addTerm(Term term) {
        terms.add(term);
    }

    public void setExponent(BigInteger exponent) {
        this.exponent = exponent;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly p = new Poly();
        for (Term term : terms) {
            p = p.add(term.toPoly(vars));
        }
        return p.power(exponent);
    }
}