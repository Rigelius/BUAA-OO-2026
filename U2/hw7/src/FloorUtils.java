import java.util.Arrays;
import java.util.List;

public final class FloorUtils {
    private static final List<String> FLOORS = Arrays.asList(
        "B4", "B3", "B2", "B1", "F1", "F2", "F3", "F4", "F5", "F6", "F7"
    );

    private FloorUtils() {
    }

    public static int toInt(String label) {
        return FLOORS.indexOf(label);
    }

    public static String toLabel(int index) {
        return FLOORS.get(index);
    }
}