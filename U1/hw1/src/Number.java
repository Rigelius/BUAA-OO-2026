import java.math.BigInteger;

public class Number implements Factor {

    private BigInteger value;

    public Number(BigInteger value) {
        this.value = value;
    }

    @Override
    public Poly toPoly() {
        return new Poly(new Mono(value, 0));
    }
}