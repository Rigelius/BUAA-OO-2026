import com.oocourse.elevator3.TimableOutput;

import java.util.List;

public class DispatchThread extends Thread {
    private final ScheduleQueue scheduleQueue;
    private final List<ElevatorShaft> shafts;
    private final ShadowDispatchStrategy strategy;

    public DispatchThread(ScheduleQueue scheduleQueue, List<ElevatorShaft> shafts) {
        this.scheduleQueue = scheduleQueue;
        this.shafts = shafts;
        this.strategy = new ShadowDispatchStrategy();
    }

    @Override
    public void run() {
        while (true) {
            Person person;
            synchronized (scheduleQueue) {
                while (scheduleQueue.isEmpty() && !isAllFinished()) {
                    try {
                        scheduleQueue.wait(200);
                    } catch (Exception e) {
                        throw new RuntimeException(e);
                    }
                }
                if (scheduleQueue.isEmpty() && isAllFinished()) {
                    for (ElevatorShaft s : shafts) {
                        s.getMainCar().getProcessQueue().setEnd(true);
                        s.getSubCar().getProcessQueue().setEnd(true);
                        synchronized (s.getSubCar()) {
                            s.getSubCar().notifyAll();
                        }
                    }
                    return;
                }
                person = scheduleQueue.take();
            }

            if (person != null) {
                int id = strategy.chooseElevator(person, shafts);
                if (id == -1) {
                    scheduleQueue.offer(person);
                    synchronized (scheduleQueue) {
                        try {
                            scheduleQueue.wait(200);
                        } catch (Exception e) {
                            throw new RuntimeException(e);
                        }
                    }
                    continue;
                }

                ElevatorShaft targetShaft = shafts.get((id > 6 ? id - 6 : id) - 1);
                final ElevatorThread targetCar =
                    id > 6 ? targetShaft.getSubCar() : targetShaft.getMainCar();

                if (targetShaft.getState() == ShaftState.DOUBLE &&
                    ((person.getFromFloor() < 5 && person.getDestFloor() > 5) ||
                        (person.getFromFloor() > 5 && person.getDestFloor() < 5))) {
                    person.setTransferFloor(5);
                }

                synchronized (targetCar.getProcessQueue()) {
                    ShaftState s = targetShaft.getState();
                    if (s == ShaftState.RECYCLE || s == ShaftState.UPDATE
                        || s == ShaftState.REPAIR || s == ShaftState.TEST
                        || (!targetCar.isMain() && s != ShaftState.DOUBLE)) {
                        person.setTransferFloor(-1);
                        scheduleQueue.offer(person);
                        continue;
                    }
                    person.setElevatorId(id);
                    TimableOutput.println(String.format("RECEIVE-%d-%d", person.getPersonId(), id));
                    targetCar.getProcessQueue().offer(person);
                }
            }
        }
    }

    private boolean isAllFinished() {
        if (!scheduleQueue.isEnd()) {
            return false;
        }
        for (ElevatorShaft s : shafts) {
            if ((!s.getMainCar().getProcessQueue().isEmpty()
                || !s.getMainCar().getCabin().isEmpty()
                || s.getState() != ShaftState.NORMAL)
                && s.getState() != ShaftState.DOUBLE) {
                return false;
            }
            if (s.getState() == ShaftState.DOUBLE
                && (!s.getSubCar().getProcessQueue().isEmpty()
                || !s.getSubCar().getCabin().isEmpty()
                || !s.getMainCar().getProcessQueue().isEmpty()
                || !s.getMainCar().getCabin().isEmpty())) {
                return false;
            }
        }
        return true;
    }
}