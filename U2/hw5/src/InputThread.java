import com.oocourse.elevator1.ElevatorInput;
import com.oocourse.elevator1.PersonRequest;
import com.oocourse.elevator1.Request;

import java.io.IOException;

public class InputThread extends Thread {
    private final ScheduleQueue scheduleQueue;

    public InputThread(ScheduleQueue scheduleQueue) {
        this.scheduleQueue = scheduleQueue;
    }

    @Override
    public void run() {
        ElevatorInput input = new ElevatorInput(System.in);
        while (true) {
            Request request = input.nextRequest();
            if (request == null) {
                scheduleQueue.setEnd(true);
                break;
            } else if (request instanceof PersonRequest) {
                Person person = new Person((PersonRequest) request);
                scheduleQueue.offer(person);
            }
        }
        try {
            input.close();
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}