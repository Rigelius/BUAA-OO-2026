import com.oocourse.elevator1.TimableOutput;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

public class ElevatorThread extends Thread {
    private final int id;
    private final ProcessQueue processQueue;
    private final List<Person> cabin = new ArrayList<>();
    private final int maxWeight = 400;
    private int currentFloor = 4;
    private int direction = 1;//1向上，-1向下
    private int currentWeight = 0;

    public ElevatorThread(int id, ProcessQueue processQueue) {
        this.id = id;
        this.processQueue = processQueue;
    }

    @Override
    public void run() {
        while (true) {
            Advice advice = Strategy.getAdvice(this);
            if (advice == Advice.WAIT) {
                synchronized (processQueue) {
                    while (processQueue.isEmpty() && cabin.isEmpty() && !processQueue.isEnd()) {
                        try {
                            processQueue.wait();
                        } catch (InterruptedException e) {
                            throw new RuntimeException(e);
                        }
                    }
                    if (processQueue.isEmpty() && cabin.isEmpty() && processQueue.isEnd()) {
                        break;
                    }
                }
                continue;
            }
            try {
                executeAdvice(advice);
            } catch (InterruptedException e) {
                throw new RuntimeException(e);
            }
        }
    }

    private void executeAdvice(Advice advice) throws InterruptedException {
        switch (advice) {
            case MOVE:
                Thread.sleep(400);
                currentFloor += direction;
                String arriveMsg = String.format("ARRIVE-%s-%d",
                    FloorUtils.toLabel(currentFloor), id);
                TimableOutput.println(arriveMsg);
                break;
            case OPEN_DOOR:
                String openMsg = String.format("OPEN-%s-%d",
                    FloorUtils.toLabel(currentFloor), id);
                TimableOutput.println(openMsg);
                cabin.removeIf(p -> {
                    if (p.getToFloor() == currentFloor) {
                        String outMsg = String.format("OUT-S-%s-%s-%s",
                            p.getPersonId(), FloorUtils.toLabel(currentFloor), id);
                        TimableOutput.println(outMsg);
                        currentWeight -= p.getWeight();
                        return true;
                    }
                    return false;
                });
                synchronized (processQueue) {
                    Iterator<Person> it = processQueue.getQueue().iterator();
                    while (it.hasNext()) {
                        Person p = it.next();
                        if (p.getFromFloor() == currentFloor
                            && (p.getToFloor() - p.getFromFloor()) * direction > 0
                            && currentWeight + p.getWeight() <= maxWeight) {
                            String inMsg = String.format("IN-%d-%s-%d",
                                p.getPersonId(), FloorUtils.toLabel(currentFloor), id);
                            TimableOutput.println(inMsg);
                            cabin.add(p);
                            currentWeight += p.getWeight();
                            it.remove();
                        }
                    }
                }
                Thread.sleep(400);

                String closeMsg = String.format("CLOSE-%s-%d",
                    FloorUtils.toLabel(currentFloor), id);
                TimableOutput.println(closeMsg);
                break;
            case REVERSE:
                direction = -direction;
                break;
            default:
                break;
        }
    }

    public List<Person> getCabin() {
        return cabin;
    }

    public int getCurrentFloor() {
        return currentFloor;
    }

    public int getCurrentWeight() {
        return currentWeight;
    }

    public int getDirection() {
        return direction;
    }

    public int getMaxWeight() {
        return maxWeight;
    }

    public ProcessQueue getProcessQueue() {
        return processQueue;
    }
}