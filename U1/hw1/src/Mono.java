import java.math.BigInteger;

public class Mono {

    private final BigInteger coefficient;

    private final int exponent;

    public Mono(BigInteger coefficient, int exponent) {
        this.coefficient = coefficient;
        this.exponent = exponent;
    }

    public BigInteger getCoefficient() {
        return coefficient;
    }

    public int getExponent() {
        return exponent;
    }

    public Mono multiply(Mono other) {
        BigInteger c = coefficient.multiply(other.getCoefficient());
        int e = exponent + other.getExponent();
        return new Mono(c, e);
    }

    public boolean isZero() {
        return coefficient.equals(BigInteger.ZERO);
    }

    public boolean isPositive() {
        return coefficient.compareTo(BigInteger.ZERO) > 0;
    }

    @Override
    public String toString() {
        if (coefficient.equals(BigInteger.ZERO)) {
            return "";
        } else if (exponent == 0) {
            return String.valueOf(coefficient);
        } else {
            StringBuilder sb = new StringBuilder();
            if (coefficient.compareTo(BigInteger.ZERO) < 0) {
                sb.append('-');
            }
            if (!coefficient.abs().equals(BigInteger.ONE)) {
                sb.append(coefficient.abs()).append("*");
            }
            sb.append('x');
            if (exponent >= 2) {
                sb.append('^').append(exponent);
            }
            return sb.toString();
        }
    }
}