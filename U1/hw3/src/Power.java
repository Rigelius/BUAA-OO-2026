import java.math.BigInteger;
import java.util.Map;

public class Power implements Factor {

    private String varName;

    private BigInteger exponent;

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
            if ("x".equals(varName)) {
                return new Poly(new Mono(BigInteger.ONE, exponent, BigInteger.ZERO, Poly.ZERO));
            } else if ("y".equals(varName)) {
                return new Poly(new Mono(BigInteger.ONE, BigInteger.ZERO, exponent, Poly.ZERO));
            }
            return Poly.ZERO;
        }
    }
}