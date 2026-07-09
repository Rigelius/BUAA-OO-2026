import com.oocourse.elevator2.TimableOutput;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

public class ElevatorThread extends Thread {
    private final int id;
    private final ProcessQueue processQueue;
    private final ScheduleQueue scheduleQueue;
    private final List<Person> cabin = new CopyOnWriteArrayList<>();
    private final int maxWeight = 400;

    private int currentFloor = 4;
    private int direction = 1;
    private int currentWeight = 0;

    private volatile ElevatorState state = ElevatorState.NORMAL;
    private volatile Maintenance maint = null;
    private long maintAcceptTime = 0;

    public ElevatorThread(int id, ProcessQueue processQueue, ScheduleQueue scheduleQueue) {
        this.id = id;
        this.processQueue = processQueue;
        this.scheduleQueue = scheduleQueue;
    }

    public synchronized void receiveMaintenance(Maintenance maint) {
        this.maint = maint;
        this.maintAcceptTime = System.currentTimeMillis();
        state = ElevatorState.REP_ACCEPT;
        synchronized (processQueue) {
            processQueue.notifyAll();
        }
    }

    public boolean isPendingMaintenance() {
        return this.maint != null; 
    }

    @Override
    public void run() {
        while (true) {
            try {
                switch (state) {
                    case NORMAL:
                        runNormal();
                        break;
                    case REP_ACCEPT:
                        runRepAccept();
                        break;
                    case REPAIR:
                        runRepair();
                        break;
                    case TEST:
                        runTest();
                        break;
                    default:
                        break;
                }
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
            if (state == ElevatorState.NORMAL
                && processQueue.isEmpty()
                && processQueue.isEnd()
                && cabin.isEmpty()) {
                break;
            }
        }
    }

    private void runNormal() throws InterruptedException {
        Advice advice = MoveStrategy.getAdvice(this);
        if (advice == Advice.WAIT) {
            synchronized (processQueue) {
                while (processQueue.isEmpty()
                    && cabin.isEmpty()
                    && !processQueue.isEnd()
                    && state == ElevatorState.NORMAL) {
                    processQueue.wait();
                }
            }
            return;
        }
        executeAdvice(advice);
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
    }

    public void runRepAccept() throws InterruptedException {
        List<Person> rebounds = new ArrayList<>();
        synchronized (processQueue) {
            rebounds.addAll(processQueue.getQueue());
            processQueue.getQueue().clear();
        }
        while (currentFloor != 4) {
            boolean drop = false;
            for (Person p : cabin) {
                if (p.getToFloor() == currentFloor) {
                    drop = true;
                    break; }
            }
            if (drop) {
                long pass = System.currentTimeMillis() - maintAcceptTime;
                long test = Math.abs(FloorUtils.toInt(maint.getToFloor()) - 4) * 400L;
                if (pass + Math.abs(currentFloor - 4) * 400L + test + 2200 < 6500) {
                    String lbl = FloorUtils.toLabel(currentFloor);
                    TimableOutput.println(String.format("OPEN-%s-%d", lbl, id));
                    cabin.removeIf(p -> {
                        if (p.getToFloor() == currentFloor) {
                            TimableOutput.println(String.format("OUT-S-%d-%s-%d",
                                p.getPersonId(), lbl, id));
                            currentWeight -= p.getWeight();
                            return true;
                        }
                        return false;
                    });
                    Thread.sleep(400);
                    TimableOutput.println(String.format("CLOSE-%s-%d", lbl, id));
                }
            }
            direction = (currentFloor < 4) ? 1 : -1;
            Thread.sleep(400);
            currentFloor += direction;
            TimableOutput.println("ARRIVE-" + FloorUtils.toLabel(currentFloor) + "-" + id);
        }
        TimableOutput.println("OPEN-F1-" + id);
        for (Person p : cabin) {
            if (p.getToFloor() == 4) {
                TimableOutput.println("OUT-S-" + p.getPersonId() + "-F1-" + id);
            } else {
                TimableOutput.println("OUT-F-" + p.getPersonId() + "-F1-" + id);
                p.setCurrentFloor(4);
                rebounds.add(p);
            }
        }
        cabin.clear();
        currentWeight = 0;
        TimableOutput.println("IN-" + maint.getWorkerId() + "-F1-" + id);
        Thread.sleep(400);
        TimableOutput.println("CLOSE-F1-" + id);
        synchronized (processQueue) {
            TimableOutput.println("MAINT1-BEGIN-" + id);
            this.state = ElevatorState.REPAIR;
        }
        for (Person p : rebounds) {
            scheduleQueue.offer(p);
        }
    }

    private void runRepair() throws InterruptedException {
        Thread.sleep(1000);
        TimableOutput.println(String.format("MAINT2-BEGIN-%d", id));
        this.state = ElevatorState.TEST;
    }

    private void runTest() throws InterruptedException {
        final int targetIndex = FloorUtils.toInt(maint.getToFloor());
        final int f1Index = 4;
        while (currentFloor != targetIndex) {
            direction = (currentFloor < targetIndex) ? 1 : -1;
            Thread.sleep(200);
            currentFloor += direction;
            TimableOutput.println(String.format("ARRIVE-%s-%d",
                FloorUtils.toLabel(currentFloor), id));
        }
        while (currentFloor != f1Index) {
            direction = (currentFloor < f1Index) ? 1 : -1;
            Thread.sleep(200);
            currentFloor += direction;
            TimableOutput.println(String.format("ARRIVE-%s-%d",
                FloorUtils.toLabel(currentFloor), id));
        }
        TimableOutput.println(String.format("OPEN-%s-%d",
            FloorUtils.toLabel(currentFloor), id));
        TimableOutput.println(String.format("OUT-S-%d-%s-%d",
            maint.getWorkerId(), FloorUtils.toLabel(currentFloor), id));
        Thread.sleep(400);
        TimableOutput.println(String.format("CLOSE-%s-%d",
            FloorUtils.toLabel(currentFloor), id));
        TimableOutput.println(String.format("MAINT-END-%d", id));
        maint = null;
        state = ElevatorState.NORMAL;
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
    }

    private void executeAdvice(Advice advice) throws InterruptedException {
        switch (advice) {
            case MOVE:
                Thread.sleep(400);
                currentFloor += direction;
                TimableOutput.println(String.format("ARRIVE-%s-%d",
                    FloorUtils.toLabel(currentFloor), id));
                break;
            case OPEN_DOOR:
                TimableOutput.println(String.format("OPEN-%s-%d",
                    FloorUtils.toLabel(currentFloor), id));
                cabin.removeIf(p -> {
                    if (p.getToFloor() == currentFloor) {
                        TimableOutput.println(String.format("OUT-S-%d-%s-%d",
                            p.getPersonId(), FloorUtils.toLabel(currentFloor), id));
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
                            TimableOutput.println(String.format("IN-%d-%s-%d",
                                p.getPersonId(), FloorUtils.toLabel(currentFloor), id));
                            cabin.add(p);
                            currentWeight += p.getWeight();
                            it.remove();
                        }
                    }
                }
                Thread.sleep(400);
                TimableOutput.println(String.format("CLOSE-%s-%d",
                    FloorUtils.toLabel(currentFloor), id));
                break;
            case REVERSE:
                direction = -direction;
                break;
            default:
                break;
        }
    }

    public List<Person> getDeepCopyCabin() {
        List<Person> copy = new ArrayList<>();
        for (Person p : cabin) {
            copy.add(new Person(p));
        }
        return copy;
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

    public int getElevatorId() {
        return id;
    }

    public ElevatorState getElevatorState() {
        return state;
    }
}