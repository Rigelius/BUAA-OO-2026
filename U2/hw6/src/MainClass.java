import com.oocourse.elevator2.TimableOutput;

import java.util.ArrayList;
import java.util.List;

public class MainClass {
    public static void main(String[] args) {
        TimableOutput.initStartTimestamp();

        ScheduleQueue scheduleQueue = new ScheduleQueue();
        List<ElevatorThread> elevators = new ArrayList<>();

        for (int i = 1; i <= 6; i++) {
            ProcessQueue processQueue = new ProcessQueue();
            ElevatorThread elevator = new ElevatorThread(i, processQueue, scheduleQueue);

            elevators.add(elevator);
            elevator.start();
        }
        DispatchStrategy strategy = new ShadowDispatchStrategy();
        DispatchThread dispatchThread = new DispatchThread(scheduleQueue, elevators, strategy);
        dispatchThread.start();

        InputThread inputThread = new InputThread(scheduleQueue, elevators);
        inputThread.start();
    }
}