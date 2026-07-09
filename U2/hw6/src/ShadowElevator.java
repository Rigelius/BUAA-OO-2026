import java.util.Iterator;
import java.util.List;

public class ShadowElevator {
    private final int maxWeight;
    private final List<Person> cabin;
    private final List<Person> processQueue;
    private int currentFloor;
    private int direction;
    private int currentWeight;
    private double virtualTime;
    private double virtualPower;

    public ShadowElevator(ElevatorThread e) {
        this.currentFloor = e.getCurrentFloor();
        this.direction = e.getDirection();
        this.currentWeight = e.getCurrentWeight();
        this.maxWeight = e.getMaxWeight();
        this.virtualTime = 0.0;
        this.virtualPower = 0.0;
        this.cabin = e.getDeepCopyCabin();
        this.processQueue = e.getProcessQueue().getDeepCopyQueue();
    }

    public double simulate(Person target) {
        if (target != null) {
            this.processQueue.add(new Person(target));
        }

        int cnt = 0;
        double[] totalPassengerTime = {0.0};

        while (cnt++ < 1500) {
            if (cabin.isEmpty() && processQueue.isEmpty()) {
                return totalPassengerTime[0] * 0.5407620713759972 
                     + virtualTime * 0.3286272314546452 
                     + virtualPower * 0.1306106971693576;
            }

            if (shouldOpenDoor()) {
                virtualTime += 0.4;
                virtualPower += 0.2;

                cabin.removeIf(p -> {
                    if (p.getToFloor() == currentFloor) {
                        currentWeight -= p.getWeight();
                        totalPassengerTime[0] += virtualTime;
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
            if (p.getFromFloor() == currentFloor
                && currentWeight + p.getWeight() <= maxWeight) {
                return true;
            }
        }
        return false;
    }
}