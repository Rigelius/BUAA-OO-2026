import java.math.BigInteger;
import java.util.Map;

public class ExpFactor implements Factor {
    private Factor argument;
    private BigInteger exponent = BigInteger.ONE;

    public ExpFactor() {
    }

    public ExpFactor(Factor argument, BigInteger exponent) {
        this.argument = argument;
        this.exponent = exponent;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly poly = argument.toPoly(vars);
        poly = poly.multiply(new Poly(new Mono(exponent, BigInteger.ZERO, Poly.ZERO)));
        return new Poly(new Mono(BigInteger.ONE, BigInteger.ZERO, poly));
    }
}