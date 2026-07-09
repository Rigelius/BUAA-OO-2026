import java.util.List;

public class ShadowDispatchStrategy implements DispatchStrategy {

    @Override
    public int chooseElevator(Person person, List<ElevatorShaft> shafts) {
        int bestId = -1;
        double minCost = Double.MAX_VALUE;
        int bestWeight = Integer.MAX_VALUE;

        for (ElevatorShaft shaft : shafts) {
            ShaftState state = shaft.getState();
            if (state == ShaftState.REP_ACCEPT
                || state == ShaftState.REPAIR
                || state == ShaftState.TEST
                || state == ShaftState.UP_ACCEPT
                || state == ShaftState.UPDATE) {
                continue;
            }

            ElevatorThread targetCar = determineTargetCar(person, shaft);
            if (targetCar == null) {
                continue;
            }

            Person virtualPerson = new Person(person);
            if (shaft.getState() == ShaftState.DOUBLE &&
                ((virtualPerson.getFromFloor() < 5 && virtualPerson.getDestFloor() > 5) ||
                    (virtualPerson.getFromFloor() > 5 && virtualPerson.getDestFloor() < 5))) {
                virtualPerson.setTransferFloor(5);
            }

            if (isOverloaded(shaft, targetCar, virtualPerson)) {
                continue;
            }

            ShadowElevator shadowWithout = new ShadowElevator(targetCar, shaft.getState());
            double costWithout = shadowWithout.simulate(null);

            ShadowElevator shadowWith = new ShadowElevator(targetCar, shaft.getState());
            double costWith = shadowWith.simulate(virtualPerson);

            if (shaft.getState() == ShaftState.DOUBLE && virtualPerson.needsTransfer()) {
                ElevatorThread otherCar =
                    (targetCar == shaft.getMainCar()) ? shaft.getSubCar() : shaft.getMainCar();
                Person secondPerson = new Person(person);
                secondPerson.setCurrentFloor(5);
                secondPerson.setTransferFloor(-1);

                ShadowElevator otherShadowWithout = new ShadowElevator(otherCar, shaft.getState());
                double otherCostWithout = otherShadowWithout.simulate(null);

                ShadowElevator otherShadowWith = new ShadowElevator(otherCar, shaft.getState());
                double otherCostWith = otherShadowWith.simulate(secondPerson);

                costWithout = (costWithout < Double.MAX_VALUE
                    && otherCostWithout < Double.MAX_VALUE)
                    ? (costWithout + otherCostWithout) : Double.MAX_VALUE;
                costWith = (costWith < Double.MAX_VALUE && otherCostWith < Double.MAX_VALUE)
                    ? (costWith + otherCostWith) : Double.MAX_VALUE;
            }

            double cost = (costWith >= Double.MAX_VALUE || costWithout >= Double.MAX_VALUE)
                ? Double.MAX_VALUE : (1.05 * costWith - costWithout);

            if (cost < minCost || (cost == minCost && targetCar.getCurrentWeight() < bestWeight)) {
                minCost = cost;
                bestId = targetCar.getElevatorId();
                bestWeight = targetCar.getCurrentWeight();
            }
        }
        return minCost > 150.0 ? -1 : bestId;
    }

    private boolean isOverloaded(ElevatorShaft shaft,
                                 ElevatorThread targetCar,
                                 Person virtualPerson) {
        int targetLoad = targetCar.getCabin().size()
            + targetCar.getProcessQueue().getQueue().size();
        if (targetLoad >= 14) {
            return true;
        }

        if (shaft.getState() == ShaftState.DOUBLE && virtualPerson.needsTransfer()) {
            ElevatorThread otherCar = (targetCar == shaft.getMainCar()) ?
                shaft.getSubCar() : shaft.getMainCar();
            int otherLoad = otherCar.getCabin().size()
                + otherCar.getProcessQueue().getQueue().size();
            return otherLoad >= 14;
        }
        
        return false;
    }

    private ElevatorThread determineTargetCar(Person p, ElevatorShaft shaft) {
        if (shaft.getState() != ShaftState.DOUBLE) {
            return shaft.getMainCar();
        }
        if (p.getFromFloor() > 5) {
            return shaft.getMainCar();
        }
        if (p.getFromFloor() < 5) {
            return shaft.getSubCar();
        }
        return p.getDestFloor() > 5 ? shaft.getMainCar() : shaft.getSubCar();
    }
}