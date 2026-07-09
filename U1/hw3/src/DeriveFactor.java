import java.util.Map;

public class DeriveFactor implements Factor {

    private final String deriveType;
    private final Expr argument;

    public DeriveFactor(String deriveType, Expr argument) {
        this.deriveType = deriveType;
        this.argument = argument;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly p = argument.toPoly(vars);
        if ("dx".equals(deriveType)) {
            return p.derive("x");
        } else if ("dy".equals(deriveType)) {
            return p.derive("y");
        } else if ("grad".equals(deriveType)) {
            return p.derive("x").add(p.derive("y"));
        }
        return Poly.ZERO;
    }
}
