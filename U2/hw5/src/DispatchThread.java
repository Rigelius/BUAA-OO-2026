import com.oocourse.elevator1.TimableOutput;

import java.util.List;

public class DispatchThread extends Thread {
    private final ScheduleQueue scheduleQueue;
    private final List<ProcessQueue> processQueues;

    public DispatchThread(ScheduleQueue scheduleQueue, List<ProcessQueue> processQueues) {
        this.scheduleQueue = scheduleQueue;
        this.processQueues = processQueues;
    }

    @Override
    public void run() {
        while (true) {
            Person person;
            synchronized (scheduleQueue) {
                while (scheduleQueue.isEmpty() && !scheduleQueue.isEnd()) {
                    try {
                        scheduleQueue.wait();
                    } catch (InterruptedException e) {
                        throw new RuntimeException(e);
                    }
                }
                if (scheduleQueue.isEmpty() && scheduleQueue.isEnd()) {
                    for (ProcessQueue pq : processQueues) {
                        pq.setEnd(true);
                    }
                    return;
                }
                person = scheduleQueue.take();
            }

            String receiveMsg = String.format("RECEIVE-%s-%s",
                person.getPersonId(), person.getElevatorId());
            TimableOutput.println(receiveMsg);

            processQueues.get(person.getElevatorId() - 1).offer(person);
        }
    }
}