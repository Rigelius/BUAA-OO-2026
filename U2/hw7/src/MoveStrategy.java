public final class MoveStrategy {
    public static Advice getAdvice(ElevatorThread elevator) {
        synchronized (elevator.getProcessQueue()) {
            if (shouldOpenDoor(elevator)) {
                return Advice.OPEN_DOOR;
            }
            if (shouldMove(elevator)) {
                return Advice.MOVE;
            }
            if (shouldReverse(elevator)) {
                return Advice.REVERSE;
            }
            if (shouldYield(elevator)) {
                return Advice.YIELD;
            }
            return Advice.WAIT;
        }
    }

    private static boolean shouldOpenDoor(ElevatorThread e) {
        for (Person p : e.getCabin()) {
            if (p.getToFloor() == e.getCurrentFloor()) {
                return true;
            }
        }
        if (!e.getProcessQueue().hasRequestAt(e.getCurrentFloor())) {
            return false;
        }
        for (Person p : e.getProcessQueue().getRequestAt(e.getCurrentFloor())) {
            if ((p.getToFloor() - p.getFromFloor()) * e.getDirection() > 0 &&
                e.getCurrentWeight() + p.getWeight() <= e.getMaxWeight()) {
                return true;
            }
        }
        return false;
    }

    private static boolean shouldMove(ElevatorThread elevator) {
        if (!elevator.getCabin().isEmpty()) {
            return true;
        }
        for (Person p : elevator.getProcessQueue().getQueue()) {
            if ((p.getFromFloor() - elevator.getCurrentFloor()) * elevator.getDirection() > 0) {
                return true;
            }
        }
        return false;
    }

    private static boolean shouldReverse(ElevatorThread elevator) {
        if (!elevator.getCabin().isEmpty()) {
            return false;
        }
        for (Person p : elevator.getProcessQueue().getQueue()) {
            if ((p.getFromFloor() - elevator.getCurrentFloor()) * elevator.getDirection() < 0) {
                return true;
            }
            if (p.getFromFloor() == elevator.getCurrentFloor()
                && elevator.getCurrentWeight() + p.getWeight() <= elevator.getMaxWeight()) {
                return true;
            }
        }
        return false;
    }

    private static boolean shouldYield(ElevatorThread elevator) {
        return elevator.getShaftState() == ShaftState.DOUBLE
            && elevator.getCurrentFloor() == 5
            && elevator.getCabin().isEmpty()
            && elevator.getProcessQueue().isEmpty();
    }
}