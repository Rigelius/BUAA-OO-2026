import com.oocourse.elevator1.TimableOutput;

import java.util.ArrayList;
import java.util.List;

public class MainClass {
    public static void main(String[] args) {
        TimableOutput.initStartTimestamp();

        ScheduleQueue scheduleQueue = new ScheduleQueue();
        List<ProcessQueue> processQueues = new ArrayList<>();

        for (int i = 1; i <= 6; i++) {
            ProcessQueue processQueue = new ProcessQueue();
            processQueues.add(processQueue);

            ElevatorThread elevator = new ElevatorThread(i, processQueue);
            elevator.start();
        }

        DispatchThread dispatchThread = new DispatchThread(scheduleQueue, processQueues);
        dispatchThread.start();

        InputThread inputThread = new InputThread(scheduleQueue);
        inputThread.start();
    }
}