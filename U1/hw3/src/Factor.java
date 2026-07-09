import java.util.Map;

public interface Factor {
    Poly toPoly(Map<String, Poly> vars);
}