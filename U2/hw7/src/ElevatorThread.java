import com.oocourse.elevator3.TimableOutput;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

public class ElevatorThread extends Thread {
    private final int elevatorId;
    private final boolean isMain;
    private final ElevatorShaft shaft;
    private final ProcessQueue processQueue;
    private final ScheduleQueue scheduleQueue;

    private final List<Person> cabin = new CopyOnWriteArrayList<>();
    private final int maxWeight = 400;
    private int currentWeight = 0;
    private int currentFloor;
    private int direction = 1;

    public ElevatorThread(int elevatorId,
                          ElevatorShaft shaft,
                          ProcessQueue processQueue,
                          ScheduleQueue scheduleQueue,
                          boolean isMain) {
        this.elevatorId = elevatorId;
        this.shaft = shaft;
        this.processQueue = processQueue;
        this.scheduleQueue = scheduleQueue;
        this.isMain = isMain;
        this.currentFloor = 4;
    }

    private void moveOneFloor(int direction, long sleepTime) throws InterruptedException {
        int next = currentFloor + direction;
        if (next == 5) {
            shaft.getF2Lock().lock();
        }
        Thread.sleep(sleepTime);
        currentFloor = next;
        TimableOutput.println(String.format("ARRIVE-%s-%d",
            FloorUtils.toLabel(currentFloor), elevatorId));
        if (currentFloor != 5 && shaft.getF2Lock().isHeldByCurrentThread()) {
            shaft.getF2Lock().unlock();
        }
    }

    private void dropAll(List<Person> rebounds) throws InterruptedException {
        TimableOutput.println(String.format("OPEN-%s-%d",
            FloorUtils.toLabel(currentFloor), elevatorId));
        for (Person p : cabin) {
            if (p.getToFloor() == currentFloor) {
                TimableOutput.println(String.format("OUT-%s-%d-%s-%d",
                    p.needsTransfer() ? "F" : "S", p.getPersonId(),
                    FloorUtils.toLabel(currentFloor), elevatorId));
                if (p.needsTransfer()) {
                    p.completeTransfer();
                    rebounds.add(p);
                }
            } else {
                TimableOutput.println(String.format("OUT-F-%d-%s-%d",
                    p.getPersonId(), FloorUtils.toLabel(currentFloor), elevatorId));
                p.setCurrentFloor(currentFloor);
                rebounds.add(p);
            }
        }
        cabin.clear();
        currentWeight = 0;
        Thread.sleep(400);
        TimableOutput.println(String.format("CLOSE-%s-%d",
            FloorUtils.toLabel(currentFloor), elevatorId));
    }

    private List<Person> rejectPendingRequests() {
        List<Person> rebounds = new ArrayList<>();
        synchronized (processQueue) {
            rebounds.addAll(processQueue.getQueue());
            processQueue.clear();
        }
        return rebounds;
    }

    private void dropArrived() throws InterruptedException {
        String floor = FloorUtils.toLabel(currentFloor);
        TimableOutput.println(String.format("OPEN-%s-%d", floor, elevatorId));
        cabin.removeIf(p -> {
            if (p.getToFloor() == currentFloor) {
                TimableOutput.println(String.format("OUT-%s-%d-%s-%d",
                    p.needsTransfer() ? "F" : "S", p.getPersonId(), floor, elevatorId));
                currentWeight -= p.getWeight();
                if (p.needsTransfer()) {
                    p.completeTransfer();
                    scheduleQueue.offer(p);
                }
                return true;
            }
            return false;
        });
        Thread.sleep(400);
        TimableOutput.println(String.format("CLOSE-%s-%d", floor, elevatorId));
    }

    private void bouncePending() {
        List<Person> stranded = rejectPendingRequests();
        if (!stranded.isEmpty()) {
            for (Person p : stranded) {
                scheduleQueue.offer(p);
            }
            synchronized (scheduleQueue) {
                scheduleQueue.notifyAll();
            }
        }
    }

    @Override
    public void run() {
        try {
            do {
                try {
                    ShaftState state = shaft.getState();
                    if (isMain) {
                        executeMain(state);
                    } else {
                        executeSub(state);
                    }
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            } while ((shaft.getState() != ShaftState.NORMAL
                && shaft.getState() != ShaftState.DOUBLE)
                || !processQueue.isEmpty()
                || !processQueue.isEnd()
                || !cabin.isEmpty());
        } finally {
            List<Person> leftovers = rejectPendingRequests();
            for (Person p : leftovers) {
                scheduleQueue.offer(p); 
            }
            synchronized (scheduleQueue) {
                scheduleQueue.notifyAll();
            }
        }
    }

    private void executeMain(ShaftState state) throws Exception {
        switch (state) {
            case NORMAL:
            case DOUBLE:
            case REC_ACCEPT:
            case RECYCLE:
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
            case UP_ACCEPT:
                runUpAccept();
                break;
            case UPDATE:
                runUpdate();
                break;
            default:
                break;
        }
    }

    private void executeSub(ShaftState state) throws Exception {
        switch (state) {
            case DOUBLE:
                runNormal();
                break;
            case REC_ACCEPT:
                runRecAccept();
                break;
            case RECYCLE:
                runRecycle();
                break;
            default:
                bouncePending();
                synchronized (this) {
                    while (shaft.getState() != ShaftState.DOUBLE &&
                        shaft.getState() != ShaftState.REC_ACCEPT &&
                        shaft.getState() != ShaftState.RECYCLE &&
                        !processQueue.isEnd()) {
                        wait();
                    }
                }
                break;
        }
    }

    private void runNormal() throws InterruptedException {
        Advice advice = MoveStrategy.getAdvice(this);
        if (advice == Advice.WAIT) {
            synchronized (processQueue) {
                if (processQueue.isEmpty()
                    && cabin.isEmpty()
                    && !processQueue.isEnd()) {
                    processQueue.wait(200);
                }
            }
            return;
        }
        executeAdvice(advice);
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
    }

    private void runRepAccept() throws InterruptedException {
        List<Person> rebounds = new ArrayList<>();
        Maintenance maint = shaft.getMaint();
        while (currentFloor != 4) {
            boolean hasArrived = false;
            for (Person p : cabin) {
                if (p.getToFloor() == currentFloor) {
                    hasArrived = true;
                }
            }
            long pass = System.currentTimeMillis() - shaft.getMaintAcceptTime();
            long moveTime = Math.abs(currentFloor - 4) * 400L;
            long testTime = Math.abs(FloorUtils.toInt(maint.getToFloor()) - 4) * 400L;
            if (hasArrived && (pass + moveTime + testTime + 2200 < 6500)) {
                dropArrived();
            }
            int direction = (currentFloor < 4) ? 1 : -1;
            moveOneFloor(direction, 400);
        }
        TimableOutput.println("OPEN-F1-" + elevatorId);
        for (Person p : cabin) {
            if (p.getToFloor() == 4) {
                TimableOutput.println("OUT-S-" + p.getPersonId() + "-F1-" + elevatorId);
            } else {
                TimableOutput.println("OUT-F-" + p.getPersonId() + "-F1-" + elevatorId);
                p.setCurrentFloor(4);
                rebounds.add(p);
            }
        }
        cabin.clear();
        currentWeight = 0;
        TimableOutput.println("IN-" + maint.getWorkerId() + "-F1-" + elevatorId);
        Thread.sleep(400);
        TimableOutput.println("CLOSE-F1-" + elevatorId);
        synchronized (processQueue) {
            rebounds.addAll(rejectPendingRequests());
            TimableOutput.println("MAINT1-BEGIN-" + elevatorId);
            shaft.setState(ShaftState.REPAIR);
        }
        for (Person p : rebounds) {
            scheduleQueue.offer(p);
        }
    }

    private void runRepair() throws InterruptedException {
        bouncePending();
        Thread.sleep(1000);
        TimableOutput.println(String.format("MAINT2-BEGIN-%d", elevatorId));
        shaft.setState(ShaftState.TEST);
    }

    private void runTest() throws InterruptedException {
        bouncePending();
        int targetIndex = FloorUtils.toInt(shaft.getMaint().getToFloor());
        while (currentFloor != targetIndex) {
            int direction = (currentFloor < targetIndex) ? 1 : -1;
            moveOneFloor(direction, 200);
        }
        while (currentFloor != 4) {
            int direction = (currentFloor < 4) ? 1 : -1;
            moveOneFloor(direction, 200);
        }
        String floor = FloorUtils.toLabel(currentFloor);
        TimableOutput.println("OPEN-" + floor + "-" + elevatorId);
        TimableOutput.println(
            "OUT-S-" + shaft.getMaint().getWorkerId() + "-" + floor + "-" + elevatorId);
        Thread.sleep(400);
        TimableOutput.println("CLOSE-" + floor + "-" + elevatorId);
        TimableOutput.println("MAINT-END-" + elevatorId);
        shaft.clearMaint();
        shaft.setState(ShaftState.NORMAL);
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
    }

    private void runUpAccept() throws InterruptedException {
        List<Person> rebounds = new ArrayList<>();
        while (currentFloor != 6) {
            boolean hasArrived = false;
            for (Person p : cabin) {
                if (p.getToFloor() == currentFloor) {
                    hasArrived = true;
                    break;
                }
            }
            long pass = System.currentTimeMillis() - shaft.getUpdateAcceptTime();
            long moveTime = Math.abs(currentFloor - 6) * 400L;
            if (hasArrived && (pass + moveTime + 400 + 500 < 5000)) {
                dropArrived();
            }
            int direction = (currentFloor < 6) ? 1 : -1;
            moveOneFloor(direction, 400);
        }
        if (!cabin.isEmpty()) {
            dropAll(rebounds);
        }
        synchronized (processQueue) {
            rebounds.addAll(rejectPendingRequests());
            TimableOutput.println("UPDATE-BEGIN-" + elevatorId);
            shaft.setState(ShaftState.UPDATE);
        }
        for (Person p : rebounds) {
            scheduleQueue.offer(p);
        }
    }

    private void runUpdate() throws InterruptedException {
        bouncePending();
        Thread.sleep(1000);
        TimableOutput.println("UPDATE-END-" + elevatorId);
        shaft.setState(ShaftState.DOUBLE);
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
        synchronized (shaft.getSubCar()) {
            shaft.getSubCar().notifyAll();
        }
    }

    private void runRecAccept() throws InterruptedException {
        List<Person> rebounds = new ArrayList<>();
        while (currentFloor != 4) {
            boolean hasArrived = false;
            for (Person p : cabin) {
                if (p.getToFloor() == currentFloor) {
                    hasArrived = true;
                    break;
                }
            }
            long pass = System.currentTimeMillis() - shaft.getRecycleAcceptTime();
            long moveTime = Math.abs(currentFloor - 4) * 400L;
            if (hasArrived && (pass + moveTime + 400 + 500 < 5000)) {
                dropArrived();
            }
            int direction = (currentFloor < 4) ? 1 : -1;
            moveOneFloor(direction, 400);
        }
        if (!cabin.isEmpty()) {
            dropAll(rebounds);
        }
        synchronized (processQueue) {
            rebounds.addAll(rejectPendingRequests());
            TimableOutput.println("RECYCLE-BEGIN-" + elevatorId);
            shaft.setState(ShaftState.RECYCLE);
        }
        for (Person p : rebounds) {
            scheduleQueue.offer(p);
        }
    }

    private void runRecycle() throws InterruptedException {
        bouncePending();
        Thread.sleep(1000);
        TimableOutput.println("RECYCLE-END-" + elevatorId);
        shaft.setState(ShaftState.NORMAL);
        synchronized (scheduleQueue) {
            scheduleQueue.notifyAll();
        }
        synchronized (shaft.getMainCar()) {
            shaft.getMainCar().notifyAll();
        }
    }

    private void executeAdvice(Advice advice) throws InterruptedException {
        switch (advice) {
            case MOVE:
                moveOneFloor(direction, 400);
                break;
            case YIELD:
                direction = isMain ? 1 : -1;
                moveOneFloor(direction, 400);
                break;
            case OPEN_DOOR:
                TimableOutput.println(String.format("OPEN-%s-%d",
                    FloorUtils.toLabel(currentFloor), elevatorId));
                cabin.removeIf(p -> {
                    if (p.getToFloor() == currentFloor) {
                        TimableOutput.println(String.format("OUT-%s-%d-%s-%d",
                            p.needsTransfer() ? "F" : "S", p.getPersonId(),
                            FloorUtils.toLabel(currentFloor), elevatorId));
                        currentWeight -= p.getWeight();
                        if (p.needsTransfer()) {
                            p.completeTransfer();
                            scheduleQueue.offer(p);
                        }
                        return true;
                    }
                    return false;
                });

                synchronized (processQueue) {
                    List<Person> list = processQueue.getRequestAt(currentFloor);
                    for (Person p : list) {
                        if ((p.getToFloor() - p.getFromFloor()) * direction > 0
                            && currentWeight + p.getWeight() <= maxWeight) {
                            TimableOutput.println(String.format("IN-%d-%s-%d",
                                p.getPersonId(), FloorUtils.toLabel(currentFloor), elevatorId));
                            cabin.add(p);
                            currentWeight += p.getWeight();
                            processQueue.remove(p);
                        }
                    }
                }
                Thread.sleep(400);
                TimableOutput.println(String.format("CLOSE-%s-%d",
                    FloorUtils.toLabel(currentFloor), elevatorId));
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
        return elevatorId;
    }

    public ShaftState getShaftState() {
        return shaft.getState();
    }

    public boolean isMain() {
        return isMain;
    }
}