import java.math.BigInteger;
import java.util.Map;

public class Number implements Factor {

    private BigInteger value;

    public Number(BigInteger value) {
        this.value = value;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        return new Poly(new Mono(value, BigInteger.ZERO, BigInteger.ZERO, Poly.ZERO));
    }
}