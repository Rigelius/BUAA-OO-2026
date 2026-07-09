import java.util.Map;

public class ChoiceFactor implements Factor {
    private Factor left;
    private Factor right;
    private Factor whenTrue;
    private Factor whenFalse;

    public ChoiceFactor() {
    }

    public ChoiceFactor(Factor left, Factor right, Factor whenTrue, Factor whenFalse) {
        this.left = left;
        this.right = right;
        this.whenTrue = whenTrue;
        this.whenFalse = whenFalse;
    }

    @Override
    public Poly toPoly(Map<String, Poly> vars) {
        if (left.toPoly(vars).subtract(right.toPoly(vars)).isZero()) {
            return whenTrue.toPoly(vars);
        } else {
            return whenFalse.toPoly(vars);
        }
    }
}