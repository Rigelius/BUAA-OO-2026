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
            return Advice.WAIT;
        }
    }

    private static boolean shouldOpenDoor(ElevatorThread elevator) {
        for (Person p : elevator.getCabin()) {
            if (p.getToFloor() == elevator.getCurrentFloor()) {
                return true;
            }
        }
        for (Person p : elevator.getProcessQueue().getQueue()) {
            if (p.getCurrentFloor() == elevator.getCurrentFloor()
                && (p.getToFloor() - p.getFromFloor()) * elevator.getDirection() > 0
                && elevator.getCurrentWeight() + p.getWeight() <= elevator.getMaxWeight()) {
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
}