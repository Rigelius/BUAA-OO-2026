import java.util.ArrayList;

public class Expr implements Factor {

    private ArrayList<Term> terms = new ArrayList<>();
    private int exponent = 1;

    public Expr() {
    }

    public void addTerm(Term term) {
        terms.add(term);
    }

    public void setExponent(int exponent) {
        this.exponent = exponent;
    }

    @Override
    public Poly toPoly() {
        Poly p = new Poly();
        for (Term term : terms) {
            p = p.add(term.toPoly());
        }
        return p.power(exponent);
    }
}