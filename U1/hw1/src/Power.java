import java.math.BigInteger;

public class Power implements Factor {

    private String varName = "x";

    private int exponent = 1;

    public Power(String varName, int exponent) {
        this.varName = varName;
        this.exponent = exponent;
    }

    @Override
    public Poly toPoly() {
        return new Poly(new Mono(BigInteger.ONE, exponent));
    }
}