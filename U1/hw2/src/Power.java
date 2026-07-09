import java.math.BigInteger;
import java.util.Map;

public class Power implements Factor {

    private String varName = "x";

    private BigInteger exponent = BigInteger.ONE;

    public Power(String varName, BigInteger exponent) {
        this.varName = varName;
        this.exponent = exponent;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        Poly base;
        if (vars != null && vars.containsKey(varName)) {
            base = vars.get(varName);
            return base.power(exponent);
        } else {
            return new Poly(new Mono(BigInteger.ONE, exponent, Poly.ZERO));
        }
    }
}