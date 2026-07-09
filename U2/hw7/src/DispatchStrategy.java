import java.util.List;

public interface DispatchStrategy {
    int chooseElevator(Person person, List<ElevatorShaft> shafts);
}
