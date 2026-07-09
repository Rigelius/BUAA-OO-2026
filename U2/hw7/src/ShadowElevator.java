import java.util.Iterator;
import java.util.List;

public class ShadowElevator {
    private final int maxWeight;
    private final List<Person> cabin;
    private final List<Person> processQueue;
    private final boolean isMain;
    private final ShaftState state;
    private int currentFloor;
    private int direction;
    private int currentWeight;
    private double virtualTime = 0.0;
    private double virtualPower = 0.0;

    public ShadowElevator(ElevatorThread e, ShaftState state) {
        this.currentFloor = e.getCurrentFloor();
        this.direction = e.getDirection();
        this.currentWeight = e.getCurrentWeight();
        this.maxWeight = e.getMaxWeight();
        this.cabin = e.getDeepCopyCabin();
        this.processQueue = e.getProcessQueue().getDeepCopyQueue();
        this.isMain = e.isMain();
        this.state = state;
    }

    public double simulate(Person target) {
        if (target != null) {
            processQueue.add(new Person(target));
        }

        int cnt = 0;
        double[] passengerTime = {0.0};
        while (cnt++ < 1500) {
            if (state == ShaftState.DOUBLE
                || state == ShaftState.REC_ACCEPT
                || state == ShaftState.RECYCLE) {
                if (isMain && currentFloor < 5) {
                    return Double.MAX_VALUE;
                }
                if (!isMain && currentFloor > 5) {
                    return Double.MAX_VALUE;
                }
            }

            if (cabin.isEmpty() && processQueue.isEmpty()) {
                return passengerTime[0] * 0.540762
                    + virtualTime * 0.328627
                    + virtualPower * 0.130610;
            }

            if (shouldOpenDoor()) {
                virtualTime += 0.4;
                virtualPower += 0.2;
                cabin.removeIf(p -> {
                    if (p.getToFloor() == currentFloor) {
                        currentWeight -= p.getWeight();
                        passengerTime[0] += virtualTime;
                        if (p.needsTransfer()) {
                            passengerTime[0] += 2.0;
                        }
                        return true;
                    }
                    return false;
                });
                Iterator<Person> it = processQueue.iterator();
                while (it.hasNext()) {
                    Person p = it.next();
                    if (p.getFromFloor() == currentFloor
                        && (p.getToFloor() - p.getFromFloor()) * direction > 0
                        && currentWeight + p.getWeight() <= maxWeight) {
                        cabin.add(p);
                        currentWeight += p.getWeight();
                        it.remove();
                    }
                }
            } else if (shouldMove()) {
                virtualTime += 0.4;
                virtualPower += 0.4;
                currentFloor += direction;
            } else if (shouldReverse()) {
                direction = -direction;
            } else {
                return Double.MAX_VALUE;
            }
        }
        return Double.MAX_VALUE;
    }

    private boolean shouldOpenDoor() {
        for (Person p : cabin) {
            if (p.getToFloor() == currentFloor) {
                return true;
            }
        }
        for (Person p : processQueue) {
            if (p.getFromFloor() == currentFloor
                && (p.getToFloor() - p.getFromFloor()) * direction > 0
                && currentWeight + p.getWeight() <= maxWeight) {
                return true;
            }

        }
        return false;
    }

    private boolean shouldMove() {
        if (!cabin.isEmpty()) {
            return true;
        }
        for (Person p : processQueue) {
            if ((p.getFromFloor() - currentFloor) * direction > 0) {
                return true;
            }
        }
        return false;
    }

    private boolean shouldReverse() {
        if (!cabin.isEmpty()) {
            return false;
        }
        for (Person p : processQueue) {
            if ((p.getFromFloor() - currentFloor) * direction < 0) {
                return true;
            }
            if (p.getFromFloor() == currentFloor && currentWeight + p.getWeight() <= maxWeight) {
                return true;
            }
        }
        return false;
    }
}