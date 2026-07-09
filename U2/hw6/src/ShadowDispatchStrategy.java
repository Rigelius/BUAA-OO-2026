import java.util.List;

public class ShadowDispatchStrategy implements DispatchStrategy {

    @Override
    public int chooseElevator(Person person, List<ElevatorThread> elevators) {
        int bestId = -1;
        double minCost = Double.MAX_VALUE;
        int normalCount = 0;

        for (ElevatorThread e : elevators) {
            if (e.getElevatorState() != ElevatorState.NORMAL || e.isPendingMaintenance()) {
                continue;
            }
            normalCount++;

            ShadowElevator shadowWithout = new ShadowElevator(e);
            double costWithout = shadowWithout.simulate(null);

            ShadowElevator shadowWith = new ShadowElevator(e);
            double costWith = shadowWith.simulate(person);

            double cost;
            if (costWith >= Double.MAX_VALUE || costWithout >= Double.MAX_VALUE) {
                cost = Double.MAX_VALUE;
            } else {
                cost = 1.05 * costWith - costWithout;
            }

            if (cost < minCost) {
                minCost = cost;
                bestId = e.getElevatorId();
            }
        }

        if (minCost > 120.0 && normalCount < elevators.size()) {
            return -1; 
        }

        if (minCost >= Double.MAX_VALUE - 100) {
            return -1;
        }
        
        return bestId;
    }
}