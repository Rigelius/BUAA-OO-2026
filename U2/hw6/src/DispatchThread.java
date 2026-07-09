import com.oocourse.elevator2.TimableOutput;

import java.util.List;

public class DispatchThread extends Thread {
    private final ScheduleQueue scheduleQueue;
    private final List<ElevatorThread> elevators;
    private final DispatchStrategy strategy;

    public DispatchThread(ScheduleQueue scheduleQueue,
                          List<ElevatorThread> elevators,
                          DispatchStrategy strategy) {
        this.scheduleQueue = scheduleQueue;
        this.elevators = elevators;
        this.strategy = strategy;
    }

    @Override
    public void run() {
        while (true) {
            Person person;
            synchronized (scheduleQueue) {
                while (scheduleQueue.isEmpty() && !isAllFinished()) {
                    try {
                        scheduleQueue.wait();
                    } catch (InterruptedException e) {
                        throw new RuntimeException(e);
                    }
                }
                if (scheduleQueue.isEmpty() && isAllFinished()) {
                    for (ElevatorThread e : elevators) {
                        e.getProcessQueue().setEnd(true);
                    }
                    return;
                }
                person = scheduleQueue.take();
            }

            if (person != null) {
                int id = strategy.chooseElevator(person, elevators);
                if (id == -1) {
                    scheduleQueue.offer(person);
                    synchronized (scheduleQueue) {
                        try {
                            scheduleQueue.wait(200); 
                        } catch (InterruptedException e) {
                            throw new RuntimeException(e);
                        }
                    }
                    continue;
                }
                person.setElevatorId(id);
                ElevatorThread targetElevator = elevators.get(id - 1);

                boolean retry = false;
                synchronized (targetElevator.getProcessQueue()) {
                    if (targetElevator.getElevatorState() != ElevatorState.NORMAL) {
                        retry = true;
                    } else {
                        TimableOutput.println(String.format("RECEIVE-%d-%d",
                            person.getPersonId(), id));
                        targetElevator.getProcessQueue().offer(person);
                    }
                }
                if (retry) {
                    scheduleQueue.offer(person);
                }
            }

        }
    }

    private boolean isAllFinished() {
        if (!scheduleQueue.isEnd()) {
            return false;
        }
        for (ElevatorThread e : elevators) {
            if (!e.getProcessQueue().isEmpty()
                || !e.getCabin().isEmpty()
                || e.getElevatorState() != ElevatorState.NORMAL) {
                return false;
            }
        }
        return true;
    }
}