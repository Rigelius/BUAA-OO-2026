import java.math.BigInteger;
import java.util.Objects;

public class Sign {
    private final BigInteger exponentX;
    private final BigInteger exponentY;
    private final Poly expPoly;
    private final int hashCache;

    public Sign(BigInteger exponentX, BigInteger exponentY, Poly expPoly) {
        this.exponentX = exponentX;
        this.exponentY = exponentY;
        this.expPoly = expPoly;
        int h = 1;
        h = 31 * h + exponentX.hashCode();
        h = 31 * h + exponentY.hashCode();
        if (expPoly != null) {
            h = 31 * h + expPoly.hashCode();
        } else {
            h = 31 * h;
        }
        this.hashCache = h;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) {
            return true;
        }
        if (obj == null || getClass() != obj.getClass()) {
            return false;
        }
        Sign other = (Sign) obj;
        if (this.hashCache != other.hashCache) {
            return false;
        }
        if (!this.exponentX.equals(other.exponentX)) {
            return false;
        }
        if (!this.exponentY.equals(other.exponentY)) {
            return false;
        }
        return Objects.equals(this.expPoly, other.expPoly);
    }

    @Override
    public int hashCode() {
        return hashCache;
    }
}